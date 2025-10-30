# In-Context Learning & Fine-Tuning Architecture

**Date:** 2025-10-29  
**Real Use Case:** Generate training data for in-context learning and fine-tuning

---

## 🎯 **The Real Goal: Training Data Generation**

You're not just evaluating candidates for recruiters to see.  
You're **generating high-quality training data** to improve your models!

### **Use Cases:**

1. **In-Context Learning (ICL)**
   - Find best examples to include in prompts
   - Test different example combinations
   - Measure quality improvement with examples

2. **Fine-Tuning**
   - Generate training dataset (input → output pairs)
   - Curate high-quality examples
   - Create domain-specific model

---

## 🏗️ **Revised Architecture: Training Data Pipeline**

```
┌─────────────────────────────────────────────────────────────┐
│                    ARIS WEB APP                             │
│              (Training Data Orchestrator)                   │
│                                                             │
│  Phase 1: Generate Initial Dataset                          │
│  ├── Select 170K candidates                                 │
│  ├── Create evaluation prompts                              │
│  └── Submit to batch server                                 │
│                                                             │
│  Phase 2: Collect Raw Outputs                               │
│  ├── Download 170K LLM evaluations                          │
│  ├── Store in training_data_raw table                       │
│  └── Analyze quality distribution                           │
│                                                             │
│  Phase 3: Curate Training Data                              │
│  ├── Filter high-quality examples (top 20%)                 │
│  ├── Human review & labeling                                │
│  ├── Add metadata (difficulty, category)                    │
│  └── Store in training_data_curated table                   │
│                                                             │
│  Phase 4: In-Context Learning                               │
│  ├── Select best examples (k=5)                             │
│  ├── Test different example combinations                    │
│  ├── Measure quality improvement                            │
│  └── Find optimal ICL strategy                              │
│                                                             │
│  Phase 5: Fine-Tuning                                       │
│  ├── Export curated data (JSONL format)                     │
│  ├── Fine-tune model (LoRA/QLoRA)                           │
│  ├── Evaluate fine-tuned model                              │
│  └── Deploy improved model                                  │
└─────────────────────────────────────────────────────────────┘
                     │                          │
                     ↓                          ↓
┌──────────────────────────────┐  ┌──────────────────────────┐
│  vLLM Batch Server           │  │  Training Data Lake      │
│  (Inference Engine)          │  │  (Permanent Storage)     │
│                              │  │                          │
│  - Generate evaluations      │  │  Raw outputs (170K)      │
│  - Return raw outputs        │  │  Curated examples (34K)  │
│  - Temporary storage         │  │  ICL examples (100)      │
│  - 30-day retention          │  │  Fine-tuning data (10K)  │
└──────────────────────────────┘  └──────────────────────────┘
```

---

## 📊 **Data Flow: Training Data Generation**

### **Phase 1: Generate Initial Dataset (170K)**

```python
# In Aris web app

async def generate_training_data():
    """Generate 170K training examples"""
    
    # Get all candidates
    candidates = await db.candidates.find().limit(170000)
    
    # Create batch requests (NO in-context examples yet)
    requests = []
    for candidate in candidates:
        requests.append({
            'custom_id': candidate['id'],
            'method': 'POST',
            'url': '/v1/chat/completions',
            'body': {
                'model': 'gpt-4',
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': format_candidate(candidate)}
                ],
                'max_tokens': 500
            }
        })
    
    # Split into 50K batches
    batches = chunk_list(requests, 50000)
    
    # Submit all batches
    batch_ids = []
    for batch in batches:
        batch_id = await batch_client.submit_batch(batch, model='google/gemma-3-4b-it')
        batch_ids.append(batch_id)
    
    # Store batch IDs for tracking
    await db.training_runs.insert({
        'run_id': 'run_001',
        'batch_ids': batch_ids,
        'total_candidates': 170000,
        'status': 'processing',
        'created_at': datetime.now()
    })
    
    return batch_ids
```

### **Phase 2: Collect Raw Outputs**

```python
async def collect_raw_outputs(batch_ids):
    """Download and store all raw LLM outputs"""
    
    all_results = []
    
    # Download all batches
    for batch_id in batch_ids:
        results = await batch_client.get_results(batch_id)
        all_results.extend(parse_jsonl(results))
    
    # Store in training_data_raw table
    for result in all_results:
        candidate_id = result['custom_id']
        llm_output = result['response']['body']['choices'][0]['message']['content']
        
        await db.training_data_raw.insert({
            'candidate_id': candidate_id,
            'llm_output': llm_output,
            'model': 'google/gemma-3-4b-it',
            'run_id': 'run_001',
            'created_at': datetime.now()
        })
    
    print(f"Stored {len(all_results)} raw training examples")
```

### **Phase 3: Curate Training Data**

