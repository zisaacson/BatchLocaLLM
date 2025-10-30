# 💰 Production Cost Estimates (Parasail)

**Purpose:** Estimate Parasail API costs for production based on actual token usage patterns.

---

## 🎯 Key Findings

### **Current Token Usage Pattern (No In-Context Learning)**

**Average per request:**
- Prompt tokens: ~795
- Completion tokens: ~310
- Total: ~1,105 tokens
- **Input/Output ratio: 72% / 28%**

### **Cheapest Parasail Option: GPT-OSS 20B**
- Input: $0.04/MTok
- Output: $0.20/MTok
- **Best value for production!**

---

## 📊 Production Cost Projections

### **Scenario 1: Minimal Context (Current - No ICL)**

**Token usage:** ~1,105 tokens/request (795 in / 310 out)

| Volume | Total Tokens | GPT-OSS 20B | Qwen3-14B | Gemma3-27B | OLMo-2-32B |
|--------|--------------|-------------|-----------|------------|------------|
| **1K** | 1.1M | **$0.09** | $0.21 | $0.31 | $0.27 |
| **10K** | 11M | **$0.93** | $2.13 | $3.12 | $2.66 |
| **100K** | 110M | **$9.31** | $21.25 | $31.17 | $26.55 |
| **1M** | 1.1B | **$93.15** | $212.55 | $311.71 | $265.50 |

**💡 Recommendation:** Use **parasail-gpt-oss-20b** - 56-70% cheaper than alternatives!

---

### **Scenario 2: Medium Context (With 2-3 Examples)**

**Estimated token usage:** ~2,500 tokens/request (1,800 in / 700 out)

| Volume | Total Tokens | GPT-OSS 20B | Qwen3-14B | Gemma3-27B | OLMo-2-32B |
|--------|--------------|-------------|-----------|------------|------------|
| **1K** | 2.5M | **$0.21** | $0.48 | $0.71 | $0.61 |
| **10K** | 25M | **$2.12** | $4.82 | $7.06 | $6.05 |
| **100K** | 250M | **$21.12** | $48.15 | $70.60 | $60.45 |
| **1M** | 2.5B | **$211.20** | $481.50 | $706.00 | $604.50 |

**Impact:** 2.3x more tokens = 2.3x higher cost

---

### **Scenario 3: Large Context (Full ICL - 5+ Examples)**

**Estimated token usage:** ~5,000 tokens/request (3,600 in / 1,400 out)

| Volume | Total Tokens | GPT-OSS 20B | Qwen3-14B | Gemma3-27B | OLMo-2-32B |
|--------|--------------|-------------|-----------|------------|------------|
| **1K** | 5M | **$0.42** | $0.96 | $1.42 | $1.21 |
| **10K** | 50M | **$4.24** | $9.64 | $14.12 | $12.11 |
| **100K** | 500M | **$42.24** | $96.30 | $141.20 | $121.05 |
| **1M** | 5B | **$422.40** | $963.00 | $1,412.00 | $1,210.50 |

**Impact:** 4.5x more tokens = 4.5x higher cost

---

## 🎯 Monthly Cost Estimates

### **Example: 100K requests/month**

| Context Size | GPT-OSS 20B | Qwen3-14B | Gemma3-27B |
|--------------|-------------|-----------|------------|
| **Minimal** (current) | **$9.31/mo** | $21.25/mo | $31.17/mo |
| **Medium** (with examples) | **$21.12/mo** | $48.15/mo | $70.60/mo |
| **Large** (full ICL) | **$42.24/mo** | $96.30/mo | $141.20/mo |

### **Example: 1M requests/month**

| Context Size | GPT-OSS 20B | Qwen3-14B | Gemma3-27B |
|--------------|-------------|-----------|------------|
| **Minimal** (current) | **$93.15/mo** | $212.55/mo | $311.71/mo |
| **Medium** (with examples) | **$211.20/mo** | $481.50/mo | $706.00/mo |
| **Large** (full ICL) | **$422.40/mo** | $963.00/mo | $1,412.00/mo |

---

## 📈 Annual Cost Projections

### **100K requests/month = 1.2M requests/year**

| Context Size | GPT-OSS 20B | Qwen3-14B | Gemma3-27B |
|--------------|-------------|-----------|------------|
| **Minimal** | **$111.72/yr** | $255.00/yr | $374.04/yr |
| **Medium** | **$253.44/yr** | $577.80/yr | $847.20/yr |
| **Large** | **$506.88/yr** | $1,155.60/yr | $1,694.40/yr |

### **1M requests/month = 12M requests/year**

| Context Size | GPT-OSS 20B | Qwen3-14B | Gemma3-27B |
|--------------|-------------|-----------|------------|
| **Minimal** | **$1,117.80/yr** | $2,550.60/yr | $3,740.52/yr |
| **Medium** | **$2,534.40/yr** | $5,778.00/yr | $8,472.00/yr |
| **Large** | **$5,068.80/yr** | $11,556.00/yr | $16,944.00/yr |

