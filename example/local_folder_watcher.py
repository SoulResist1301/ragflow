#!/usr/bin/env python3
"""
Local Folder Watcher Service for RAGFlow

This service watches a local folder for file changes and automatically
syncs them to RAGFlow using the connector API. It implements:

- File watching with inotify/watchdog
- SHA-256 content hashing for deduplication
- Metadata normalization (source, owner, created_at, checksum, mime)
- Change detection (only sync modified files)
- Explicit handoff to RAGFlow via API

Usage:
    python local_folder_watcher.py --folder /path/to/documents \\
        --ragflow-url http://localhost:9380 \\
        --api-key your-api-key \\
        --connector-id your-connector-id

Requirements:
    pip install watchdog requests

Systemd Service:
    See local_folder_watcher.service for systemd integration
"""

import argparse
import hashlib
import json
import logging
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('local_folder_watcher')


class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events and sync to RAGFlow"""
    
    def __init__(
        self,
        ragflow_url: str,
        api_key: str,
        connector_id: str,
        folder_path: str,
        file_patterns: Optional[list] = None,
        debounce_seconds: int = 2,
    ):
        """Initialize file change handler
        
        Args:
            ragflow_url: RAGFlow API base URL
            api_key: RAGFlow API key
            connector_id: Connector ID to sync to
            folder_path: Folder being watched
            file_patterns: Optional list of file patterns to include
            debounce_seconds: Debounce time for file changes
        """
        self.ragflow_url = ragflow_url.rstrip('/')
        self.api_key = api_key
        self.connector_id = connector_id
        self.folder_path = Path(folder_path)
        self.file_patterns = file_patterns or []
        self.debounce_seconds = debounce_seconds
        
        # Track file hashes to detect changes
        self.file_hashes: Dict[str, str] = {}
        
        # Track pending changes (for debouncing)
        self.pending_changes: Dict[str, float] = {}
        
        # Initialize file hashes
        self._scan_initial_files()
    
    def _scan_initial_files(self):
        """Scan all existing files and compute their hashes"""
        logger.info(f"Scanning initial files in {self.folder_path}")
        count = 0
        
        for file_path in self.folder_path.rglob('*'):
            if file_path.is_file() and self._should_include_file(str(file_path)):
                try:
                    file_hash = self._compute_file_hash(str(file_path))
                    self.file_hashes[str(file_path)] = file_hash
                    count += 1
                except Exception as e:
                    logger.error(f"Error scanning {file_path}: {e}")
        
        logger.info(f"Scanned {count} files")
    
    def _should_include_file(self, file_path: str) -> bool:
        """Check if file should be included based on patterns
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file should be included
        """
        if not self.file_patterns:
            return True
        
        from fnmatch import fnmatch
        filename = os.path.basename(file_path)
        return any(fnmatch(filename, pattern) for pattern in self.file_patterns)
    
    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of file content
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex string of SHA-256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _get_file_metadata(self, file_path: str) -> dict:
        """Extract file metadata
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary of metadata
        """
        stat_info = os.stat(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        
        return {
            "source_path": file_path,
            "relative_path": os.path.relpath(file_path, self.folder_path),
            "folder_path": str(self.folder_path),
            "file_size": stat_info.st_size,
            "mime_type": mime_type or "application/octet-stream",
            "created_at": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "owner": stat_info.st_uid,
            "checksum": self._compute_file_hash(file_path),
            "checksum_algorithm": "SHA-256",
        }
    
    def _sync_file_to_ragflow(self, file_path: str):
        """Sync file to RAGFlow via connector API
        
        Args:
            file_path: Path to file to sync
        """
        try:
            logger.info(f"Syncing file to RAGFlow: {file_path}")
            
            # Compute file hash
            file_hash = self._compute_file_hash(file_path)
            
            # Check if file changed
            old_hash = self.file_hashes.get(file_path)
            if old_hash == file_hash:
                logger.info(f"File unchanged (same hash): {file_path}")
                return
            
            # Get metadata
            metadata = self._get_file_metadata(file_path)
            
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Prepare multipart upload
            files = {
                'file': (os.path.basename(file_path), file_content)
            }
            
            data = {
                'kb_id': self.connector_id,
                'metadata': json.dumps(metadata)
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # Upload to RAGFlow
            response = requests.post(
                f'{self.ragflow_url}/v1/document/upload',
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully synced: {file_path}")
                # Update hash cache
                self.file_hashes[file_path] = file_hash
            else:
                logger.error(
                    f"Failed to sync {file_path}: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Error syncing {file_path}: {e}", exc_info=True)
    
    def _handle_file_change(self, file_path: str):
        """Handle file change with debouncing
        
        Args:
            file_path: Path to changed file
        """
        if not os.path.exists(file_path):
            # File was deleted
            if file_path in self.file_hashes:
                del self.file_hashes[file_path]
            return
        
        if not os.path.isfile(file_path):
            return
        
        if not self._should_include_file(file_path):
            return
        
        # Debounce: mark file as pending
        self.pending_changes[file_path] = time.time()
    
    def process_pending_changes(self):
        """Process pending file changes after debounce period"""
        current_time = time.time()
        to_process = []
        
        for file_path, change_time in list(self.pending_changes.items()):
            if current_time - change_time >= self.debounce_seconds:
                to_process.append(file_path)
                del self.pending_changes[file_path]
        
        for file_path in to_process:
            self._sync_file_to_ragflow(file_path)
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation event"""
        if not event.is_directory:
            logger.debug(f"File created: {event.src_path}")
            self._handle_file_change(event.src_path)
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification event"""
        if not event.is_directory:
            logger.debug(f"File modified: {event.src_path}")
            self._handle_file_change(event.src_path)
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion event"""
        if not event.is_directory:
            logger.debug(f"File deleted: {event.src_path}")
            self._handle_file_change(event.src_path)
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move event"""
        if not event.is_directory:
            logger.debug(f"File moved: {event.src_path} -> {event.dest_path}")
            self._handle_file_change(event.src_path)
            self._handle_file_change(event.dest_path)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Watch local folder and sync changes to RAGFlow'
    )
    parser.add_argument(
        '--folder',
        required=True,
        help='Folder path to watch'
    )
    parser.add_argument(
        '--ragflow-url',
        default='http://localhost:9380',
        help='RAGFlow API base URL (default: http://localhost:9380)'
    )
    parser.add_argument(
        '--api-key',
        required=True,
        help='RAGFlow API key'
    )
    parser.add_argument(
        '--connector-id',
        required=True,
        help='RAGFlow connector ID'
    )
    parser.add_argument(
        '--patterns',
        nargs='+',
        help='File patterns to include (e.g., *.pdf *.docx)'
    )
    parser.add_argument(
        '--debounce',
        type=int,
        default=2,
        help='Debounce time in seconds (default: 2)'
    )
    parser.add_argument(
        '--initial-sync',
        action='store_true',
        help='Sync all existing files on startup'
    )
    
    args = parser.parse_args()
    
    # Validate folder exists
    if not os.path.exists(args.folder):
        logger.error(f"Folder does not exist: {args.folder}")
        sys.exit(1)
    
    if not os.path.isdir(args.folder):
        logger.error(f"Path is not a directory: {args.folder}")
        sys.exit(1)
    
    logger.info(f"Starting file watcher for: {args.folder}")
    logger.info(f"RAGFlow URL: {args.ragflow_url}")
    logger.info(f"Connector ID: {args.connector_id}")
    if args.patterns:
        logger.info(f"File patterns: {args.patterns}")
    
    # Create event handler
    event_handler = FileChangeHandler(
        ragflow_url=args.ragflow_url,
        api_key=args.api_key,
        connector_id=args.connector_id,
        folder_path=args.folder,
        file_patterns=args.patterns,
        debounce_seconds=args.debounce,
    )
    
    # Initial sync if requested
    if args.initial_sync:
        logger.info("Performing initial sync...")
        for file_path in Path(args.folder).rglob('*'):
            if file_path.is_file():
                event_handler._sync_file_to_ragflow(str(file_path))
    
    # Start watching
    observer = Observer()
    observer.schedule(event_handler, args.folder, recursive=True)
    observer.start()
    
    logger.info("File watcher started. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
            # Process pending changes
            event_handler.process_pending_changes()
    except KeyboardInterrupt:
        logger.info("Stopping file watcher...")
        observer.stop()
    
    observer.join()
    logger.info("File watcher stopped.")


if __name__ == '__main__':
    main()
