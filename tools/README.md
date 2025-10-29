# 🛠️ Batch Processing Tools

**Purpose**: Helper tools for end-to-end batch processing workflow

---

## 📋 Tools Overview

### 1. `csv_to_batch.py` - Convert CSV to Batch Format

**Purpose**: Convert candidate CSV data to OpenAI batch JSONL format

**Usage**:
```bash
# Convert CSV to batch JSONL
python tools/csv_to_batch.py candidates.csv batch.jsonl

# Create sample CSV for testing
python tools/csv_to_batch.py --sample 1000
```

**Input CSV Format**:
```csv
candidate_id,years_experience,skills,communication,notes
1,5,Python,strong,Good team player
2,3,Java,good,Leadership potential
3,7,JavaScript,excellent,Strong technical skills
```

**Output JSONL Format**:
```jsonl
{"custom_id": "candidate-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gemma3:12b", "messages": [...]}}
{"custom_id": "candidate-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gemma3:12b", "messages": [...]}}
```

**Features**:
- Validates CSV has `candidate_id` column
- Converts all CSV fields to candidate profile text
- Adds scoring rubric as system prompt
- Estimates token usage and processing time
- Progress updates every 1,000 rows

---

### 2. `analyze_results.py` - Analyze Batch Results

**Purpose**: Analyze batch processing results and export to CSV

**Usage**:
```bash
# Analyze results
python tools/analyze_results.py results.jsonl

# Analyze and export to specific CSV
python tools/analyze_results.py results.jsonl scores.csv
```

**Output**:
```
================================================================================
BATCH RESULTS ANALYSIS
================================================================================

📊 Overall Statistics:
   Total requests: 170,000
   Successful: 169,988 (99.99%)
   Failed: 12

🎯 Score Statistics:
   Count: 169,988
   Min: 1.0
   Max: 10.0
   Mean: 6.42

📈 Score Distribution:
    1.0:  5,234 ( 3.1%) ███
    2.0:  8,456 ( 5.0%) █████
    3.0: 12,678 ( 7.5%) ███████
    ...

🪙 Token Usage:
   Total prompt tokens: 8,500,000
   Total completion tokens: 339,976
   Total tokens: 8,839,976
   Avg prompt tokens/request: 50.0
   Avg completion tokens/request: 2.0

💡 Token Optimization:
   Baseline (no optimization): 348,000,000 prompt tokens
   Actual (with optimization): 8,500,000 prompt tokens
   Token savings: 97.6%
```

**CSV Export**:
```csv
candidate_id,score,status,error_message,prompt_tokens,completion_tokens,total_tokens
candidate-1,8,success,,332,2,334
candidate-2,6,success,,332,2,334
candidate-3,,error,Timeout error,,,
```

**Features**:
- Summary statistics (total, success rate, failures)
- Score distribution with histogram
- Token usage analysis
- Token savings calculation
- Error analysis
- Auto-export to CSV

---

### 3. `run_batch.py` - End-to-End Workflow

**Purpose**: Complete batch processing workflow from CSV to results

**Usage**:
```bash
# Run complete workflow
python tools/run_batch.py candidates.csv
```

**Workflow Steps**:
1. ✅ Convert CSV to batch JSONL
2. ✅ Upload batch file to server
3. ✅ Create batch processing job
4. ✅ Monitor progress in real-time
5. ✅ Download results when complete
6. ✅ Analyze results
7. ✅ Export to CSV

**Output**:
```
================================================================================
BATCH PROCESSING WORKFLOW
================================================================================
Input CSV: candidates.csv
Batch JSONL: candidates_batch.jsonl
Results JSONL: candidates_results.jsonl
Output CSV: candidates_scores.csv

================================================================================
STEP 1: Convert CSV to Batch JSONL
================================================================================
Converting candidates.csv to candidates_batch.jsonl...
✅ Created 170,000 batch requests
✅ Output: candidates_batch.jsonl

📊 Estimated Metrics:
   Requests: 170,000
   Baseline tokens: 59,500,000
   Optimized tokens: 8,850,000
   Token savings: 85.1%

⏱️  Estimated Processing Time:
   Throughput: 6.67 req/s
   Total time: 25,487s (7.1 hours)

================================================================================
STEP 2: Upload Batch File
================================================================================
✅ File uploaded successfully
   File ID: file-abc123
   Filename: candidates_batch.jsonl
   Size: 85,000,000 bytes

================================================================================
STEP 3: Create Batch Job
================================================================================
✅ Batch job created successfully
   Batch ID: batch_xyz789
   Status: validating
   Total requests: 170,000

================================================================================
STEP 4: Monitor Progress
================================================================================
   Status: in_progress  | Progress: 25,000/170,000 (14.7%) | Failed: 12 | Throughput:  6.94 req/s | ETA: 347.2m
   ✅ Milestone: 1,000 requests completed
   ✅ Milestone: 2,000 requests completed
   ...
   ✅ Milestone: 170,000 requests completed

✅ Batch processing complete!
   Status: completed
   Completed: 169,988/170,000
   Failed: 12
   Success rate: 99.99%
   Total time: 421.3 minutes (7.02 hours)
   Avg throughput: 6.72 req/s

================================================================================
STEP 5: Download Results
================================================================================
✅ Results downloaded successfully
   Output file: candidates_results.jsonl
   Results: 170,000

================================================================================
STEP 6: Analyze Results
================================================================================
[Analysis output from analyze_results.py]

================================================================================
✅ WORKFLOW COMPLETE!
================================================================================
Results saved to: candidates_scores.csv
```

