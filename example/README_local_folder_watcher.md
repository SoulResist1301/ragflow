# Local Folder Watcher for RAGFlow

This service watches local folders for file changes and automatically syncs them to RAGFlow using the connector API.

## Features

- **File Watching**: Uses watchdog (inotify on Linux) to detect file changes in real-time
- **SHA-256 Hashing**: Computes content hashes to detect actual changes (not just timestamp updates)
- **Metadata Normalization**: Extracts and normalizes file metadata (MIME type, size, timestamps, checksums)
- **Change Detection**: Only syncs files that have actually changed (based on content hash)
- **Debouncing**: Prevents rapid re-syncing during file edits
- **Pattern Filtering**: Include only specific file types (e.g., `*.pdf`, `*.docx`)
- **API Integration**: Uses RAGFlow's standard document upload API

## Installation

### Prerequisites

```bash
pip install watchdog requests
```

### Basic Usage

```bash
python local_folder_watcher.py \
    --folder /path/to/your/documents \
    --ragflow-url http://localhost:9380 \
    --api-key your-api-key \
    --connector-id your-connector-id \
    --patterns "*.pdf" "*.docx" "*.txt"
```

### Arguments

- `--folder`: Path to folder to watch (required)
- `--ragflow-url`: RAGFlow API base URL (default: http://localhost:9380)
- `--api-key`: RAGFlow API key (required)
- `--connector-id`: RAGFlow connector ID (required)
- `--patterns`: File patterns to include (optional, e.g., `*.pdf *.docx`)
- `--debounce`: Debounce time in seconds (default: 2)
- `--initial-sync`: Sync all existing files on startup

## Systemd Service

### Install as System Service

1. Copy files:
```bash
sudo cp local_folder_watcher.py /opt/ragflow/
sudo cp local_folder_watcher.service /etc/systemd/system/
```

2. Edit service file:
```bash
sudo nano /etc/systemd/system/local_folder_watcher.service
```

Update these values:
- `/path/to/your/documents` → Your actual folder path
- `YOUR_API_KEY` → Your RAGFlow API key
- `YOUR_CONNECTOR_ID` → Your connector ID

3. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable local_folder_watcher
sudo systemctl start local_folder_watcher
```

4. Check status:
```bash
sudo systemctl status local_folder_watcher
sudo journalctl -u local_folder_watcher -f
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Your Documents                        │
│              /path/to/documents/                        │
│  ├── report.pdf                                         │
│  ├── manual.docx                                        │
│  └── data/                                              │
│      └── analysis.pdf                                   │
└────────────┬────────────────────────────────────────────┘
             │
             │ File system events (inotify/watchdog)
             ↓
┌─────────────────────────────────────────────────────────┐
│          Local Folder Watcher Service                   │
│  ┌─────────────────────────────────────────────┐       │
│  │  1. Detect file change                      │       │
│  │  2. Compute SHA-256 hash                    │       │
│  │  3. Compare with previous hash              │       │
│  │  4. Extract metadata                        │       │
│  │  5. Prepare for upload                      │       │
│  └─────────────────────────────────────────────┘       │
└────────────┬────────────────────────────────────────────┘
             │
             │ HTTP POST with file + metadata
             ↓
┌─────────────────────────────────────────────────────────┐
│              RAGFlow API Server                         │
│         POST /v1/document/upload                        │
│  ┌─────────────────────────────────────────────┐       │
│  │  Receives:                                  │       │
│  │  - File content (blob)                      │       │
│  │  - Metadata (JSON)                          │       │
│  │    - checksum (SHA-256)                     │       │
│  │    - mime_type                              │       │
│  │    - file_size                              │       │
│  │    - source_path                            │       │
│  │    - timestamps                             │       │
│  └─────────────────────────────────────────────┘       │
│                                                          │
│  Treats as external source (like Paperless-ngx)        │
└────────────┬────────────────────────────────────────────┘
             │
             │ Parse & Index
             ↓
┌─────────────────────────────────────────────────────────┐
│            RAGFlow Knowledge Base                       │
│  ┌─────────────────────────────────────────────┐       │
│  │  - Chunks stored in Elasticsearch           │       │
│  │  - Embeddings in vector DB                  │       │
│  │  - Original file in MinIO (for re-parsing)  │       │
│  └─────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### Change Detection Flow

1. **Initial Scan**: On startup, compute hashes for all existing files
2. **File Changed**: Watchdog detects file system event
3. **Debounce**: Wait for debounce period to avoid rapid re-syncs
4. **Hash Comparison**: Compute new SHA-256 hash and compare
5. **Sync if Changed**: Only upload if hash changed
6. **Update Cache**: Store new hash for future comparisons

### Metadata Structure

```json
{
  "source_path": "/path/to/documents/report.pdf",
  "relative_path": "reports/2024/report.pdf",
  "folder_path": "/path/to/documents",
  "file_size": 1048576,
  "mime_type": "application/pdf",
  "created_at": "2024-01-15T10:30:00",
  "modified_at": "2024-01-20T14:45:00",
  "owner": 1000,
  "checksum": "a3b2c1...",
  "checksum_algorithm": "SHA-256"
}
```

## Use Cases

### 1. Paperless-ngx Integration

Watch Paperless-ngx document directory:

```bash
python local_folder_watcher.py \
    --folder /path/to/paperless/documents \
    --ragflow-url http://localhost:9380 \
    --api-key xxx \
    --connector-id xxx \
    --patterns "*.pdf"
```

### 2. Network Share Monitoring

Monitor an NFS/SMB share:

```bash
python local_folder_watcher.py \
    --folder /mnt/company-docs \
    --ragflow-url http://ragflow.company.com \
    --api-key xxx \
    --connector-id xxx \
    --initial-sync
```

### 3. Development Document Folder

Watch a local development folder:

```bash
python local_folder_watcher.py \
    --folder ~/Documents/research \
    --ragflow-url http://localhost:9380 \
    --api-key xxx \
    --connector-id xxx \
    --patterns "*.md" "*.pdf" "*.txt"
```

## Benefits vs Direct File Access

### ✅ API-Based Approach (This Service)

- RAGFlow treats it as external source (proper separation)
- Hash-based change detection (efficient)
- Metadata normalization enforced
- Works like Paperless-ngx, Confluence, etc.
- Can integrate with external systems
- Scalable and maintainable

### ❌ Direct File Access (file:// approach)

- Tight coupling with file system
- No change detection mechanism
- No metadata normalization
- Files must stay in exact location forever
- Breaks if files move/rename
- Not suitable for integration scenarios

## Troubleshooting

### Service won't start

Check logs:
```bash
sudo journalctl -u local_folder_watcher -n 50
```

### Files not syncing

1. Check file patterns match
2. Verify API key and connector ID
3. Check RAGFlow is accessible
4. Look for permission issues

### High CPU usage

Increase debounce time:
```bash
--debounce 5
```

### Need to exclude files

Use negative patterns in your wrapper script:
```bash
# Only sync PDFs, not scans
--patterns "*.pdf"
# Skip temporary files by watching main folder only
```

## Advanced Configuration

### Multiple Folders

Create separate service files for each folder:
```bash
/etc/systemd/system/ragflow-watcher-docs.service
/etc/systemd/system/ragflow-watcher-media.service
```

### Custom Processing

Extend the `FileChangeHandler` class:
```python
class CustomHandler(FileChangeHandler):
    def _get_file_metadata(self, file_path: str) -> dict:
        metadata = super()._get_file_metadata(file_path)
        # Add custom metadata
        metadata['department'] = self._extract_department(file_path)
        return metadata
```

## See Also

- [RAGFlow Connector Documentation](../../docs/guides/connectors.md)
- [Local Folder Connector](../../common/data_source/local_folder_connector.py)
- [API Documentation](../../docs/api.md)
