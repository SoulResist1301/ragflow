"""Local Folder connector for indexing files from mounted directories"""
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Generator

from common.data_source.config import DocumentSource, INDEX_BATCH_SIZE
from common.data_source.exceptions import (
    ConnectorMissingCredentialError,
    ConnectorValidationError,
)
from common.data_source.interfaces import LoadConnector, PollConnector
from common.data_source.models import Document, SecondsSinceUnixEpoch
from common.data_source.utils import get_file_ext


logger = logging.getLogger(__name__)


class LocalFolderConnector(LoadConnector, PollConnector):
    """
    Local Folder connector for syncing files from mounted directories.
    
    This connector provides API-based access to local folders, similar to external
    sources like Paperless-ngx. It computes file hashes for change detection and
    provides proper metadata normalization.
    
    Unlike direct file system access, this connector:
    - Treats local folders as an external API source
    - Computes SHA-256 hashes for deduplication
    - Normalizes metadata (source, owner, timestamps, checksums)
    - Enables change detection based on content hashes
    - Integrates with RAGFlow's connector framework
    """

    def __init__(
        self,
        folder_path: str,
        recursive: bool = True,
        file_patterns: Optional[list[str]] = None,
        compute_hash: bool = True,
        batch_size: int = INDEX_BATCH_SIZE,
        allowed_base_path: str = "/ragflow/mounted_data",
    ) -> None:
        """Initialize Local Folder connector
        
        Args:
            folder_path: Absolute path to the folder to index
            recursive: Whether to recursively scan subdirectories
            file_patterns: Optional list of file patterns to include (e.g., ["*.pdf", "*.docx"])
            compute_hash: Whether to compute SHA-256 hashes for change detection
            batch_size: Number of documents per batch
            allowed_base_path: Security restriction - folder must be under this path
        """
        self.folder_path = os.path.abspath(folder_path)
        self.recursive = recursive
        self.file_patterns = file_patterns or []
        self.compute_hash = compute_hash
        self.batch_size = batch_size
        self.allowed_base_path = os.path.abspath(allowed_base_path)
        
        # Validate path is within allowed base
        if not self.folder_path.startswith(self.allowed_base_path):
            raise ConnectorValidationError(
                f"Folder path must be within {self.allowed_base_path}"
            )
        
        logger.info(f"Initialized LocalFolderConnector for {self.folder_path}")

    def load_credentials(self, credentials: dict[str, Any]) -> dict[str, Any] | None:
        """Load credentials (not needed for local folders)
        
        Args:
            credentials: Not used for local folders
        
        Returns:
            None
        """
        # Local folders don't need credentials, but we validate the path exists
        if not os.path.exists(self.folder_path):
            raise ConnectorMissingCredentialError(
                f"Folder path does not exist: {self.folder_path}"
            )
        
        if not os.path.isdir(self.folder_path):
            raise ConnectorValidationError(
                f"Path is not a directory: {self.folder_path}"
            )
        
        return None

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of file content
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex string of SHA-256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _should_include_file(self, file_path: str) -> bool:
        """Check if file matches include patterns
        
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

    def _list_files(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> list[str]:
        """List files in the folder
        
        Args:
            start_time: Optional start time for filtering by modification time
            end_time: Optional end time for filtering by modification time
            
        Returns:
            List of file paths
        """
        files = []
        
        if self.recursive:
            # Recursively walk the directory tree
            for root, dirs, filenames in os.walk(self.folder_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    
                    # Check if file matches patterns
                    if not self._should_include_file(file_path):
                        continue
                    
                    # Filter by modification time if provided
                    if start_time or end_time:
                        try:
                            mtime = datetime.fromtimestamp(
                                os.path.getmtime(file_path), 
                                tz=timezone.utc
                            )
                            if start_time and mtime < start_time:
                                continue
                            if end_time and mtime > end_time:
                                continue
                        except OSError:
                            logger.warning(f"Could not get modification time for {file_path}")
                            continue
                    
                    files.append(file_path)
        else:
            # Only scan the top-level directory
            try:
                for entry in os.scandir(self.folder_path):
                    if entry.is_file():
                        file_path = entry.path
                        
                        # Check if file matches patterns
                        if not self._should_include_file(file_path):
                            continue
                        
                        # Filter by modification time if provided
                        if start_time or end_time:
                            try:
                                mtime = datetime.fromtimestamp(
                                    entry.stat().st_mtime,
                                    tz=timezone.utc
                                )
                                if start_time and mtime < start_time:
                                    continue
                                if end_time and mtime > end_time:
                                    continue
                            except OSError:
                                logger.warning(f"Could not get modification time for {file_path}")
                                continue
                        
                        files.append(file_path)
            except OSError as e:
                logger.error(f"Error scanning directory {self.folder_path}: {e}")
                raise ConnectorValidationError(f"Cannot access directory: {e}")
        
        return files

    def _create_document(self, file_path: str) -> Document:
        """Create Document object from file
        
        Args:
            file_path: Path to file
            
        Returns:
            Document object
        """
        try:
            # Get file stats
            stat_info = os.stat(file_path)
            file_size = stat_info.st_size
            mtime = datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc)
            
            # Read file content
            with open(file_path, "rb") as f:
                blob = f.read()
            
            # Compute hash if enabled (use as document ID for deduplication)
            if self.compute_hash:
                file_hash = self._compute_file_hash(file_path)
                doc_id = f"local_folder_{file_hash}"
            else:
                # Use relative path as ID
                rel_path = os.path.relpath(file_path, self.folder_path)
                doc_id = f"local_folder_{hashlib.md5(rel_path.encode()).hexdigest()}"
            
            # Get file extension
            extension = get_file_ext(file_path)
            
            # Create relative path for semantic identifier
            rel_path = os.path.relpath(file_path, self.folder_path)
            semantic_identifier = os.path.basename(file_path)
            
            # Create metadata
            metadata = {
                "source_path": file_path,
                "relative_path": rel_path,
                "folder_path": self.folder_path,
                "file_size": file_size,
                "mime_type": self._get_mime_type(file_path),
            }
            
            if self.compute_hash:
                metadata["checksum"] = self._compute_file_hash(file_path)
                metadata["checksum_algorithm"] = "SHA-256"
            
            # Create Document
            doc = Document(
                id=doc_id,
                source=DocumentSource.LOCAL_FOLDER.value,
                semantic_identifier=semantic_identifier,
                extension=extension,
                blob=blob,
                doc_updated_at=mtime,
                size_bytes=file_size,
                metadata=metadata,
            )
            
            return doc
            
        except Exception as e:
            logger.error(f"Error creating document from {file_path}: {e}")
            raise

    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type for file
        
        Args:
            file_path: Path to file
            
        Returns:
            MIME type string
        """
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"

    def load_from_state(self) -> Generator[list[Document], None, None]:
        """Load all documents from the folder
        
        Yields:
            Batches of Document objects
        """
        logger.info(f"Loading documents from {self.folder_path}")
        
        # List all files
        files = self._list_files()
        logger.info(f"Found {len(files)} files to index")
        
        # Process in batches
        batch = []
        for file_path in files:
            try:
                doc = self._create_document(file_path)
                batch.append(doc)
                
                if len(batch) >= self.batch_size:
                    logger.info(f"Yielding batch of {len(batch)} documents")
                    yield batch
                    batch = []
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                continue
        
        # Yield remaining documents
        if batch:
            logger.info(f"Yielding final batch of {len(batch)} documents")
            yield batch

    def poll_source(
        self, 
        start: SecondsSinceUnixEpoch, 
        end: SecondsSinceUnixEpoch
    ) -> Generator[list[Document], None, None]:
        """Poll for documents modified within time range
        
        Args:
            start: Start time (seconds since Unix epoch)
            end: End time (seconds since Unix epoch)
            
        Yields:
            Batches of Document objects
        """
        start_time = datetime.fromtimestamp(start, tz=timezone.utc)
        end_time = datetime.fromtimestamp(end, tz=timezone.utc)
        
        logger.info(
            f"Polling {self.folder_path} for documents modified between "
            f"{start_time} and {end_time}"
        )
        
        # List files modified in time range
        files = self._list_files(start_time, end_time)
        logger.info(f"Found {len(files)} modified files")
        
        # Process in batches
        batch = []
        for file_path in files:
            try:
                doc = self._create_document(file_path)
                batch.append(doc)
                
                if len(batch) >= self.batch_size:
                    logger.info(f"Yielding batch of {len(batch)} documents")
                    yield batch
                    batch = []
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                continue
        
        # Yield remaining documents
        if batch:
            logger.info(f"Yielding final batch of {len(batch)} documents")
            yield batch
