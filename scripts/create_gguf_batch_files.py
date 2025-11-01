#!/usr/bin/env python3
"""Create batch files with GGUF model IDs for OLMo 2 7B and GPT-OSS 20B."""

import json
from pathlib import Path

def create_batch_file(input_file: str, output_file: str, model_id: str):
    """Replace model ID in batch file."""
    
    with open(input_file) as f_in, open(output_file, 'w') as f_out:
        for line in f_in:
            if line.strip():
                req = json.loads(line)
                # Replace model ID
                req['body']['model'] = model_id
                f_out.write(json.dumps(req) + '\n')
    
    print(f"✅ Created {output_file} with model {model_id}")

if __name__ == "__main__":
    # Create OLMo 2 7B batch file
    create_batch_file(
        "batch_5k.jsonl",
        "batch_5k_olmo2_7b.jsonl",
        "bartowski/OLMo-2-1124-7B-Instruct-GGUF"
    )
    
    # Create GPT-OSS 20B batch file
    create_batch_file(
        "batch_5k.jsonl",
        "batch_5k_gptoss_20b.jsonl",
        "bartowski/openai_gpt-oss-20b-GGUF"
    )
    
    print("\n✅ Both batch files created!")
    print("  • batch_5k_olmo2_7b.jsonl")
    print("  • batch_5k_gptoss_20b.jsonl")

