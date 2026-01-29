---
sidebar_position: 19
slug: /index_local_folder
---

# Index local folders

RAGFlow supports indexing documents from local folders that are already mounted in the Docker container. This feature allows you to index existing files through the RAGFlow interface without manually uploading them, while still benefiting from RAGFlow's document processing and storage capabilities.

## Overview

When you have documents stored on your host machine that are already accessible to the RAGFlow Docker container through volume mounts, you can use the local folder indexing feature to:

- Index files through RAGFlow's interface without manual uploads
- Preserve your existing file organization structure
- Efficiently manage large document collections
- Use read-only mounts for added safety
- Automatically process and store files in RAGFlow's storage system

**Note**: Files are read from the mounted folder and stored in RAGFlow's storage system for processing. This provides the benefit of simplified indexing while maintaining RAGFlow's document management capabilities.

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
- The `:ro` suffix mounts the folder as read-only, preventing accidental modifications
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

## FAQ

**Q: Will the files be duplicated in RAGFlow's storage?**

A: Yes, the files are read from the mounted folder and stored in RAGFlow's storage system. This ensures they are available for parsing and retrieval. The benefit is that you can organize and prepare your files on your filesystem first, then index them without manually uploading each file through the web interface. The read-only mount option also provides an additional safety layer to prevent accidental modifications to your original files.

**Q: Can I index the same folder multiple times?**

A: Yes, but this will create duplicate documents in your dataset. RAGFlow will detect duplicates by filename and add a suffix to avoid conflicts.

**Q: Can I index folders on network drives?**

A: Yes, as long as the network drive is mounted on your host machine and you mount it into the Docker container.

**Q: Is there a size limit for the folder?**

A: There is no specific folder size limit, but indexing very large folders may take time. The system processes files sequentially to avoid overwhelming the system.

**Q: Can I update files in the mounted folder after indexing?**

A: Changes to files in the mounted folder will NOT automatically update the indexed documents. You would need to re-index the folder or manually update specific documents.

## See also

- [Manage files](./manage_files)
- [Configure knowledge base](./dataset/configure_knowledge_base)
- [Upload files via API](../references/http_api_reference#upload-documents)
