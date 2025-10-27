# 🧪 Testing Roadmap

**Date**: 2025-10-27  
**Branch**: `ollama`  
**Goal**: Validate system for 170K production run

---

## 📋 Testing Checklist

### Phase 1: Context Limits ⏳ IN PROGRESS

**Purpose**: Find actual VRAM limits for Gemma 3 12B

**Test**: `test_context_limits.py`

**What we're testing**:
- [ ] Base model VRAM usage (no context)
- [ ] KV cache growth rate (VRAM per token)
- [ ] Maximum context before OOM
- [ ] Safe context threshold (80% of max)
- [ ] Optimal trim interval

**Expected results**:
```
Base model VRAM: ~8GB
KV cache growth: ~0.5MB/token (estimated)
Max safe context: ~14K tokens (estimated)
Recommended trim threshold: ~12K tokens
```

**How to run**:
```bash
# Make sure Ollama is running
ollama serve

# Run context limit tests (30-60 minutes)
python test_context_limits.py

# Review results
cat context_limit_results.json
```

**Success criteria**:
- ✅ Find maximum context without OOM
- ✅ Measure VRAM growth rate
- ✅ Generate safe limit recommendations
- ✅ No crashes or hangs

**Risks**:
- ⚠️ May cause OOM (expected - that's what we're testing!)
- ⚠️ May take 30-60 minutes
- ⚠️ May need to restart Ollama after OOM

---

### Phase 2: Small Scale (100 requests) ⏳ TODO

**Purpose**: Validate basic optimization works

**Test**: `test_performance_benchmarks.py` (100 requests)

**What we're testing**:
- [ ] Conversation batching works
- [ ] Token savings match predictions (>90%)
- [ ] Throughput is consistent (~6.67 req/s)
- [ ] VRAM stays within safe limits
- [ ] No errors or crashes

**Expected results**:
```
Requests: 100
Time: ~15 seconds
Throughput: 6.67 req/s
Token savings: >90%
VRAM: <12 GB
Errors: 0
```

**How to run**:
```bash
# Start server (in another terminal)
python -m uvicorn src.main:app --host 0.0.0.0 --port 4080

# Run benchmark (15 seconds)
python test_performance_benchmarks.py --size 100

# Review results
cat performance_benchmarks_100.json
```

**Success criteria**:
- ✅ All 100 requests complete successfully
- ✅ Token savings >90%
- ✅ Throughput 6-7 req/s
- ✅ VRAM <12 GB
- ✅ No errors

---

### Phase 3: Medium Scale (1,000 requests) ⏳ TODO

**Purpose**: Validate context trimming works

**Test**: `test_performance_benchmarks.py` (1,000 requests)

**What we're testing**:
- [ ] Context trimming prevents OOM
- [ ] Performance stays consistent
- [ ] Token savings stay high (>95%)
- [ ] VRAM stays within safe limits
- [ ] No memory leaks

**Expected results**:
```
Requests: 1,000
Time: ~2.5 minutes
Throughput: 6.67 req/s
Token savings: >95%
Context trims: ~20 (every 50 requests)
VRAM: <12 GB
Errors: 0
```

**How to run**:
```bash
# Run benchmark (2.5 minutes)
python test_performance_benchmarks.py --size 1000

# Review results
cat performance_benchmarks_1000.json
```

**Success criteria**:
- ✅ All 1,000 requests complete successfully
- ✅ Token savings >95%
- ✅ Throughput consistent (6-7 req/s)
- ✅ Context trimming works (no OOM)
- ✅ VRAM <12 GB
- ✅ No errors

---

### Phase 4: Large Scale (10,000 requests) ⏳ TODO

**Purpose**: Validate long-running stability

**Test**: `test_performance_benchmarks.py` (10,000 requests)

**What we're testing**:
- [ ] System stable over 25+ minutes
- [ ] No memory leaks
- [ ] Performance doesn't degrade
- [ ] Token savings stay high (>97%)
- [ ] VRAM stays within safe limits
- [ ] Error rate stays low (<0.1%)

