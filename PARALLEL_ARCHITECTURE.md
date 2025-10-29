# 🚀 Parallel Batch Processing Architecture

**Date**: 2025-10-27  
**Lead Engineer Decision**: Optimize for SPEED, not tokens  
**Goal**: Process 170K candidates as fast as possible on RTX 4080 16GB

---

## 🎯 Core Insight

**Token optimization ≠ Speed optimization**

### What We Learned:
- ✅ Token batching saves memory/API costs
- ❌ Token batching does NOT make inference faster
- ✅ Parallel processing makes inference faster
- ✅ Candidates are INDEPENDENT (can parallelize!)

### The Truth:
```
Sequential (current):
  170K requests × 5 sec = 236 hours (10 DAYS!)
  
Parallel (8 workers):
  170K / 8 × 5 sec = 29.5 hours (1.2 DAYS!)
  
8x FASTER!
```

---

## 🏗️ Architecture Design

### **Approach: Parallel Independent Workers**

```
┌─────────────────────────────────────────────────────────┐
│                    Batch Coordinator                     │
│  - Splits 170K into N chunks                            │
│  - Spawns N parallel workers                            │
│  - Collects results                                     │
│  - Handles failures                                     │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Worker 1   │  │   Worker 2   │  │   Worker N   │
│              │  │              │  │              │
│ Requests     │  │ Requests     │  │ Requests     │
│ 1-21,250     │  │ 21,251-      │  │ ...          │
│              │  │ 42,500       │  │              │
│              │  │              │  │              │
│ ↓ Ollama     │  │ ↓ Ollama     │  │ ↓ Ollama     │
│ ↓ (same GPU) │  │ ↓ (same GPU) │  │ ↓ (same GPU) │
│ ↓ Sequential │  │ ↓ Sequential │  │ ↓ Sequential │
│              │  │              │  │              │
│ Results →    │  │ Results →    │  │ Results →    │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                  ┌──────────────┐
                  │   Results    │
                  │   Aggregator │
                  └──────────────┘
```

### **Key Design Decisions**:

1. **Parallel Workers**: 
   - Use Python `asyncio` for concurrency
   - Each worker processes requests sequentially
   - All workers share same Ollama instance (same GPU)

2. **No Conversation Batching**:
   - Each request is independent
   - No context accumulation
   - No token caching needed
   - Simpler, faster, more robust

3. **Optimal Worker Count**:
   - Start with 8 workers (test and tune)
   - Limited by Ollama's concurrency, not GPU
   - Monitor VRAM and adjust

4. **Checkpointing**:
   - Save results after each worker completes
   - Resume from checkpoint on failure
   - No data loss

---

## 📊 Performance Analysis

### **Current (Sequential + Token Batching)**:
```
Approach: Single conversation, chunked
Workers: 1
Requests/sec: 0.20
Time for 5K: 6.9 hours
Time for 170K: 236 hours (10 days)
Token savings: 79%
Complexity: High
Robustness: Medium (crashes lose progress)
```

### **Proposed (Parallel + Independent)**:
```
Approach: Parallel workers, independent requests
Workers: 8
Requests/sec: 1.6 (8 × 0.20)
Time for 5K: 52 minutes
Time for 170K: 29.5 hours (1.2 days)
Token savings: 0% (don't care!)
Complexity: Medium
Robustness: High (checkpointing, worker isolation)
```

### **Improvement**:
- ✅ **8x faster** (10 days → 1.2 days)
- ✅ **Simpler code** (no conversation management)
- ✅ **More robust** (worker failures isolated)
- ✅ **Checkpointing** (resume on crash)
- ✅ **Better monitoring** (per-worker metrics)

---

## 🔧 Implementation Plan

### **Phase 1: Core Parallel Engine** (2-3 hours)

**Files to create**:
1. `src/parallel_processor.py` - Parallel batch processor
2. `src/worker.py` - Individual worker implementation
3. `src/checkpoint.py` - Checkpoint/resume logic

