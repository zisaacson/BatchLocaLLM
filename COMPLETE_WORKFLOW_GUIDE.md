# 📚 COMPLETE CANDIDATE CURATION WORKFLOW GUIDE

**Last Updated:** 2025-11-05  
**Commit:** 21d6813  
**Status:** ✅ **PRODUCTION READY**

---

## 🎯 **WHAT THIS SYSTEM DOES**

This is a **complete candidate curation system** that allows you to:

1. ✅ View candidates processed through vLLM
2. ✅ See the questions asked to the LLM
3. ✅ See the LLM's answers to those questions
4. ✅ Edit any incorrect answers
5. ✅ Save changes to the database
6. ✅ Mark best examples as gold stars
7. ✅ Export gold stars for model fine-tuning

---

## 🚀 **QUICK START**

### **Step 1: Access the Candidate Table**
```
Open in browser: http://localhost:8001/table
```

### **Step 2: Review Candidates**
- See all candidates in a beautiful table
- View stats: Total, Gold Stars, Strong Yes, Reviewed
- Filter by status or search by name

### **Step 3: Edit Answers**
1. Click "✏️ Edit" on any candidate
2. Modal opens showing all questions and current answers
3. Change any answers using dropdown selectors
4. Click "💾 Save Changes" or "⭐ Save & Mark Gold Star"

### **Step 4: Export for Fine-Tuning**
```bash
curl "http://localhost:4080/v1/aris/icl/examples?philosopher=your@email.com&limit=100"
```

---

## 📊 **COMPLETE WORKFLOW**

### **Phase 1: Candidate Processing**

#### **1.1 Create Conquests in Aristotle**
Your Aristotle web app creates conquests for candidate evaluation:

```javascript
// In Aristotle app
POST /api/conquests
{
  "conquest_type": "candidate_evaluation",
  "prompt_data": {
    "name": "John Doe",
    "current_role": "Senior Engineer",
    "current_company": "Google",
    "education": "MIT, BS Computer Science",
    "work_history": [...]
  }
}
```

#### **1.2 vLLM Processes Candidates**
vLLM batch server processes the conquest:
- Loads the model (e.g., Gemma 3 4B)
- Generates evaluation
- Stores results in `conquest_responses.data`

#### **1.3 Results Stored in Database**
```sql
-- conquest_responses table
{
  "evaluation": {
    "recommendation": "Strong Yes",
    "trajectory_rating": "Exceptional",
    "company_pedigree_rating": "Strong",
    "educational_pedigree_rating": "Good",
    "is_software_engineer": true
  }
}
```

---

### **Phase 2: Review & Curation**

#### **2.1 Open Candidate Table**
```
URL: http://localhost:8001/table
```

**What you see:**
- Stats dashboard at top
- Filter controls (All, Gold, Strong Yes, Pending)
- Search box
- Table with all candidates

**Table Columns:**
1. Candidate (name, title, company)
2. Recommendation (Strong Yes/Yes/Maybe/No/Strong No)
3. Trajectory (Exceptional/Strong/Good/Average/Weak)
4. Company Pedigree (Exceptional/Strong/Good/Average/Weak)
5. Education (Exceptional/Strong/Good/Average/Weak)
6. Software Engineer (Yes/No)
7. Actions (Edit, Gold Star buttons)

#### **2.2 Review Candidate Details**
Click "✏️ Edit" on any candidate to see:

**Modal Contents:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Editing: John Doe
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall Recommendation
Current: Strong Yes
[Dropdown: Strong Yes / Yes / Maybe / No / Strong No]

Trajectory Rating
Current: Exceptional
[Dropdown: Exceptional / Strong / Good / Average / Weak]

Company Pedigree Rating
Current: Strong
[Dropdown: Exceptional / Strong / Good / Average / Weak]

Educational Pedigree Rating
Current: Good
[Dropdown: Exceptional / Strong / Good / Average / Weak]

Is Software Engineer?
Current: Yes
[Dropdown: Yes / No]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[💾 Save Changes]  [⭐ Save & Mark Gold Star]  [Cancel]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### **2.3 Edit Incorrect Answers**

**Example: LLM made a mistake**
- LLM said: "Maybe" recommendation
- You know: Should be "Strong Yes"
- Action: Change dropdown to "Strong Yes"

**Example: Rating too high**
- LLM said: "Exceptional" trajectory
- You know: Should be "Strong"
- Action: Change dropdown to "Strong"

#### **2.4 Save Changes**

**Option A: Save Only**
1. Click "💾 Save Changes"
2. API call: `PUT /api/conquests/{id}/response`
3. Database updated
4. Success message shown
5. Modal closes
6. Table refreshes with new values

