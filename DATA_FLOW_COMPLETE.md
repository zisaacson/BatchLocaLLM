# Complete Data Flow - 170K Candidates

**Date:** 2025-10-29  
**Question:** How does data flow when Aris sends 170K candidates but batch server has 50K limit?

---

## 🎯 **The Two Chunking Layers**

There are **TWO different chunking strategies** at play:

### **Layer 1: API-Level Chunking (50K limit)**
- **Who:** Aris web app
- **Why:** Batch server has 50K requests/batch limit
- **Solution:** Aris splits 170K into multiple batch jobs

### **Layer 2: Memory-Level Chunking (5K chunks)**
- **Who:** Batch server worker
- **Why:** RTX 4080 16GB can't load 50K prompts into memory at once
- **Solution:** Worker processes 50K job in 5K chunks internally

---

## 📊 **Complete Data Flow: 170K Candidates**

### **Scenario:** Aris wants to evaluate 170K candidates

```
┌─────────────────────────────────────────────────────────────┐
│                    ARIS WEB APP                             │
│                                                             │
│  User clicks: "Evaluate 170,000 candidates"                 │
│                                                             │
│  Step 1: Split into batches (50K limit)                     │
│  ├── Batch 1: 50,000 candidates                             │
│  ├── Batch 2: 50,000 candidates                             │
│  ├── Batch 3: 50,000 candidates                             │
│  └── Batch 4: 20,000 candidates                             │
│                                                             │
│  Step 2: Submit to batch server                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ POST /v1/batches (4 separate requests)
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              BATCH SERVER (Port 4080)                       │
│                                                             │
│  Queue:                                                     │
│  ├── batch_001 (50K) - Status: running                      │
│  ├── batch_002 (50K) - Status: pending                      │
│  ├── batch_003 (50K) - Status: pending                      │
│  └── batch_004 (20K) - Status: pending                      │
│                                                             │
│  Limit: Max 5 concurrent batches ✅                         │
│  Limit: Max 100K total queued ✅ (170K > 100K!)             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              WORKER PROCESS                                 │
│                                                             │
│  Processing batch_001 (50K requests):                       │
│                                                             │
│  Step 1: Load 50K requests from file                        │
│  Step 2: Split into 5K chunks (memory limit)                │
│  ├── Chunk 1: 5,000 requests → vLLM → Save results          │
│  ├── Chunk 2: 5,000 requests → vLLM → Save results          │
│  ├── Chunk 3: 5,000 requests → vLLM → Save results          │
│  ├── ...                                                    │
│  └── Chunk 10: 5,000 requests → vLLM → Save results         │
│                                                             │
│  Step 3: Mark batch_001 as completed                        │
│  Step 4: Move to batch_002                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              RTX 4080 16GB GPU                              │
│                                                             │
│  Processing 5K requests at a time                           │
│  Memory usage: ~11 GiB (constant)                           │
│  Throughput: 2,511 tokens/sec                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              RESULTS STORAGE                                │
│                                                             │
│  data/batches/output/                                       │
│  ├── batch_001_results.jsonl (50K results)                  │
│  ├── batch_002_results.jsonl (50K results)                  │
│  ├── batch_003_results.jsonl (50K results)                  │
│  └── batch_004_results.jsonl (20K results)                  │
│                                                             │
│  Retention: 30 days                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ GET /v1/batches/{id}/results (4 downloads)
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    ARIS WEB APP                             │
│                                                             │
│  Step 3: Download all results                               │
│  ├── Download batch_001_results.jsonl                       │
│  ├── Download batch_002_results.jsonl                       │
│  ├── Download batch_003_results.jsonl                       │
│  └── Download batch_004_results.jsonl                       │
│                                                             │
│  Step 4: Merge results (170K total)                         │
│  Step 5: Store in Aris database                             │
│  Step 6: Show to end user                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚠️ **PROBLEM: 100K Queue Limit!**

**Current Issue:**
- Batch server has **100K max total queued requests** limit
- Aris wants to submit **170K requests**
- **170K > 100K** → Will be rejected!

**Solutions:**

### **Option A: Increase Queue Limit (Recommended)**

```python
# batch_app/api_server.py

MAX_TOTAL_QUEUED_REQUESTS = 200000  # Increase to 200K
```

**Pros:**
- ✅ Simple
- ✅ Aris can submit all 4 batches at once
- ✅ Batch server manages queue

**Cons:**
- ⚠️ More memory usage (SQLite database)

### **Option B: Sequential Submission**

Aris submits batches one at a time:

```python
# In Aris web app

