#!/usr/bin/env python3
"""
Create 50K batch by duplicating 5K batch 10 times

This simulates a real 50K production batch for testing.
"""

import sys
from pathlib import Path

def main():
    input_file = Path("batch_5k.jsonl")
    output_file = Path("batch_50k.jsonl")
    
    if not input_file.exists():
        print(f"❌ {input_file} not found!")
        sys.exit(1)
    
    print(f"Creating 50K batch from {input_file}...")
    print(f"Reading 5K batch...")
    
    # Read 5K batch
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    print(f"✅ Read {len(lines)} lines")
    
    # Write 10 copies
    print(f"Writing 10 copies to {output_file}...")
    with open(output_file, 'w') as f:
        for copy_num in range(10):
            for line_num, line in enumerate(lines):
                # Update custom_id to be unique
                import json
                data = json.loads(line)
                original_id = data['custom_id']
                data['custom_id'] = f"copy{copy_num}_{original_id}"
                f.write(json.dumps(data) + '\n')
            
            print(f"  Copy {copy_num + 1}/10 complete ({(copy_num + 1) * len(lines)} lines)")
    
    # Verify
    with open(output_file, 'r') as f:
        total_lines = sum(1 for _ in f)
    
    print(f"\n✅ Created {output_file}")
    print(f"   Total lines: {total_lines:,}")
    print(f"   File size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()

