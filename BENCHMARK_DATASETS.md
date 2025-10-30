# 📊 Benchmark Datasets & Test Scenarios

**Purpose:** Track different test scenarios with varying context window requirements.

---

## 🎯 Dataset Categories

### **1. Minimal Context (Current Baseline)**
- **Prompt size:** ~800 tokens
- **Completion size:** ~300 tokens
- **Total:** ~1,100 tokens/request
- **Use case:** Simple candidate evaluation, no examples
- **Status:** ✅ **TESTED**

**Files:**
- `batch_10_test.jsonl` - 10 requests
- `batch_5k.jsonl` - 5,000 requests

**Results:**
- Gemma 3 4B: 2,511 tok/s, $0.05 for 5K
- Qwen 3 4B: 1,533 tok/s, $0.0002 for 10

---

### **2. Medium Context (With Examples)**
- **Prompt size:** ~2,000 tokens
- **Completion size:** ~500 tokens
- **Total:** ~2,500 tokens/request
- **Use case:** Candidate evaluation with 2-3 examples
- **Status:** ⏳ **TO CREATE**

**Planned files:**
- `batch_medium_context_10.jsonl` - 10 requests
- `batch_medium_context_1k.jsonl` - 1,000 requests
- `batch_medium_context_5k.jsonl` - 5,000 requests

**Expected impact:**
- 2.3x more tokens than minimal
- Self-hosted: Same time, same cost
- Parasail: 2.3x higher cost
- **Self-hosted advantage increases to 95%**

---

### **3. Large Context (Full ICL)**
- **Prompt size:** ~4,000 tokens
- **Completion size:** ~1,000 tokens
- **Total:** ~5,000 tokens/request
- **Use case:** Comprehensive evaluation with 5+ examples
- **Status:** ⏳ **TO CREATE**

**Planned files:**
- `batch_large_context_10.jsonl` - 10 requests
- `batch_large_context_1k.jsonl` - 1,000 requests
- `batch_large_context_5k.jsonl` - 5,000 requests

**Expected impact:**
- 4.5x more tokens than minimal
- Self-hosted: Same time, same cost
- Parasail: 4.5x higher cost
- **Self-hosted advantage increases to 97%**

---

### **4. Variable Context (Mixed)**
- **Prompt size:** 500-4,000 tokens (varied)
- **Completion size:** 200-1,000 tokens (varied)
- **Total:** Variable
- **Use case:** Realistic production mix
- **Status:** ⏳ **TO CREATE**

**Planned files:**
- `batch_variable_context_1k.jsonl` - 1,000 requests

**Purpose:**
- Test real-world variability
- Measure average vs peak performance
- Validate cost estimates

---

## 📁 Dataset Structure

```
benchmarks/
├── datasets/
│   ├── minimal_context/
│   │   ├── batch_10.jsonl
│   │   ├── batch_1k.jsonl
│   │   └── batch_5k.jsonl
│   ├── medium_context/
│   │   ├── batch_10.jsonl
│   │   ├── batch_1k.jsonl
│   │   └── batch_5k.jsonl
│   ├── large_context/
│   │   ├── batch_10.jsonl
│   │   ├── batch_1k.jsonl
│   │   └── batch_5k.jsonl
│   └── variable_context/
│       └── batch_1k.jsonl
├── metadata/
│   └── [benchmark results]
└── reports/
    └── [analysis reports]
```

---

## 🧪 Test Matrix

| Dataset | Size | Gemma 3 4B | Qwen 3 4B | Llama 3.2 1B | Llama 3.2 3B |
|---------|------|------------|-----------|--------------|--------------|
| **Minimal - 10** | 10 | ✅ Tested | ✅ Tested | ⏳ To test | ⏳ To test |
| **Minimal - 5K** | 5,000 | ✅ Tested | ⏳ To test | ⏳ To test | ⏳ To test |
| **Medium - 10** | 10 | ⏳ To test | ⏳ To test | ⏳ To test | ⏳ To test |
| **Medium - 1K** | 1,000 | ⏳ To test | ⏳ To test | ⏳ To test | ⏳ To test |
| **Large - 10** | 10 | ⏳ To test | ⏳ To test | ⏳ To test | ⏳ To test |
| **Large - 1K** | 1,000 | ⏳ To test | ⏳ To test | ⏳ To test | ⏳ To test |
| **Variable - 1K** | 1,000 | ⏳ To test | ⏳ To test | ⏳ To test | ⏳ To test |

---

## 📊 Cost Comparison by Dataset

### **Minimal Context (Current)**

| Batch Size | Self-Hosted | Parasail GPT-OSS | Savings |
|------------|-------------|------------------|---------|
| 10 | $0.0002 | $0.0009 | 78% |
| 5,000 | $0.05 | $0.47 | 89% |
| 50,000 | $0.51 | $4.66 | 89% |