batch_ids = []

# Submit batch 1
batch_id_1 = await submit_batch(candidates[0:50000])
batch_ids.append(batch_id_1)

# Wait for batch 1 to complete
await wait_for_completion(batch_id_1)

# Submit batch 2
batch_id_2 = await submit_batch(candidates[50000:100000])
batch_ids.append(batch_id_2)

# ... and so on
```

**Pros:**
- ✅ Respects queue limits
- ✅ Lower memory usage

**Cons:**
- ❌ Slower (sequential, not parallel)
- ❌ More complex Aris code

### **Option C: Smart Queuing in Aris**

Aris monitors queue and submits when space available:

```python
# In Aris web app

async def submit_large_batch(candidates, batch_size=50000):
    """Submit 170K candidates intelligently"""
    
    # Split into batches
    batches = [candidates[i:i+batch_size] 
               for i in range(0, len(candidates), batch_size)]
    
    batch_ids = []
    
    for batch in batches:
        # Wait for queue space
        while True:
            health = await batch_client.get_health()
            if health['queue']['queue_available'] > 0:
                break
            await asyncio.sleep(30)  # Check every 30s
        
        # Submit batch
        batch_id = await batch_client.submit_batch(batch)
        batch_ids.append(batch_id)
    
    return batch_ids
```

**Pros:**
- ✅ Respects queue limits
- ✅ Automatic (no manual intervention)
- ✅ Parallel processing (as queue allows)

**Cons:**
- ⚠️ More complex Aris code

---

## 🔄 **Recommended Flow: Option A + Smart Polling**

### **Step 1: Increase Queue Limit**

```python
# batch_app/api_server.py

MAX_QUEUE_DEPTH = 10  # Allow 10 concurrent batches
MAX_REQUESTS_PER_JOB = 50000  # Keep at 50K
MAX_TOTAL_QUEUED_REQUESTS = 500000  # Increase to 500K (future-proof)
```

### **Step 2: Aris Submits All Batches**

```python
# In Aris web app

async def evaluate_all_candidates(candidates):
    """Evaluate 170K candidates"""
    
    # Split into 50K batches
    batches = chunk_list(candidates, 50000)
    # Result: [50K, 50K, 50K, 20K]
    
    # Submit all batches at once
    batch_ids = []
    for i, batch in enumerate(batches):
        # Create JSONL file
        jsonl_file = create_batch_jsonl(batch)
        
        # Submit to batch server
        batch_id = await batch_client.submit_batch(
            file=jsonl_file,
            model='google/gemma-3-4b-it'
        )
        
        batch_ids.append(batch_id)
        print(f"Submitted batch {i+1}/4: {batch_id}")
    
    # Return all batch IDs
    return batch_ids
```

### **Step 3: Aris Polls for Completion**

```python
async def wait_for_all_batches(batch_ids):
    """Wait for all batches to complete"""
    
    completed = set()
    
    while len(completed) < len(batch_ids):
        for batch_id in batch_ids:
            if batch_id in completed:
                continue
            
            # Check status
            status = await batch_client.get_status(batch_id)
            
            if status['status'] == 'completed':
                completed.add(batch_id)
                print(f"Batch {batch_id} completed! ({len(completed)}/{len(batch_ids)})")
            elif status['status'] == 'failed':
                print(f"Batch {batch_id} failed: {status['error_message']}")
                completed.add(batch_id)  # Don't retry
        
        # Wait before next poll
        await asyncio.sleep(30)  # Poll every 30 seconds
    
    print("All batches completed!")
```

### **Step 4: Aris Downloads All Results**

```python
async def download_all_results(batch_ids):
    """Download and merge all results"""
    
    all_results = []
    
    for batch_id in batch_ids:
        # Download results
        results = await batch_client.get_results(batch_id)
        
        # Parse JSONL
        for line in results.split('\n'):
            if line.strip():
                result = json.loads(line)
                all_results.append(result)
    
    print(f"Downloaded {len(all_results)} total results")
    return all_results
```

### **Step 5: Aris Stores in Database**

```python
async def store_evaluations(results):
    """Store evaluations in Aris database"""
    
    for result in results:
        candidate_id = result['custom_id']
        llm_output = result['response']['body']['choices'][0]['message']['content']
        
        # Parse evaluation
        evaluation = parse_evaluation(llm_output)
        
        # Store in database
        await db.evaluations.insert({
            'candidate_id': candidate_id,
            'evaluation': evaluation,
            'llm_output': llm_output,
            'created_at': datetime.now()
        })