```python
async def curate_training_data():
    """Filter and curate high-quality examples"""
    
    # Get all raw outputs
    raw_examples = await db.training_data_raw.find({'run_id': 'run_001'})
    
    curated = []
    
    for example in raw_examples:
        # Calculate quality score
        quality_score = calculate_quality(example['llm_output'])
        
        # Filter: Keep top 20% (34K out of 170K)
        if quality_score >= 0.8:
            # Get candidate context
            candidate = await db.candidates.find_one({'id': example['candidate_id']})
            
            # Store curated example
            await db.training_data_curated.insert({
                'candidate_id': example['candidate_id'],
                'input': format_candidate(candidate),  # Input prompt
                'output': example['llm_output'],        # LLM output
                'quality_score': quality_score,
                'needs_review': True,  # Human review
                'approved': False,
                'metadata': {
                    'company': candidate['company'],
                    'title': candidate['title'],
                    'difficulty': calculate_difficulty(candidate)
                },
                'created_at': datetime.now()
            })
            
            curated.append(example)
    
    print(f"Curated {len(curated)} high-quality examples (top 20%)")
    return curated
```

### **Phase 4: In-Context Learning**

```python
async def find_best_icl_examples(k=5):
    """Find best examples for in-context learning"""
    
    # Get approved curated examples
    examples = await db.training_data_curated.find({
        'approved': True,
        'quality_score': {'$gte': 0.9}
    }).limit(100)
    
    # Test different combinations
    best_examples = []
    best_score = 0
    
    for combination in itertools.combinations(examples, k):
        # Test this combination on validation set
        score = await test_icl_combination(combination)
        
        if score > best_score:
            best_score = score
            best_examples = combination
    
    # Store best ICL examples
    await db.icl_examples.insert({
        'examples': [e['id'] for e in best_examples],
        'k': k,
        'validation_score': best_score,
        'created_at': datetime.now()
    })
    
    return best_examples

async def test_icl_combination(examples):
    """Test ICL examples on validation set"""
    
    # Get validation candidates (not in training set)
    validation_candidates = await db.candidates.find({
        'in_training_set': False
    }).limit(100)
    
    # Create prompts with ICL examples
    requests = []
    for candidate in validation_candidates:
        # Build prompt with examples
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT}
        ]
        
        # Add ICL examples
        for example in examples:
            messages.append({'role': 'user', 'content': example['input']})
            messages.append({'role': 'assistant', 'content': example['output']})
        
        # Add actual candidate
        messages.append({'role': 'user', 'content': format_candidate(candidate)})
        
        requests.append({
            'custom_id': candidate['id'],
            'method': 'POST',
            'url': '/v1/chat/completions',
            'body': {
                'model': 'gpt-4',
                'messages': messages,
                'max_tokens': 500
            }
        })
    
    # Submit batch
    batch_id = await batch_client.submit_batch(requests, model='google/gemma-3-4b-it')
    
    # Wait for completion
    await wait_for_completion(batch_id)
    
    # Download results
    results = await batch_client.get_results(batch_id)
    
    # Calculate quality score
    total_score = 0
    for result in results:
        output = result['response']['body']['choices'][0]['message']['content']
        score = calculate_quality(output)
        total_score += score
    
    avg_score = total_score / len(results)
    return avg_score
```

### **Phase 5: Fine-Tuning**

```python
async def export_for_finetuning():
    """Export curated data for fine-tuning"""
    
    # Get approved examples
    examples = await db.training_data_curated.find({
        'approved': True,
        'quality_score': {'$gte': 0.85}
    })
    
    # Convert to fine-tuning format
    finetuning_data = []
    
    for example in examples:
        finetuning_data.append({
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': example['input']},
                {'role': 'assistant', 'content': example['output']}
            ]
        })
    
    # Save as JSONL
    with open('finetuning_data.jsonl', 'w') as f:
        for item in finetuning_data:
            f.write(json.dumps(item) + '\n')
    
    print(f"Exported {len(finetuning_data)} examples for fine-tuning")
    return 'finetuning_data.jsonl'

async def finetune_model():
    """Fine-tune model with curated data"""
    
    # Export data
    training_file = await export_for_finetuning()
    
    # Fine-tune with LoRA/QLoRA
    # (This would use unsloth, axolotl, or similar)
    
    # Example with unsloth:
    from unsloth import FastLanguageModel
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="google/gemma-3-4b-it",
        max_seq_length=2048,
        load_in_4bit=True
    )
    
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,  # LoRA rank
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]
    )
    
    # Train
    trainer = SFTTrainer(
        model=model,
        train_dataset=load_dataset('json', data_files=training_file),
        max_seq_length=2048,
        num_train_epochs=3
    )
    
    trainer.train()
    
    # Save fine-tuned model
    model.save_pretrained("gemma-3-4b-aris-finetuned")
    
    return "gemma-3-4b-aris-finetuned"
```

---

## 🗄️ **Database Schema: Training Data Lake**

### **training_data_raw** (170K rows)
```sql
CREATE TABLE training_data_raw (
    id UUID PRIMARY KEY,
    candidate_id VARCHAR(255),
    llm_output TEXT,
    model VARCHAR(255),
    run_id VARCHAR(255),
    created_at TIMESTAMP
);
```