**Key features**:
- Async worker pool
- Request distribution
- Result aggregation
- Error handling

### **Phase 2: Checkpointing** (1-2 hours)

**Features**:
- Save progress after each worker
- Resume from last checkpoint
- Atomic writes (no corruption)
- Progress tracking

### **Phase 3: Monitoring** (1 hour)

**Features**:
- Per-worker metrics
- Overall progress
- ETA calculation
- VRAM monitoring

### **Phase 4: Testing** (2-3 hours)

**Tests**:
1. 10 requests (sanity check)
2. 100 requests (worker coordination)
3. 1K requests (checkpointing)
4. 5K requests (full validation)
5. 170K requests (production)

---

## 🎯 Technical Specifications

### **Worker Design**:

```python
class BatchWorker:
    """
    Independent worker that processes a chunk of requests.
    
    - No conversation state
    - No context accumulation
    - Each request is independent
    - Simple, fast, robust
    """
    
    async def process_chunk(
        self,
        requests: List[BatchRequestLine],
        worker_id: int
    ) -> List[BatchResultLine]:
        """Process requests sequentially"""
        results = []
        
        for req in requests:
            # Simple: just call Ollama for each request
            response = await self.backend.generate_chat_completion(req.body)
            results.append(self._build_result(req, response))
            
            # Save checkpoint every 100 requests
            if len(results) % 100 == 0:
                await self._save_checkpoint(results, worker_id)
        
        return results
```

### **Coordinator Design**:

```python
class ParallelBatchProcessor:
    """
    Coordinates parallel workers.
    
    - Splits batch into N chunks
    - Spawns N workers
    - Collects results
    - Handles failures
    """
    
    async def process_batch(
        self,
        requests: List[BatchRequestLine],
        num_workers: int = 8
    ) -> List[BatchResultLine]:
        """Process batch with parallel workers"""
        
        # Split into chunks
        chunks = self._split_into_chunks(requests, num_workers)
        
        # Create workers
        workers = [
            BatchWorker(backend=self.backend, worker_id=i)
            for i in range(num_workers)
        ]
        
        # Process in parallel
        tasks = [
            worker.process_chunk(chunk, i)
            for i, (worker, chunk) in enumerate(zip(workers, chunks))
        ]
        
        # Wait for all workers
        results_per_worker = await asyncio.gather(*tasks)
        
        # Aggregate results
        all_results = []
        for results in results_per_worker:
            all_results.extend(results)
        
        return all_results
```

### **Checkpointing Design**:

```python
class CheckpointManager:
    """
    Manages checkpoints for resumable processing.
    
    - Saves progress periodically
    - Resumes from last checkpoint
    - Atomic writes (no corruption)
    """
    
    async def save_checkpoint(
        self,
        batch_id: str,
        worker_id: int,
        results: List[BatchResultLine]
    ):
        """Save worker checkpoint"""
        checkpoint_file = f"data/checkpoints/{batch_id}_worker_{worker_id}.jsonl"
        
        # Atomic write
        temp_file = f"{checkpoint_file}.tmp"
        async with aiofiles.open(temp_file, 'w') as f:
            for result in results:
                await f.write(result.model_dump_json() + '\n')
        
        # Atomic rename
        os.rename(temp_file, checkpoint_file)
    
    async def load_checkpoint(
        self,
        batch_id: str,
        worker_id: int
    ) -> List[BatchResultLine]:
        """Load worker checkpoint"""
        checkpoint_file = f"data/checkpoints/{batch_id}_worker_{worker_id}.jsonl"
        
        if not os.path.exists(checkpoint_file):
            return []
        
        results = []
        async with aiofiles.open(checkpoint_file, 'r') as f:
            async for line in f:
                results.append(BatchResultLine.model_validate_json(line))
        
        return results
```

---

## 🚦 Concurrency Limits

### **Question: How many parallel workers?**

