#!/usr/bin/env python3
"""
Fix model names in batch JSONL files.
Replaces Ollama model names with HuggingFace model names for vLLM compatibility.
"""

import json
import sys

def fix_batch_file(input_file, output_file, new_model_name):
    """Replace model names in all requests."""
    count = 0
    with open(input_file, 'r') as f_in, open(output_file, 'w') as f_out:
        for line in f_in:
            if not line.strip():
                continue
            
            request = json.loads(line)
            
            # Update model name in the request body
            if 'body' in request and 'model' in request['body']:
                request['body']['model'] = new_model_name
            
            f_out.write(json.dumps(request) + '\n')
            count += 1
    
    return count

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python fix_batch_model_names.py <input_file> <output_file> <new_model_name>")
        print("Example: python fix_batch_model_names.py batch_5k.jsonl batch_5k_qwen.jsonl 'Qwen/Qwen3-4B-Instruct-2507'")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    new_model_name = sys.argv[3]
    
    print(f"📝 Fixing model names in {input_file}...")
    print(f"   New model: {new_model_name}")
    
    count = fix_batch_file(input_file, output_file, new_model_name)
    
    print(f"✅ Fixed {count} requests")
    print(f"   Output: {output_file}")

