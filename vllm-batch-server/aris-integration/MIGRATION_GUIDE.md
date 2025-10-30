# 🔄 Aris Migration Guide: Ollama → vLLM Batch System

## Overview

This guide helps you migrate Aris from the old Ollama real-time endpoint to the new vLLM batch processing system.

**Why migrate?**
- ✅ **Batch processing** - Process 5K candidates in 24 minutes (vs hours with Ollama)
- ✅ **Model switching** - Easily compare Gemma 3 4B vs Qwen 2.5 3B vs Llama 3.2 3B
- ✅ **Webhook callbacks** - Get notified when jobs complete
- ✅ **Same interface** - Drop-in replacement for ParasailBatchClient
- ✅ **Free** - $0 cost for development/testing

---

## Current State

**Aris currently uses:**
- Real-time inference (slow, one-by-one processing)
- No batch processing support
- Limited to single model at a time

**New vLLM batch system provides:**
- ✅ Batch processing (3.47 req/s vs 0.2 req/s)
- ✅ Model switching (Gemma 3 4B ↔ Qwen 2.5 3B)
- ✅ Webhook callbacks
- ✅ Same interface as Parasail (easy migration to production)

---

## Migration Steps

### Step 1: Update Environment Variables

Add to Aris `.env.local`:

```bash
# vLLM Batch Server (RTX 4080)
VLLM_BATCH_URL=http://10.0.0.223:4080
VLLM_WEBHOOK_URL=http://10.0.0.223:4000/api/ml/batch/webhook  # Aris webhook endpoint

# Inference Provider Selection
# Options: 'vllm-batch' | 'parasail-batch' | 'ollama' (legacy)
INFERENCE_PROVIDER=vllm-batch
```

### Step 2: Copy vLLM Batch Client

```bash
# From vllm-batch-server repo
cp aris-integration/vllm-batch-client.ts ../aris/src/lib/inference/

# Verify
ls -la ../aris/src/lib/inference/vllm-batch-client.ts
```

### Step 3: Update app-config.ts

```typescript
// src/config/app-config.ts

export const INFERENCE_CONFIG = {
  // Provider Selection
  PROVIDER: process.env.INFERENCE_PROVIDER as 'vllm-batch' | 'parasail-batch' | 'ollama' | undefined,

  // vLLM Batch Configuration (Local RTX 4080 - Development)
  VLLM_BATCH_URL: process.env.VLLM_BATCH_URL || 'http://10.0.0.223:4080',
  VLLM_WEBHOOK_URL: process.env.VLLM_WEBHOOK_URL,
  VLLM_DEFAULT_MODEL: 'gemma3:4b',  // Ollama-style name (auto-translated to google/gemma-3-4b-it)
  VLLM_TIMEOUT: 180000,

  // Parasail Batch Configuration (Production - Gemma 27B)
  PARASAIL_API_KEY: process.env.PARASAIL_API_KEY,
  PARASAIL_BASE_URL: 'https://api.parasail.io/v1',
  PARASAIL_DEFAULT_MODEL: 'google/gemma-2-27b-it',
  PARASAIL_TIMEOUT: 180000,

  // Shared Model Parameters
  TEMPERATURE: 0.1,
  MAX_TOKENS: 4096,
  TOP_P: 0.9,
}
```

### Step 4: Create Batch Client Factory

Create `src/lib/inference/batch-client-factory.ts`:

```typescript
import { INFERENCE_CONFIG } from '@/config/app-config'
import { ParasailBatchClient } from './parasail-batch-client'
import { VLLMBatchClient } from './vllm-batch-client'

export type BatchClient = ParasailBatchClient | VLLMBatchClient

/**
 * Create batch client based on environment configuration
 */
export function createBatchClient(): BatchClient {
  const provider = INFERENCE_CONFIG.PROVIDER

  if (provider === 'vllm-batch') {
    return new VLLMBatchClient({
      baseUrl: INFERENCE_CONFIG.VLLM_BATCH_URL,
      webhookUrl: INFERENCE_CONFIG.VLLM_WEBHOOK_URL
    })
  }

  if (provider === 'parasail-batch' || provider === 'parasail') {
    return new ParasailBatchClient()
  }

  // Default: Use vLLM for development, Parasail for production
  if (process.env.NODE_ENV === 'production') {
    return new ParasailBatchClient()
  }

  return new VLLMBatchClient({
    baseUrl: INFERENCE_CONFIG.VLLM_BATCH_URL,
    webhookUrl: INFERENCE_CONFIG.VLLM_WEBHOOK_URL
  })
}
```

