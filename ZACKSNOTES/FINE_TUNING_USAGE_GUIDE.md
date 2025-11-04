# 🎯 Fine-Tuning System - Complete Usage Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Web Dashboard](#web-dashboard)
4. [API Reference](#api-reference)
5. [Workflow Examples](#workflow-examples)
6. [Model Comparison](#model-comparison)
7. [A/B Testing](#ab-testing)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

The Fine-Tuning System allows you to:
- **Export gold star conquests** to training datasets
- **Train custom models** using Unsloth (2x faster than HuggingFace)
- **Monitor training progress** in real-time
- **Deploy fine-tuned models** to vLLM
- **Compare models** side-by-side with metrics
- **Run A/B tests** to validate improvements

### Key Features

✅ **Multi-Backend Support**: Unsloth, Axolotl, OpenAI, HuggingFace  
✅ **Real-Time Monitoring**: Track loss, epochs, ETA  
✅ **Comprehensive Metrics**: Quality, performance, efficiency  
✅ **Model Versioning**: Track all versions with rollback  
✅ **A/B Testing**: Validate improvements with real prompts  
✅ **Beautiful Web UI**: Modern dashboard for everything  

---

## 🚀 Quick Start

### 1. Access the Dashboard

Navigate to: **http://localhost:8000/fine-tuning**

### 2. Export a Dataset

```bash
curl -X POST http://localhost:8000/v1/fine-tuning/datasets/export \
  -H "Content-Type: application/json" \
  -d '{
    "philosopher": "zack@pacheightspartners.com",
    "domain": "pacheightspartners.com",
    "format": "chatml"
  }'
```

Response:
```json
{
  "dataset_path": "data/training_datasets/zack_pacheightspartners_20250104_123456.jsonl",
  "sample_count": 42,
  "format": "chatml"
}
```

### 3. Start Training

```bash
curl -X POST http://localhost:8000/v1/fine-tuning/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "philosopher": "zack@pacheightspartners.com",
    "domain": "pacheightspartners.com",
    "base_model": "google/gemma-3-12b-it",
    "backend": "unsloth",
    "num_epochs": 3,
    "batch_size": 4,
    "learning_rate": 0.0002
  }'
```

Response:
```json
{
  "id": "uuid-here",
  "status": "running",
  "base_model": "google/gemma-3-12b-it",
  "backend": "unsloth",
  "created_at": "2025-01-04T12:34:56Z"
}
```

### 4. Monitor Progress

```bash
curl http://localhost:8000/v1/fine-tuning/jobs/{job_id}
```

Response:
```json
{
  "id": "uuid-here",
  "status": "running",
  "progress": 67.5,
  "current_epoch": 2,
  "total_epochs": 3,
  "current_loss": 0.234,
  "eta_seconds": 1200
}
```

### 5. Deploy Model

```bash
curl -X POST http://localhost:8000/v1/fine-tuning/models/{model_id}/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_config": {
      "gpu_memory_utilization": 0.9,
      "max_model_len": 4096
    },
    "notes": "Deploying v1.0 to production"
  }'
```

---

## 🖥️ Web Dashboard

### Main Dashboard (`/fine-tuning`)

**Stats Overview**:
- Gold star count
- Active training jobs
- Deployed models
- Average win rate

**Training Datasets**:
- Export new datasets
- View existing datasets
- Download datasets

**Active Jobs**:
- Real-time progress bars
- Loss curves
- ETA countdown
- Cancel jobs

**Deployed Models**:
- Model versions
- Performance metrics
- Deployment status
- Compare models

### Model Comparison (`/model-comparison`)

**Features**:
- Side-by-side metrics comparison
- Quality charts (win rate, gold star rate)
- Performance charts (tokens/sec, latency)
- Color-coded improvements (green = better, red = worse)
- A/B testing interface

---

## 📚 API Reference

### Dataset Export

**POST** `/v1/fine-tuning/datasets/export`

Request:
```json
{
  "philosopher": "user@domain.com",
  "domain": "domain.com",
  "format": "chatml",  // or "alpaca", "openai"
  "min_rating": 4
}
```

### Create Training Job

**POST** `/v1/fine-tuning/jobs`

Request:
```json
{
  "philosopher": "user@domain.com",
  "domain": "domain.com",
  "base_model": "google/gemma-3-12b-it",
  "backend": "unsloth",
  "dataset_path": "path/to/dataset.jsonl",  // optional
  "num_epochs": 3,
  "batch_size": 4,
  "learning_rate": 0.0002,
  "lora_r": 16,
  "lora_alpha": 32,
  "lora_dropout": 0.05
}
```

### Get Job Status

**GET** `/v1/fine-tuning/jobs/{job_id}`

Response:
```json
{
  "id": "uuid",
  "status": "running",
  "progress": 67.5,
  "current_epoch": 2,
  "total_epochs": 3,
  "current_loss": 0.234,
  "best_loss": 0.189,
  "eta_seconds": 1200,
  "created_at": "2025-01-04T12:34:56Z"
}
```

### Cancel Job

**POST** `/v1/fine-tuning/jobs/{job_id}/cancel`

### List Models

**GET** `/v1/fine-tuning/models?philosopher=user@domain.com&domain=domain.com`

Response:
```json
[
  {
    "id": "uuid",
    "name": "gemma-3-12b-conquest-v1",
    "base_model": "google/gemma-3-12b-it",
    "version": "1.0",
    "status": "deployed",
    "win_rate": 72.5,
    "gold_star_rate": 85.0,
    "tokens_per_second": 55.2,
    "latency_ms": 90,
    "created_at": "2025-01-04T12:34:56Z"
  }
]
```

### Deploy Model

**POST** `/v1/fine-tuning/models/{model_id}/deploy`

Request:
```json
{
  "deployment_config": {
    "gpu_memory_utilization": 0.9,
    "max_model_len": 4096,
    "tensor_parallel_size": 1
  },
  "notes": "Production deployment v1.0"
}
```

### Run A/B Test

**POST** `/v1/fine-tuning/ab-test`

Request:
```json
{
  "base_model_id": "google/gemma-3-12b-it",
  "fine_tuned_model_id": "uuid-here",
  "test_prompts": [
    "Analyze this candidate profile...",
    "Generate a conquest summary..."
  ]
}
```

Response:
```json
{
  "comparison_id": "uuid",
  "status": "ready",
  "test_prompts": [...],
  "message": "A/B test created. Use the comparison UI to vote on responses."
}
```

### Record A/B Test Vote

**POST** `/v1/fine-tuning/ab-test/{comparison_id}/vote`

Request:
```json
{
  "comparison_id": "uuid",
  "winner": "fine_tuned"  // or "base" or "tie"
}
```

Response:
```json
{
  "comparison_id": "uuid",
  "base_wins": 5,
  "fine_tuned_wins": 12,
  "ties": 3,
  "win_rate": 67.5
}
```

---

## 🔄 Workflow Examples

### Example 1: Train Your First Model

```bash
# 1. Export dataset
curl -X POST http://localhost:8000/v1/fine-tuning/datasets/export \
  -H "Content-Type: application/json" \
  -d '{"philosopher": "zack@pacheightspartners.com", "domain": "pacheightspartners.com", "format": "chatml"}'

# 2. Start training (auto-exports if no dataset provided)
curl -X POST http://localhost:8000/v1/fine-tuning/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "philosopher": "zack@pacheightspartners.com",
    "domain": "pacheightspartners.com",
    "base_model": "google/gemma-3-12b-it",
    "backend": "unsloth",
    "num_epochs": 3
  }'

# 3. Monitor (replace {job_id} with actual ID)
watch -n 5 'curl http://localhost:8000/v1/fine-tuning/jobs/{job_id}'

# 4. Deploy when complete
curl -X POST http://localhost:8000/v1/fine-tuning/models/{model_id}/deploy \
  -H "Content-Type: application/json" \
  -d '{"deployment_config": {}, "notes": "First deployment"}'
```

### Example 2: Compare Two Models

```bash
# 1. List models
curl "http://localhost:8000/v1/fine-tuning/models?philosopher=zack@pacheightspartners.com&domain=pacheightspartners.com"

# 2. Navigate to comparison UI
# http://localhost:8000/model-comparison

# 3. Select base and fine-tuned models
# 4. View side-by-side metrics
# 5. Run A/B test with real prompts
```

---

## 📊 Model Comparison

### Metrics Explained

**Quality Metrics**:
- **Win Rate**: % of times fine-tuned beats base in A/B tests
- **Gold Star Rate**: % of outputs rated as gold stars
- **Avg Rating**: Mean rating (1-5 stars)
- **Consistency**: Lower std dev = more consistent

**Performance Metrics**:
- **Tokens/Second**: Inference speed
- **Latency**: Time to first token (TTFT)
- **Throughput**: Requests/second at saturation

**Efficiency Metrics**:
- **Model Size**: MB on disk
- **VRAM Usage**: GB during inference
- **Cost per 1M Tokens**: Estimated cost

---

## 🧪 A/B Testing

### How It Works

1. **Create Test**: Provide base model, fine-tuned model, and test prompts
2. **Generate Responses**: Both models generate responses for each prompt
3. **Vote**: Human evaluator votes on which response is better
4. **Calculate Win Rate**: System tracks wins/losses/ties

### Best Practices

- Use **10-20 diverse prompts** for reliable results
- Include **edge cases** and **common scenarios**
- Have **multiple evaluators** vote to reduce bias
- Track **win rate over time** to monitor improvements

---

## 🔧 Troubleshooting

### Training Job Stuck

```bash
# Check job status
curl http://localhost:8000/v1/fine-tuning/jobs/{job_id}

# Check logs
tail -f data/training/logs/train_{timestamp}.log

# Cancel if needed
curl -X POST http://localhost:8000/v1/fine-tuning/jobs/{job_id}/cancel
```

### Out of Memory (OOM)

Reduce batch size or use smaller model:
```json
{
  "batch_size": 2,  // reduce from 4
  "base_model": "google/gemma-3-4b-it"  // smaller model
}
```

### No Gold Stars Found

Check Aristotle database:
```sql
SELECT COUNT(*) FROM ml_analysis_rating 
WHERE is_gold_star = true 
AND use_as_sample_response = true;
```

---

## 🎉 Success!

You now have a complete fine-tuning system! 🚀

**Next Steps**:
1. Export your first dataset
2. Train a model with Unsloth
3. Compare with base model
4. Run A/B tests
5. Deploy to production

**Questions?** Check the implementation notes in `FINE_TUNING_SYSTEM_COMPLETE.md`

