/**
 * vLLM Batch Client for Aris
 * 
 * BUSINESS_CONTEXT: Local batch processing using RTX 4080 vLLM server
 * Enables FREE processing of large-scale ML inference jobs for development/testing
 * 
 * COST SAVINGS:
 * - Local processing = $0 (vs Parasail $0.85 per 5K candidates)
 * - Use for: prompt development, model comparison, training data curation
 * - Production: Use Parasail for high-quality 27B results
 * 
 * ARCHITECTURE:
 * - Mirrors ParasailBatchClient interface for easy switching
 * - Uses vLLM batch server at http://10.0.0.223:4080
 * - JSONL file format (same as Parasail)
 * - Webhook callbacks for job completion
 * 
 * INTEGRATION:
 * - Drop-in replacement for ParasailBatchClient
 * - Same request/response format
 * - Automatic model name translation (Ollama → HuggingFace)
 * 
 * INSTALLATION:
 * 1. Copy this file to: src/lib/inference/vllm-batch-client.ts
 * 2. Add to .env: VLLM_BATCH_URL=http://10.0.0.223:4080
 * 3. Use like ParasailBatchClient
 */

import { z } from 'zod'
import { logger } from '@/lib/core/secure-logger'

// ============================================================================
// TYPES & SCHEMAS (Match Parasail format)
// ============================================================================

/**
 * Batch request line (JSONL format)
 * 100% compatible with Parasail/OpenAI batch API spec
 */
export const BatchRequestLineSchema = z.object({
  custom_id: z.string(),
  method: z.literal('POST').optional(),
  url: z.literal('/v1/chat/completions').optional(),
  body: z.object({
    model: z.string(),
    messages: z.array(z.object({
      role: z.enum(['system', 'user', 'assistant']),
      content: z.string()
    })),
    temperature: z.number().optional(),
    max_completion_tokens: z.number().optional(),
    top_p: z.number().optional()
  })
})

export type BatchRequestLine = z.infer<typeof BatchRequestLineSchema>

export const BatchStatusSchema = z.enum([
  'validating',
  'pending',
  'in_progress',
  'running',
  'completed',
  'failed',
  'expired',
  'cancelled'
])

export type BatchStatus = z.infer<typeof BatchStatusSchema>

export const BatchJobSchema = z.object({
  id: z.string(),
  status: BatchStatusSchema,
  input_file_id: z.string().optional(),
  output_file_id: z.string().optional(),
  error_file_id: z.string().optional(),
  created_at: z.number(),
  completed_at: z.number().optional(),
  failed_at: z.number().optional(),
  request_counts: z.object({
    total: z.number(),
    completed: z.number(),
    failed: z.number()
  }).optional(),
  metadata: z.record(z.string(), z.string()).optional()
})

export type BatchJob = z.infer<typeof BatchJobSchema>

export const BatchResultLineSchema = z.object({
  custom_id: z.string(),
  response: z.object({
    status_code: z.number().optional(),
    body: z.object({
      id: z.string().optional(),
      object: z.literal('chat.completion').optional(),
      created: z.number().optional(),
      model: z.string(),
      choices: z.array(z.object({
        index: z.number().optional(),
        message: z.object({
          role: z.literal('assistant'),
          content: z.string()
        }),
        finish_reason: z.string().optional()
      })),
      usage: z.object({
        prompt_tokens: z.number(),
        completion_tokens: z.number(),
        total_tokens: z.number()
      })
    })
  }),
  error: z.object({
    message: z.string(),
    type: z.string(),
    code: z.string()
  }).nullable().optional()
})

export type BatchResultLine = z.infer<typeof BatchResultLineSchema>

// ============================================================================
// MODEL NAME TRANSLATION
// ============================================================================

/**
 * Translate Ollama model names to HuggingFace format
 *
 * SUPPORTED MODELS (RTX 4080 16GB):
 * - Gemma 3 4B: Fast, good quality, fits easily
 * - Qwen 2.5 3B: Faster, experimental, good for comparison
 *
 * Aris uses Ollama-style names (gemma3:4b)
 * vLLM uses HuggingFace names (google/gemma-3-4b-it)
 */
const MODEL_NAME_MAP: Record<string, string> = {
  // Gemma 3 4B (Primary model - recommended)
  'gemma3:4b': 'google/gemma-3-4b-it',

  // Qwen 2.5 3B (Alternative - for comparison)
  'qwen2.5:3b': 'Qwen/Qwen2.5-3B-Instruct',
}

function translateModelName(ollamaName: string): string {
  const translated = MODEL_NAME_MAP[ollamaName]
  
  if (!translated) {
    logger.warn('Unknown Ollama model name, using as-is', {
      ollamaName,
      context: 'vllm_model_translation'
    })
    return ollamaName
  }
  
  return translated
}

// ============================================================================
// VLLM BATCH CLIENT
// ============================================================================

