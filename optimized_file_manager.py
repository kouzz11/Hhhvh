import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
import mmap
import gc
from typing import Iterator, Dict, List
import psutil
import tempfile

class OptimizedFileManager:
    def __init__(self, memory_limit_mb: int = 500):
        """
        Initialize with memory management
        
        Args:
            memory_limit_mb: Maximum memory usage in MB before triggering cleanup
        """
        self.memory_limit = memory_limit_mb * 1024 * 1024  # Convert to bytes
        self.temp_dir = tempfile.mkdtemp(prefix="file_manager_")
        self.stats = {'processed': 0, 'errors': 0, 'total_size': 0}
        
    def check_memory_usage(self) -> bool:
        """Check if memory usage is within limits"""
        process = psutil.Process()
        memory_usage = process.memory_info().rss
        return memory_usage < self.memory_limit
    
    def cleanup_memory(self):
        """Force garbage collection to free memory"""
        gc.collect()
    
    def scan_directory_efficiently(self, directory: str, file_extensions: set = None) -> Iterator[Path]:
        """
        Memory-efficient directory scanning using generators
        Solves "folder contents too high" issue by not loading everything into memory
        """
        try:
            directory_path = Path(directory)
            if not directory_path.exists():
                print(f"Directory {directory} does not exist")
                return
            
            # Use os.scandir for better performance than os.listdir
            def scan_recursive(path: Path):
                try:
                    with os.scandir(path) as entries:
                        for entry in entries:
                            # Check memory usage periodically
                            if self.stats['processed'] % 1000 == 0:
                                if not self.check_memory_usage():
                                    self.cleanup_memory()
                            
                            if entry.is_file():
                                file_path = Path(entry.path)
                                # Filter by extensions if provided
                                if file_extensions is None or file_path.suffix.lower() in file_extensions:
                                    yield file_path
                                    self.stats['processed'] += 1
                            elif entry.is_dir():
                                # Recursively scan subdirectories
                                yield from scan_recursive(Path(entry.path))
                                
                except PermissionError:
                    print(f"Permission denied: {path}")
                except OSError as e:
                    print(f"OS Error scanning {path}: {e}")
                    self.stats['errors'] += 1
            
            yield from scan_recursive(directory_path)
            
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}")
            self.stats['errors'] += 1
    
    def copy_large_file_mmap(self, src: Path, dst: Path, chunk_size: int = 1024*1024) -> bool:
        """
        Copy large files using memory mapping for efficiency
        """
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # For very large files, use memory mapping
            if src.stat().st_size > 100 * 1024 * 1024:  # Files > 100MB
                with open(src, 'rb') as src_file, open(dst, 'wb') as dst_file:
                    with mmap.mmap(src_file.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                        dst_file.write(mmapped_file)
            else:
                # For smaller files, use regular chunked copying
                with open(src, 'rb') as src_file, open(dst, 'wb') as dst_file:
                    while True:
                        chunk = src_file.read(chunk_size)
                        if not chunk:
                            break
                        dst_file.write(chunk)
            
            # Preserve metadata
            shutil.copystat(src, dst)
            self.stats['total_size'] += src.stat().st_size
            return True
            
        except Exception as e:
            print(f"Error copying {src}: {e}")
            self.stats['errors'] += 1
            return False
    
    def extract_media_batch_processing(self, source_dir: str, dest_dir: str, 
                                     batch_size: int = 100) -> Dict:
        """
        Extract media files in batches to handle large directories
        This prevents "folder contents too high" errors
        """
        media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', 
                          '.webp', '.mp4', '.avi', '.mkv', '.mov', '.wmv', 
                          '.flv', '.webm', '.m4v', '.mp3', '.wav', '.flac'}
        
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (dest_path / "images").mkdir(exist_ok=True)
        (dest_path / "videos").mkdir(exist_ok=True)
        (dest_path / "audio").mkdir(exist_ok=True)
        
        batch = []
        total_processed = 0
        
        print(f"Starting batch processing from: {source_dir}")
        print(f"Batch size: {batch_size}")
        
        for file_path in self.scan_directory_efficiently(source_dir, media_extensions):
            batch.append(file_path)
            
            # Process batch when it reaches the specified size
            if len(batch) >= batch_size:
                self._process_batch(batch, dest_path)
                total_processed += len(batch)
                print(f"Processed {total_processed} files so far...")
                batch.clear()
                
                # Force memory cleanup after each batch
                self.cleanup_memory()
        
        # Process remaining files in the last batch
        if batch:
            self._process_batch(batch, dest_path)
            total_processed += len(batch)
        
        print(f"Total files processed: {total_processed}")
        return self.stats
    
    def _process_batch(self, batch: List[Path], dest_path: Path):
        """Process a batch of files"""
        for file_path in batch:
            try:
                # Determine file type and destination
                suffix = file_path.suffix.lower()
                if suffix in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}:
                    dest_subdir = dest_path / "images"
                elif suffix in {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}:
                    dest_subdir = dest_path / "videos"
                elif suffix in {'.mp3', '.wav', '.flac', '.aac', '.ogg'}:
                    dest_subdir = dest_path / "audio"
                else:
                    continue
                
                # Handle duplicate filenames
                dest_file = dest_subdir / file_path.name
                counter = 1
                while dest_file.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    dest_file = dest_subdir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                if self.copy_large_file_mmap(file_path, dest_file):
                    print(f"✓ Copied: {file_path.name}")
                
            except Exception as e:
                print(f"✗ Error processing {file_path}: {e}")
                self.stats['errors'] += 1
    
    def use_system_commands(self, source_dir: str, dest_dir: str, file_pattern: str = "*"):
        """
        Use system commands for very large operations
        Sometimes more efficient than Python for massive file operations
        """
        try:
            # Create destination directory
            dest_path = Path(dest_dir)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # Use find command to locate files efficiently
            if sys.platform.startswith('linux') or sys.platform == 'darwin':
                # Unix-like systems
                for ext in ['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mkv', 'mov']:
                    cmd = f'find "{source_dir}" -type f -iname "*.{ext}" -exec cp {{}} "{dest_dir}/" \\;'
                    print(f"Executing: {cmd}")
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"Successfully copied .{ext} files")
                    else:
                        print(f"Error copying .{ext} files: {result.stderr}")
            
            elif sys.platform.startswith('win'):
                # Windows systems
                for ext in ['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mkv', 'mov']:
                    cmd = f'forfiles /p "{source_dir}" /s /m "*.{ext}" /c "cmd /c copy @path \\"{dest_dir}\\""'
                    print(f"Executing: {cmd}")
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"Successfully copied .{ext} files")
                    else:
                        print(f"Error copying .{ext} files: {result.stderr}")
            
            return True
            
        except Exception as e:
            print(f"Error using system commands: {e}")
            return False
    
    def create_file_index(self, directory: str, output_file: str = "file_index.json"):
        """
        Create an index of files instead of copying them all
        Useful for very large directories
        """
        index = {
            'directory': directory,
            'files': [],
            'total_size': 0,
            'file_count': 0
        }
        
        media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', 
                          '.webp', '.mp4', '.avi', '.mkv', '.mov', '.wmv', 
                          '.flv', '.webm', '.m4v'}
        
        print(f"Creating file index for: {directory}")
        
        for file_path in self.scan_directory_efficiently(directory, media_extensions):
            try:
                stat_info = file_path.stat()
                file_info = {
                    'path': str(file_path),
                    'name': file_path.name,
                    'size': stat_info.st_size,
                    'modified': stat_info.st_mtime,
                    'type': 'image' if file_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'} else 'video'
                }
                
                index['files'].append(file_info)
                index['total_size'] += stat_info.st_size
                index['file_count'] += 1
                
                if index['file_count'] % 1000 == 0:
                    print(f"Indexed {index['file_count']} files...")
                    self.cleanup_memory()
                    
            except Exception as e:
                print(f"Error indexing {file_path}: {e}")
        
        # Save index to file
        with open(output_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        print(f"Index saved to {output_file}")
        print(f"Total files: {index['file_count']}")
        print(f"Total size: {index['total_size']:,} bytes")
        
        return index
    
    def copy_from_index(self, index_file: str, dest_dir: str, file_type: str = "all"):
        """
        Copy files based on a previously created index
        Allows selective copying
        """
        try:
            with open(index_file, 'r') as f:
                index = json.load(f)
            
            dest_path = Path(dest_dir)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            copied = 0
            for file_info in index['files']:
                if file_type != "all" and file_info['type'] != file_type:
                    continue
                
                src_path = Path(file_info['path'])
                if not src_path.exists():
                    print(f"File not found: {src_path}")
                    continue
                
                dest_file = dest_path / file_info['name']
                if self.copy_large_file_mmap(src_path, dest_file):
                    copied += 1
                    print(f"Copied: {file_info['name']}")
            
            print(f"Copied {copied} files from index")
            return copied
            
        except Exception as e:
            print(f"Error copying from index: {e}")
            return 0
    
    def __del__(self):
        """Cleanup temporary directory"""
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

def main():
    print("=== Optimized File Manager ===")
    print("This tool handles large directories and prevents memory issues.")
    print()
    
    manager = OptimizedFileManager(memory_limit_mb=500)
    
    while True:
        print("\nOptions:")
        print("1. Extract media files (batch processing)")
        print("2. Create file index")
        print("3. Copy from index")
        print("4. Use system commands")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == "1":
            source = input("Enter source directory: ").strip()
            dest = input("Enter destination directory: ").strip()
            batch_size = input("Enter batch size (default 100): ").strip()
            
            batch_size = int(batch_size) if batch_size.isdigit() else 100
            
            if source and dest:
                results = manager.extract_media_batch_processing(source, dest, batch_size)
                print(f"\nResults: {results}")
        
        elif choice == "2":
            source = input("Enter directory to index: ").strip()
            output = input("Enter output file name (default: file_index.json): ").strip()
            
            output = output if output else "file_index.json"
            
            if source:
                manager.create_file_index(source, output)
        
        elif choice == "3":
            index_file = input("Enter index file path: ").strip()
            dest = input("Enter destination directory: ").strip()
            file_type = input("Enter file type (image/video/all): ").strip()
            
            file_type = file_type if file_type in ['image', 'video', 'all'] else 'all'
            
            if index_file and dest:
                manager.copy_from_index(index_file, dest, file_type)
        
        elif choice == "4":
            source = input("Enter source directory: ").strip()
            dest = input("Enter destination directory: ").strip()
            
            if source and dest:
                manager.use_system_commands(source, dest)
        
        elif choice == "5":
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()