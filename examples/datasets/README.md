# Synthetic Test Datasets

This directory contains synthetic (fake) candidate data for testing and demonstration purposes.

## Available Datasets

### `synthetic_candidates_10.jsonl`
- **Size:** 10 requests
- **Use case:** Quick testing, examples in documentation
- **Format:** OpenAI Batch API compatible
- **Content:** Diverse software engineering candidates with realistic but fake profiles

### Generating Larger Datasets

You can generate larger synthetic datasets using the provided tool:

```bash
python tools/generate_synthetic_data.py --output examples/datasets/synthetic_100.jsonl --count 100
```

## Dataset Format

Each line is a JSON object following the OpenAI Batch API format:

```json
{
  "custom_id": "candidate-001",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "google/gemma-3-4b-it",
    "messages": [
      {
        "role": "system",
        "content": "You are an expert technical recruiter..."
      },
      {
        "role": "user",
        "content": "**Candidate Profile**\n\n**Name:** Sarah Chen\n..."
      }
    ],
    "max_tokens": 1000
  }
}
```

## Privacy Notice

⚠️ **All data in this directory is synthetic (fake) and generated for testing purposes only.**

- Names are randomly generated
- Companies are fictional
- Work histories are fabricated
- No real candidate data is included

## Using These Datasets

### Submit a batch job:

```bash
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-abc123",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h"
  }'
```

### Or use the Python client:

```python
from examples.simple_batch import submit_batch

batch_id = submit_batch(
    input_file="examples/datasets/synthetic_candidates_10.jsonl",
    model="google/gemma-3-4b-it"
)
print(f"Batch submitted: {batch_id}")
```

## Benchmark Datasets

For benchmarking, we recommend:
- **10 requests:** Quick smoke test (~30 seconds)
- **100 requests:** Standard benchmark (~5 minutes)
- **1000 requests:** Stress test (~1 hour)
- **5000 requests:** Production simulation (~5 hours)

## Contributing

To add new synthetic datasets:

1. Ensure all data is completely fictional
2. Use diverse, realistic scenarios
3. Follow the OpenAI Batch API format
4. Add documentation to this README
5. Submit a pull request

## License

These synthetic datasets are released under the same Apache 2.0 license as the main project.

