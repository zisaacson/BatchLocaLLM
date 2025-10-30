# Gold-Star Curation System - First Principles Design

**Date:** 2025-10-29  
**Role:** Lead Engineer  
**Task:** Design training data curation system from first principles

---

## 🧠 **First Principles Brainstorm**

### **What Are We Actually Trying to Do?**

**Core Problem:**
- We have 170K LLM outputs (candidate evaluations)
- Some are excellent, some are garbage
- We need to identify the best ones for ICL/fine-tuning
- Multiple agents/humans need to collaborate on this

**Core Requirements:**
1. **View** - See LLM outputs in context (candidate + evaluation)
2. **Judge** - Mark quality (good/bad/excellent)
3. **Annotate** - Add metadata (why is this good? what category?)
4. **Collaborate** - Multiple people reviewing
5. **Export** - Get curated data in usable format (JSONL for ICL/fine-tuning)

---

## 🎯 **Design Principles**

### **Principle 1: Simplicity Over Features**
- Don't build a complex annotation platform
- Use what we already have (web viewer on port 8001)
- Add minimal features to enable curation

### **Principle 2: File-Based Storage (Not Database)**
- We already store results as JSONL files
- Keep gold-star data as JSONL files too
- Easy to version control, backup, inspect
- No database complexity

### **Principle 3: Stateless API**
- Each gold-star action is independent
- No sessions, no complex state
- Just append to files

### **Principle 4: Human-Readable Formats**
- Everything should be inspectable with `cat` or text editor
- JSONL for data, JSON for metadata
- No binary formats

### **Principle 5: Incremental Curation**
- Don't need to review all 170K at once
- Review in batches (100 at a time)
- Save progress as you go

---

## 📁 **Data Model**

### **What Do We Store?**

```json
{
  "custom_id": "candidate_12345",
  "candidate_name": "John Doe",
  "candidate_title": "Senior Software Engineer",
  "candidate_company": "Google",
  "llm_output": "Strong candidate with 10 years...",
  "model": "google/gemma-3-4b-it",
  "batch_id": "batch_001",
  "quality_score": 9,
  "tags": ["excellent", "senior", "tech"],
  "notes": "Great example of evaluating senior engineers",
  "starred_by": "agent_alice",
  "starred_at": "2025-10-29T12:34:56Z"
}
```

### **File Structure:**

```
data/
├── batches/
│   └── output/
│       ├── batch_001_results.jsonl (50K results - raw)
│       ├── batch_002_results.jsonl (50K results - raw)
│       └── ...
│
└── gold_star/
    ├── starred.jsonl (all gold-starred examples)
    ├── exports/
    │   ├── icl_examples_2025-10-29.jsonl
    │   └── finetuning_data_2025-10-29.jsonl
    └── metadata.json (stats, counts, etc.)
```

---

## 🔧 **Technical Design**

### **Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Web UI (Port 8001)                       │
│                                                             │
│  Table View:                                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Name      │ Title    │ Evaluation      │ Actions    │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ John Doe  │ Engineer │ Strong cand...  │ ⭐ [9/10] │  │
│  │ Jane Smith│ Manager  │ Excellent...    │ ⭐ [10/10]│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Actions:                                                   │
│  - Click star → Show rating modal (1-10)                    │
│  - Add tags, notes                                          │
│  - Save → POST /api/gold-star                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP POST
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              serve_results.py (API Server)                  │
│                                                             │
│  POST /api/gold-star                                        │
│  ├── Validate input                                         │
│  ├── Append to data/gold_star/starred.jsonl                 │
│  └── Return success                                         │
│                                                             │
│  GET /api/gold-star                                         │
│  ├── Read data/gold_star/starred.jsonl                      │
│  └── Return all starred examples                            │
│                                                             │
│  GET /api/export-gold-star?format=icl                       │
│  ├── Read starred.jsonl                                     │
│  ├── Filter by quality_score >= 9                           │
│  ├── Format for ICL (messages array)                        │
│  └── Return JSONL file                                      │
└─────────────────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              File System                                    │
│                                                             │
│  data/gold_star/starred.jsonl                               │
│  ├── One JSON object per line                               │
│  ├── Append-only (no updates)                               │
│  └── Human-readable                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 **UI Design**

### **Option A: Inline Gold-Star (Minimal)**

Add to existing `table_view.html`:

