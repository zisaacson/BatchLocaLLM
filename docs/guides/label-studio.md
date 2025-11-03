# Label Studio ML Backend Setup Guide

Complete guide to setting up Label Studio with vLLM Batch Server for training data curation.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Workflow](#workflow)
6. [Troubleshooting](#troubleshooting)

---

## Overview

### What is Label Studio?

Label Studio is an open-source data labeling platform that allows you to:
- ✅ Annotate and label data with a web UI
- ✅ Track ground truth annotations
- ✅ Calculate model accuracy
- ✅ Export curated datasets for fine-tuning

### Why Integrate with vLLM Batch Server?

**Without ML Backend:**
- Annotators label from scratch (slow)
- No model predictions to validate
- Manual quality tracking

**With ML Backend:**
- **50-70% faster labeling** - Pre-filled predictions
- **Validate, don't create** - Annotators correct instead of writing
- **Automatic quality metrics** - Track accuracy vs ground truth
- **Webhook automation** - Training triggers at milestones

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Label Studio UI                          │
│                      (Port 4115)                                │
│  - Annotators review/correct predictions                       │
│  - Mark ground truth annotations                               │
│  - Trigger training data export                                │
└────────────┬────────────────────────────────┬───────────────────┘
             │                                │
             │ 1. Request prediction          │ 2. Send webhook
             │                                │
             ▼                                ▼
┌─────────────────────────┐      ┌─────────────────────────────┐
│   ML Backend Server     │      │   vLLM Batch API Server     │
│   (Port 4082)           │      │   (Port 4080)               │
│                         │      │                             │
│ - Receives task         │      │ - Receives webhook events   │
│ - Calls inference API   │◄─────┤ - Validates annotations     │
│ - Returns predictions   │      │ - Triggers training export  │
└─────────────────────────┘      │ - Calculates accuracy       │
                                 └──────────┬──────────────────┘
                                            │
                                            │ 3. Single inference
                                            │
                                            ▼
                                 ┌─────────────────────────────┐
                                 │   Inference Engine          │
                                 │   (In-memory vLLM)          │
                                 │                             │
                                 │ - Keeps model loaded        │
                                 │ - Fast single predictions   │
                                 │ - Low latency (<2s)         │
                                 └─────────────────────────────┘
```

---

## Installation

### 1. Start All Services

```bash
# Start Docker services (PostgreSQL, Label Studio, monitoring)
docker compose -f docker/docker-compose.yml up -d

# Start native Python services (API, Worker, ML Backend)
./scripts/start-services.sh
```

### 2. Verify Services

```bash
# Check API Server
curl http://localhost:4080/health

# Check ML Backend
curl http://localhost:4082/

# Check Label Studio
curl http://localhost:4115/health
```

### 3. Access Label Studio

Open http://localhost:4115 in your browser.

**Default credentials:**
- Username: `admin@vllm-batch.local`
- Password: `vllm_batch_2024`

---

## Configuration

### Step 1: Create a Project

1. Click **"Create Project"**
2. Name: `Candidate Evaluation`
3. Click **"Save"**

### Step 2: Configure Labeling Interface

Go to **Settings > Labeling Interface** and paste this XML:

```xml
<View>
  <Header value="Candidate Evaluation"/>
  
  <!-- Display candidate data -->
  <Text name="candidate_name" value="$name"/>
  <Text name="candidate_title" value="$title"/>
  <Text name="candidate_company" value="$company"/>
  
  <!-- Recommendation -->
  <Choices name="recommendation" toName="candidate_name" choice="single" required="true">
    <Choice value="strong_yes"/>
    <Choice value="yes"/>
    <Choice value="maybe"/>
    <Choice value="no"/>
    <Choice value="strong_no"/>
  </Choices>
  
  <!-- Trajectory Rating -->
  <Choices name="trajectory_rating" toName="candidate_name" choice="single" required="true">
    <Choice value="exceptional"/>
    <Choice value="strong"/>
    <Choice value="good"/>
    <Choice value="average"/>
    <Choice value="weak"/>
  </Choices>
  
  <!-- Pedigree Rating -->
  <Choices name="pedigree_rating" toName="candidate_name" choice="single" required="true">
    <Choice value="exceptional"/>
    <Choice value="strong"/>
    <Choice value="good"/>
    <Choice value="average"/>
    <Choice value="weak"/>
  </Choices>
  
  <!-- Reasoning -->
  <TextArea name="reasoning" toName="candidate_name" placeholder="Explain your evaluation..." required="false"/>
</View>
```

### Step 3: Connect ML Backend

1. Go to **Settings > Machine Learning**
2. Click **"Add Model"**
3. Enter:
   - **URL**: `http://host.docker.internal:4082`
   - **Title**: `vLLM Batch Server`
4. Click **"Validate and Save"**

**✅ Success:** You should see "Connected" status.

### Step 4: Configure Webhooks

1. Go to **Settings > Webhooks**
2. Click **"Add Webhook"**
3. Enter:
   - **URL**: `http://host.docker.internal:4080/v1/webhooks/label-studio`
   - **Events**: Select all:
     - `ANNOTATION_CREATED`
     - `ANNOTATION_UPDATED`
     - `ANNOTATION_DELETED`
     - `TASK_CREATED`
     - `TASK_DELETED`
     - `PROJECT_CREATED`
     - `PROJECT_UPDATED`
     - `START_TRAINING`
4. Click **"Save"**

**✅ Success:** Webhooks will now trigger automatically.

---

## Workflow

### 1. Import Batch Results

After running a batch job, import results to Label Studio:

```python
import requests

# Get batch results
batch_id = "batch_abc123"
response = requests.get(f"http://localhost:4080/v1/batches/{batch_id}")
output_file_id = response.json()["output_file_id"]

# Import to Label Studio
project_id = 123
requests.post(
    f"http://localhost:4080/v1/label-studio/import/{project_id}",
    json={
        "batch_id": batch_id,
        "output_file_id": output_file_id
    }
)
```

### 2. Annotate with ML Backend

1. Open a task in Label Studio
2. **ML Backend automatically provides predictions** (pre-filled)
3. Annotator reviews and corrects if needed
4. Click **"Submit"**

**Result:** 50-70% faster than labeling from scratch!

### 3. Mark Ground Truth

For high-quality annotations you want to use as gold standard:

1. Open the annotation
2. Click **"⭐ Mark as Ground Truth"**
3. This annotation will be used for accuracy calculation

### 4. Automatic Milestones

Webhooks automatically trigger at these milestones:
- ✅ **100 annotations** - First checkpoint
- ✅ **500 annotations** - Early training data
- ✅ **1,000 annotations** - Minimum viable dataset
- ✅ **5,000 annotations** - Production-ready dataset
- ✅ **10,000 annotations** - Large-scale dataset

**What happens:**
- Logs milestone reached
- Exports training data automatically
- Saves to `data/training/project_{id}_export.json`

### 5. Export Training Data

**Manual export:**
```bash
curl http://localhost:4080/v1/label-studio/export/123 > training_data.json
```

**Automatic export (webhook):**
1. Go to Label Studio project
2. Click **"Start Training"** button
3. Webhook triggers export automatically
4. Check `data/training/project_123_export.json`

### 6. Calculate Accuracy

Compare model predictions vs ground truth:

```python
import requests

# Get model predictions
model_predictions = [
    {
        "task_id": 1,
        "prediction": {
            "recommendation": "yes",
            "trajectory_rating": "strong",
            "pedigree_rating": "good"
        }
    },
    # ... more predictions
]

# Calculate accuracy
response = requests.post(
    f"http://localhost:4080/v1/label-studio/accuracy/123",
    json={"predictions": model_predictions}
)

accuracy = response.json()
print(f"Overall: {accuracy['overall_accuracy']:.1%}")
print(f"By field: {accuracy['field_accuracy']}")
```

---

## Troubleshooting

### ML Backend Not Connecting

**Solution:**
```bash
# Check ML Backend is running
curl http://localhost:4082/

# Restart services
./scripts/stop-services.sh
./scripts/start-services.sh
```

### Predictions Not Appearing

**Solution:**
1. Check ML Backend is connected in Label Studio settings
2. Verify model is loaded
3. Check inference endpoint works

### Webhooks Not Firing

**Solution:**
1. Check webhook configuration in Label Studio
2. Verify URL: `http://host.docker.internal:4080/v1/webhooks/label-studio`
3. Check logs: `tail -f logs/api_server.log | grep webhook`

---

## Best Practices

1. **Start Small** - Begin with 100 examples
2. **Use Smaller Models** - Gemma 3 4B for labeling (fast)
3. **Mark Ground Truth** - Select diverse, high-quality examples
4. **Monitor Accuracy** - Calculate every 100 annotations
5. **Export Regularly** - Backup at milestones

---

## Next Steps

1. ✅ Set up Label Studio
2. ✅ Run batch job
3. ✅ Import to Label Studio
4. ✅ Annotate with ML Backend
5. ✅ Mark ground truth
6. ✅ Calculate accuracy
7. ✅ Export training data

**Questions?** Check the [main README](../README.md) or [open an issue](https://github.com/zisaacson/vllm-batch-server/issues).