### **Medium Context (Estimated)**

| Batch Size | Self-Hosted | Parasail GPT-OSS | Savings |
|------------|-------------|------------------|---------|
| 10 | $0.0002 | $0.0021 | 90% |
| 5,000 | $0.05 | $1.08 | **95%** |
| 50,000 | $0.51 | $10.75 | **95%** |

### **Large Context (Estimated)**

| Batch Size | Self-Hosted | Parasail GPT-OSS | Savings |
|------------|-------------|------------------|---------|
| 10 | $0.0002 | $0.0041 | 95% |
| 5,000 | $0.05 | $2.12 | **98%** |
| 50,000 | $0.51 | $21.15 | **98%** |

---

## 🎯 Testing Roadmap

### **Phase 1: Validate Minimal Context** ✅ IN PROGRESS
1. [x] Gemma 3 4B - 10 requests
2. [x] Gemma 3 4B - 5K requests
3. [x] Qwen 3 4B - 10 requests
4. [ ] Qwen 3 4B - 5K requests
5. [ ] Llama 3.2 1B - 10 requests
6. [ ] Llama 3.2 3B - 10 requests

### **Phase 2: Create Medium Context Datasets**
1. [ ] Generate medium context prompts (2K tokens)
2. [ ] Create 10-request test set
3. [ ] Create 1K-request test set
4. [ ] Test with Gemma 3 4B
5. [ ] Compare costs vs minimal

### **Phase 3: Create Large Context Datasets**
1. [ ] Generate large context prompts (4K tokens)
2. [ ] Create 10-request test set
3. [ ] Create 1K-request test set
4. [ ] Test with Gemma 3 4B
5. [ ] Compare costs vs minimal/medium

### **Phase 4: Variable Context Testing**
1. [ ] Create mixed dataset (500-4K tokens)
2. [ ] Test with multiple models
3. [ ] Analyze performance variability
4. [ ] Validate production estimates

---

## 📝 Dataset Creation Guidelines

### **Minimal Context Template:**
```json
{
  "custom_id": "candidate-001",
  "body": {
    "messages": [
      {
        "role": "user",
        "content": "Evaluate this candidate:\n\nResume: [800 tokens]\n\nProvide a brief assessment."
      }
    ]
  }
}
```

### **Medium Context Template:**
```json
{
  "custom_id": "candidate-001",
  "body": {
    "messages": [
      {
        "role": "user",
        "content": "Evaluate this candidate:\n\nResume: [800 tokens]\n\nJob Description: [400 tokens]\n\nExample Evaluations:\n1. [300 tokens]\n2. [300 tokens]\n3. [200 tokens]\n\nProvide a detailed assessment."
      }
    ]
  }
}
```

### **Large Context Template:**
```json
{
  "custom_id": "candidate-001",
  "body": {
    "messages": [
      {
        "role": "user",
        "content": "Evaluate this candidate:\n\nResume: [800 tokens]\n\nJob Description: [600 tokens]\n\nCompany Context: [400 tokens]\n\nExample Evaluations:\n1. [400 tokens]\n2. [400 tokens]\n3. [400 tokens]\n4. [400 tokens]\n5. [400 tokens]\n\nProvide a comprehensive assessment."
      }
    ]
  }
}
```

---

## 🔧 Tools for Dataset Creation

### **1. Generate Medium Context Dataset**
```bash
python scripts/generate_dataset.py \
  --context-size medium \
  --num-requests 1000 \
  --output benchmarks/datasets/medium_context/batch_1k.jsonl
```

### **2. Generate Large Context Dataset**
```bash
python scripts/generate_dataset.py \
  --context-size large \
  --num-requests 1000 \
  --output benchmarks/datasets/large_context/batch_1k.jsonl
```

### **3. Analyze Token Distribution**
```bash
python scripts/analyze_tokens.py \
  --input benchmarks/datasets/medium_context/batch_1k.jsonl
```

---

## 📊 Metrics to Track

For each dataset and model combination:

1. **Performance:**
   - Throughput (tokens/sec)
   - Requests/sec
   - Total time

2. **Token Usage:**
   - Avg prompt tokens
   - Avg completion tokens
   - Total tokens
   - Input/output ratio

3. **Costs:**
   - Self-hosted cost
   - Parasail comparison costs
   - Savings percentage

4. **Quality:**
   - Success rate
   - Error types
   - Output quality (manual review)

---

## 🎯 Success Criteria

**For production readiness:**

1. ✅ Test all context sizes (minimal, medium, large)
2. ✅ Test with 3+ models
3. ✅ Validate cost estimates
4. ✅ Measure quality across contexts
5. ✅ Document recommendations

**Target:** Complete testing by end of week!