```html
<tr data-candidate-id="12345">
  <td>John Doe</td>
  <td>Senior Engineer</td>
  <td>Google</td>
  <td class="evaluation">Strong candidate with 10 years...</td>
  <td>
    <!-- Gold-star button -->
    <button onclick="goldStar(this)" class="star-btn">⭐</button>
  </td>
</tr>

<script>
function goldStar(btn) {
  const row = btn.closest('tr');
  const candidateId = row.dataset.candidateId;
  
  // Show simple rating modal
  const rating = prompt('Rate this evaluation (1-10):', '9');
  if (!rating) return;
  
  const tags = prompt('Tags (comma-separated):', 'excellent');
  const notes = prompt('Notes:', '');
  
  // Save
  fetch('/api/gold-star', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      custom_id: candidateId,
      quality_score: parseInt(rating),
      tags: tags.split(',').map(t => t.trim()),
      notes: notes,
      starred_by: 'user',
      starred_at: new Date().toISOString()
    })
  }).then(() => {
    btn.textContent = '⭐ ' + rating;
    btn.disabled = true;
    row.classList.add('starred');
  });
}
</script>
```

**Pros:**
- ✅ Minimal code
- ✅ Works immediately
- ✅ No new pages

**Cons:**
- ⚠️ Basic UX (prompts)
- ⚠️ No rich editing

### **Option B: Modal Dialog (Better UX)**

```html
<!-- Modal for gold-starring -->
<div id="goldStarModal" class="modal">
  <div class="modal-content">
    <h2>⭐ Gold-Star This Evaluation</h2>
    
    <div class="candidate-preview">
      <strong id="candidateName"></strong>
      <p id="candidateTitle"></p>
      <div id="evaluation"></div>
    </div>
    
    <label>Quality Score (1-10):</label>
    <input type="range" id="qualityScore" min="1" max="10" value="9">
    <span id="scoreDisplay">9</span>
    
    <label>Tags:</label>
    <div class="tag-selector">
      <label><input type="checkbox" value="excellent"> Excellent</label>
      <label><input type="checkbox" value="senior"> Senior</label>
      <label><input type="checkbox" value="tech"> Tech</label>
      <label><input type="checkbox" value="leadership"> Leadership</label>
    </div>
    
    <label>Notes:</label>
    <textarea id="notes" placeholder="Why is this a good example?"></textarea>
    
    <button onclick="saveGoldStar()">Save</button>
    <button onclick="closeModal()">Cancel</button>
  </div>
</div>
```

**Pros:**
- ✅ Better UX
- ✅ Rich editing
- ✅ Preview context

**Cons:**
- ⚠️ More code
- ⚠️ More complex

### **Option C: Dedicated Curation Page (Full-Featured)**

New page: `curate.html`

```html
<!-- Full curation interface -->
<div class="curation-interface">
  <div class="left-panel">
    <!-- List of candidates to review -->
    <h3>To Review (170K)</h3>
    <ul id="reviewQueue">
      <li onclick="loadCandidate('12345')">John Doe - Engineer</li>
      <li onclick="loadCandidate('12346')">Jane Smith - Manager</li>
      ...
    </ul>
  </div>
  
  <div class="center-panel">
    <!-- Current candidate -->
    <h2 id="candidateName">John Doe</h2>
    <p id="candidateTitle">Senior Software Engineer @ Google</p>
    
    <div class="evaluation-display">
      <h3>LLM Evaluation:</h3>
      <div id="evaluation">Strong candidate with 10 years...</div>
    </div>
    
    <div class="rating-panel">
      <h3>Your Rating:</h3>
      <input type="range" id="qualityScore" min="1" max="10" value="9">
      <span id="scoreDisplay">9/10</span>
      
      <div class="quick-actions">
        <button onclick="rate(10)">⭐⭐⭐ Excellent (10)</button>
        <button onclick="rate(7)">⭐⭐ Good (7)</button>
        <button onclick="rate(4)">⭐ Poor (4)</button>
        <button onclick="skip()">Skip</button>
      </div>
    </div>
  </div>
  
  <div class="right-panel">
    <!-- Stats -->
    <h3>Progress</h3>
    <p>Reviewed: 1,234 / 170,000</p>
    <p>Gold-starred: 234</p>
    <p>Avg quality: 7.8</p>
    
    <h3>Export</h3>
    <button onclick="exportICL()">Export ICL Examples</button>
    <button onclick="exportFinetune()">Export Fine-tuning Data</button>
  </div>
</div>
```

**Pros:**
- ✅ Full-featured
- ✅ Optimized for curation workflow
- ✅ Progress tracking

**Cons:**
- ⚠️ Most code
- ⚠️ Separate page

---

## 🚀 **Recommendation: Hybrid Approach**

### **Phase 1: Minimal (Ship Today)**

1. **Add inline gold-star to `table_view.html`**
   - Simple star button
   - Basic prompt for rating
   - Append to `starred.jsonl`

