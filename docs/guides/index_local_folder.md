---
sidebar_position: 19
slug: /index_local_folder
---

# Index local folders

RAGFlow supports indexing documents from local folders that are already mounted in the Docker container. This feature allows you to index existing files through the RAGFlow interface without manually uploading them, while still benefiting from RAGFlow's document processing and storage capabilities.

## Overview

When you have documents stored on your host machine that are already accessible to the RAGFlow Docker container through volume mounts, you can use the local folder indexing feature to:

- Index files directly from mounted folders without copying them
- Save disk space by avoiding file duplication  
- Efficiently manage large document collections
- Use read-only mounts for added safety
- Store only the parsed content (chunks/embeddings) in RAGFlow

### How Zero-Copy Indexing Works

**Important**: This feature uses a zero-copy architecture - files remain in their original location:

1. **Read**: Files are read from your mounted folder (which can be read-only)
2. **Parse**: Files are parsed directly from the mounted location
3. **Index**: Only the parsed chunks and embeddings are stored in RAGFlow's database

**Files never leave the mounted folder.** RAGFlow only stores references to the file locations and the parsed index data. This means:

- ✅ No file duplication - massive disk space savings
- ✅ Faster indexing - no file copying step
- ✅ True read-only support - mounted folders are never written to
- ⚠️ **Files must remain in the mounted location** - moving or unmounting breaks document access
- ⚠️ **Folder must stay mounted** - RAGFlow reads files on-demand during parsing and retrieval

```
┌─────────────────────┐
│  Host Machine       │
│  /your/documents/   │  ← Files stay here permanently
└──────────┬──────────┘
           │ Docker volume mount (:ro)
           ↓
┌─────────────────────┐
│  RAGFlow Container  │
│  /ragflow/mounted   │  ← Reference files here
└──────────┬──────────┘
           │ Parse & extract
           ↓
┌─────────────────────┐
│  RAGFlow Database   │
│  (Elasticsearch)    │  ← Only chunks/embeddings stored here
└─────────────────────┘
```

## Prerequisites

Before indexing local folders, ensure that:

1. Your RAGFlow instance is running via Docker
2. You have mounted your local folder into the Docker container
3. The mounted folder is within the allowed base path (default: `/ragflow/mounted_data`)

## Mount local folders

To make your local folders accessible to RAGFlow, you need to mount them as volumes in your Docker container.

### Step 1: Edit docker-compose.yml

Open `docker/docker-compose.yml` and add a volume mount under the `ragflow-cpu` or `ragflow-gpu` service:

```yaml
volumes:
  - ./ragflow-logs:/ragflow/logs
  - ./nginx/ragflow.conf:/etc/nginx/conf.d/ragflow.conf
  # ... other volumes ...
  # Mount your local documents folder (read-only recommended)
  - /path/to/your/documents:/ragflow/mounted_data:ro
```

**Important notes:**
- Replace `/path/to/your/documents` with the actual path to your local folder
- The `:ro` suffix mounts the folder as read-only, preventing accidental modifications to your original files
- **Files remain in this location** - RAGFlow references them directly without copying
- **Do not unmount or move files** after indexing - RAGFlow needs access to parse and retrieve them
- The container path must be under `/ragflow/mounted_data` (or your configured `MOUNTED_FOLDERS_PATH`)

### Step 2: Configure allowed base path (optional)

If you want to use a different base path, edit `docker/.env`:

```bash
# Base path for mounted folders that can be indexed in RAGFlow
MOUNTED_FOLDERS_PATH=/ragflow/mounted_data
```

### Step 3: Restart RAGFlow

After updating the docker-compose file, restart RAGFlow:

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
