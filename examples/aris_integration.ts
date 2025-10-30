/**
 * Aris App Integration Example
 * 
 * Shows how to integrate the local vLLM batch server with the Aris web app.
 * 
 * Features:
 * - Submit batch jobs from Aris
 * - Receive webhook callbacks
 * - Parse and store results in database
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// Configuration
const BATCH_API_URL = process.env.VLLM_BATCH_API_URL || 'http://localhost:4080';
const WEBHOOK_URL = process.env.NEXT_PUBLIC_URL + '/api/aristotle/batch/webhook';

/**
 * Submit candidates for batch analysis
 * 
 * POST /api/aristotle/batch/submit
 */
export async function POST_submit(req: NextRequest) {
  const { candidateIds, model = 'google/gemma-3-4b-it' } = await req.json();
  
  // Fetch candidates from database
  const candidates = await prisma.candidate.findMany({
    where: { aristotleId: { in: candidateIds } },
    select: {
      aristotleId: true,
      name: true,
      title: true,
      company: true,
      experience: true,
      education: true,
    }
  });
  
  // Build batch JSONL
  const batchLines = candidates.map((candidate, idx) => {
    const prompt = buildCandidatePrompt(candidate);
    
    return JSON.stringify({
      custom_id: candidate.aristotleId,
      body: {
        messages: [
          { role: 'system', content: 'You are an expert technical recruiter...' },
          { role: 'user', content: prompt }
        ]
      }
    });
  });
  
  const batchContent = batchLines.join('\n');
  
  // Submit to batch API
  const formData = new FormData();
  formData.append('file', new Blob([batchContent], { type: 'application/jsonl' }), 'batch.jsonl');
  formData.append('model', model);
  formData.append('webhook_url', WEBHOOK_URL);
  formData.append('metadata', JSON.stringify({
    userId: req.headers.get('x-user-id'),
    candidateCount: candidates.length,
    submittedAt: new Date().toISOString()
  }));
  
  const response = await fetch(`${BATCH_API_URL}/v1/batches`, {
    method: 'POST',
    body: formData
  });
  
  if (!response.ok) {
    const error = await response.text();
    return NextResponse.json({ error }, { status: response.status });
  }
  
  const batch = await response.json();
  
  // Create batch record in Aris database
  await prisma.mLAnalysisBatch.create({
    data: {
      batchId: batch.batch_id,
      model: model,
      status: batch.status,
      totalRequests: batch.progress.total,
      completedRequests: 0,
      estimatedCompletionMinutes: batch.estimate?.completion_time_minutes,
      createdAt: new Date()
    }
  });
  
  return NextResponse.json({
    batchId: batch.batch_id,
    status: batch.status,
    candidateCount: candidates.length,
    estimatedCompletionMinutes: batch.estimate?.completion_time_minutes
  });
}

/**
 * Receive webhook callback when batch completes
 * 
 * POST /api/aristotle/batch/webhook
 */
export async function POST_webhook(req: NextRequest) {
  const webhook = await req.json();
  
  console.log('📡 Webhook received:', webhook.id);
  
  // Update batch status in database
  await prisma.mLAnalysisBatch.update({
    where: { batchId: webhook.id },
    data: {
      status: webhook.status,
      completedRequests: webhook.request_counts.completed,
      failedRequests: webhook.request_counts.failed,
      completedAt: webhook.completed_at ? new Date(webhook.completed_at * 1000) : null
    }
  });
  
  // If completed, download and process results
  if (webhook.status === 'completed') {
    await processResults(webhook.id);
  }
  
  return NextResponse.json({ received: true });
}

/**
 * Download and process batch results
 */
