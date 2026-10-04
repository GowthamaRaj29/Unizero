import os
import sys
import zipfile
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
ZIP_NAME = "BNP-Chennai-team-33.zip"
OUTPUT_ZIP_PATH = os.path.join(ROOT_DIR, ZIP_NAME)

EXCLUDED_DIRS = {
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    ".git",
    ".system_generated"
}

EXCLUDED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".zip"
}

def should_exclude(rel_path):
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDED_DIRS:
            return True
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in EXCLUDED_EXTENSIONS:
        return True
    return False

print("=" * 80)
print(f"Compressing Project: {ROOT_DIR}")
print(f"Destination: {OUTPUT_ZIP_PATH}")
print(f"Excluded: node_modules, __pycache__, .pytest_cache, dist, .zip")
print("=" * 80)

total_files = 0
total_uncompressed_bytes = 0

start_time = time.time()

with zipfile.ZipFile(OUTPUT_ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
    for root, dirs, files in os.walk(ROOT_DIR):
        # Modify dirs in-place to prevent walking into excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, ROOT_DIR)
            
            if should_exclude(rel_path):
                continue
            
            # Use root folder name in archive so extraction produces a clean folder
            archive_path = os.path.join("BNP-Chennai-team-33", rel_path)
            
            file_size = os.path.getsize(full_path)
            total_uncompressed_bytes += file_size
            total_files += 1
            
            zip_file.write(full_path, archive_path)
            
            if total_files % 100 == 0:
                print(f"  Archived {total_files} files...")

duration = time.time() - start_time
compressed_size = os.path.getsize(OUTPUT_ZIP_PATH)

print("\n" + "=" * 80)
print("COMPRESSION COMPLETED SUCCESSFULLY!")
print(f"  Archive: {OUTPUT_ZIP_PATH}")
print(f"  Total Files Included: {total_files}")
print(f"  Uncompressed Size:    {total_uncompressed_bytes / (1024 * 1024):.2f} MB")
print(f"  Compressed Size:      {compressed_size / (1024 * 1024):.2f} MB")
print(f"  Compression Ratio:    {(1 - compressed_size / total_uncompressed_bytes) * 100:.1f}% saved")
print(f"  Time Taken:           {duration:.2f} seconds")
print("=" * 80)
