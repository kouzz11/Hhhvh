#!/usr/bin/env python3
"""
Simple Media Extractor - Fixes picture/video extraction and "folder contents too high" issues
No external dependencies required - uses only Python standard library
"""

import os
import shutil
import json
from pathlib import Path
from typing import Generator, List, Dict
import gc
import sys

class SimpleMediaExtractor:
    def __init__(self, chunk_size: int = 8192):
        """
        Initialize the extractor
        
        Args:
            chunk_size: Size of chunks for file operations (default 8KB)
        """
        self.chunk_size = chunk_size
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        self.stats = {'images': 0, 'videos': 0, 'errors': 0, 'total_size': 0}
    
    def is_media_file(self, file_path: Path) -> bool:
        """Check if file is a supported media file"""
        ext = file_path.suffix.lower()
        return ext in (self.image_extensions | self.video_extensions)
    
    def get_file_type(self, file_path: Path) -> str:
        """Determine if file is image or video"""
        ext = file_path.suffix.lower()
        if ext in self.image_extensions:
            return "image"
        elif ext in self.video_extensions:
            return "video"
        return "unknown"
    
    def scan_directory_generator(self, source_dir: str) -> Generator[Path, None, None]:
        """
        Generator to scan directories without loading everything into memory
        Solves the "folder contents too high" issue
        """
        source_path = Path(source_dir)
        
        if not source_path.exists():
            print(f"❌ Error: Directory '{source_dir}' does not exist")
            return
        
        print(f"🔍 Scanning directory: {source_dir}")
        file_count = 0
        
        try:
            for root, dirs, files in os.walk(source_path):
                # Process files one by one to avoid memory issues
                for filename in files:
                    file_path = Path(root) / filename
                    
                    if self.is_media_file(file_path):
                        yield file_path
                        file_count += 1
                        
                        # Print progress every 100 files
                        if file_count % 100 == 0:
                            print(f"📁 Found {file_count} media files so far...")
                            # Force garbage collection to free memory
                            gc.collect()
        
        except PermissionError as e:
            print(f"❌ Permission denied: {e}")
        except OSError as e:
            print(f"❌ OS Error: {e}")
    
    def copy_file_safely(self, src: Path, dst: Path) -> bool:
        """
        Copy file in chunks to handle large files safely
        """
        try:
            # Create destination directory if needed
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file in chunks to avoid memory issues
            with open(src, 'rb') as src_file, open(dst, 'wb') as dst_file:
                while True:
                    chunk = src_file.read(self.chunk_size)
                    if not chunk:
                        break
                    dst_file.write(chunk)
            
            # Copy file metadata
            shutil.copystat(src, dst)
            return True
            
        except Exception as e:
            print(f"❌ Error copying {src.name}: {e}")
            self.stats['errors'] += 1
            return False
    
    def extract_media_files(self, source_dir: str, dest_dir: str, organize: bool = True) -> Dict:
        """
        Extract pictures and videos from source to destination
        
        Args:
            source_dir: Source directory to search
            dest_dir: Destination directory
            organize: Whether to organize into images/ and videos/ subdirectories
        
        Returns:
            Dictionary with extraction results
        """
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        if organize:
            (dest_path / "images").mkdir(exist_ok=True)
            (dest_path / "videos").mkdir(exist_ok=True)
        
        print(f"🚀 Starting media extraction...")
        print(f"📂 Source: {source_dir}")
        print(f"📁 Destination: {dest_dir}")
        print(f"📋 Organize by type: {organize}")
        print()
        
        processed = 0
        
        # Process files using generator to avoid memory issues
        for media_file in self.scan_directory_generator(source_dir):
            try:
                file_type = self.get_file_type(media_file)
                
                # Determine destination based on organization preference
                if organize:
                    if file_type == "image":
                        dest_subdir = dest_path / "images"
                    elif file_type == "video":
                        dest_subdir = dest_path / "videos"
                    else:
                        dest_subdir = dest_path / "other"
                else:
                    dest_subdir = dest_path
                
                # Handle duplicate filenames
                dest_file = dest_subdir / media_file.name
                counter = 1
                original_dest = dest_file
                
                while dest_file.exists():
                    stem = original_dest.stem
                    suffix = original_dest.suffix
                    dest_file = dest_subdir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                # Copy the file
                if self.copy_file_safely(media_file, dest_file):
                    file_size = media_file.stat().st_size
                    self.stats['total_size'] += file_size
                    
                    if file_type == "image":
                        self.stats['images'] += 1
                    elif file_type == "video":
                        self.stats['videos'] += 1
                    
                    processed += 1
                    print(f"✅ Copied: {media_file.name} ({file_size:,} bytes)")
                
                # Periodic cleanup
                if processed % 50 == 0:
                    gc.collect()
                    
            except Exception as e:
                print(f"❌ Error processing {media_file}: {e}")
                self.stats['errors'] += 1
        
        return self.stats
    
    def batch_process(self, source_dir: str, dest_dir: str, batch_size: int = 50) -> Dict:
        """
        Process files in batches for very large directories
        """
        print(f"🔄 Using batch processing (batch size: {batch_size})")
        
        batch = []
        total_processed = 0
        
        for media_file in self.scan_directory_generator(source_dir):
            batch.append(media_file)
            
            # Process batch when it reaches the specified size
            if len(batch) >= batch_size:
                self._process_batch(batch, dest_dir)
                total_processed += len(batch)
                print(f"📊 Processed {total_processed} files (batch complete)")
                batch.clear()
                gc.collect()  # Clean memory after each batch
        
        # Process remaining files
        if batch:
            self._process_batch(batch, dest_dir)
            total_processed += len(batch)
        
        print(f"🎉 Batch processing complete! Total processed: {total_processed}")
        return self.stats
    
    def _process_batch(self, batch: List[Path], dest_dir: str):
        """Process a single batch of files"""
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        for file_path in batch:
            try:
                file_type = self.get_file_type(file_path)
                
                # Organize by type
                if file_type == "image":
                    dest_subdir = dest_path / "images"
                elif file_type == "video":
                    dest_subdir = dest_path / "videos"
                else:
                    dest_subdir = dest_path / "other"
                
                dest_subdir.mkdir(exist_ok=True)
                
                # Handle duplicates
                dest_file = dest_subdir / file_path.name
                counter = 1
                while dest_file.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    dest_file = dest_subdir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                if self.copy_file_safely(file_path, dest_file):
                    if file_type == "image":
                        self.stats['images'] += 1
                    elif file_type == "video":
                        self.stats['videos'] += 1
                    
                    self.stats['total_size'] += file_path.stat().st_size
                    
            except Exception as e:
                print(f"❌ Error in batch processing {file_path}: {e}")
                self.stats['errors'] += 1
    
    def create_file_list(self, source_dir: str, output_file: str = "media_files.json") -> int:
        """
        Create a JSON list of all media files (useful for very large directories)
        """
        files_info = []
        count = 0
        
        print(f"📝 Creating file list for: {source_dir}")
        
        for media_file in self.scan_directory_generator(source_dir):
            try:
                stat_info = media_file.stat()
                file_info = {
                    'path': str(media_file.absolute()),
                    'name': media_file.name,
                    'size': stat_info.st_size,
                    'type': self.get_file_type(media_file),
                    'modified': stat_info.st_mtime
                }
                
                files_info.append(file_info)
                count += 1
                
                if count % 500 == 0:
                    print(f"📄 Listed {count} files...")
                    
            except Exception as e:
                print(f"❌ Error listing {media_file}: {e}")
        
        # Save to JSON file
        with open(output_file, 'w') as f:
            json.dump({
                'source_directory': source_dir,
                'total_files': count,
                'files': files_info
            }, f, indent=2)
        
        print(f"💾 File list saved to: {output_file}")
        print(f"📊 Total files found: {count}")
        
        return count