async function processResults(batchId: string) {
  console.log('📥 Downloading results for batch:', batchId);
  
  // Download results
  const response = await fetch(`${BATCH_API_URL}/v1/batches/${batchId}/results`);
  const resultsText = await response.text();
  
  // Parse JSONL
  const results = resultsText.trim().split('\n').map(line => JSON.parse(line));
  
  console.log(`📊 Processing ${results.length} results...`);
  
  // Insert into database
  for (const result of results) {
    const aristotleId = result.custom_id;
    const response = result.response.body;
    const content = response.choices[0].message.content;
    
    // Parse LLM response (assuming JSON format)
    const analysis = parseAnalysisResponse(content);
    
    await prisma.mLCandidateAnalysis.create({
      data: {
        aristotleId: aristotleId,
        batchId: batchId,
        domain: 'software_engineering',
        
        // Scores
        overallScore: analysis.overall_score,
        trackRecordScore: analysis.track_record_score,
        educationPedigreeScore: analysis.education_pedigree_score,
        companyPedigreeScore: analysis.company_pedigree_score,
        
        // Ratings
        recommendation: analysis.recommendation,
        trajectoryRating: analysis.trajectory_rating,
        companyPedigreeRating: analysis.company_pedigree_rating,
        educationalPedigreeRating: analysis.educational_pedigree_rating,
        
        // Flags
        isSoftwareEngineer: analysis.is_software_engineer,
        
        // Insights
        strengths: analysis.strengths,
        weaknesses: analysis.weaknesses,
        keyInsights: analysis.key_insights,
        
        // Metadata
        modelUsed: 'google/gemma-3-4b-it',
        promptTokens: response.usage.prompt_tokens,
        completionTokens: response.usage.completion_tokens,
        
        createdAt: new Date()
      }
    });
  }
  
  console.log(`✅ Processed ${results.length} results`);
}

/**
 * Parse LLM response into structured analysis
 */
function parseAnalysisResponse(content: string) {
  try {
    // Try to parse as JSON
    const json = JSON.parse(content);
    return json;
  } catch (e) {
    // If not JSON, extract structured data from text
    // (implement your own parsing logic here)
    return {
      overall_score: 0,
      track_record_score: 0,
      education_pedigree_score: 0,
      company_pedigree_score: 0,
      recommendation: 'maybe',
      trajectory_rating: 'average',
      company_pedigree_rating: 'average',
      educational_pedigree_rating: 'average',
      is_software_engineer: false,
      strengths: [],
      weaknesses: [],
      key_insights: []
    };
  }
}

/**
 * Build candidate evaluation prompt
 */
function buildCandidatePrompt(candidate: any): string {
  return `
Evaluate this candidate for a senior software engineering role:

Name: ${candidate.name}
Current Title: ${candidate.title}
Current Company: ${candidate.company}

Experience:
${candidate.experience.map((exp: any) => `- ${exp.title} at ${exp.company} (${exp.duration})`).join('\n')}

Education:
${candidate.education.map((edu: any) => `- ${edu.degree} from ${edu.school}`).join('\n')}

Provide a structured evaluation with:
1. Overall recommendation (strong_yes/yes/maybe/no/strong_no)
2. Trajectory rating (exceptional/strong/good/average/weak)
3. Company pedigree rating (exceptional/strong/good/average/weak)
4. Educational pedigree rating (exceptional/strong/good/average/weak)
5. Is this a software engineer? (true/false)
6. Key strengths (list)
7. Key weaknesses (list)
8. Key insights (list)

Return as JSON.
`.trim();
}

/**
 * Poll batch status
 * 
 * GET /api/aristotle/batch/{batchId}/status
 */
export async function GET_status(req: NextRequest, { params }: { params: { batchId: string } }) {
  const { batchId } = params;
  
  // Check local database first
  const localBatch = await prisma.mLAnalysisBatch.findUnique({
    where: { batchId }
  });
  
  // Fetch latest status from batch API
  const response = await fetch(`${BATCH_API_URL}/v1/batches/${batchId}`);
  const batch = await response.json();
  
  return NextResponse.json({
    batchId: batch.batch_id,
    status: batch.status,
    progress: batch.progress,
    createdAt: localBatch?.createdAt,
    estimatedCompletionMinutes: localBatch?.estimatedCompletionMinutes,
    throughputTokensPerSec: batch.throughput_tokens_per_sec
  });
}

/**
 * List all batches
 * 
 * GET /api/aristotle/batch
 */
export async function GET_list(req: NextRequest) {
  const batches = await prisma.mLAnalysisBatch.findMany({
    orderBy: { createdAt: 'desc' },
    take: 50
  });
  
  return NextResponse.json({ batches });
}

