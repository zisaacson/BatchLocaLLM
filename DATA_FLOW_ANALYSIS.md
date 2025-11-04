# 🔍 DATA FLOW ANALYSIS - COMPLETE SYSTEM TRACE

**Date**: November 4, 2025  
**Status**: ⚠️ **CRITICAL ISSUES FOUND**

---

## 🎯 USER'S QUESTION

> "Review our user prompt, trace how data flows, does it work? Is Label Studio set up correctly? Is our curation app able to see the questions that we ask and then able to modify the answers?"

---

## ❌ CRITICAL PROBLEMS IDENTIFIED

### **Problem 1: MISSING CONQUEST DATA IN LABEL STUDIO** 🚨

**What's Wrong:**
- vLLM batch server sends results to Label Studio via `LabelStudioHandler`
- The handler extracts: `custom_id`, `batch_id`, `input_messages`, `llm_response`, `model`
- **BUT IT DOES NOT EXTRACT THE ACTUAL CONQUEST DATA** (candidate name, role, education, work history, etc.)

**Current Code** (`core/result_handlers/label_studio.py` lines 124-131):
```python
task_data = {
    "custom_id": custom_id,
    "batch_id": batch_id,
    "input_messages": input_messages,  # ❌ Raw messages array
    "llm_response": llm_response,      # ❌ Raw LLM text
    "model": body.get('model', 'unknown'),
    "schema_type": metadata.get('schema_type', 'generic'),
}
```

**What's Missing:**
- Candidate name
- Current role
- Location
- Work history
- Education
- System prompt
- User prompt (the questions being asked)

**Impact:**
- ❌ Curation UI cannot display candidate information
- ❌ Users cannot see what questions were asked
- ❌ Users cannot see the structured data being evaluated
- ❌ Gold star sync to Aristotle will fail (missing `conquest_id`, `philosopher`, `domain`)

---

### **Problem 2: CONQUEST DATA NOT PARSED FROM MESSAGES** 🚨

**What's Wrong:**
- The batch results contain conquest data in the `messages` array
- The `LabelStudioHandler` does NOT parse this data
- The curation app has a `_parse_candidate_from_messages()` function but it's ONLY used in bulk import, NOT in the automatic import

**Current Flow:**
```
vLLM Batch Job Completes
    ↓
Worker calls auto_import_to_curation()
    ↓
LabelStudioHandler.handle() is called
    ↓
Creates tasks with RAW messages array ❌
    ↓
Label Studio stores incomplete data ❌
    ↓
Curation UI cannot display properly ❌
```

**What Should Happen:**
```
vLLM Batch Job Completes
    ↓
Worker calls auto_import_to_curation()
    ↓
LabelStudioHandler.handle() is called
    ↓
PARSE messages to extract conquest data ✅
    ↓
Create tasks with structured data ✅
    ↓
Label Studio stores complete data ✅
    ↓
Curation UI displays properly ✅
```

---

### **Problem 3: SCHEMA TYPE NOT PROPERLY USED** 🚨

**What's Wrong:**
- The `schema_type` is stored in task metadata
- But the conquest schema (from `conquest_schemas/candidate_evaluation.json`) is NOT used to structure the data
- The schema defines what questions are asked, but this is NOT visible in Label Studio tasks

**Schema Defines** (`candidate_evaluation.json`):
- Data sources: name, role, location, education, work_history, resume, linkedin
- Questions: recommendation, educational_pedigree, company_pedigree, trajectory, is_software_engineer, notes

**But Label Studio Tasks Only Have:**
- custom_id
- batch_id
- input_messages (raw array)
- llm_response (raw text)
- model
- schema_type (just a string, not the actual schema)

---

### **Problem 4: BIDIRECTIONAL SYNC WILL FAIL** 🚨

**What's Wrong:**
- The bidirectional sync code expects tasks to have:
  - `conquest_id` in task data
  - `philosopher` in task data
  - `domain` in task data
- But the `LabelStudioHandler` does NOT set these fields!

