#!/usr/bin/env python3
"""
Convert CSV candidate data to OpenAI batch format (JSONL)

Usage:
    python csv_to_batch.py candidates.csv output.jsonl

CSV Format:
    candidate_id,years_experience,skills,communication,notes
    1,5,Python,strong,Good team player
    2,3,Java,good,Leadership potential
    ...

Output JSONL Format:
    {"custom_id": "candidate-1", "method": "POST", "url": "/v1/chat/completions", "body": {...}}
    {"custom_id": "candidate-2", "method": "POST", "url": "/v1/chat/completions", "body": {...}}
    ...
"""

import csv
import json
import sys
from typing import Dict, List

# Default scoring rubric (can be customized)
SYSTEM_PROMPT = """You are an expert candidate evaluator. Score candidates on a scale of 1-10 based on:
- Technical skills
- Communication ability
- Cultural fit
- Leadership potential

Analyze the candidate profile and provide only a numeric score (1-10) as your response."""

def csv_row_to_candidate_profile(row: Dict) -> str:
    """Convert CSV row to candidate profile text"""
    parts = []
    
    # Add all fields from CSV
    for key, value in row.items():
        if key != 'candidate_id' and value:
            # Convert snake_case to Title Case
            label = key.replace('_', ' ').title()
            parts.append(f"{label}: {value}")
    
    return ", ".join(parts)

def create_batch_request(candidate_id: str, profile: str, model: str = "gemma3:12b") -> Dict:
    """Create a single batch request in OpenAI format"""
    return {
        "custom_id": f"candidate-{candidate_id}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": profile}
            ],
            "max_tokens": 10,
            "temperature": 0.7
        }
    }

def convert_csv_to_batch(csv_file: str, output_file: str, model: str = "gemma3:12b"):
    """Convert CSV file to batch JSONL format"""
    
    print(f"Converting {csv_file} to {output_file}...")
    
    requests_created = 0
    
    with open(csv_file, 'r') as csv_f, open(output_file, 'w') as jsonl_f:
        reader = csv.DictReader(csv_f)
        
        # Validate CSV has required fields
        if 'candidate_id' not in reader.fieldnames:
            print("❌ Error: CSV must have 'candidate_id' column")
            sys.exit(1)
        
        for row in reader:
            candidate_id = row['candidate_id']
            profile = csv_row_to_candidate_profile(row)
            
            # Create batch request
            request = create_batch_request(candidate_id, profile, model)
            
            # Write to JSONL
            jsonl_f.write(json.dumps(request) + '\n')
            requests_created += 1
            
            # Progress update every 1000 rows
            if requests_created % 1000 == 0:
                print(f"  Processed {requests_created:,} candidates...")
    
    print(f"✅ Created {requests_created:,} batch requests")
    print(f"✅ Output: {output_file}")
    
    # Calculate estimated metrics
    avg_tokens_per_request = 350  # System prompt + candidate data
    total_tokens_baseline = requests_created * avg_tokens_per_request
    total_tokens_optimized = avg_tokens_per_request + (requests_created * 50)  # System prompt once + user messages
    token_savings = ((total_tokens_baseline - total_tokens_optimized) / total_tokens_baseline) * 100
    
    print(f"\n📊 Estimated Metrics:")
    print(f"   Requests: {requests_created:,}")
    print(f"   Baseline tokens: {total_tokens_baseline:,}")
    print(f"   Optimized tokens: {total_tokens_optimized:,}")
    print(f"   Token savings: {token_savings:.1f}%")
    
    # Estimate processing time
    throughput = 6.67  # req/s (from benchmarks)
    estimated_time_sec = requests_created / throughput
    estimated_time_hours = estimated_time_sec / 3600
    
    print(f"\n⏱️  Estimated Processing Time:")
    print(f"   Throughput: {throughput} req/s")
    print(f"   Total time: {estimated_time_sec:,.0f}s ({estimated_time_hours:.1f} hours)")

def create_sample_csv(output_file: str = "sample_candidates.csv", num_rows: int = 100):
    """Create a sample CSV file for testing"""
    
    print(f"Creating sample CSV with {num_rows} candidates...")
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'candidate_id',
            'years_experience',
            'skills',
            'communication',
            'notes'
        ])
        writer.writeheader()
        
        for i in range(1, num_rows + 1):
            writer.writerow({
                'candidate_id': str(i),
                'years_experience': str(3 + (i % 10)),
                'skills': ['Python', 'Java', 'JavaScript', 'Go', 'Rust'][i % 5],
                'communication': ['excellent', 'good', 'strong', 'clear'][i % 4],
                'notes': f"Candidate #{i} profile"
            })
    
    print(f"✅ Created {output_file} with {num_rows} rows")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Convert CSV to batch JSONL:")
        print("    python csv_to_batch.py input.csv output.jsonl")
        print()
        print("  Create sample CSV:")
        print("    python csv_to_batch.py --sample [num_rows]")
        print()
        print("Examples:")
        print("  python csv_to_batch.py candidates.csv batch.jsonl")
        print("  python csv_to_batch.py --sample 1000")
        sys.exit(1)
    
    # Handle --sample flag
    if sys.argv[1] == '--sample':
        num_rows = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        create_sample_csv(num_rows=num_rows)
        sys.exit(0)
    
    # Convert CSV to batch
    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'batch_requests.jsonl'
    model = sys.argv[3] if len(sys.argv) > 3 else 'gemma3:12b'
    
    convert_csv_to_batch(csv_file, output_file, model)

if __name__ == "__main__":
    main()

