# 🚀 Quick Start: Aris + vLLM Batch Integration

## 5-Minute Setup

### 1. Copy Client to Aris

```bash
cd ~/Documents/augment-projects/Local/vllm-batch-server
cp aris-integration/vllm-batch-client.ts ../aris/src/lib/inference/
```

### 2. Add Environment Variables

Add to `~/Documents/augment-projects/Local/aris/.env.local`:

```bash
# vLLM Batch Server
VLLM_BATCH_URL=http://10.0.0.223:4080
VLLM_WEBHOOK_URL=http://10.0.0.223:4000/api/ml/batch/webhook
INFERENCE_PROVIDER=vllm-batch
```

### 3. Use in Code

```typescript
import { VLLMBatchClient } from '@/lib/inference/vllm-batch-client'

// Create client
const client = new VLLMBatchClient()

// Submit batch
const job = await client.submitBatch([
  {
    custom_id: 'candidate-123',
    body: {
      model: 'gemma3:4b',  // Ollama-style name (auto-translated)
      messages: [
        { role: 'system', content: 'You are a recruiting assistant.' },
        { role: 'user', content: 'Evaluate this candidate...' }
      ],
      temperature: 0.1,
      max_completion_tokens: 2048
    }
  }
])

console.log(`Batch submitted: ${job.id}`)

// Poll for completion
const status = await client.getBatchStatus(job.id)
console.log(`Status: ${status.status}`)

// Download results
if (status.status === 'completed') {
  const results = await client.downloadResults(job.id)
  console.log(`Got ${results.length} results`)
}
```

---

## Supported Models

Only two models supported (RTX 4080 16GB):

| Use This | Translates To | Use Case |
|----------|---------------|----------|
| `gemma3:4b` | `google/gemma-3-4b-it` | **Recommended** - Primary model |
| `qwen2.5:3b` | `Qwen/Qwen2.5-3B-Instruct` | Alternative for comparison |

---

## Performance

| Batch Size | Time | Throughput |
|------------|------|------------|
| 100 | 30s | 3.3 req/s |
| 1,000 | 5 min | 3.3 req/s |
| 5,000 | 24 min | 3.47 req/s |
| 50,000 | 4 hours | 3.47 req/s |

---

## Comparison

| Feature | vLLM Batch | Parasail Batch |
|---------|-----------|----------------|
| **Cost** | $0 | $0.85 per 5K |
| **Speed** | 3.47 req/s | ~10 req/s |
| **Model** | Gemma 4B | Gemma 27B |
| **Use** | Development | Production |

---

## Full Documentation

- **Migration Guide**: `MIGRATION_GUIDE.md`
- **API Reference**: `../BATCH_API.md`
- **Production Guide**: `../PRODUCTION_READY.md`