**Current Webhook Handler** (`core/batch_app/api_server.py` lines 3920-3925):
```python
conquest_id = task_data.get('conquest_id') or task_data.get('id')
philosopher = task_data.get('philosopher', 'unknown@example.com')
domain = task_data.get('domain', 'default')

if conquest_id:
    # Sync to Aristotle
```

**Problem:**
- `task_data.get('conquest_id')` → **WILL BE NONE** ❌
- `task_data.get('philosopher')` → **WILL BE 'unknown@example.com'** ❌
- `task_data.get('domain')` → **WILL BE 'default'** ❌

**Impact:**
- ❌ Gold stars marked in Label Studio will NOT sync to Aristotle
- ❌ The sync will fail silently or use wrong data
- ❌ The entire bidirectional sync system is broken

---

## ✅ WHAT WORKS

### **1. Conquest Schemas Are Well-Defined** ✅
- `integrations/aris/conquest_schemas/candidate_evaluation.json` is excellent
- Defines data sources, questions, rendering, export formats
- Has ICL and fine-tuning export templates

### **2. Curation API Has Parsing Logic** ✅
- `_parse_candidate_from_messages()` function exists
- Can extract candidate data from messages array
- Used in bulk import endpoint

### **3. Bidirectional Sync Code Is Correct** ✅
- Webhook handler logic is correct
- Aristotle database integration is correct
- Sync functions work properly
- **BUT they depend on data that doesn't exist in tasks!**

### **4. Label Studio Client Works** ✅
- Can create tasks
- Can create predictions
- Can update task metadata
- Can send webhooks

---

## 🔧 HOW TO FIX

### **Fix 1: Update LabelStudioHandler to Parse Conquest Data**

**File**: `core/result_handlers/label_studio.py`

**Change** (lines 104-154):
```python
# Convert results to Label Studio tasks
tasks = []
for result in results:
    # Skip failed results
    if 'error' in result:
        continue

    # Extract data
    custom_id = result.get('custom_id', 'unknown')
    response = result.get('response', {})
    body = response.get('body', {})

    # Get input messages
    input_messages = result.get('input', {}).get('messages', [])

    # Get LLM response text
    llm_response = body.get('choices', [{}])[0].get('message', {}).get('content', '')

    # ✅ NEW: Parse conquest data from messages
    conquest_data = self._parse_conquest_from_messages(input_messages, metadata.get('schema_type', 'generic'))

    # ✅ NEW: Extract conquest metadata
    conquest_id = metadata.get('conquest_id') or custom_id
    philosopher = metadata.get('philosopher', 'unknown@example.com')
    domain = metadata.get('domain', 'default')

    # Build task data with STRUCTURED conquest data
    task_data = {
        "custom_id": custom_id,
        "batch_id": batch_id,
        "conquest_id": conquest_id,  # ✅ ADDED
        "philosopher": philosopher,   # ✅ ADDED
        "domain": domain,             # ✅ ADDED
        "schema_type": metadata.get('schema_type', 'generic'),
        "model": body.get('model', 'unknown'),
        
        # ✅ ADDED: Structured conquest data
        **conquest_data,  # name, role, location, work_history, education, etc.
        
        # ✅ ADDED: Prompts for training
        "system_prompt": conquest_data.get('system_prompt', ''),
        "user_prompt": conquest_data.get('user_prompt', ''),
        
        # LLM response
        "llm_response": llm_response,
    }
```

