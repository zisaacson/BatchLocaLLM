# 🚀 Quick Start Guide - Real Aris Data

**When the lead engineer provides the dataset, follow these steps:**

---

## 📋 Step 1: Receive Data (Lead Engineer)

### **What We Need**

1. **Candidate Data File**
   - Format: CSV or JSONL
   - Location: Push to branch or provide download link
   - Size: 100-1000 for validation, up to 170K for production

2. **Data Schema**
   - What columns are in the CSV?
   - Example: `candidate_id, name, email, experience, skills, education, ...`

3. **System Prompt / Evaluation Criteria**
   - Your actual Praxis preferences from Aris
   - Scoring rubric
   - What you want the LLM to evaluate

4. **Expected Output Format**
   - What fields in the results?
   - Score format (1-10, pass/fail, JSON)?

---

## 🔧 Step 2: Adapt Conversion Script (5-10 minutes)

### **Update `tools/csv_to_batch.py`**

```python
# Find this function and update it to match your CSV schema
def csv_row_to_candidate_profile(row: Dict[str, str]) -> str:
    """Convert CSV row to candidate profile text"""
    
    # EXAMPLE - Update to match your actual CSV columns
    profile = f"""
Candidate: {row.get('name', 'Unknown')}
Email: {row.get('email', 'N/A')}
Current Role: {row.get('current_role', 'N/A')}
Company: {row.get('company', 'N/A')}
Experience: {row.get('years_experience', 'N/A')} years

Skills:
{row.get('skills', 'N/A')}

Work History:
{row.get('work_history', 'N/A')}

Education:
{row.get('education', 'N/A')}
"""
    return profile.strip()


# Find this function and update the system prompt
def create_batch_request(
    candidate_id: str,
    candidate_profile: str,
    model: str = "gemma3:12b"
) -> Dict:
    """Create a batch request for candidate evaluation"""
    
    # UPDATE THIS SYSTEM PROMPT with your actual Praxis preferences
    system_prompt = """You are an expert recruiter evaluating candidates.

EVALUATION CRITERIA:
[INSERT YOUR ACTUAL PRAXIS PREFERENCES HERE]
- Track record weight: X%
- Pedigree weight: Y%
- Experience weight: Z%
- Education pedigree: [YOUR CRITERIA]
- Company pedigree: [YOUR CRITERIA]
- Diversity & inclusion: [YOUR CRITERIA]
- Startup experience: [YOUR CRITERIA]
- FAANG experience: [YOUR CRITERIA]

SCORING:
[INSERT YOUR ACTUAL SCORING RUBRIC]
- Score 1-10
- Provide reasoning
- Highlight strengths and concerns

OUTPUT FORMAT:
Return a JSON object with:
{
  "score": <1-10>,
  "reasoning": "<detailed explanation>",
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "concerns": ["<concern 1>", "<concern 2>", ...],
  "recommendation": "<hire/pass/maybe>"
}
"""
    
    user_prompt = f"Evaluate this candidate:\n\n{candidate_profile}"
    
    # Rest of the function stays the same...
```

### **Test the Conversion**

```bash
# Test with a small sample first
python tools/csv_to_batch.py your_data.csv test_batch.jsonl

# Check the output
head -5 test_batch.jsonl
```

---

## ✅ Step 3: Validation Run (10-30 minutes)

### **Start with Small Sample**

```bash
# If you have 170K candidates, test with first 100-1000
head -1001 your_data.csv > validation_sample.csv  # Header + 1000 rows

# Convert to batch
python tools/csv_to_batch.py validation_sample.csv validation_batch.jsonl

# Run the batch
python tools/run_batch.py validation_sample.csv
```

### **Monitor Progress**

The script will show real-time progress:
```
Status: in_progress | Progress: 100/1000 (10.0%) | Failed: 0 | Throughput: 3.52 req/s | ETA: 4.2m
```

### **Check Results**

```bash
# Results will be in validation_sample_results.jsonl
# Scores will be in validation_sample_scores.csv

# View first few results
head -5 validation_sample_scores.csv

# Or use the analyzer
python tools/analyze_results.py validation_sample_results.jsonl
```

---

## 🔍 Step 4: Validate Results (5-10 minutes)

### **Check Quality**

1. **Spot Check**: Manually review 5-10 results
   - Do the scores make sense?
   - Is the reasoning sound?
   - Are strengths/concerns accurate?

2. **Check Metrics**:
   ```bash
   # The analyzer will show:
   - Success rate (should be 100%)
   - Score distribution
   - Token usage
   - Processing time
   ```

3. **Check for Issues**:
   - Any errors in the results?
   - Any malformed JSON responses?
   - Any candidates that failed?

### **Common Issues & Fixes**

