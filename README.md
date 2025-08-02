# Media Extractor and File Manager

This repository contains Python scripts to fix common issues with extracting pictures/videos and copying data, specifically addressing the "folder contents too high" error.

## Issues Fixed

1. **Picture and Video Extraction Not Working**: Improved file detection and handling
2. **Folder Contents Too High**: Memory-efficient processing using generators and batch operations
3. **Memory Issues**: Chunked file copying and automatic memory cleanup
4. **Large File Handling**: Memory mapping for efficient large file operations

## Files

- `media_extractor.py`: Basic media extraction with threading support
- `optimized_file_manager.py`: Advanced file manager with memory optimization
- `requirements.txt`: Required Python packages

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Media Extraction

```bash
python media_extractor.py
```

This script will:
- Prompt for source and destination directories
- Extract all images and videos
- Organize files by type (images/, videos/)
- Handle duplicate filenames automatically

### Advanced File Manager (Recommended for Large Directories)

```bash
python optimized_file_manager.py
```

Features:
1. **Batch Processing**: Processes files in small batches to avoid memory issues
2. **File Indexing**: Create an index first, then copy selectively
3. **System Commands**: Use native OS commands for very large operations
4. **Memory Management**: Automatic memory cleanup and monitoring

## Key Features

### Memory Optimization
- Uses generators instead of loading all files into memory
- Processes files in configurable batches (default: 100 files)
- Automatic garbage collection when memory usage is high
- Chunked file copying for large files

### File Handling
- Supports all common image formats: JPG, PNG, GIF, BMP, TIFF, WebP
- Supports all common video formats: MP4, AVI, MKV, MOV, WMV, FLV, WebM
- Automatic duplicate filename handling
- Preserves file metadata and timestamps

### Error Handling
- Permission error handling
- Path validation
- Comprehensive error reporting
- Graceful handling of corrupted files

## Configuration Options

### MediaExtractor Class
```python
extractor = MediaExtractor(
    chunk_size=16384,    # 16KB chunks for file copying
    max_threads=2        # Number of concurrent operations
)
```

### OptimizedFileManager Class
```python
manager = OptimizedFileManager(
    memory_limit_mb=500  # Memory limit before cleanup
)
```

## Common Usage Examples

### Extract all media files
```python
from media_extractor import MediaExtractor

extractor = MediaExtractor()
results = extractor.extract_media_files(
    source_dir="/path/to/source",
    destination_dir="/path/to/destination",
    organize_by_type=True
)
```

### Handle very large directories
```python
from optimized_file_manager import OptimizedFileManager

manager = OptimizedFileManager()

# First create an index
manager.create_file_index("/very/large/directory", "index.json")

# Then copy selectively
manager.copy_from_index("index.json", "/destination", file_type="image")
```

### Use system commands for massive operations
```python
manager.use_system_commands("/source", "/destination")
```

## Troubleshooting

### "Folder contents too high" error
- Use the `OptimizedFileManager` with batch processing
- Reduce batch size (try 50 or 25 instead of 100)
- Use the indexing approach for very large directories

### Memory issues
- Reduce the number of threads: `max_threads=1`
- Increase chunk size: `chunk_size=32768`
- Lower memory limit: `memory_limit_mb=256`

### Permission errors
- Run with appropriate permissions
- Check file/folder access rights
- Use system commands option for privileged operations

### Performance optimization
- For SSDs: Increase chunk_size and max_threads
- For HDDs: Decrease max_threads to 1-2
- For network drives: Use larger chunk_size

## System Requirements

- Python 3.6+
- Available memory: At least 512MB free
- Disk space: Sufficient for destination files
- OS: Windows, Linux, or macOS

## Notes

- The scripts preserve original file timestamps and metadata
- Duplicate files are renamed with a counter suffix
- Progress is displayed during operations
- All operations can be interrupted safely with Ctrl+C