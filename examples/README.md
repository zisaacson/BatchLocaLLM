# Examples

This directory contains examples demonstrating how to use vLLM Batch Server.

## Quick Start Examples

### 1. Simple Batch Processing (`simple_batch.py`)

The simplest way to submit a batch job:

```bash
python examples/simple_batch.py
```

This example:
- Uploads a batch file
- Creates a batch job
- Polls for completion
- Downloads and displays results

### 2. Model Comparison (`compare_models.py`)

Compare multiple models on the same dataset:

```bash
python examples/compare_models.py
```

This example:
- Runs the same prompts through multiple models
- Compares quality, speed, and cost
- Generates a comparison report

### 3. Streaming Progress (`streaming_progress.py`)

Monitor batch progress in real-time:

```bash
python examples/streaming_progress.py
```

This example:
- Shows real-time progress updates
- Displays throughput metrics
- Estimates time remaining

## Language-Specific Examples

### Python

See `python/` directory for:
- `basic_client.py` - Minimal example
- `async_client.py` - Async/await example
- `batch_with_webhooks.py` - Webhook notifications
- `custom_result_handler.py` - Custom result processing

### curl

See `curl/` directory for:
- `submit_batch.sh` - Submit a batch job
- `check_status.sh` - Check job status
- `download_results.sh` - Download results
- `cancel_batch.sh` - Cancel a running job

### TypeScript/JavaScript

See `typescript/` directory for:
- `client.ts` - TypeScript client
- `batch_processor.js` - Node.js example
- `react_integration.tsx` - React component

## Use Case Examples

### Training Data Curation

```bash
python examples/use_cases/training_data_curation.py
```

Generate and curate training datasets:
1. Process thousands of examples
2. Review outputs in web UI
3. Mark high-quality examples
4. Export curated dataset

### Benchmark Multiple Models

```bash
python examples/use_cases/benchmark_models.py \
  --dataset examples/datasets/synthetic_100.jsonl \
  --models gemma-3-4b llama-3.2-3b qwen-3-4b
```

Compare models scientifically:
- Same dataset for all models
- Measure throughput and latency
- Compare output quality
- Generate comparison report

### Batch Inference at Scale

```bash
python examples/use_cases/large_scale_inference.py \
  --input large_dataset.jsonl \
  --model google/gemma-3-4b-it \
  --chunk-size 1000
```

Process large datasets efficiently:
- Automatic chunking
- Incremental saves
- Progress tracking
- Error recovery

## Integration Examples

### FastAPI Integration

```python
# examples/integrations/fastapi_app.py
from fastapi import FastAPI
from vllm_batch_client import VLLMBatchClient

app = FastAPI()
client = VLLMBatchClient("http://localhost:4080")

@app.post("/analyze")
async def analyze(data: dict):
    # Submit batch job
    batch_id = await client.submit_batch(data)
    return {"batch_id": batch_id}
```

### Celery Integration

```python
# examples/integrations/celery_tasks.py
from celery import Celery
from vllm_batch_client import VLLMBatchClient

app = Celery('tasks')
client = VLLMBatchClient("http://localhost:4080")

@app.task
def process_batch(data):
    batch_id = client.submit_batch(data)
    client.wait_for_completion(batch_id)
    return client.get_results(batch_id)
```

## Testing Examples

### Unit Tests

```python
# examples/testing/test_client.py
import pytest
from vllm_batch_client import VLLMBatchClient

def test_submit_batch(mock_server):
    client = VLLMBatchClient(mock_server.url)
    batch_id = client.submit_batch(test_data)
    assert batch_id.startswith("batch-")
```

### Integration Tests

```python
# examples/testing/test_integration.py
def test_end_to_end_workflow():
    # Upload file
    file_id = upload_file("test.jsonl")
    
    # Create batch
    batch_id = create_batch(file_id)
    
    # Wait for completion
    wait_for_batch(batch_id)
    
    # Verify results
    results = download_results(batch_id)
    assert len(results) == expected_count
```

## Datasets

See `datasets/` directory for:
- `synthetic_candidates_10.jsonl` - 10 synthetic examples
- `synthetic_100.jsonl` - 100 synthetic examples
- `README.md` - Dataset documentation

## Running Examples

### Prerequisites

```bash
# Ensure vLLM Batch Server is running
curl http://localhost:4080/health

# Install example dependencies
pip install -r examples/requirements.txt
```

### Run All Examples

```bash
# Run all examples
./examples/run_all.sh

# Run specific category
./examples/run_all.sh python
./examples/run_all.sh use_cases
```

## Creating Your Own Examples

### Template

```python
#!/usr/bin/env python3
"""
Example: [Brief description]

This example demonstrates:
- Feature 1
- Feature 2
- Feature 3
"""

import requests

API_URL = "http://localhost:4080"

def main():
    # Your code here
    pass

if __name__ == "__main__":
    main()
```

### Best Practices

1. **Keep it simple** - Focus on one concept per example
2. **Add comments** - Explain what each step does
3. **Handle errors** - Show proper error handling
4. **Use realistic data** - Use synthetic but realistic examples
5. **Document output** - Show what the output looks like

## Contributing Examples

We welcome new examples! To contribute:

1. Create your example in the appropriate directory
2. Add documentation to this README
3. Test your example thoroughly
4. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Support

- **Issues**: [GitHub Issues](https://github.com/zisaacson/vllm-batch-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zisaacson/vllm-batch-server/discussions)
- **Documentation**: [docs/](../docs/)

