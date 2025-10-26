# ARIS Integration Guide

This guide shows how to integrate vLLM Batch Server with the ARIS application for local development.

## Overview

ARIS currently uses Parasail for production batch processing. With vLLM Batch Server, you can:

- ✅ Test batch workflows locally without cloud costs
- ✅ Develop and iterate faster with local GPU
- ✅ Use the same code for local and production (environment-based switching)
- ✅ Validate batch processing logic before deploying

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ARIS Application                      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  ParasailBatchClient                           │    │
│  │  (No changes needed!)                          │    │
│  └────────────────────┬───────────────────────────┘    │
│                       │                                  │
│                       │ OpenAI SDK                       │
│                       │                                  │
└───────────────────────┼──────────────────────────────────┘
                        │
                        │ Environment-based routing
                        │
        ┌───────────────┴────────────────┐
        │                                │
        ▼                                ▼
┌──────────────────┐          ┌──────────────────┐
│  vLLM Batch      │          │    Parasail      │
│  Server (Local)  │          │  (Production)    │
│  localhost:8000  │          │  api.parasail.io │
└──────────────────┘          └──────────────────┘
```

## Step 1: Start vLLM Batch Server

On your local machine (or the machine with RTX 4080):

```bash
cd /path/to/vllm-batch-server

# Configure environment
cp .env.example .env

# Edit .env to set your model
# MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
# HF_TOKEN=your_huggingface_token

# Start the server
docker-compose up -d

# Verify it's running
curl http://localhost:8000/health
```

## Step 2: Update ARIS Configuration

In your ARIS project, update the inference configuration to support environment-based provider selection.

### Option A: Modify `src/config/app-config.ts`

```typescript
// src/config/app-config.ts

export const INFERENCE_CONFIG = {
  // ... existing config ...

  // Batch API configuration
  BATCH_BASE_URL: process.env.BATCH_BASE_URL || 
    (process.env.NODE_ENV === 'production' 
      ? 'https://api.parasail.io/v1'      // Production: Parasail
      : 'http://localhost:8000/v1'),      // Local: vLLM Batch Server

  BATCH_API_KEY: process.env.BATCH_API_KEY || 
    (process.env.NODE_ENV === 'production'
      ? process.env.PARASAIL_API_KEY
      : 'local-dev'),  // vLLM doesn't require auth by default
}
```

### Option B: Use Environment Variables

Add to your `.env.local`:

```bash
# Local development with vLLM Batch Server
BATCH_BASE_URL=http://localhost:8000/v1
BATCH_API_KEY=local-dev

# Or if vLLM server is on remote machine (RTX 4080)
BATCH_BASE_URL=http://10.0.0.223:8000/v1
BATCH_API_KEY=local-dev
```

Add to your `.env.production`:

```bash
# Production with Parasail
BATCH_BASE_URL=https://api.parasail.io/v1
BATCH_API_KEY=${PARASAIL_API_KEY}
```

## Step 3: Update ParasailBatchClient (Optional)

Your existing `ParasailBatchClient` should work without changes! But you can make it more explicit:

```typescript
// src/lib/inference/parasail-batch-client.ts

export class ParasailBatchClient {
  private client: OpenAI

  constructor() {
    // Use environment-based configuration
    const baseURL = INFERENCE_CONFIG.BATCH_BASE_URL
    const apiKey = INFERENCE_CONFIG.BATCH_API_KEY

    if (!apiKey) {
      throw new Error('BATCH_API_KEY is required for batch processing')
    }

    this.client = new OpenAI({
      baseURL,
      apiKey
    })

    logger.info('Batch client initialized', {
      baseUrl: baseURL,
      provider: baseURL.includes('parasail') ? 'parasail' : 'vllm-local',
      context: 'batch_client_init'
    })
  }

  // ... rest of the class remains unchanged ...
}
```

## Step 4: Test Locally

Now you can test batch processing locally:

```typescript
// In your Inngest function or API route
import { ParasailBatchClient } from '@/lib/inference/parasail-batch-client'

const client = new ParasailBatchClient()

// This will use vLLM locally, Parasail in production
const batch = await client.submitBatch(requests, { batchId: 'test-batch' })