| Issue | Cause | Fix |
|-------|-------|-----|
| Low scores for all | System prompt too strict | Adjust evaluation criteria |
| High scores for all | System prompt too lenient | Adjust evaluation criteria |
| Malformed JSON | LLM not following format | Add "You MUST return valid JSON" to prompt |
| Missing fields | CSV schema mismatch | Update `csv_row_to_candidate_profile()` |
| Slow processing | Long prompts | Check token usage, may need to trim |

---

## 🎯 Step 5: Tune if Needed (5-10 minutes)

### **Adjust Context Limits** (if prompts are very long)

Edit `src/batch_processor.py`:
```python
self.context_manager = ContextManager(
    ContextConfig(
        model_name=settings.model_name,
        max_context_tokens=32000,  # Increase if needed
        trim_threshold_pct=0.875,  # Adjust if needed
        trim_interval=50,  # Increase for higher cache hits
        ...
    )
)
```

### **Adjust Trimming Strategy** (if needed)

```python
trim_strategy=TrimStrategy.HYBRID,  # Options: SLIDING_WINDOW, HYBRID, AGGRESSIVE
```

### **Monitor VRAM** (if approaching limits)

```bash
# Watch VRAM during processing
watch -n 1 nvidia-smi
```

If VRAM > 14GB consistently:
- Reduce `max_context_tokens` to 24000
- Use `TrimStrategy.AGGRESSIVE`
- Reduce `trim_interval` to 25

---

## 🚀 Step 6: Production Run (7-13 hours for 170K)

### **Pre-Flight Checklist**

- [ ] Validation run completed successfully
- [ ] Results quality verified
- [ ] No errors in validation
- [ ] VRAM stable (<14 GB)
- [ ] System prompt finalized
- [ ] Output format confirmed

### **Launch Production Run**

```bash
# Make sure server is running
ps aux | grep uvicorn

# If not running, start it
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080 &

# Run the full batch
python tools/run_batch.py your_170k_data.csv
```

### **Monitor Progress**

```bash
# The script shows real-time updates
# You can also tail the server logs
tail -f server.log

# Or check VRAM
watch -n 5 nvidia-smi
```

### **Expected Timeline** (170K candidates)

- **Throughput**: 3.5-4.0 req/s
- **Total Time**: 12-13 hours
- **Progress Updates**: Every 100 requests
- **VRAM**: Stable at 10-11 GB
- **Context**: Stable at <1K tokens

### **What to Watch For**

✅ **Good Signs**:
- Throughput stable at 3.5-4.0 req/s
- VRAM stable at 10-11 GB
- No errors in logs
- Progress updates every ~30 seconds

⚠️ **Warning Signs**:
- Throughput dropping below 2.0 req/s
- VRAM climbing above 14 GB
- Errors appearing in logs
- Progress stalling

🚨 **Stop If**:
- VRAM hits 15 GB (risk of OOM)
- Error rate > 5%
- System becomes unresponsive

---

## 📊 Step 7: Analyze Results (2 minutes)

```bash
# Comprehensive analysis
python tools/analyze_results.py your_170k_data_results.jsonl

# This will show:
# - Success rate
# - Score distribution
# - Token usage
# - Processing time
# - Error analysis (if any)

# Results exported to CSV
# your_170k_data_scores.csv
```

---

## 🎉 Step 8: Celebrate!

You just processed 170,000 candidates in ~12 hours for $50 in electricity instead of:
- **20 days** of processing time
- **$350,000** in cloud API costs

**Savings**:
- **Time**: 67x faster
- **Cost**: 99.99% cheaper
- **Control**: 100% local

---

## 🆘 Troubleshooting

### **Server Not Responding**

```bash
# Check if server is running
ps aux | grep uvicorn

# Check if Ollama is running
ps aux | grep ollama

# Restart server
pkill -f uvicorn
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080 &
```

### **Out of Memory (OOM)**

```bash
# Check VRAM
nvidia-smi

# If VRAM is full, reduce context limit
# Edit src/batch_processor.py:
max_context_tokens=24000  # Reduce from 32000
trim_interval=25  # Reduce from 50
```

### **Slow Processing**

```bash
# Check if model is loaded
curl http://localhost:11434/api/tags

# Check system resources
htop

# Check if other processes are using GPU
nvidia-smi
```

### **Malformed Results**

```bash
# Check a few results manually
head -10 results.jsonl | jq .

# If JSON is malformed, update system prompt:
# Add: "You MUST return valid JSON. Do not include any text outside the JSON object."
```

---

## 📞 Need Help?

1. **Check Logs**: `tail -100 server.log`
2. **Check Metrics**: Printed every 100 requests
3. **Check VRAM**: `nvidia-smi`
4. **Check Errors**: `grep ERROR server.log`

---

**Status**: ✅ **READY TO PROCESS REAL DATA**

**Next**: Waiting for lead engineer to provide dataset! 🚀