### **training_data_curated** (34K rows - top 20%)
```sql
CREATE TABLE training_data_curated (
    id UUID PRIMARY KEY,
    candidate_id VARCHAR(255),
    input TEXT,              -- Formatted candidate prompt
    output TEXT,             -- LLM evaluation
    quality_score FLOAT,     -- 0.0 - 1.0
    needs_review BOOLEAN,
    approved BOOLEAN,
    reviewed_by VARCHAR(255),
    metadata JSONB,          -- {company, title, difficulty, etc.}
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### **icl_examples** (100 rows - best examples)
```sql
CREATE TABLE icl_examples (
    id UUID PRIMARY KEY,
    example_ids UUID[],      -- References to training_data_curated
    k INTEGER,               -- Number of examples (e.g., 5)
    validation_score FLOAT,  -- Quality score on validation set
    use_case VARCHAR(255),   -- 'general', 'tech', 'executive', etc.
    created_at TIMESTAMP
);
```

### **finetuning_runs** (Track fine-tuning experiments)
```sql
CREATE TABLE finetuning_runs (
    id UUID PRIMARY KEY,
    base_model VARCHAR(255),
    training_examples INTEGER,
    validation_score FLOAT,
    model_path VARCHAR(255),
    hyperparameters JSONB,
    created_at TIMESTAMP
);
```

---

## 🔄 **Complete Workflow**

### **Week 1: Generate Raw Data**
```bash
# Generate 170K evaluations
python -m aris.training_data.generate --candidates 170000

# Wait ~20 hours for batch processing
# Result: 170K raw LLM outputs
```

### **Week 2: Curate Data**
```bash
# Filter top 20% (34K examples)
python -m aris.training_data.curate --threshold 0.8

# Human review (recruiters label quality)
# Result: 10K approved high-quality examples
```

### **Week 3: In-Context Learning**
```bash
# Find best ICL examples
python -m aris.training_data.find_icl_examples --k 5

# Test on validation set
python -m aris.training_data.test_icl

# Result: 5 best examples for prompts
```

### **Week 4: Fine-Tuning**
```bash
# Export training data
python -m aris.training_data.export --format jsonl

# Fine-tune model
python -m aris.training_data.finetune \
    --base_model google/gemma-3-4b-it \
    --training_file finetuning_data.jsonl \
    --epochs 3

# Result: gemma-3-4b-aris-finetuned
```

---

## 📈 **Quality Metrics**

### **Raw Data Quality Distribution**
```
170K total examples:
├── Excellent (0.9-1.0): 17K (10%)
├── Good (0.8-0.9): 34K (20%)
├── Acceptable (0.7-0.8): 51K (30%)
├── Poor (0.6-0.7): 34K (20%)
└── Bad (0.0-0.6): 34K (20%)
```

### **Curation Funnel**
```
170K raw outputs
  ↓ Filter: quality_score >= 0.8
34K high-quality examples
  ↓ Human review
10K approved examples
  ↓ Export for fine-tuning
10K training examples
```

### **ICL vs Fine-Tuning**
```
Baseline (no examples):     Quality = 0.65
ICL (k=5 examples):         Quality = 0.78 (+20%)
Fine-tuned model:           Quality = 0.85 (+31%)
```

---

## 🎯 **Key Insights**

### **1. Batch Server Role**
- ✅ Generate raw training data (170K examples)
- ✅ Test ICL combinations (validation batches)
- ✅ Evaluate fine-tuned models (benchmark batches)
- ❌ NOT for serving to end users
- ❌ NOT for production inference

### **2. Aris Web App Role**
- ✅ Orchestrate training data generation
- ✅ Curate and label examples
- ✅ Store training data permanently
- ✅ Export for fine-tuning
- ✅ Manage ICL examples
- ✅ Track experiments

### **3. Data Storage**
- **Batch Server:** Temporary (30 days) - raw LLM outputs
- **Aris Database:** Permanent - curated training data
- **Model Registry:** Permanent - fine-tuned models

### **4. End User Experience**
- **NOT real-time evaluation** (that's production inference)
- **Training data generation** (offline, batch process)
- **Model improvement** (better evaluations over time)

---

## 🚀 **Next Steps**

1. ✅ **Generate 170K raw examples** (batch server)
2. ✅ **Build curation pipeline** (Aris web app)
3. ✅ **Create human review UI** (Aris web app)
4. ✅ **Find best ICL examples** (k=5)
5. ✅ **Fine-tune model** (LoRA/QLoRA)
6. ✅ **Deploy improved model** (production)

---

## 📊 **Summary**

**This is a TRAINING DATA PIPELINE, not a production inference system!**

- ✅ Batch server generates 170K training examples
- ✅ Aris curates top 20% (34K examples)
- ✅ Human review approves 10K examples
- ✅ Find best 5 ICL examples
- ✅ Fine-tune model with 10K examples
- ✅ Deploy improved model to production

**The 170K candidates are NOT for end users to see - they're for training better models!** 🎯

