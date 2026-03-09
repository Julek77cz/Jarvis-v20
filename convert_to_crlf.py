#!/usr/bin/env python3
"""Convert all .bat files in scripts/ to CRLF line endings."""
import glob
import os

# Find all .bat files
bat_files = glob.glob('scripts/*.bat')

for bat_file in bat_files:
    print(f"Processing {bat_file}...")
    
    # Read the file
    with open(bat_file, 'rb') as f:
        content = f.read()
    
    # Convert LF to CRLF
    content_crlf = content.replace(b'\n', b'\r\n')
    
    # Remove any double CRLF that might have been created
    content_crlf = content_crlf.replace(b'\r\r\n', b'\r\n')
    
    # Write back with CRLF
    with open(bat_file, 'wb') as f:
        f.write(content_crlf)
    
    print(f"  ✓ Converted to CRLF")

print("\nAll .bat files converted to CRLF line endings!")