```

### **Step 6: Aris Shows to End User**

```python
# In Aris UI

@app.get("/candidates/{candidate_id}/evaluation")
async def get_evaluation(candidate_id: str):
    """Show evaluation to recruiter"""
    
    evaluation = await db.evaluations.find_one({
        'candidate_id': candidate_id
    })
    
    return {
        'candidate_id': candidate_id,
        'evaluation': evaluation['evaluation'],
        'score': evaluation['score'],
        'recommendation': evaluation['recommendation']
    }
```

---

## ⏱️ **Timeline: 170K Candidates**

### **Processing Time**

**Assumptions:**
- 50K batch = ~6 hours (based on 5K = 36 min)
- 4 batches total
- Sequential processing (1 GPU)

**Timeline:**
```
Hour 0:  Submit all 4 batches
Hour 0:  Batch 1 starts processing (50K)
Hour 6:  Batch 1 completes, Batch 2 starts (50K)
Hour 12: Batch 2 completes, Batch 3 starts (50K)
Hour 18: Batch 3 completes, Batch 4 starts (20K)
Hour 20: Batch 4 completes (20K = ~2.4 hours)
Hour 20: All done! Download results
```

**Total Time: ~20 hours**

---

## 🎯 **Does End User See Results?**

**Two Approaches:**

### **Approach 1: Batch Processing (Recommended)**

**Flow:**
1. Recruiter clicks "Evaluate 170K candidates"
2. Aris shows: "Processing... ETA: 20 hours"
3. Recruiter comes back tomorrow
4. Aris shows: "Completed! View results"
5. Recruiter browses evaluations

**Pros:**
- ✅ Simple
- ✅ Efficient (batch processing)
- ✅ No real-time pressure

**Cons:**
- ⚠️ Not real-time

### **Approach 2: Progressive Results**

**Flow:**
1. Recruiter clicks "Evaluate 170K candidates"
2. Aris shows progress: "Completed: 50,000 / 170,000 (29%)"
3. Recruiter can view completed evaluations while others process
4. Results appear progressively

**Implementation:**
```python
# In Aris web app

async def show_progress(batch_ids):
    """Show progressive results to user"""
    
    while True:
        total_completed = 0
        total_requests = 170000
        
        for batch_id in batch_ids:
            status = await batch_client.get_status(batch_id)
            total_completed += status['completed_requests']
        
        # Update UI
        progress_percent = (total_completed / total_requests) * 100
        print(f"Progress: {total_completed:,} / {total_requests:,} ({progress_percent:.1f}%)")
        
        # Download completed batches
        for batch_id in batch_ids:
            status = await batch_client.get_status(batch_id)
            if status['status'] == 'completed' and not is_downloaded(batch_id):
                results = await batch_client.get_results(batch_id)
                await store_evaluations(results)
                mark_as_downloaded(batch_id)
        
        if total_completed == total_requests:
            break
        
        await asyncio.sleep(60)  # Update every minute
```

**Pros:**
- ✅ User sees progress
- ✅ Can view results as they complete
- ✅ Better UX

**Cons:**
- ⚠️ More complex code

---

## 📊 **Summary**

### **Data Flow:**

```
Aris (170K candidates)
  ↓
Split into 4 batches (50K, 50K, 50K, 20K)
  ↓
Submit to batch server (4 POST requests)
  ↓
Batch server queues (max 5 concurrent)
  ↓
Worker processes sequentially
  ├── Batch 1: 50K → 10 chunks of 5K → vLLM → Results
  ├── Batch 2: 50K → 10 chunks of 5K → vLLM → Results
  ├── Batch 3: 50K → 10 chunks of 5K → vLLM → Results
  └── Batch 4: 20K → 4 chunks of 5K → vLLM → Results
  ↓
Aris downloads 4 result files
  ↓
Aris merges 170K results
  ↓
Aris stores in database
  ↓
End user sees evaluations
```

### **Key Points:**

1. ✅ **Aris splits** 170K into 4 batches (API limit: 50K)
2. ✅ **Batch server queues** all 4 batches
3. ✅ **Worker chunks** each 50K batch into 5K pieces (memory limit)
4. ✅ **Results stored** temporarily (30 days)
5. ✅ **Aris downloads** all 4 result files
6. ✅ **Aris merges** and stores in permanent database
7. ✅ **End user sees** evaluations in Aris UI

**Total time: ~20 hours for 170K candidates** 🚀