**Expected results**:
```
Requests: 10,000
Time: ~25 minutes
Throughput: 6.67 req/s
Token savings: >97%
Context trims: ~200
VRAM: <12 GB
Errors: <10 (0.1%)
```

**How to run**:
```bash
# Run benchmark (25 minutes)
python test_performance_benchmarks.py --size 10000

# Review results
cat performance_benchmarks_10000.json
```

**Success criteria**:
- ✅ All 10,000 requests complete successfully
- ✅ Token savings >97%
- ✅ Throughput consistent (6-7 req/s)
- ✅ No performance degradation
- ✅ VRAM <12 GB
- ✅ Error rate <0.1%
- ✅ No memory leaks

---

### Phase 5: Configuration Update ⏳ TODO

**Purpose**: Update config with measured values

**What we're updating**:
- [ ] MAX_CONTEXT_TOKENS (from context limit tests)
- [ ] CONTEXT_TRIM_THRESHOLD (80% of max)
- [ ] TRIM_INTERVAL (from performance tests)
- [ ] MODEL_VRAM_GB (from context limit tests)
- [ ] KV_CACHE_PER_TOKEN_MB (from context limit tests)

**How to update**:
```python
# src/batch_processor.py

# OLD (guessed values)
MAX_CONTEXT_TOKENS = 32000
CONTEXT_TRIM_THRESHOLD = 28000
TRIM_INTERVAL = 50

# NEW (data-driven values from tests)
MAX_CONTEXT_TOKENS = 14000  # From context limit tests
CONTEXT_TRIM_THRESHOLD = 12000  # 85% of max
TRIM_INTERVAL = 75  # From performance tests
```

**Success criteria**:
- ✅ All values updated with measured data
- ✅ Documentation updated
- ✅ Assumptions documented
- ✅ Committed to git

---

### Phase 6: Validation Run (50,000 requests) ⏳ TODO

**Purpose**: Validate at near-production scale

**Test**: Manual test with 50K requests

**What we're testing**:
- [ ] System handles 50K requests (2+ hours)
- [ ] Extrapolation to 170K is accurate
- [ ] No issues at large scale
- [ ] Progress logging works correctly
- [ ] ETA calculations are accurate

**Expected results**:
```
Requests: 50,000
Time: ~2.1 hours
Throughput: 6.67 req/s
Token savings: 97.6%
VRAM: <12 GB
Errors: <50 (0.1%)
```

**How to run**:
```bash
# Create 50K sample
python tools/csv_to_batch.py --sample 50000

# Run batch
python tools/run_batch.py sample_candidates.csv
```

**Success criteria**:
- ✅ All 50,000 requests complete successfully
- ✅ Token savings 97.6%
- ✅ Throughput consistent
- ✅ No crashes or hangs
- ✅ Progress logging works
- ✅ ETA accurate

---

### Phase 7: Production Run (170,000 requests) ⏳ TODO

**Purpose**: Full production run

**Test**: Actual 170K candidate evaluation

**What we're testing**:
- [ ] System handles 170K requests (7+ hours)
- [ ] All metrics match predictions
- [ ] No issues at full scale
- [ ] Results are high quality

**Expected results**:
```
Requests: 170,000
Time: ~7.1 hours
Throughput: 6.67 req/s
Token savings: 97.6%
Total tokens: 17M
Cost: ~$50 electricity
VRAM: <12 GB
Errors: <170 (0.1%)
```

**How to run**:
```bash
# Convert your CSV
python tools/csv_to_batch.py candidates_170k.csv batch.jsonl

# Run batch
python tools/run_batch.py candidates_170k.csv

# Results saved to: candidates_170k_scores.csv
```

**Success criteria**:
- ✅ All 170,000 requests complete successfully
- ✅ Token savings 97.6%
- ✅ Time <8 hours
- ✅ Cost <$100
- ✅ Error rate <0.1%
- ✅ Results are high quality

---

## 📊 Testing Progress

### Completed ✅