/**
 * Client for local vLLM batch processing
 * 
 * USAGE:
 * ```typescript
 * const client = new VLLMBatchClient()
 * 
 * // Submit batch
 * const job = await client.submitBatch(requests, { batchId: 'my-batch' })
 * 
 * // Poll for completion
 * const status = await client.getBatchStatus(job.id)
 * 
 * // Download results
 * const results = await client.downloadResults(job.id)
 * ```
 */
export class VLLMBatchClient {
  private baseUrl: string
  private webhookUrl?: string

  constructor(config?: { baseUrl?: string; webhookUrl?: string }) {
    this.baseUrl = config?.baseUrl || process.env.VLLM_BATCH_URL || 'http://10.0.0.223:4080'
    this.webhookUrl = config?.webhookUrl

    logger.info('vLLM batch client initialized', {
      baseUrl: this.baseUrl,
      webhookUrl: this.webhookUrl,
      context: 'vllm_batch_init'
    })
  }

  /**
   * Submit a batch job to vLLM server
   */
  async submitBatch(
    requests: BatchRequestLine[],
    metadata?: Record<string, string>
  ): Promise<BatchJob> {
    // Validate batch size
    if (requests.length === 0) {
      throw new Error('Batch must contain at least one request')
    }

    if (requests.length > 50000) {
      throw new Error('Batch size exceeds maximum of 50,000 requests')
    }

    // Convert to vLLM JSONL format (simpler than Parasail)
    const vllmRequests = requests.map(req => ({
      custom_id: req.custom_id,
      body: {
        messages: req.body.messages,
        temperature: req.body.temperature,
        max_tokens: req.body.max_completion_tokens,
        top_p: req.body.top_p
      }
    }))

    const jsonlContent = vllmRequests.map(req => JSON.stringify(req)).join('\n')

    // Get model from first request (all should use same model)
    const ollamaModel = requests[0].body.model
    const vllmModel = translateModelName(ollamaModel)

    logger.info('Submitting vLLM batch', {
      requestCount: requests.length,
      ollamaModel,
      vllmModel,
      context: 'vllm_batch_submit'
    })

    // Create FormData for file upload
    const formData = new FormData()
    formData.append('file', new Blob([jsonlContent], { type: 'application/jsonl' }), 'batch.jsonl')
    formData.append('model', vllmModel)
    
    if (this.webhookUrl) {
      formData.append('webhook_url', this.webhookUrl)
    }
    
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata))
    }

    // Submit to vLLM server
    const response = await fetch(`${this.baseUrl}/v1/batches`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`vLLM batch submission failed: ${error}`)
    }

    const result = await response.json()

    // Convert vLLM response to Parasail format
    return {
      id: result.batch_id,
      status: this.mapStatus(result.status),
      created_at: new Date(result.created_at).getTime() / 1000,
      request_counts: {
        total: result.progress.total,
        completed: result.progress.completed,
        failed: result.progress.failed || 0
      },
      metadata
    }
  }

  /**
   * Get batch job status
   */
  async getBatchStatus(batchId: string): Promise<BatchJob> {
    const response = await fetch(`${this.baseUrl}/v1/batches/${batchId}`)

    if (!response.ok) {
      throw new Error(`Failed to get batch status: ${response.statusText}`)
    }

    const result = await response.json()

    return {
      id: result.batch_id,
      status: this.mapStatus(result.status),
      created_at: new Date(result.created_at).getTime() / 1000,
      completed_at: result.completed_at ? new Date(result.completed_at).getTime() / 1000 : undefined,
      request_counts: {
        total: result.progress.total,
        completed: result.progress.completed,
        failed: result.progress.failed || 0
      }
    }
  }

  /**
   * Download batch results
   */
  async downloadResults(batchId: string): Promise<BatchResultLine[]> {
    const response = await fetch(`${this.baseUrl}/v1/batches/${batchId}/results`)

    if (!response.ok) {
      throw new Error(`Failed to download results: ${response.statusText}`)
    }

    const text = await response.text()
    const lines = text.trim().split('\n').filter(line => line.trim())

    return lines.map(line => {
      const result = JSON.parse(line)
      
      // Convert vLLM format to Parasail format
      return {
        custom_id: result.custom_id,
        response: {
          status_code: 200,
          body: {
            model: result.response.body.model,
            choices: result.response.body.choices,
            usage: result.response.body.usage
          }
        },
        error: null
      }
    })
  }

  /**
   * Map vLLM status to Parasail status
   */
  private mapStatus(vllmStatus: string): BatchStatus {
    const statusMap: Record<string, BatchStatus> = {
      'pending': 'pending',
      'running': 'in_progress',
      'completed': 'completed',
      'failed': 'failed'
    }

    return statusMap[vllmStatus] || 'pending'
  }
}

/**
 * Factory function to create vLLM batch client
 */
export function createVLLMBatchClient(config?: { baseUrl?: string; webhookUrl?: string }): VLLMBatchClient {
  return new VLLMBatchClient(config)
}