console.log('Batch submitted:', batch.id)
console.log('Provider:', process.env.BATCH_BASE_URL)
```

## Step 5: Verify Batch Processing

### Check Batch Status

```bash
# Get batch status
curl http://localhost:8000/v1/batches/{batch_id}
```

### Download Results

```bash
# Get output file content
curl http://localhost:8000/v1/files/{output_file_id}/content
```

### Monitor Health

```bash
# Check server health
curl http://localhost:8000/health

# Response:
# {
#   "status": "healthy",
#   "model_loaded": true,
#   "active_batches": 1,
#   "gpu_available": true,
#   "gpu_memory_used_gb": 12.5,
#   "gpu_memory_total_gb": 16.0
# }
```

## Differences from Parasail

### What Works the Same

- ✅ OpenAI SDK compatibility
- ✅ JSONL batch format
- ✅ Batch job lifecycle (validating → in_progress → completed)
- ✅ File upload/download
- ✅ Request/response format

### What's Different

| Feature | Parasail | vLLM Batch Server |
|---------|----------|-------------------|
| **Authentication** | Required (API key) | Optional (can disable) |
| **Pricing** | 50% off real-time | Free (your GPU) |
| **Processing Time** | Variable (queue) | Immediate (if GPU free) |
| **Max Batch Size** | 50,000 requests | 50,000 requests |
| **Prefix Caching** | Automatic | Automatic (vLLM APC) |
| **Models** | Parasail's catalog | Any HuggingFace model |

## Example: Full Workflow

```typescript
// 1. Create batch requests (same as before)
const requests = candidates.map(candidate => ({
  custom_id: candidate.id,
  method: 'POST',
  url: '/v1/chat/completions',
  body: {
    model: 'meta-llama/Llama-3.1-8B-Instruct',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: candidateData }
    ],
    max_tokens: 500
  }
}))

// 2. Submit batch (works with both Parasail and vLLM)
const client = new ParasailBatchClient()
const batch = await client.submitBatch(requests)

console.log('Batch ID:', batch.id)
console.log('Status:', batch.status)

// 3. Poll for completion (same as before)
let status = await client.getBatchStatus(batch.id)
while (status.status === 'in_progress') {
  await new Promise(resolve => setTimeout(resolve, 5000))
  status = await client.getBatchStatus(batch.id)
}

// 4. Download results (same as before)
if (status.status === 'completed') {
  const results = await client.downloadResults(batch.id)
  
  for (const result of results) {
    console.log('Candidate:', result.custom_id)
    console.log('Score:', result.response.body.choices[0].message.content)
  }
}
```

## Troubleshooting

### vLLM Server Not Responding

```bash
# Check if server is running
docker ps | grep vllm-batch-server

# Check logs
docker logs vllm-batch-server

# Restart server
docker-compose restart
```

### Model Not Loading

```bash
# Check GPU availability
nvidia-smi

# Check vLLM logs for errors
docker logs vllm-batch-server | grep ERROR

# Verify HuggingFace token
docker exec vllm-batch-server env | grep HF_TOKEN
```

### Batch Processing Slow

```bash
# Check GPU utilization
nvidia-smi -l 1

# Increase batch size in .env
MAX_NUM_SEQS=512

# Enable CUDA graphs
ENABLE_CUDA_GRAPH=true

# Restart server
docker-compose restart
```

## Production Deployment

When deploying to production:

1. **Set environment variables** to use Parasail:
   ```bash
   BATCH_BASE_URL=https://api.parasail.io/v1
   BATCH_API_KEY=${PARASAIL_API_KEY}
   ```

2. **No code changes needed** - your `ParasailBatchClient` works with both!

3. **Test in staging** with vLLM first, then switch to Parasail for production.

## Next Steps

- [ ] Test batch processing with small dataset (10-100 candidates)
- [ ] Compare results between vLLM and Parasail
- [ ] Benchmark processing time and cost
- [ ] Set up monitoring for batch jobs
- [ ] Document any model-specific configurations

## Support

- **vLLM Batch Server Issues**: [GitHub Issues](https://github.com/YOUR_ORG/vllm-batch-server/issues)
- **ARIS Integration Help**: Contact your team lead
- **vLLM Documentation**: https://docs.vllm.ai