**Add New Method**:
```python
def _parse_conquest_from_messages(self, messages: list, schema_type: str) -> dict:
    """
    Parse conquest data from messages array.
    
    Extracts structured data based on schema type.
    """
    result = {
        "name": "Unknown",
        "role": "",
        "location": "",
        "work_history": [],
        "education": [],
        "system_prompt": "",
        "user_prompt": ""
    }
    
    if not messages or len(messages) < 2:
        return result
    
    # Extract system prompt
    if messages[0].get("role") == "system":
        result["system_prompt"] = messages[0].get("content", "")
    
    # Extract user prompt
    if messages[1].get("role") == "user":
        user_content = messages[1].get("content", "")
        result["user_prompt"] = user_content
        
        # Parse candidate data from user prompt
        # (Use regex or structured parsing based on schema)
        # For candidate_evaluation schema:
        if schema_type == "candidate_evaluation":
            # Extract name
            name_match = re.search(r"Name:\s*(.+?)(?:\n|$)", user_content)
            if name_match:
                result["name"] = name_match.group(1).strip()
            
            # Extract role
            role_match = re.search(r"(?:Current Role|Role):\s*(.+?)(?:\n|$)", user_content)
            if role_match:
                result["role"] = role_match.group(1).strip()
            
            # Extract location
            location_match = re.search(r"Location:\s*(.+?)(?:\n|$)", user_content)
            if location_match:
                result["location"] = location_match.group(1).strip()
            
            # Extract work history (simplified)
            work_match = re.search(r"Work History:\s*(.+?)(?:\n\n|Education:|$)", user_content, re.DOTALL)
            if work_match:
                work_text = work_match.group(1).strip()
                # Parse into structured format
                result["work_history"] = work_text.split("\n")
            
            # Extract education (simplified)
            edu_match = re.search(r"Education:\s*(.+?)(?:\n\n|$)", user_content, re.DOTALL)
            if edu_match:
                edu_text = edu_match.group(1).strip()
                result["education"] = edu_text.split("\n")
    
    return result
```

---

### **Fix 2: Pass Conquest Metadata to LabelStudioHandler**

**File**: `core/batch_app/worker.py`

**Change** (lines 756-765):
```python
# Prepare metadata
metadata = json.loads(job.metadata_json) if job.metadata_json else {}
metadata['label_studio_project_id'] = settings.LABEL_STUDIO_PROJECT_ID

# ✅ ADDED: Extract conquest metadata from job
metadata['schema_type'] = metadata.get('conquest_type', 'generic')
metadata['conquest_id'] = job.batch_id  # or extract from first result
metadata['philosopher'] = metadata.get('philosopher', 'unknown@example.com')
metadata['domain'] = metadata.get('domain', 'default')

# completed_at is a Unix timestamp (int), not datetime
if job.completed_at:
    from datetime import datetime, timezone
    metadata['completed_at'] = datetime.fromtimestamp(job.completed_at, tz=timezone.utc).isoformat()
```

---

### **Fix 3: Update Batch Job Creation to Include Conquest Metadata**

**File**: `core/batch_app/api_server.py`

**Change** (batch job creation endpoint):
```python
# When creating batch job, extract conquest metadata from input file
# and store in job.metadata_json

metadata = {
    "conquest_type": "candidate_evaluation",  # Extract from request or first line
    "philosopher": "user@example.com",        # Extract from auth or request
    "domain": "software_engineering",         # Extract from request
    # ... other metadata
}

job.metadata_json = json.dumps(metadata)
```

---

## 📊 SUMMARY

### **Current State**: ❌ **BROKEN**

1. ❌ Conquest data NOT extracted from messages
2. ❌ Label Studio tasks have incomplete data
3. ❌ Curation UI cannot display questions or answers properly
4. ❌ Bidirectional sync will fail (missing conquest_id, philosopher, domain)
5. ❌ Gold stars cannot sync to Aristotle

### **After Fixes**: ✅ **WORKING**

1. ✅ Conquest data extracted and structured
2. ✅ Label Studio tasks have complete data
3. ✅ Curation UI can display questions and answers
4. ✅ Bidirectional sync works (has conquest_id, philosopher, domain)
5. ✅ Gold stars sync to Aristotle correctly

---

## 🚀 NEXT STEPS

1. **Implement Fix 1**: Update `LabelStudioHandler` to parse conquest data
2. **Implement Fix 2**: Pass conquest metadata to handler
3. **Implement Fix 3**: Store conquest metadata in batch jobs
4. **Test End-to-End**: Create batch job → Process → View in curation UI → Mark gold star → Verify sync
5. **Update Documentation**: Document the complete data flow

---

**BOTTOM LINE**: The bidirectional sync code is correct, but it depends on data that doesn't exist in Label Studio tasks. We need to fix the data import pipeline first.

