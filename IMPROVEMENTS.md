# System Improvements - October 28, 2025

## 🚨 Critical Issue Resolved: Data Loss Prevention

### Problem
The Qwen 3-4B 5K benchmark ran for **24 hours**, processed **777/5000 requests**, then crashed. **ALL WORK WAS LOST** because the script only saved results at the very end.

### Root Cause
```python
# OLD APPROACH - DANGEROUS
outputs = llm.generate(prompts, sampling_params)  # Wait for ALL 5000
# ... then save results
```

If the process crashes, OOM occurs, or system reboots → **everything is lost**.

### Solution: Incremental Saving
Created `test_qwen3_4b_5k_incremental.py` with:

1. **Batch Processing**: Process 100 requests at a time
2. **Immediate Saving**: Save results after each batch
3. **Checkpoint System**: Resume from last completed batch if interrupted
4. **Progress Tracking**: Real-time progress updates

```python
# NEW APPROACH - SAFE
for batch_start in range(start_idx, total_requests, BATCH_SIZE):
    batch_prompts = prompts[batch_start:batch_end]
    outputs = llm.generate(batch_prompts, sampling_params)
    
    # SAVE IMMEDIATELY
    with open(output_file, 'a') as f:
        for output in outputs:
            f.write(json.dumps(result) + '\n')
    
    # UPDATE CHECKPOINT
    with open(checkpoint_file, 'w') as f:
        f.write(str(batch_end))
```

**Benefits:**
- ✅ No data loss if process crashes
- ✅ Can resume from checkpoint
- ✅ See partial results while running
- ✅ Better progress tracking

---

## 🎨 Web Viewer Improvements

### 1. Candidate Name Extraction

**Before:** Showed random IDs like `02a9485f`, `6a324008`

**After:** Extracts real names from candidate data:
- `Natalie P (Software Engineer at Meta)`
- `Rushi G (Software Engineering Intern at Meta)`
- `Alli Buller (Software Engineer at Meta)`

**Implementation:**
```javascript
function extractCandidateName(candidate) {
    const userMsg = candidate.body?.messages?.find(m => m.role === 'user');
    // Look for **Candidate:** pattern
    const nameMatch = userMsg.content.match(/\*\*Candidate:\*\*\s*([^\n]+)/);
    if (nameMatch) {
        const name = nameMatch[1].trim();
        // Also get current role
        const roleMatch = userMsg.content.match(/\*\*Current Role:\*\*\s*([^\n]+)/);
        if (roleMatch) {
            return `${name} (${roleMatch[1].trim()})`;
        }
        return name;
    }
    return candidate.custom_id?.substring(0, 8) || 'Unknown';
}
```

### 2. Duplicate Dataset Removal

**Before:** Showed `batch_5k_optimized_results.jsonl` twice

**After:** Filtered out duplicate/obsolete datasets

**Implementation:**
```python
# In serve_results.py
result_files = glob.glob('*_results.jsonl') + glob.glob('benchmarks/raw/*.jsonl')
result_files = [f for f in result_files if 'batch_5k_optimized_results.jsonl' not in f]
```

### 3. Highlight Different Recommendations

**Before:** All responses looked the same

**After:** 
- ⚠️ **Red border** around cells when models disagree
- **"⚠️ DIFF"** badge on differing recommendations
- Easy to spot where models have different opinions

**Implementation:**
```javascript
// Detect if models disagree
const recommendations = modelNames.map(modelName => {
    const result = modelData[modelName][globalIdx];
    return result ? extractRecommendation(result) : null;
}).filter(r => r !== null);

const allSame = recommendations.every(r => r === recommendations[0]);
const hasDifferences = !allSame && recommendations.length > 1;

// Add visual indicator
const highlightStyle = hasDifferences ? 'border: 2px solid #f85149;' : '';
```

### 4. Filter to Show Only Differences

**New Feature:** Checkbox to show only candidates where models disagree

**Use Case:** Finding interesting cases for in-context learning examples

**Implementation:**
```javascript
function applyFilters() {
    if (showDiffsOnly) {
        filteredCandidates = allCandidates.filter((candidate, idx) => {
            const recommendations = modelNames.map(modelName => {
                const result = modelData[modelName][idx];
                return result ? extractRecommendation(result) : null;
            }).filter(r => r !== null);
            
            const allSame = recommendations.every(r => r === recommendations[0]);
            return !allSame && recommendations.length > 1;
        });
    } else {
        filteredCandidates = allCandidates;
    }
}
```

---

## 📊 Current Benchmark Status

### Completed (5K batch):
- ✅ **Gemma 3 4B**: 37 min, excellent quality
- ✅ **Llama 3.2 3B**: 13 min, good quality
- ✅ **Llama 3.2 1B**: 1.8 min, poor quality (not viable)

### Failed:
- ❌ **Qwen 3-4B**: Crashed at 777/5000 after 24 hours (no results saved)

### Next Steps:
1. **Retry Qwen 3-4B** using new incremental script
2. **Test OLMo 2 7B** (100 samples first)
3. **Test Gemma 3 12B QAT** (the big prize)

---

## 🎯 How to Use New Features

### Running Benchmarks Safely

**Old way (DANGEROUS):**
```bash
python test_qwen3_4b_5k.py  # Loses everything if crashes
```

**New way (SAFE):**
```bash
python test_qwen3_4b_5k_incremental.py  # Saves every 100 requests
```

**Resume after crash:**
```bash
# Just run the same command - it auto-resumes from checkpoint
python test_qwen3_4b_5k_incremental.py
```

### Viewing Results

1. **Start server:**
   ```bash
   python3 serve_results.py
   ```

2. **Open browser:** http://localhost:8001/

3. **Select dataset:** Click on `batch_5k.jsonl`

4. **View comparison table:**
   - See all candidates with real names
   - Compare model responses side-by-side
   - Red borders show where models disagree

5. **Filter for differences:**
   - Check "Show only different recommendations"
   - Perfect for finding good/bad examples for in-context learning

---

## 🔍 Finding Good Examples for In-Context Learning

### Strategy

1. **Filter for differences:** Enable "Show only different recommendations"

2. **Look for patterns:**
   - Where does Gemma 3 4B say "Strong Yes" but Llama says "Maybe"?
   - Where do all models agree on "Strong Yes"? (clear positive examples)
   - Where do all models agree on "No"? (clear negative examples)

3. **Extract examples:**
   - **Strong positives:** All models say "Strong Yes" → use as positive examples
   - **Strong negatives:** All models say "No" → use as negative examples
   - **Edge cases:** Models disagree → interesting for teaching nuance

4. **Build prompt library:**
   - Collect 5-10 strong positive examples
   - Collect 5-10 strong negative examples
   - Collect 2-3 edge cases with explanations

### Example Use Case

```
User: "Find me 10 candidates where all models agree on 'Strong Yes'"

1. Filter: Uncheck "Show only different recommendations"
2. Manually scan for rows where all 3 models show green "Strong Yes" badges
3. Extract those candidate profiles
4. Use as positive examples in future prompts
```

---

## 📝 Files Changed

### New Files:
- `test_qwen3_4b_5k_incremental.py` - Safe incremental benchmark script
- `IMPROVEMENTS.md` - This document

### Modified Files:
- `serve_results.py` - Filter out duplicate datasets
- `table_view.html` - Name extraction, difference highlighting, filtering

---

## 🚀 Next Actions

1. **Restart Qwen 3-4B benchmark** using incremental script
2. **Monitor progress** via web viewer GPU status widget
3. **Collect examples** for in-context learning using difference filter
4. **Test remaining models** (OLMo 2 7B, Gemma 3 12B QAT)