### Step 5: Update Existing Code

**Before (Ollama real-time):**

```typescript
// Old approach: Real-time inference
const response = await fetch(`${INFERENCE_CONFIG.OLLAMA_BASE_URL}/api/chat`, {
  method: 'POST',
  body: JSON.stringify({
    model: 'gemma3:12b',
    messages: [{ role: 'user', content: prompt }]
  })
})
```

**After (vLLM batch):**

```typescript
import { createBatchClient } from '@/lib/inference/batch-client-factory'

// New approach: Batch processing
const batchClient = createBatchClient()

// Submit batch
const requests = candidates.map(c => ({
  custom_id: c.id,
  body: {
    model: 'gemma3:4b',  // Ollama-style name (auto-translated)
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: buildPrompt(c) }
    ],
    temperature: 0.1,
    max_completion_tokens: 2048
  }
}))

const job = await batchClient.submitBatch(requests, {
  batchId: `candidates-${Date.now()}`,
  source: 'aris-app'
})

console.log(`Batch submitted: ${job.id}`)
console.log(`Processing ${job.request_counts.total} candidates...`)

// Poll for completion (or use webhook)
const checkStatus = async () => {
  const status = await batchClient.getBatchStatus(job.id)
  
  if (status.status === 'completed') {
    const results = await batchClient.downloadResults(job.id)
    return results
  }
  
  if (status.status === 'failed') {
    throw new Error('Batch job failed')
  }
  
  // Still processing
  console.log(`Progress: ${status.request_counts.completed}/${status.request_counts.total}`)
  await new Promise(resolve => setTimeout(resolve, 30000))  // Wait 30s
  return checkStatus()
}

const results = await checkStatus()
```

### Step 6: Create Webhook Endpoint

Create `src/app/api/ml/batch/webhook/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { logger } from '@/lib/core/secure-logger'
import { createBatchClient } from '@/lib/inference/batch-client-factory'

/**
 * Webhook endpoint for vLLM batch job completion
 * 
 * Called by vLLM server when batch jobs complete/fail
 */
export async function POST(request: NextRequest) {
  try {
    const payload = await request.json()

    logger.info('Received vLLM batch webhook', {
      batchId: payload.id,
      status: payload.status,
      requestCounts: payload.request_counts,
      context: 'vllm_webhook'
    })

    // Download results if completed
    if (payload.status === 'completed') {
      const batchClient = createBatchClient()
      const results = await batchClient.downloadResults(payload.id)

      logger.info('Downloaded batch results', {
        batchId: payload.id,
        resultCount: results.length,
        context: 'vllm_webhook'
      })

      // TODO: Process results (save to database, trigger next steps, etc.)
      // For now, just log
      console.log(`Batch ${payload.id} completed with ${results.length} results`)
    }

    return NextResponse.json({ success: true })

  } catch (error) {
    logger.error('Webhook processing failed', {
      error: error instanceof Error ? error.message : String(error),
      context: 'vllm_webhook'
    })

    return NextResponse.json(
      { error: 'Webhook processing failed' },
      { status: 500 }
    )
  }
}
```

---

## Model Name Translation

The vLLM batch client automatically translates Ollama-style model names to HuggingFace format:

| Aris (Ollama) | vLLM (HuggingFace) | Notes |
|---------------|-------------------|-------|
| `gemma3:4b` | `google/gemma-3-4b-it` | **Recommended** - Primary model |
| `qwen2.5:3b` | `Qwen/Qwen2.5-3B-Instruct` | Alternative for comparison |

**You can keep using Ollama-style names in Aris!** The client handles translation automatically.

**Why only these two models?**
- ✅ Both fit comfortably on RTX 4080 16GB
- ✅ Fast inference (3-4 req/s)
- ✅ Good quality for development/testing
- ✅ Easy to compare results side-by-side

---

## Testing

### 1. Start vLLM Batch Server

```bash
cd ~/Documents/augment-projects/Local/vllm-batch-server

# Start API server
python -m batch_app.api_server

# Start worker (separate terminal)
python -m batch_app.worker
```