**Option B: Save & Mark Gold Star**
1. Click "⭐ Save & Mark Gold Star"
2. Enter your email
3. API calls:
   - `PUT /api/conquests/{id}/response` (save edits)
   - `POST /api/conquests/{id}/mark-victory` (mark gold star)
4. Database updated:
   - `conquest_responses.data` = edited values
   - `conquests.result` = 'VICTORY'
   - `ml_analysis_ratings.use_as_example` = true
5. Row turns yellow with gold border
6. Button changes to "✅ Gold Star"

---

### **Phase 3: Gold Star Management**

#### **3.1 Mark Gold Stars**
You can mark gold stars in two ways:

**Method 1: From Edit Modal**
- Edit answers first
- Click "⭐ Save & Mark Gold Star"
- Saves edits AND marks as VICTORY

**Method 2: Direct Gold Star**
- Click "⭐ Gold Star" button in table row
- Enter your email
- Marks as VICTORY without editing

#### **3.2 Filter Gold Stars**
In the candidate table:
1. Click "Gold" filter button
2. See only gold star candidates
3. Yellow rows with gold left border
4. ⭐ icon next to candidate name

#### **3.3 View Gold Star Stats**
Stats dashboard shows:
- Total Candidates: 150
- ⭐ Gold Stars: 25
- Strong Yes: 45
- Reviewed: 100

---

### **Phase 4: Export for Fine-Tuning**

#### **4.1 Export Gold Star Examples**

**API Call:**
```bash
curl "http://localhost:4080/v1/aris/icl/examples?philosopher=your@email.com&limit=100" | jq '.'
```

**Response:**
```json
{
  "philosopher": "your@email.com",
  "domain": "candidate_evaluation",
  "conquest_type": "candidate_evaluation",
  "format": "openai",
  "count": 25,
  "examples": [
    {
      "messages": [
        {
          "role": "system",
          "content": "You are an expert recruiter..."
        },
        {
          "role": "user",
          "content": "Evaluate this candidate:\nName: John Doe\n..."
        },
        {
          "role": "assistant",
          "content": "{\"evaluation\": {\"recommendation\": \"Strong Yes\", ...}}"
        }
      ]
    },
    ...
  ]
}
```

**What you get:**
- All conquests marked as VICTORY
- With your edited answers (not original LLM answers)
- In OpenAI fine-tuning format
- Ready to use for model training

#### **4.2 Use for Fine-Tuning**

**Save to file:**
```bash
curl "http://localhost:4080/v1/aris/icl/examples?philosopher=your@email.com&limit=1000" \
  > training_data.jsonl
```

**Use with OpenAI:**
```bash
openai api fine_tunes.create \
  -t training_data.jsonl \
  -m gpt-3.5-turbo
```

**Use with local models:**
```python
from datasets import load_dataset

dataset = load_dataset('json', data_files='training_data.jsonl')
# Use for fine-tuning with Hugging Face, vLLM, etc.
```

---

## 🔌 **API REFERENCE**

### **Curation App (Port 8001)**

#### **GET /table**
Serves the candidate table UI

**Response:** HTML page

---

#### **GET /api/conquests**
List conquests from Aristotle database

**Query Parameters:**
- `conquest_type` - Filter by type (e.g., "candidate_evaluation")
- `status` - Filter by status
- `result` - Filter by result ("VICTORY" for gold stars)
- `limit` - Max results (default 20, max 100)
- `offset` - Pagination offset

**Response:**
```json
{
  "conquests": [...],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

---

#### **PUT /api/conquests/{id}/response**
Update conquest response data (edit answers)

**Request Body:**
```json
{
  "evaluation": {
    "recommendation": "Strong Yes",
    "trajectory_rating": "Exceptional",
    "company_pedigree_rating": "Strong",
    "educational_pedigree_rating": "Good",
    "is_software_engineer": true
  }
}
```

**Response:**
```json
{
  "status": "success",
  "conquest_id": "abc123",
  "updated": true
}
```

---

#### **POST /api/conquests/{id}/mark-victory**
Mark conquest as VICTORY (gold star)

**Query Parameters:**
- `evaluated_by` - Email of evaluator (required)
- `result_notes` - Optional notes

**Response:**
```json
{
  "status": "success",
  "conquest_id": "abc123",
  "result": "VICTORY"
}
```

---

### **vLLM Batch Server (Port 4080)**

#### **GET /v1/aris/conquests**
List conquests from database (backend)

Same as curation app endpoint but direct to database.

---

#### **PUT /v1/aris/conquests/{id}/response**
Update conquest response in database (backend)

**Request Body:**
```json
{
  "evaluation": {...}
}
```

**Database Update:**
```sql
UPDATE conquest_responses
SET data = {...},
    updated_at = NOW()