---

## 🔍 Token Usage Breakdown

### **Current Pattern (Minimal Context)**

**Input tokens (72%):**
- Resume text: ~600 tokens
- Job description: ~100 tokens
- Instructions: ~95 tokens
- **Total: ~795 tokens**

**Output tokens (28%):**
- Evaluation: ~250 tokens
- Reasoning: ~60 tokens
- **Total: ~310 tokens**

### **With In-Context Learning (Medium Context)**

**Input tokens (72%):**
- Resume text: ~600 tokens
- Job description: ~200 tokens
- Instructions: ~100 tokens
- **Examples (2-3): ~900 tokens**
- **Total: ~1,800 tokens**

**Output tokens (28%):**
- Evaluation: ~500 tokens
- Reasoning: ~200 tokens
- **Total: ~700 tokens**

---

## 💡 Cost Optimization Strategies

### **1. Choose the Right Model**

**For production, use parasail-gpt-oss-20b:**
- ✅ **56-70% cheaper** than alternatives
- ✅ Good quality for candidate evaluation
- ✅ 20B parameters (comparable to Qwen 3 4B quality)

### **2. Optimize Context Size**

**Start minimal, add context only if needed:**
- Test with minimal context first
- Add examples only if quality improves significantly
- Monitor quality vs cost tradeoff

### **3. Batch Processing**

**Use batch API if available:**
- Often 50% cheaper than real-time
- Acceptable for non-urgent evaluations
- Can process overnight

### **4. Smart Caching**

**Cache common patterns:**
- Job descriptions (reused across candidates)
- Example evaluations (reused for similar roles)
- Reduces input tokens by 20-30%

---

## 📊 Cost Comparison by Model

### **Why GPT-OSS 20B is Cheapest:**

| Model | Input $/MTok | Output $/MTok | Total (1K req) | Savings vs GPT-OSS |
|-------|--------------|---------------|----------------|---------------------|
| **GPT-OSS 20B** | $0.04 | $0.20 | **$0.09** | Baseline |
| Qwen3-14B | $0.15 | $0.30 | $0.21 | **-57%** |
| Gemma3-27B | $0.20 | $0.50 | $0.31 | **-71%** |
| OLMo-2-32B | $0.20 | $0.35 | $0.27 | **-67%** |

**Key insight:** GPT-OSS 20B has **5x cheaper input** and **1.5x cheaper output**!

---

## 🎯 Recommendations for Parasail Production

### **Phase 1: Validate with Minimal Context**
1. ✅ Use current token pattern (~1,105 tokens/request)
2. ✅ Test with parasail-gpt-oss-20b
3. ✅ Measure quality vs local models
4. ✅ Estimate: **$9.31 per 100K requests**

### **Phase 2: Test with In-Context Learning**
1. ⏳ Add 2-3 examples to prompts
2. ⏳ Measure quality improvement
3. ⏳ Calculate cost increase (2.3x)
4. ⏳ Estimate: **$21.12 per 100K requests**

### **Phase 3: Optimize for Production**
1. ⏳ Find optimal context size
2. ⏳ Implement caching strategies
3. ⏳ Use batch API if available
4. ⏳ Monitor quality vs cost

---

## 📋 Next Steps

### **To Get Accurate Production Estimates:**

1. **Measure actual usage patterns**
   - How many requests per month?
   - What context size is needed?
   - What quality threshold is acceptable?

2. **Test with real Aris data**
   - Use actual resumes and job descriptions
   - Test with parasail-gpt-oss-20b
   - Measure quality vs cost

3. **Create cost model**
   - Input: monthly volume
   - Input: context size
   - Output: monthly cost estimate

4. **Make production decision**
   - Compare to alternatives (OpenAI, Anthropic)
   - Factor in quality requirements
   - Consider hybrid approach

---

## 🔧 Tools

### **Calculate Custom Estimates**
```bash
python cost_analysis.py
```

### **Project Costs for Your Volume**
```python
from cost_analysis import calculate_parasail_cost

# Your monthly volume
monthly_requests = 100_000
avg_prompt_tokens = 795
avg_completion_tokens = 310

# Calculate
total_prompt = monthly_requests * avg_prompt_tokens
total_completion = monthly_requests * avg_completion_tokens

cost = calculate_parasail_cost(
    total_prompt, 
    total_completion, 
    "parasail-gpt-oss-20b"
)

print(f"Monthly cost: ${cost['total_cost']:.2f}")
```

---

## 💰 Bottom Line

**For production on Parasail:**

- **Use parasail-gpt-oss-20b** - cheapest option
- **Current pattern: $9.31 per 100K requests**
- **With ICL: $21-42 per 100K requests** (depending on context)
- **1M requests/month: $93-422/month** (depending on context)

**Next:** Test with real Aris data to validate quality and refine estimates!