### 2. Test from Aris

```typescript
// Test script: src/scripts/test-vllm-batch.ts
import { createBatchClient } from '@/lib/inference/batch-client-factory'

async function testVLLMBatch() {
  const client = createBatchClient()

  // Submit small test batch
  const requests = [
    {
      custom_id: 'test-1',
      body: {
        model: 'gemma3:4b',
        messages: [
          { role: 'user', content: 'What is 2+2?' }
        ],
        temperature: 0.1,
        max_completion_tokens: 100
      }
    }
  ]

  const job = await client.submitBatch(requests, { test: 'true' })
  console.log('Job submitted:', job.id)

  // Poll for completion
  while (true) {
    const status = await client.getBatchStatus(job.id)
    console.log('Status:', status.status, `(${status.request_counts.completed}/${status.request_counts.total})`)

    if (status.status === 'completed') {
      const results = await client.downloadResults(job.id)
      console.log('Results:', results)
      break
    }

    await new Promise(resolve => setTimeout(resolve, 5000))
  }
}

testVLLMBatch()
```

Run test:

```bash
cd ~/Documents/augment-projects/Local/aris
npx tsx src/scripts/test-vllm-batch.ts
```

---

## Comparison: Ollama vs vLLM Batch vs Parasail

| Feature | Ollama (Old) | vLLM Batch (New) | Parasail Batch |
|---------|-------------|------------------|----------------|
| **Cost** | $0 | $0 | $0.85 per 5K |
| **Throughput** | 0.2 req/s | 3.47 req/s | ~10 req/s |
| **5K candidates** | ~7 hours | 24 minutes | 8-10 minutes |
| **Model quality** | Gemma 12B | Gemma 4B | Gemma 27B |
| **Use case** | ❌ Deprecated | ✅ Development | ✅ Production |
| **Batch support** | ❌ No | ✅ Yes | ✅ Yes |
| **Webhooks** | ❌ No | ✅ Yes | ✅ Yes |
| **Model switching** | Manual | Automatic | Automatic |

---

## Recommended Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT WORKFLOW                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Step 1: Develop Prompts (vLLM Batch - Gemma 4B)           │
│  ├─ Test with 100 candidates                                │
│  ├─ Iterate on prompts                                      │
│  ├─ Compare models (Gemma vs Qwen vs Llama)                │
│  ├─ Cost: $0                                                │
│  └─ Time: 30 seconds                                        │
│                                                              │
│  Step 2: Validate Quality (vLLM Batch - Gemma 4B)          │
│  ├─ Test with 1000 candidates                               │
│  ├─ Review results in UI                                    │
│  ├─ Gold-star good examples                                 │
│  ├─ Cost: $0                                                │
│  └─ Time: 5 minutes                                         │
│                                                              │
│  Step 3: Production Run (Parasail - Gemma 27B)             │
│  ├─ Process all 170K candidates                             │
│  ├─ High-quality results                                    │
│  ├─ Customer-facing                                         │
│  ├─ Cost: $28.90                                            │
│  └─ Time: 4-6 hours                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Port Conflict (4080)

**Problem**: Both Ollama and vLLM batch server use port 4080

**Solution**: Change Ollama to port 11434 (standard Ollama port)

```bash
# Update Ollama config
OLLAMA_BASE_URL=http://10.0.0.223:11434
```

### Model Not Found

**Problem**: `Model google/gemma-3-4b-it not found`

**Solution**: Make sure vLLM worker has loaded the model

```bash
# Check worker logs
tail -f data/logs/worker.log

# Should see: "✅ Model loaded: google/gemma-3-4b-it"
```

### Webhook Not Received

**Problem**: Batch completes but webhook not called

**Solution**: Make sure Aris is accessible from RTX 4080 machine

```bash
# Test from RTX 4080
curl http://10.0.0.223:4000/api/ml/batch/webhook

# Should return 405 Method Not Allowed (POST required)
```

---

## Next Steps

1. ✅ Copy `vllm-batch-client.ts` to Aris
2. ✅ Update `.env.local` with vLLM config
3. ✅ Create batch client factory
4. ✅ Create webhook endpoint
5. ✅ Test with small batch
6. ✅ Migrate existing inference code
7. ✅ Deploy to production

**Questions?** Check the main README or ask for help!

