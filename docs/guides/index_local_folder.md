---
sidebar_position: 19
slug: /index_local_folder
---

# Index local folders

RAGFlow supports indexing documents from local folders through two approaches:

1. **API-Based Connector** (Recommended) - Uses RAGFlow's connector framework
2. **Direct File Access** - For simple use cases

This guide covers the **API-based connector approach**, which provides better integration, change detection, and metadata control.

## Overview - API-Based Connector

The API-based approach treats local folders like external sources (Paperless-ngx, Confluence, etc.):

- **Proper Separation**: RAGFlow treats it as an external API source
- **Hash-Based Deduplication**: SHA-256 checksums prevent re-indexing unchanged files
- **Metadata Control**: Normalized metadata with checksums, MIME types, timestamps
- **Change Detection**: Only sync modified files based on content hashes
- **Scalable**: Works with RAGFlow's standard connector framework

### How It Works

```
┌─────────────────────┐
│  Your Documents     │
│  /your/docs/        │  ← Files stay here
└──────────┬──────────┘
           │
           │ File Watcher Service (optional)
           │ - Detects changes (inotify/watchdog)
           │ - Computes SHA-256 hashes
           │ - Normalizes metadata
           ↓
┌─────────────────────┐
│  RAGFlow API        │
│  POST /v1/document  │  ← Receives files + metadata
└──────────┬──────────┘
           │
           │ Parse & Index
           ↓
┌─────────────────────┐
│  RAGFlow Database   │
│  (chunks/vectors)   │  ← Only index data stored
└─────────────────────┘
```

**Key difference from direct access:** Files are uploaded through the API (like regular uploads), but the process can be automated with a file watcher service.

## Prerequisites

1. Your RAGFlow instance is running
2. You have an API key ([How to get API key](../develop/acquire_ragflow_api_key.md))
3. You have mounted your local folder (if using Docker)

## Setup Methods

### Method 1: Manual Connector Setup (Web UI)

1. **Navigate to Data Sources**
   - Go to RAGFlow web interface
   - Click "Data Sources" or "Connectors"

2. **Add Local Folder Connector**
   - Click "Add Connector"
   - Select "Local Folder" as type
   - Configure:
     - **Folder Path**: `/ragflow/mounted_data/documents`
     - **Recursive**: Enable for subdirectories
     - **File Patterns**: `*.pdf`, `*.docx`, `*.txt` (optional)
     - **Compute Hash**: Enable for change detection

3. **Sync Documents**
   - Click "Sync Now" to index all files
   - Connector will track file hashes
   - Only changed files will be re-indexed on future syncs

### Method 2: Automated File Watcher Service (Recommended)

For real-time syncing, use the included file watcher service:

```bash
# Install dependencies
pip install watchdog requests

# Run file watcher
python example/local_folder_watcher.py \
    --folder /path/to/your/documents \
    --ragflow-url http://localhost:9380 \
    --api-key your-api-key \
    --connector-id your-connector-id \
    --patterns "*.pdf" "*.docx" \
    --initial-sync
```

**Features:**
- Watches folder for changes in real-time (inotify/watchdog)
- Computes SHA-256 hashes to detect actual changes
- Debounces rapid changes to avoid re-syncing during edits
- Normalizes metadata (checksums, MIME types, timestamps)
- Only syncs files that have actually changed

**Install as systemd service:**
```bash
sudo cp example/local_folder_watcher.service /etc/systemd/system/
sudo systemctl enable local_folder_watcher
sudo systemctl start local_folder_watcher
```

See [File Watcher Documentation](../example/README_local_folder_watcher.md) for details.

## Mount local folders (Docker)

To make your local folders accessible to RAGFlow:

### Step 1: Edit docker-compose.yml

```yaml
services:
  ragflow-cpu:
    volumes:
      - ./ragflow-logs:/ragflow/logs
      # ... other volumes ...
      # Mount your local documents folder
      - /path/to/your/documents:/ragflow/mounted_data:ro
```

**Notes:**
- Replace `/path/to/your/documents` with your actual path
- The `:ro` suffix makes it read-only (recommended)
- Container path should be under `/ragflow/mounted_data`

### Step 2: Restart RAGFlow

```bash
cd docker
docker compose down
docker compose up -d
```

## Index a local folder

Once your folders are mounted, you can index them through the RAGFlow web interface:

### Step 1: Navigate to your dataset

1. Go to the **Knowledge Base** section
2. Select or create a dataset where you want to index the files

### Step 2: Open the index local folder dialog

1. Click the **Add file** button
2. Select **Index local folder** from the dropdown menu

![Index local folder option](../img/index-local-folder-menu.png)

### Step 3: Configure indexing options

In the dialog that appears, configure the following options:

![Index local folder dialog](../img/index-local-folder-dialog.png)

- **Local folder path**: Enter the path to the folder inside the container (e.g., `/ragflow/mounted_data/my-documents`)
- **Scan subdirectories**: Enable this option to recursively scan all subdirectories
- **Parse after indexing**: Enable this option to automatically start parsing documents after they are indexed

### Step 4: Start indexing

Click **OK** to start the indexing process. RAGFlow will:

1. Scan the specified folder for supported file types
2. Create document records in your dataset
3. Store the files in RAGFlow's storage system
4. Optionally start parsing the documents if enabled

## Supported file types

The local folder indexing feature supports the same file types as regular file uploads:

- **Documents**: PDF, DOCX, DOC, TXT, MD
- **Spreadsheets**: XLSX, XLS, CSV
- **Presentations**: PPTX, PPT
- **Images**: JPG, JPEG, PNG, TIF, GIF
- **Audio**: MP3, WAV
- **Email**: MSG, EML
- **And more**: See the [supported file types](https://ragflow.io/docs/dev/supported_file_formats) documentation

## Security considerations

The local folder indexing feature includes several security measures:

1. **Path validation**: Only folders within the configured `MOUNTED_FOLDERS_PATH` can be indexed
2. **Directory traversal protection**: Path traversal attacks (e.g., `../../../etc/passwd`) are blocked
3. **Read-only mounts**: Use the `:ro` flag when mounting volumes to prevent modifications
4. **Tenant isolation**: Each user can only index folders in their authorized datasets

## Use cases

### Use case 1: Indexing existing document archives

If you have a large collection of documents on your server:

```bash
# Mount your archive folder
volumes:
  - /mnt/documents/company-archive:/ragflow/mounted_data/archive:ro
```

Then index `/ragflow/mounted_data/archive` through the web interface.

### Use case 2: Multiple document sources

Mount multiple folders for different purposes:

```bash
volumes:
  - /mnt/documents/contracts:/ragflow/mounted_data/contracts:ro
  - /mnt/documents/manuals:/ragflow/mounted_data/manuals:ro
  - /mnt/documents/research:/ragflow/mounted_data/research:ro
```

### Use case 3: Shared network storage

Mount network storage (NFS, CIFS) and index it:

```bash
volumes:
  - /mnt/nfs/shared-docs:/ragflow/mounted_data/shared:ro
```

## Troubleshooting

### Error: "Access denied. Path must be within..."

**Cause**: The folder path you entered is outside the allowed base path.

**Solution**: Ensure your path starts with the configured `MOUNTED_FOLDERS_PATH` (default: `/ragflow/mounted_data`).

### Error: "Path does not exist"

**Cause**: The folder doesn't exist in the container, or the volume mount is incorrect.

**Solution**: 
1. Check that your volume mount in `docker-compose.yml` is correct
2. Verify the folder exists on your host machine
3. Restart the Docker container after changing volume mounts

### Files are not being indexed

**Cause**: The files might have unsupported extensions or be corrupted.

**Solution**: Check the error messages returned after indexing. Files with unsupported types will be skipped with specific error messages.

### Error: "Local file not found" during parsing

**Cause**: The mounted folder was unmounted or files were moved after indexing.

**Solution**:
1. Ensure the mounted folder remains accessible at the same path
2. Files must stay in their original location for RAGFlow to access them
3. If you moved files, re-index from the new location

## FAQ

**Q: Where are the files stored when I use local folder indexing?**

A: **Files remain in your mounted folder** - they are NOT copied to RAGFlow's storage. The zero-copy architecture works as follows:
1. Files **stay in** your mounted folder (e.g., `/ragflow/mounted_data/documents/`)
2. RAGFlow **stores references** to file locations (e.g., `file:///ragflow/mounted_data/documents/report.pdf`)
3. Only **parsed chunks and embeddings** are stored in RAGFlow's database

This saves disk space by avoiding file duplication. However, it means the mounted folder must remain accessible.

**Q: Can I unmount the folder after indexing?**

A: **No!** Unlike regular file uploads, local folder indexing keeps files in place. If you unmount or move the folder, RAGFlow will not be able to access the documents for:
- Re-parsing with different settings
- Generating previews
- Chat responses with file context

The mounted folder must remain accessible for the lifetime of the indexed documents.

**Q: What happens if I delete files from the mounted folder?**

A: The parsed chunks will remain in RAGFlow's database and searches will still work. However:
- You won't be able to re-parse the document
- File previews will not work
- Some features requiring the original file will fail

It's recommended to delete documents from RAGFlow's UI first, which will clean up both the reference and the parsed data.

**Q: How much storage space does this save?**

A: Significant savings! For example:
- **Regular upload**: 10GB of PDFs → 10GB in MinIO + ~500MB index = 10.5GB total
- **Local folder indexing**: 10GB of PDFs in mounted folder + ~500MB index = 500MB RAGFlow storage

You only use storage for the parsed index, not the raw files.

**Q: Can I index the same folder multiple times?**

A: Yes, but each indexing creates new document references. Since files stay in place, you won't duplicate the actual file data, only the document metadata and index entries.

**Q: Can I index folders on network drives?**

A: Yes! This is actually ideal for zero-copy indexing. Mount NFS/CIFS shares into the container, and RAGFlow will reference files directly without copying them. Just ensure the network share remains accessible.

**Q: What if I need to reorganize my files?**

A: If you move files after indexing, the references will break. Options:
1. Delete old documents from RAGFlow and re-index from the new location
2. Keep files in their original location and use symbolic links
3. Use RAGFlow's UI to delete and re-add documents

**Q: Does this work with cloud storage (S3, Google Drive)?**

A: Not directly. This feature is for local file systems and network mounts (NFS/CIFS). For cloud storage, consider:
1. Using RAGFlow's data connector features
2. Mounting cloud storage as a local file system (e.g., s3fs, rclone mount)
3. Using RAGFlow's regular upload API

## See also

- [Manage files](./manage_files)
- [Configure knowledge base](./dataset/configure_knowledge_base)
- [Upload files via API](../references/http_api_reference#upload-documents)