WHERE conquest_analysis_id = 'abc123'
```

---

#### **POST /v1/aris/sync/victory-to-gold-star**
Mark conquest as VICTORY in database (backend)

**Request Body:**
```json
{
  "conquest_id": "abc123",
  "evaluated_by": "your@email.com",
  "result_notes": "Excellent candidate"
}
```

**Database Updates:**
```sql
UPDATE conquests SET result = 'VICTORY' WHERE id = 'abc123';
UPDATE ml_analysis_ratings SET use_as_example = true WHERE conquest_analysis_id = 'abc123';
```

---

#### **GET /v1/aris/icl/examples**
Export gold star examples for fine-tuning

**Query Parameters:**
- `philosopher` - Email of evaluator (required)
- `domain` - Domain filter (optional)
- `conquest_type` - Type filter (optional)
- `format` - Output format: "openai" or "raw" (default "openai")
- `limit` - Max examples (default 100)

**Response:**
```json
{
  "philosopher": "your@email.com",
  "count": 25,
  "examples": [...]
}
```

---

## 🎨 **UI FEATURES**

### **Color Coding**

**Recommendations:**
- 🟢 Strong Yes - Green badge
- 🔵 Yes - Blue badge
- 🟡 Maybe - Yellow badge
- 🔴 No - Red badge
- 🔴 Strong No - Dark red badge

**Ratings:**
- 🟢 Exceptional - Green badge
- 🔵 Strong - Blue badge
- 🔵 Good - Teal badge
- 🟡 Average - Yellow badge
- 🔴 Weak - Red badge

**Gold Stars:**
- 🟡 Yellow background on row
- 🟡 Gold left border
- ⭐ Icon next to name
- ✅ "Gold Star" button (disabled)

### **Filters**

**Status Filters:**
- All - Show all candidates
- Gold - Show only gold stars
- Strong Yes - Show only "Strong Yes" recommendations
- Pending - Show non-gold-star candidates

**Search:**
- Type candidate name
- Real-time filtering
- Case-insensitive

---

## 🧪 **TESTING THE WORKFLOW**

### **Test 1: View Candidates**
```bash
# Open in browser
open http://localhost:8001/table

# Should see:
# - Stats dashboard
# - Filter controls
# - Table with candidates
# - Edit and Gold Star buttons
```

### **Test 2: Edit Candidate**
```bash
# In browser:
1. Click "✏️ Edit" on first candidate
2. Modal opens
3. Change "Recommendation" to "Strong Yes"
4. Change "Trajectory" to "Exceptional"
5. Click "💾 Save Changes"
6. See success message
7. Modal closes
8. Table refreshes
9. Verify changes in table
```

### **Test 3: Mark Gold Star**
```bash
# In browser:
1. Click "⭐ Gold Star" on a candidate
2. Enter email: test@example.com
3. Click OK
4. Row turns yellow
5. Button changes to "✅ Gold Star"
6. Stats update: Gold Stars count increases
```

### **Test 4: Filter Gold Stars**
```bash
# In browser:
1. Click "Gold" filter button
2. See only yellow rows
3. All have ⭐ icon
4. All have "✅ Gold Star" button
```

### **Test 5: Export ICL**
```bash
curl "http://localhost:4080/v1/aris/icl/examples?philosopher=test@example.com&limit=10" | jq '.'

# Should return:
# - Only gold star conquests
# - With edited answers
# - In OpenAI format
```

---

## ✅ **VERIFICATION CHECKLIST**

Before using in production, verify:

- [ ] All services running (vLLM, Curation App, Aristotle DB)
- [ ] Candidate table accessible at http://localhost:8001/table
- [ ] Can see candidates in table
- [ ] Can click "Edit" and see modal
- [ ] Can change dropdown values
- [ ] Can save changes successfully
- [ ] Changes persist after refresh
- [ ] Can mark gold stars
- [ ] Gold star rows turn yellow
- [ ] Can filter by gold stars
- [ ] Can export ICL examples
- [ ] Exported data includes edited answers

---

## 🎉 **YOU'RE READY!**

**The complete candidate curation workflow is now operational!**

### **Next Steps:**
1. Process candidates in Aristotle
2. Open http://localhost:8001/table
3. Review and edit LLM answers
4. Mark best examples as gold stars
5. Export for model fine-tuning

**Happy curating!** 🚀

