#!/usr/bin/env python3
"""Test a single request to understand actual processing time"""

import json
import time

import requests

# Load one request from batch file
with open("batch_5k.jsonl") as f:
    req = json.loads(f.readline())

print("Request body:")
print(json.dumps(req["body"], indent=2))

# Send request
print("\nSending request...")
start = time.time()

response = requests.post(
    "http://localhost:4080/v1/chat/completions",
    json=req["body"],
    timeout=300
)

elapsed = time.time() - start

print(f"\n✅ Response received in {elapsed:.2f} seconds")
print("\nResponse:")
data = response.json()
print(json.dumps(data, indent=2))

# Extract key metrics
if "usage" in data:
    print("\n📊 Metrics:")
    print(f"  Prompt tokens: {data['usage'].get('prompt_tokens', 0)}")
    print(f"  Completion tokens: {data['usage'].get('completion_tokens', 0)}")
    print(f"  Total tokens: {data['usage'].get('total_tokens', 0)}")

if "choices" in data and len(data["choices"]) > 0:
    content = data["choices"][0]["message"]["content"]
    print(f"\n📝 Generated content ({len(content)} chars):")
    print(content[:500])