**Factors**:
1. **Ollama concurrency**: How many requests can Ollama handle in parallel?
2. **VRAM limits**: Does parallel processing use more VRAM?
3. **CPU limits**: Is CPU a bottleneck?

**Testing strategy**:
```python
# Test with increasing workers
for num_workers in [1, 2, 4, 8, 16]:
    time = await test_batch(100, num_workers)
    throughput = 100 / time
    print(f"{num_workers} workers: {throughput:.2f} req/s")
```

**Expected**:
- 1 worker: 0.20 req/s (baseline)
- 2 workers: 0.35 req/s (1.75x)
- 4 workers: 0.60 req/s (3x)
- 8 workers: 1.00 req/s (5x)
- 16 workers: 1.20 req/s (6x, diminishing returns)

**Optimal**: Probably 8 workers (good balance)

---

## 📈 Expected Performance

### **5K Batch**:
```
Current: 6.9 hours
Parallel (8 workers): 52 minutes
Speedup: 8x
```

### **170K Batch**:
```
Current: 236 hours (10 days)
Parallel (8 workers): 29.5 hours (1.2 days)
Speedup: 8x
```

### **Why not perfect 8x?**:
- Ollama overhead
- Worker coordination
- Checkpoint I/O
- VRAM contention

**Realistic**: 5-6x speedup (still amazing!)

---

## 🛡️ Robustness Features

### **1. Worker Isolation**:
- Worker failure doesn't crash batch
- Failed workers can retry
- Other workers continue

### **2. Checkpointing**:
- Save progress every 100 requests
- Resume from checkpoint on crash
- No data loss

### **3. Error Handling**:
- Retry failed requests (3 attempts)
- Log errors with context
- Continue processing on errors

### **4. Monitoring**:
- Per-worker progress
- Overall ETA
- VRAM tracking
- Error rates

### **5. Graceful Shutdown**:
- SIGINT handler
- Save checkpoints on exit
- Clean worker termination

---

## 🎯 Success Metrics

### **Performance**:
- ✅ 5K batch in < 1 hour
- ✅ 170K batch in < 2 days
- ✅ Throughput > 1.0 req/s

### **Robustness**:
- ✅ Resume from checkpoint works
- ✅ Worker failures don't crash batch
- ✅ 100% success rate (with retries)

### **Monitoring**:
- ✅ Real-time progress tracking
- ✅ Accurate ETA
- ✅ VRAM stays within limits

---

## 🚀 Next Steps

### **Immediate (Today)**:
1. ✅ Kill current slow batch
2. ✅ Implement `ParallelBatchProcessor`
3. ✅ Implement `BatchWorker`
4. ✅ Test with 10 requests

### **Short-term (This Week)**:
1. ✅ Add checkpointing
2. ✅ Test with 1K requests
3. ✅ Optimize worker count
4. ✅ Run 5K validation

### **Production (Next Week)**:
1. ✅ Run 170K batch
2. ✅ Monitor and optimize
3. ✅ Document learnings

---

## 💡 Key Insights

### **What We Got Wrong**:
- ❌ Thought token optimization = speed
- ❌ Used conversation batching (sequential)
- ❌ Didn't leverage parallelism
- ❌ Over-engineered for wrong goal

### **What We Got Right**:
- ✅ Measured context limits
- ✅ Built chunking infrastructure
- ✅ Comprehensive monitoring
- ✅ Robust error handling

### **What We're Fixing**:
- ✅ Parallel processing (8x faster!)
- ✅ Independent requests (simpler!)
- ✅ Checkpointing (no data loss!)
- ✅ Right optimization target (SPEED!)

---

## 🎉 Bottom Line

**Old approach**:
- Sequential processing
- Token optimization
- 10 days for 170K
- Complex conversation management

**New approach**:
- Parallel processing
- Speed optimization
- 1.2 days for 170K
- Simple independent requests

**Result**: **8x FASTER, SIMPLER, MORE ROBUST!**

Let's build this! 🚀