def main():
    """Main function with user interface"""
    print("🎬 Simple Media Extractor")
    print("=" * 50)
    print("Fixes issues with picture/video extraction and large directories")
    print()
    
    extractor = SimpleMediaExtractor()
    
    while True:
        print("\n📋 Options:")
        print("1. Extract media files (normal)")
        print("2. Extract media files (batch processing - for large directories)")
        print("3. Create file list (scan only)")
        print("4. Exit")
        
        choice = input("\n🔢 Enter your choice (1-4): ").strip()
        
        if choice == "1":
            source = input("📂 Enter source directory path: ").strip()
            dest = input("📁 Enter destination directory path: ").strip()
            
            if source and dest:
                organize = input("📋 Organize by type? (y/n, default=y): ").strip().lower()
                organize = organize != 'n'
                
                print("\n🚀 Starting extraction...")
                results = extractor.extract_media_files(source, dest, organize)
                
                print(f"\n📊 Results:")
                print(f"🖼️  Images copied: {results['images']}")
                print(f"🎥 Videos copied: {results['videos']}")
                print(f"❌ Errors: {results['errors']}")
                print(f"💾 Total size: {results['total_size']:,} bytes")
            else:
                print("❌ Please enter both source and destination paths")
        
        elif choice == "2":
            source = input("📂 Enter source directory path: ").strip()
            dest = input("📁 Enter destination directory path: ").strip()
            batch_size = input("📦 Enter batch size (default=50): ").strip()
            
            batch_size = int(batch_size) if batch_size.isdigit() else 50
            
            if source and dest:
                print("\n🚀 Starting batch extraction...")
                results = extractor.batch_process(source, dest, batch_size)
                
                print(f"\n📊 Results:")
                print(f"🖼️  Images copied: {results['images']}")
                print(f"🎥 Videos copied: {results['videos']}")
                print(f"❌ Errors: {results['errors']}")
                print(f"💾 Total size: {results['total_size']:,} bytes")
            else:
                print("❌ Please enter both source and destination paths")
        
        elif choice == "3":
            source = input("📂 Enter directory to scan: ").strip()
            output = input("📄 Output file name (default=media_files.json): ").strip()
            
            output = output if output else "media_files.json"
            
            if source:
                count = extractor.create_file_list(source, output)
                print(f"✅ Created list of {count} media files")
            else:
                print("❌ Please enter source directory path")
        
        elif choice == "4":
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 6):
        print("❌ This script requires Python 3.6 or higher")
        sys.exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("Please check your paths and try again")