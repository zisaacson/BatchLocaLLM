# Dual System Architecture - Production + Training Data Curation

**Date:** 2025-10-29  
**Reality Check:** Two parallel systems running simultaneously

---

## 🎯 **The Two Systems**

### **System #1: Production Inference (Real-Time)**
- **Purpose:** Serve Aris web app's real requests
- **Users:** Recruiters evaluating candidates NOW
- **Latency:** Need responses back (async batch, but timely)
- **Data Flow:** Aris → Batch Server → Results → Aris → Show to recruiter

### **System #2: Training Data Curation (Offline)**
- **Purpose:** Curate data from production responses for ICL/fine-tuning
- **Users:** Data scientists, ML engineers, agents
- **Latency:** No rush, can take days/weeks
- **Data Flow:** Batch Server → Web Viewer → Human review → Gold-star dataset → ICL/fine-tuning

---

## 🏗️ **Complete Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    ARIS WEB APP                             │
│              (Production System)                            │
│                                                             │
│  Recruiter: "Evaluate these 170K candidates"                │
│  ↓                                                          │
│  Submit 4 batches (50K each) to port 4080                   │
│  ↓                                                          │
│  Poll for completion (~20 hours)                            │
│  ↓                                                          │
│  Download results                                           │
│  ↓                                                          │
│  Store in aris.evaluations table                            │
│  ↓                                                          │
│  Show to recruiter: "Here are your 170K evaluations"        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP API (Port 4080)
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              vLLM Batch Server (Port 4080)                  │
│              (Inference Engine)                             │
│                                                             │
│  - Accept batch jobs from Aris                              │
│  - Process with vLLM (chunked)                              │
│  - Return results to Aris                                   │
│  - ALSO store results locally (30 days)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Results stored in:
                     │ data/batches/output/*.jsonl
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Web Viewer (Port 8001)                         │
│              (Training Data Curation UI)                    │
│                                                             │
│  - View all batch results                                   │
│  - Compare model outputs                                    │
│  - Review individual evaluations                            │
│  - Gold-star high-quality examples ⭐                       │
│  - Export gold-starred data for ICL/fine-tuning             │
│  - Multiple agents can collaborate                          │
└─────────────────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Gold-Star Dataset                              │
│              (Curated Training Data)                        │
│                                                             │
│  data/gold_star/                                            │
│  ├── icl_examples.jsonl (best 100 examples)                 │
│  ├── finetuning_data.jsonl (10K curated examples)           │
│  └── metadata.json (quality scores, labels)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 **System #1: Production Inference**

### **Data Flow:**

```
Aris Web App
  ↓
POST /v1/batches (170K candidates, split into 4 batches)
  ↓
Batch Server (Port 4080)
  ↓
Worker processes (vLLM, chunked)
  ↓
Results stored:
  - data/batches/output/batch_001_results.jsonl (50K)
  - data/batches/output/batch_002_results.jsonl (50K)
  - data/batches/output/batch_003_results.jsonl (50K)
  - data/batches/output/batch_004_results.jsonl (20K)
  ↓
Aris downloads via GET /v1/batches/{id}/results
  ↓
Aris stores in aris.evaluations table
  ↓
Recruiter sees evaluations in Aris UI
```

### **Timeline:**
- Hour 0: Aris submits 4 batches
- Hour 20: All batches complete
- Hour 20: Aris downloads results
- Hour 20: Recruiter sees 170K evaluations

### **Purpose:**
- ✅ Serve production requests
- ✅ Return results to Aris
- ✅ Enable recruiter workflow

---

## 📊 **System #2: Training Data Curation**

### **Data Flow:**

```
Batch Server (has results stored locally)
  ↓
data/batches/output/*.jsonl (170K results)
  ↓
Web Viewer (Port 8001)
  ↓
Human/Agent reviews results:
  - View individual evaluations
  - Compare different model outputs
  - Gold-star ⭐ high-quality examples
  - Add labels/metadata
  - Export selected examples
  ↓
Gold-Star Dataset
  ↓
Use for ICL/fine-tuning
```

### **Timeline:**
- Week 1: Generate 170K evaluations (production)
- Week 2-4: Review and gold-star examples (curation)
- Week 5: Export gold-star dataset
- Week 6: Use for ICL/fine-tuning

### **Purpose:**
- ✅ Curate training data
- ✅ Gold-star best examples
- ✅ Export for ICL/fine-tuning
- ✅ Improve models over time

---

## 🌐 **Enhanced Web Viewer for Curation**

### **Current Features (Already Built):**
- ✅ View datasets (index.html)
- ✅ Table view (table_view.html)
- ✅ Compare results (compare_results.html)
- ✅ Side-by-side comparison

### **New Features Needed:**

#### **1. Gold-Star UI**
```html
<!-- Add to table_view.html -->

<tr>
  <td>John Doe</td>
  <td>Software Engineer</td>
  <td>Strong candidate...</td>
  <td>
    <button onclick="goldStar(this)" class="gold-star-btn">
      ⭐ Gold Star
    </button>
  </td>
</tr>

<script>
function goldStar(btn) {
  const row = btn.closest('tr');
  const candidateId = row.dataset.candidateId;
  const evaluation = row.querySelector('.evaluation').textContent;
  
  // Save to gold-star dataset
  fetch('/api/gold-star', {
    method: 'POST',
    body: JSON.stringify({
      candidate_id: candidateId,
      evaluation: evaluation,
      quality: 'high',
      starred_by: 'user@example.com',
      starred_at: new Date().toISOString()
    })
  });
  
  // Visual feedback
  btn.textContent = '⭐ Starred!';
  btn.disabled = true;
  row.classList.add('gold-starred');
}
</script>
```

#### **2. Metadata Editor**
```html
<!-- Add metadata editing -->

<div class="metadata-editor">
  <h3>Edit Metadata</h3>
  <label>Quality Score:</label>
  <input type="range" min="0" max="100" value="85">
  
  <label>Category:</label>
  <select>
    <option>Excellent</option>
    <option>Good</option>
    <option>Needs Improvement</option>
  </select>
  
  <label>Tags:</label>
  <input type="text" placeholder="senior, tech, strong-communication">
  
  <label>Notes:</label>
  <textarea placeholder="Why this is a good example..."></textarea>
  
  <button onclick="saveMetadata()">Save</button>
</div>
```

#### **3. Export Gold-Star Dataset**
```html
<!-- Add export functionality -->

<div class="export-panel">
  <h3>Export Gold-Star Dataset</h3>
  
  <label>Format:</label>
  <select id="exportFormat">
    <option value="icl">In-Context Learning (JSONL)</option>
    <option value="finetuning">Fine-Tuning (JSONL)</option>
    <option value="csv">CSV (for analysis)</option>
  </select>
  
  <label>Filter:</label>
  <select id="exportFilter">
    <option value="all">All gold-starred</option>
    <option value="quality_high">Quality >= 80</option>
    <option value="recent">Last 30 days</option>
  </select>
  
  <button onclick="exportGoldStar()">
    📥 Export Dataset
  </button>
</div>

<script>
async function exportGoldStar() {
  const format = document.getElementById('exportFormat').value;
  const filter = document.getElementById('exportFilter').value;
  
  const response = await fetch(`/api/export-gold-star?format=${format}&filter=${filter}`);
  const blob = await response.blob();
  
  // Download file
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `gold_star_${format}_${Date.now()}.jsonl`;
  a.click();
}
</script>
```

---

## 🗄️ **Storage Strategy**

### **Batch Server (Port 4080)**

```
data/batches/
├── input/
│   ├── batch_001.jsonl (50K requests)
│   ├── batch_002.jsonl (50K requests)
│   ├── batch_003.jsonl (50K requests)
│   └── batch_004.jsonl (20K requests)
│
├── output/
│   ├── batch_001_results.jsonl (50K results) ← Aris downloads
│   ├── batch_002_results.jsonl (50K results) ← Aris downloads
│   ├── batch_003_results.jsonl (50K results) ← Aris downloads
│   └── batch_004_results.jsonl (20K results) ← Aris downloads
│
└── database/
    └── batches.db (job metadata)

Retention: 30 days
Purpose: Serve Aris + Enable curation
```

### **Web Viewer (Port 8001)**

```
data/gold_star/
├── starred_examples.jsonl (gold-starred examples)
├── metadata.json (quality scores, labels, notes)
└── exports/
    ├── icl_examples_2025-10-29.jsonl
    └── finetuning_data_2025-10-29.jsonl

Retention: Permanent
Purpose: Curated training data
```

### **Aris Database**

```
aris.evaluations (170K rows)
├── candidate_id
├── evaluation (LLM output)
├── batch_id (reference to batch server)
├── created_at
└── shown_to_recruiter (boolean)

Retention: Permanent
Purpose: Production data
```

---

## 🔄 **Complete Workflow**

### **Week 1: Production Inference**

```python
# Aris web app
batch_ids = await submit_batches(candidates=170000)
await wait_for_completion(batch_ids)
results = await download_results(batch_ids)
await store_in_database(results)
show_to_recruiter(results)
```

**Result:** Recruiter sees 170K evaluations

### **Week 2-4: Training Data Curation**

```python
# Data scientist opens web viewer
http://localhost:8001/table_view.html

# Review results
# Gold-star ⭐ best examples
# Add metadata (quality scores, tags, notes)
# Export gold-star dataset
```

**Result:** 10K gold-starred examples

### **Week 5: Export for ICL/Fine-Tuning**

```python
# Export gold-star dataset
http://localhost:8001/export

# Download:
# - icl_examples.jsonl (100 best examples)
# - finetuning_data.jsonl (10K examples)
```

**Result:** Ready for ICL/fine-tuning

### **Week 6: Use in Production**

```python
# Update Aris to use ICL examples
SYSTEM_PROMPT = load_icl_examples('icl_examples.jsonl')

# Or fine-tune model
model = finetune('google/gemma-3-4b-it', 'finetuning_data.jsonl')
```

**Result:** Better evaluations in production

---

## 🎯 **Key Points**

### **1. Dual Purpose of Batch Server**

**Purpose A: Serve Aris (Production)**
- ✅ Accept batch jobs
- ✅ Process with vLLM
- ✅ Return results to Aris
- ✅ Enable recruiter workflow

**Purpose B: Enable Curation (Training Data)**
- ✅ Store results locally (30 days)
- ✅ Expose via web viewer
- ✅ Allow gold-starring
- ✅ Export curated datasets

### **2. Two Separate UIs**

**Aris UI (Production)**
- For recruiters
- Shows evaluations
- Real-time workflow

**Web Viewer UI (Curation)**
- For data scientists/agents
- Reviews results
- Gold-stars examples
- Exports datasets

### **3. Data Flow**

```
Production Flow:
Aris → Batch Server → Aris → Recruiter

Curation Flow:
Batch Server → Web Viewer → Gold-Star → ICL/Fine-Tuning
```

---

## 🚀 **Next Steps**

### **1. Enhance Web Viewer**

Add to `serve_results.py`:
```python
@app.route('/api/gold-star', methods=['POST'])
def gold_star():
    """Save gold-starred example"""
    data = request.json
    
    # Save to gold_star dataset
    with open('data/gold_star/starred_examples.jsonl', 'a') as f:
        f.write(json.dumps(data) + '\n')
    
    return {'status': 'success'}

@app.route('/api/export-gold-star')
def export_gold_star():
    """Export gold-starred dataset"""
    format = request.args.get('format', 'icl')
    
    # Load gold-starred examples
    examples = load_gold_star_examples()
    
    if format == 'icl':
        # Format for in-context learning
        output = format_for_icl(examples)
    elif format == 'finetuning':
        # Format for fine-tuning
        output = format_for_finetuning(examples)
    
    return send_file(output, as_attachment=True)
```

### **2. Add Gold-Star UI**

Create `gold_star.html`:
- View all results
- Gold-star button
- Metadata editor
- Export panel

### **3. Update Dashboard**

Add to `dashboard.html`:
- Link to gold-star UI
- Show count of gold-starred examples
- Export button

---

## 📊 **Summary**

**Two Parallel Systems:**

| System | Purpose | Users | Latency | Storage |
|--------|---------|-------|---------|---------|
| **Production** | Serve Aris requests | Recruiters | ~20 hours | Aris DB (permanent) |
| **Curation** | Build training data | Data scientists | Weeks | Gold-star dataset (permanent) |

**Both use the same batch server, but for different purposes!**

- ✅ Aris gets results back for recruiters
- ✅ Web viewer enables curation for training data
- ✅ Gold-star best examples
- ✅ Export for ICL/fine-tuning
- ✅ Improve models over time

**Does this match your vision now?** 🎯

