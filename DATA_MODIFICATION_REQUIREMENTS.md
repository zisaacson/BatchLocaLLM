# 📝 Data Modification Requirements - First Principles

**Date:** 2025-10-29  
**Status:** Critical Feature Gap

---

## 🔍 **THE REAL USE CASE**

### **Why Modify Data?**

You're not just **reviewing** LLM outputs - you're **curating training data**. That means:

1. **Fix LLM mistakes** - Model got it wrong, you know better
2. **Improve quality** - Make good examples even better
3. **Standardize format** - Ensure consistency across examples
4. **Add missing info** - LLM missed something important
5. **Remove hallucinations** - LLM made stuff up
6. **Refine reasoning** - Make explanations clearer

### **What Needs to be Editable?**

| Data Type | Current | Should Be Editable? | Why? |
|-----------|---------|---------------------|------|
| **Candidate info** | Read-only | ❌ NO | Source of truth from Aris |
| **Input prompt** | Read-only | ❌ NO | Original request is sacred |
| **LLM output** | Read-only | ✅ **YES!** | Fix mistakes, improve quality |
| **Recommendation** | Read-only | ✅ **YES!** | Override wrong decisions |
| **Reasoning** | Read-only | ✅ **YES!** | Improve explanations |
| **Ratings** | Read-only | ✅ **YES!** | Fix incorrect ratings |
| **Quality score** | Editable (prompts) | ✅ YES | Already works |
| **Tags** | Editable (prompts) | ✅ YES | Already works |
| **Notes** | Editable (prompts) | ✅ YES | Already works |

---

## 🎯 **USER STORIES**

### **Story 1: Fix Wrong Recommendation**

**Scenario:**
- LLM says "Strong Yes" for a candidate
- But you know they're actually not a good fit
- You want to change it to "No" and fix the reasoning

**Current workflow:**
- ❌ Can't edit - data is read-only
- ❌ Have to skip this example
- ❌ Lose a potentially good training example

**Desired workflow:**
- ✅ Click "Edit" button
- ✅ Change recommendation from "Strong Yes" → "No"
- ✅ Update reasoning to explain why
- ✅ Save as corrected training example

---

### **Story 2: Improve Reasoning Quality**

**Scenario:**
- LLM got the right answer ("Strong Yes")
- But the reasoning is weak or generic
- You want to make it more specific and insightful

**Current workflow:**
- ❌ Can't edit reasoning
- ❌ Have to accept mediocre quality
- ❌ Training data won't be as good

**Desired workflow:**
- ✅ Click "Edit" button
- ✅ Enhance the reasoning with specific details
- ✅ Save as high-quality training example

---

### **Story 3: Fix Hallucinations**

**Scenario:**
- LLM says "Great - Stanford PhD"
- But candidate only has a BS from state school
- LLM hallucinated the PhD

**Current workflow:**
- ❌ Can't fix the hallucination
- ❌ Have to skip this example
- ❌ Can't use it for training

**Desired workflow:**
- ✅ Click "Edit" button
- ✅ Remove the hallucinated PhD reference
- ✅ Fix the educational pedigree rating
- ✅ Save as corrected example

---

### **Story 4: Standardize Format**

**Scenario:**
- Some LLM outputs are well-formatted JSON
- Others are messy text with inconsistent structure
- You want to standardize them

**Current workflow:**
- ❌ Can't edit format
- ❌ Have to manually fix later
- ❌ Inconsistent training data

**Desired workflow:**
- ✅ Click "Edit" button
- ✅ Reformat to standard JSON structure
- ✅ Save as standardized example

---

## 💡 **SOLUTION: Inline Editing**

### **Option 1: Edit Mode Toggle** ⭐ RECOMMENDED

**Concept:** Click "Edit" to make fields editable