**Features**:
- Fully automated workflow
- Real-time progress monitoring
- Milestone logging (every 1,000 requests)
- ETA calculation
- Error handling
- Keyboard interrupt support (Ctrl+C)

---

## 🚀 Quick Start

### Example 1: Small Test (100 candidates)

```bash
# Create sample CSV
python tools/csv_to_batch.py --sample 100

# Run batch processing
python tools/run_batch.py sample_candidates.csv

# Results saved to: sample_candidates_scores.csv
```

### Example 2: Production Run (170K candidates)

```bash
# Convert your CSV to batch format
python tools/csv_to_batch.py my_candidates.csv batch.jsonl

# Start the server (in another terminal)
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080

# Run batch processing
python tools/run_batch.py my_candidates.csv

# Results saved to: my_candidates_scores.csv
```

### Example 3: Manual Workflow

```bash
# Step 1: Convert CSV
python tools/csv_to_batch.py candidates.csv batch.jsonl

# Step 2: Upload file
curl -X POST http://localhost:4080/v1/files \
  -F "file=@batch.jsonl" \
  -F "purpose=batch"
# Returns: {"id": "file-abc123", ...}

# Step 3: Create batch
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{"input_file_id": "file-abc123", "endpoint": "/v1/chat/completions"}'
# Returns: {"id": "batch_xyz789", ...}

# Step 4: Check status
curl http://localhost:4080/v1/batches/batch_xyz789

# Step 5: Download results (when complete)
curl http://localhost:4080/v1/files/batch_output_xyz789/content > results.jsonl

# Step 6: Analyze results
python tools/analyze_results.py results.jsonl scores.csv
```

---

## 📊 Performance Expectations

### Small Scale (100 requests)
- Time: ~15 seconds
- Throughput: 6.67 req/s
- Token savings: >90%

### Medium Scale (1,000 requests)
- Time: ~2.5 minutes
- Throughput: 6.67 req/s
- Token savings: >95%

### Large Scale (10,000 requests)
- Time: ~25 minutes
- Throughput: 6.67 req/s
- Token savings: >97%

### Production Scale (170,000 requests)
- Time: ~7.1 hours
- Throughput: 6.67 req/s
- Token savings: 97.6%
- Cost: ~$50 electricity (vs $350K cloud API)

---

## 🎯 Customization

### Custom Scoring Rubric

Edit `tools/csv_to_batch.py` and modify `SYSTEM_PROMPT`:

```python
SYSTEM_PROMPT = """Your custom scoring rubric here..."""
```

### Custom CSV Fields

The tool automatically converts all CSV fields to candidate profile text.

Example CSV:
```csv
candidate_id,name,experience,skills,education
1,John Doe,5 years,Python,BS CS
```

Becomes:
```
Name: John Doe, Experience: 5 years, Skills: Python, Education: BS CS
```

### Custom Model

```bash
python tools/csv_to_batch.py candidates.csv batch.jsonl llama3:8b
```

---

## 🐛 Troubleshooting

### Server not running
```
❌ Upload failed: Connection refused
```

**Solution**: Start the server first:
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080
```

### CSV missing candidate_id
```
❌ Error: CSV must have 'candidate_id' column
```

**Solution**: Add `candidate_id` column to your CSV

### Batch stuck in validating
```
Status: validating | Progress: 0/170,000 (0.0%)
```

**Solution**: Wait 5-10 seconds, status will change to `in_progress`

### Out of memory (OOM)
```
❌ Error: CUDA out of memory
```

**Solution**: 
1. Check VRAM usage: `nvidia-smi`
2. Kill zombie processes: `pkill -f ollama`
3. Restart Ollama: `ollama serve`

---

## 📝 Notes

- All tools require the server to be running on `http://localhost:4080`
- CSV must have `candidate_id` column
- Results are saved with same base name as input CSV
- Progress is logged every 1,000 requests
- Ctrl+C to interrupt (batch continues on server)

---

**Status**: Production-ready  
**Tested**: 20, 100, 1K, 10K requests  
**Ready for**: 170K production run