2. **Add API endpoints to `serve_results.py`**
   - `POST /api/gold-star` - Save starred example
   - `GET /api/gold-star` - List starred examples
   - `GET /api/export-gold-star` - Export for ICL/fine-tuning

3. **File storage**
   - `data/gold_star/starred.jsonl` - All starred examples
   - Append-only, human-readable

**Time to ship: 1 hour**

### **Phase 2: Better UX (Next Week)**

1. **Add modal dialog**
   - Better rating UI
   - Tag selector
   - Notes field

2. **Add filtering**
   - Show only unreviewed
   - Show only gold-starred
   - Filter by quality score

**Time to ship: 4 hours**

### **Phase 3: Full Curation (Future)**

1. **Dedicated curation page**
   - Queue-based workflow
   - Progress tracking
   - Keyboard shortcuts

2. **Multi-user support**
   - Track who starred what
   - Consensus scoring

**Time to ship: 2 days**

---

## 📝 **API Specification**

### **POST /api/gold-star**

**Request:**
```json
{
  "custom_id": "candidate_12345",
  "quality_score": 9,
  "tags": ["excellent", "senior"],
  "notes": "Great example",
  "starred_by": "agent_alice"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Example starred successfully"
}
```

**Implementation:**
```python
@app.route('/api/gold-star', methods=['POST'])
def gold_star():
    data = request.json
    
    # Validate
    if 'custom_id' not in data:
        return {'error': 'custom_id required'}, 400
    
    # Enrich with timestamp
    data['starred_at'] = datetime.now().isoformat()
    
    # Append to file
    os.makedirs('data/gold_star', exist_ok=True)
    with open('data/gold_star/starred.jsonl', 'a') as f:
        f.write(json.dumps(data) + '\n')
    
    return {'status': 'success'}
```

### **GET /api/gold-star**

**Response:**
```json
[
  {
    "custom_id": "candidate_12345",
    "quality_score": 9,
    "tags": ["excellent"],
    "starred_at": "2025-10-29T12:34:56Z"
  },
  ...
]
```

**Implementation:**
```python
@app.route('/api/gold-star', methods=['GET'])
def get_gold_star():
    starred = []
    
    if os.path.exists('data/gold_star/starred.jsonl'):
        with open('data/gold_star/starred.jsonl', 'r') as f:
            for line in f:
                if line.strip():
                    starred.append(json.loads(line))
    
    return starred
```

### **GET /api/export-gold-star?format=icl&min_quality=9**

**Response:** JSONL file download

**Implementation:**
```python
@app.route('/api/export-gold-star', methods=['GET'])
def export_gold_star():
    format = request.args.get('format', 'icl')
    min_quality = int(request.args.get('min_quality', 9))
    
    # Load starred examples
    starred = []
    with open('data/gold_star/starred.jsonl', 'r') as f:
        for line in f:
            if line.strip():
                example = json.loads(line)
                if example.get('quality_score', 0) >= min_quality:
                    starred.append(example)
    
    # Format for ICL
    if format == 'icl':
        output = []
        for example in starred[:100]:  # Top 100
            output.append({
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': example['input']},
                    {'role': 'assistant', 'content': example['llm_output']}
                ]
            })
        
        # Return as JSONL
        response = '\n'.join(json.dumps(item) for item in output)
        return Response(response, mimetype='application/jsonl')
    
    # Format for fine-tuning
    elif format == 'finetuning':
        # Same as ICL but all examples
        ...
```

---

## 🎯 **Decision: Start with Phase 1**

### **Why?**

1. **Ship fast** - 1 hour to working system
2. **Validate workflow** - See if this is actually useful
3. **Iterate** - Add features based on real usage
4. **Simple** - No complex UI, just append to file

### **What to Build:**

1. ✅ Add star button to `table_view.html`
2. ✅ Add 3 API endpoints to `serve_results.py`
3. ✅ Create `data/gold_star/` directory
4. ✅ Test with 10 examples

### **Success Criteria:**

- ✅ Can star an example in <5 seconds
- ✅ Starred examples saved to file
- ✅ Can export for ICL (top 100 examples)
- ✅ Can export for fine-tuning (all examples)

---

## 📊 **Summary**

**First Principles:**
- Simple file-based storage (JSONL)
- Stateless API (append-only)
- Minimal UI (inline buttons)
- Incremental curation (review as you go)

**Phase 1 (Ship Today):**
- Inline gold-star button
- 3 API endpoints
- File storage
- Export functionality

**Time to ship: 1 hour** 🚀

**Ready to implement?**