```
┌─────────────────────────────────────────────────────────┐
│  🤖 LLM EVALUATION                    [Edit] [Save]     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Recommendation: [Strong Yes ▼]  ← Dropdown when editing│
│                                                         │
│  Reasoning:                                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Strong MIT background with top companies...     │   │
│  │ [Editable textarea when in edit mode]           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Educational Pedigree:                                  │
│  Rating: [Great ▼]  ← Dropdown when editing            │
│  Reasoning:                                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ MIT BS+MEng in Computer Science...              │   │
│  │ [Editable textarea when in edit mode]           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [Similar for Company Pedigree, Trajectory, etc.]      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Workflow:**
1. Review evaluation
2. Click **[Edit]** button
3. Fields become editable (textareas, dropdowns)
4. Make changes
5. Click **[Save]** button
6. Changes saved to gold-star data

**Advantages:**
- ✅ Clear edit/view modes
- ✅ Can't accidentally edit
- ✅ Easy to implement
- ✅ Familiar pattern

---

### **Option 2: Always Editable (Contenteditable)**

**Concept:** All fields are always editable, auto-save on blur

```
┌─────────────────────────────────────────────────────────┐
│  🤖 LLM EVALUATION                    [Modified ✓]     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Recommendation: Strong Yes  ← Click to edit           │
│                                                         │
│  Reasoning:                                             │
│  Strong MIT background with top companies...            │
│  ← Click anywhere to edit, auto-saves on blur          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Advantages:**
- ✅ Fastest workflow
- ✅ No mode switching
- ✅ Inline editing

**Disadvantages:**
- ❌ Easy to accidentally edit
- ❌ No clear save point
- ❌ Harder to implement well

---

### **Option 3: Side-by-Side Edit**

**Concept:** Original on left, edited version on right

```
┌──────────────────────┬──────────────────────────────────┐
│ ORIGINAL (LLM)       │ EDITED (YOU)                     │
├──────────────────────┼──────────────────────────────────┤
│ Recommendation:      │ Recommendation:                  │
│ Strong Yes           │ [No ▼]                           │
│                      │                                  │
│ Reasoning:           │ Reasoning:                       │
│ Strong MIT...        │ [Actually weak - only BS...]     │
└──────────────────────┴──────────────────────────────────┘
```

**Advantages:**
- ✅ See original + edited
- ✅ Easy to compare
- ✅ Clear what changed

**Disadvantages:**
- ❌ Takes more screen space
- ❌ More complex UI

---

## 🎯 **RECOMMENDED APPROACH**

### **Option 1: Edit Mode Toggle**

**Why?**
1. **Clear intent** - Explicit edit/save actions
2. **Safe** - Can't accidentally modify
3. **Simple** - Easy to implement
4. **Familiar** - Standard pattern
5. **Undo-friendly** - Can cancel edits

### **Implementation Plan**

#### **Phase 1: Basic Editing (2 hours)**

1. **Add Edit/Save buttons**
   ```html
   <div class="evaluation-header">
     <h2>🤖 LLM Evaluation</h2>
     <button id="edit-btn" onclick="toggleEditMode()">Edit</button>
     <button id="save-btn" onclick="saveEdits()" style="display:none">Save</button>
     <button id="cancel-btn" onclick="cancelEdits()" style="display:none">Cancel</button>
   </div>
   ```

2. **Make fields editable**
   ```javascript
   function toggleEditMode() {
     isEditing = true;
     
     // Show save/cancel, hide edit
     document.getElementById('edit-btn').style.display = 'none';
     document.getElementById('save-btn').style.display = 'inline';
     document.getElementById('cancel-btn').style.display = 'inline';
     
     // Make fields editable
     document.getElementById('recommendation').innerHTML = `
       <select id="recommendation-select">
         <option>Strong Yes</option>
         <option>Yes</option>
         <option>Maybe</option>
         <option>No</option>
         <option>Strong No</option>
       </select>
     `;
     
     document.getElementById('reasoning').innerHTML = `
       <textarea id="reasoning-text">${originalReasoning}</textarea>
     `;
     
     // Similar for other fields...
   }
   ```