- [x] Basic functionality (20 requests)
- [x] OpenAI API compatibility
- [x] Conversation batching
- [x] Metrics tracking
- [x] Context trimming
- [x] Progress logging
- [x] End-to-end tools
- [x] Documentation

### In Progress ⏳

- [ ] Context limit testing
- [ ] Performance benchmarks (100, 1K, 10K)
- [ ] Configuration tuning

### Blocked 🚫

- [ ] Validation run (50K) - blocked on benchmarks
- [ ] Production run (170K) - blocked on validation

---

## 🎯 Success Metrics

### Performance

| Metric | Target | Status |
|--------|--------|--------|
| Throughput | >6 req/s | ⏳ Testing |
| Time (170K) | <8 hours | ⏳ Testing |
| Token savings | >97% | ⏳ Testing |
| Error rate | <0.1% | ⏳ Testing |

### Reliability

| Metric | Target | Status |
|--------|--------|--------|
| No OOM crashes | 100% | ⏳ Testing |
| No memory leaks | 100% | ⏳ Testing |
| VRAM <14GB | 100% | ⏳ Testing |
| Uptime | >99% | ⏳ Testing |

### Quality

| Metric | Target | Status |
|--------|--------|--------|
| Consistent scoring | 100% | ✅ Pass |
| Reproducible | 100% | ✅ Pass |
| No bias/drift | 100% | ⏳ Testing |

---

## 🚀 Execution Plan

### Today (2025-10-27)

**Morning** (2-3 hours):
1. ✅ Run `test_context_limits.py` (30-60 min)
2. ✅ Review context limit results
3. ✅ Run `test_performance_benchmarks.py` --size 100 (15 sec)
4. ✅ Run `test_performance_benchmarks.py` --size 1000 (2.5 min)

**Afternoon** (2-3 hours):
5. ✅ Run `test_performance_benchmarks.py` --size 10000 (25 min)
6. ✅ Review all benchmark results
7. ✅ Update configuration with measured values
8. ✅ Commit all changes

**Evening** (optional):
9. ⏳ Run validation test (50K requests, 2 hours)

### Tomorrow (2025-10-28)

**If validation passes**:
10. ✅ Production run (170K requests, 7 hours)
11. ✅ Analyze results
12. ✅ Document final metrics
13. ✅ Celebrate! 🎉

---

## 🐛 Troubleshooting

### Context Limit Tests

**Problem**: OOM during testing  
**Solution**: Expected! Restart Ollama and continue

**Problem**: Tests hang  
**Solution**: Ctrl+C, check `nvidia-smi`, kill zombie processes

**Problem**: VRAM not measured  
**Solution**: Install `nvidia-smi` or check manually

### Performance Benchmarks

**Problem**: Throughput lower than expected  
**Solution**: Check CPU/GPU usage, kill other processes

**Problem**: Token savings lower than expected  
**Solution**: Check if requests have identical system prompts

**Problem**: Errors during processing  
**Solution**: Check logs, verify Ollama is running

---

## 📈 Expected Timeline

```
Day 1 (Today):
├── Context limit tests (1 hour)
├── Benchmark 100 requests (1 min)
├── Benchmark 1K requests (3 min)
├── Benchmark 10K requests (30 min)
├── Update configuration (30 min)
└── Validation 50K requests (2 hours) [optional]

Day 2 (Tomorrow):
└── Production 170K requests (7 hours)

Total: 1-2 days
```

---

## ✅ Definition of Done

### For Each Test Phase

- [ ] Test completes successfully
- [ ] Results documented
- [ ] Metrics within expected ranges
- [ ] No critical issues found
- [ ] Learnings documented

### For Overall Testing

- [ ] All test phases complete
- [ ] Configuration updated with measured values
- [ ] Documentation updated
- [ ] All changes committed
- [ ] Ready for production

### For Production Run

- [ ] 170K requests processed successfully
- [ ] Results analyzed and exported
- [ ] Final metrics documented
- [ ] User story complete
- [ ] System validated

---

**Status**: Testing roadmap defined  
**Next**: Run context limit tests  
**Goal**: Production-ready in 1-2 days