3. **Save edited data**
   ```javascript
   async function saveEdits() {
     const editedData = {
       custom_id: currentCandidate.custom_id,
       original_llm_output: currentCandidate.llm_output,
       edited_llm_output: {
         recommendation: document.getElementById('recommendation-select').value,
         reasoning: document.getElementById('reasoning-text').value,
         // ... other fields
       },
       edited_by: 'user',
       edited_at: new Date().toISOString()
     };
     
     // Save to API
     await fetch('/api/gold-star', {
       method: 'POST',
       body: JSON.stringify(editedData)
     });
     
     // Exit edit mode
     toggleEditMode();
   }
   ```

#### **Phase 2: Advanced Features (2 hours)**

1. **Track changes**
   - Show what was modified
   - Highlight edited fields
   - Show edit history

2. **Validation**
   - Ensure required fields filled
   - Validate JSON format
   - Check rating values

3. **Undo/Redo**
   - Revert to original
   - Undo last edit
   - Edit history

---

## 📊 **DATA STRUCTURE**

### **Current (Read-Only)**

```json
{
  "custom_id": "candidate_123",
  "input_prompt": {...},
  "llm_output": "Here is the evaluation...",
  "quality_score": 9,
  "tags": ["excellent"],
  "notes": "Great example"
}
```

### **With Editing Support**

```json
{
  "custom_id": "candidate_123",
  "input_prompt": {...},
  "original_llm_output": "Here is the evaluation...",
  "edited_llm_output": {
    "recommendation": "No",
    "reasoning": "Actually weak - only BS from state school",
    "analysis": {
      "educational_pedigree": {
        "rating": "Average",
        "reasoning": "State school BS, not top-tier"
      },
      "company_pedigree": {
        "rating": "Good",
        "reasoning": "Bloomberg is good but only 1 year"
      },
      "trajectory": {
        "rating": "Average",
        "reasoning": "Too early to tell"
      }
    }
  },
  "is_edited": true,
  "edited_by": "user",
  "edited_at": "2025-10-29T14:30:00Z",
  "quality_score": 9,
  "tags": ["corrected", "hallucination-fix"],
  "notes": "Fixed LLM hallucination about PhD"
}
```

### **Export Format (ICL/Fine-tuning)**

```json
{
  "messages": [
    {"role": "system", "content": "You are evaluating..."},
    {"role": "user", "content": "**Candidate:** Min Thet K..."},
    {"role": "assistant", "content": "EDITED VERSION (not original LLM)"}
  ],
  "metadata": {
    "is_edited": true,
    "original_available": true,
    "quality_score": 9
  }
}
```

---

## 🚀 **INTEGRATION WITH CARD UI**

### **Combined Workflow**

```
1. See candidate card (left: profile, right: evaluation)
2. Press "e" key → Enter edit mode
3. Fields become editable (dropdowns, textareas)
4. Make changes
5. Press "s" key → Save edits
6. Press "9" key → Rate and star
7. Press "n" key → Next candidate
```

**Total time:** ~15-20 seconds per candidate (with editing)  
**Total time:** ~5-10 seconds per candidate (no editing needed)

---

## ✅ **RECOMMENDATION**

### **Build Edit Mode into Card UI**

**Features:**
1. ✅ **Edit button** - Toggle edit mode
2. ✅ **Editable fields** - Recommendation, reasoning, ratings
3. ✅ **Save/Cancel** - Explicit actions
4. ✅ **Track changes** - Store original + edited
5. ✅ **Keyboard shortcuts** - "e" to edit, "s" to save
6. ✅ **Visual indicators** - Show edited fields
7. ✅ **Export both** - Original + edited versions

**Implementation:**
- Phase 1: Basic editing (2 hours)
- Phase 2: Advanced features (2 hours)
- **Total:** 4 hours

**ROI:**
- Can now use 100% of examples (not just perfect ones)
- Higher quality training data
- Fix LLM mistakes instead of discarding
- Standardize format across all examples

---

## 💬 **QUESTIONS**

1. **Should we store both original + edited?** (Recommended: YES)
2. **Should we export both versions?** (Recommended: YES, with flag)
3. **Should we track who edited?** (Recommended: YES)
4. **Should we allow re-editing?** (Recommended: YES)
5. **Should we show edit history?** (Recommended: Later)

**Ready to build editing support?** 🚀


