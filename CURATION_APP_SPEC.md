# 🎯 Gold-Star Curation App - Complete Specification

**Date:** 2025-10-29  
**Status:** Ready to Build

---

## 🎨 **FINAL DESIGN: Card UI + Inline Editing**

### **The Complete Workflow**

```
1. Open curation app
2. See ONE candidate card (full screen)
   - Left: Candidate profile (read-only)
   - Right: LLM evaluation (editable)
3. Review evaluation
4. If needs editing:
   - Press "e" → Edit mode
   - Fix mistakes, improve quality
   - Press "s" → Save edits
5. Press "1-9" → Rate and star
6. Press "n" → Next candidate
7. Repeat
```

**Time per candidate:**
- No editing needed: ~5-10 seconds
- With editing: ~15-30 seconds
- **Average: ~10-15 seconds**

**For 1000 candidates:** ~3-4 hours (vs 10.5 hours current)

---

## 🖼️ **UI MOCKUP**

### **View Mode (Default)**

```
┌─────────────────────────────────────────────────────────────────┐
│  Gold-Star Curation                    23/5000 (8 ⭐, 15 skip)  │
│  [Filter ▼] [Search] [Help ?]                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────┐  ┌───────────────────────────┐   │
│  │ 👤 CANDIDATE             │  │ 🤖 LLM EVALUATION         │   │
│  │                          │  │                  [Edit]   │   │
│  │ Min Thet K               │  │                           │   │
│  │ Software Engineer        │  │ Recommendation:           │   │
│  │ Bloomberg                │  │ ⭐ STRONG YES             │   │
│  │ New York, NY             │  │                           │   │
│  │                          │  │ Reasoning:                │   │
│  │ 💼 WORK HISTORY          │  │ Strong MIT background     │   │
│  │ • Bloomberg (2023-now)   │  │ with experience at top    │   │
│  │ • Microsoft (2021-2022)  │  │ companies like Bloomberg  │   │
│  │ • MIT TA (2020-2023)     │  │ and Microsoft...          │   │
│  │ • Dexai Robotics (2018)  │  │                           │   │
│  │                          │  │ 📊 ANALYSIS               │   │
│  │ 🎓 EDUCATION             │  │                           │   │
│  │ • MIT BS CS              │  │ Educational Pedigree:     │   │
│  │ • MIT MEng CS            │  │ ⭐ GREAT                  │   │
│  │                          │  │ MIT BS+MEng in CS         │   │
│  │                          │  │                           │   │
│  │                          │  │ Company Pedigree:         │   │
│  │                          │  │ ⭐ GREAT                  │   │
│  │                          │  │ Bloomberg, Microsoft      │   │
│  │                          │  │                           │   │
│  │                          │  │ Trajectory:               │   │
│  │                          │  │ ⭐ GREAT                  │   │
│  │                          │  │ Rapid career growth       │   │
│  └──────────────────────────┘  └───────────────────────────┘   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Press 1-9 to rate  │  E: Edit  │  N: Next  │  S: Skip    │ │
│  │  P: Prev  │  U: Undo  │  F: Filter  │  ?: Help            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 23/5000 (0.46%)│
└─────────────────────────────────────────────────────────────────┘
```

### **Edit Mode**

```
┌─────────────────────────────────────────────────────────────────┐
│  Gold-Star Curation                    23/5000 (8 ⭐, 15 skip)  │
│  [Filter ▼] [Search] [Help ?]                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────┐  ┌───────────────────────────┐   │
│  │ 👤 CANDIDATE             │  │ 🤖 LLM EVALUATION         │   │
│  │                          │  │    [Save] [Cancel]        │   │
│  │ Min Thet K               │  │                           │   │
│  │ Software Engineer        │  │ Recommendation:           │   │
│  │ Bloomberg                │  │ [Strong Yes ▼]            │   │
│  │ New York, NY             │  │                           │   │
│  │                          │  │ Reasoning:                │   │
│  │ 💼 WORK HISTORY          │  │ ┌───────────────────────┐ │   │
│  │ • Bloomberg (2023-now)   │  │ │Strong MIT background  │ │   │
│  │ • Microsoft (2021-2022)  │  │ │with experience at top │ │   │
│  │ • MIT TA (2020-2023)     │  │ │companies...           │ │   │
│  │ • Dexai Robotics (2018)  │  │ └───────────────────────┘ │   │
│  │                          │  │                           │   │
│  │ 🎓 EDUCATION             │  │ 📊 ANALYSIS               │   │
│  │ • MIT BS CS              │  │                           │   │
│  │ • MIT MEng CS            │  │ Educational Pedigree:     │   │
│  │                          │  │ [Great ▼]                 │   │
│  │                          │  │ ┌───────────────────────┐ │   │
│  │                          │  │ │MIT BS+MEng in CS      │ │   │
│  │                          │  │ └───────────────────────┘ │   │
│  │                          │  │                           │   │
│  │                          │  │ Company Pedigree:         │   │
│  │                          │  │ [Great ▼]                 │   │
│  │                          │  │ ┌───────────────────────┐ │   │
│  │                          │  │ │Bloomberg, Microsoft   │ │   │
│  │                          │  │ └───────────────────────┘ │   │
│  └──────────────────────────┘  └───────────────────────────┘   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  S: Save edits  │  ESC: Cancel  │  Modified ✏️            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 23/5000 (0.46%)│
└─────────────────────────────────────────────────────────────────┘
```

---

## ⌨️ **KEYBOARD SHORTCUTS**

### **Navigation**
- `n` or `→` - Next candidate
- `p` or `←` - Previous candidate
- `s` - Skip (not good enough)
- `u` - Undo last action
- `f` - Open filter dialog
- `?` - Show help overlay

### **Rating**
- `1-9` - Rate and star (auto-advance to next)
- `0` - Unstar current

### **Editing**
- `e` - Enter edit mode
- `s` (in edit mode) - Save edits
- `ESC` - Cancel edits

### **Filtering**
- `a` - Show all
- `r` - Show unreviewed only
- `t` - Show starred only
- `k` - Show skipped only

---

## 🗂️ **STATE MANAGEMENT**

```javascript
const state = {
  // Data
  candidates: [],              // All candidates from batch file
  results: {},                 // Model results by custom_id
  
  // Navigation
  currentIndex: 0,             // Current position
  filteredIndices: [],         // Filtered candidate indices
  
  // Review state
  reviewed: new Set(),         // custom_ids of reviewed candidates
  starred: new Map(),          // custom_id → {rating, tags, notes, edited_data}
  skipped: new Set(),          // custom_ids of skipped candidates
  
  // Edit state
  isEditing: false,            // Currently in edit mode?
  originalData: null,          // Original data before editing
  editedData: null,            // Current edited data
  
  // History (for undo)
  history: [],                 // [{action, data, timestamp}]
  
  // Filters
  filter: 'all',               // 'all' | 'unreviewed' | 'starred' | 'skipped'
  searchQuery: ''              // Search by candidate name
};
```

---

## 📊 **DATA STRUCTURES**

### **Starred Example (with editing)**

```json
{
  "custom_id": "candidate_123",
  "candidate_name": "Min Thet K (Software Engineer at Bloomberg)",
  
  "input_prompt": {
    "system": "You are evaluating a candidate...",
    "user": "**Candidate:** Min Thet K..."
  },
  
  "original_llm_output": "Here is the evaluation of Min Thet K:\n\n```json\n{...}",
  
  "edited_llm_output": {
    "recommendation": "No",
    "reasoning": "Actually weak - only 1 year at Bloomberg",
    "analysis": {
      "educational_pedigree": {
        "rating": "Great",
        "reasoning": "MIT BS+MEng in CS"
      },
      "company_pedigree": {
        "rating": "Good",
        "reasoning": "Bloomberg is good but only 1 year"
      },
      "trajectory": {
        "rating": "Average",
        "reasoning": "Too early to tell with only 1 year"
      },
      "is_software_engineer": {
        "value": true,
        "reasoning": "Software Engineer at Bloomberg"
      }
    }
  },
  
  "is_edited": true,
  "edited_by": "user",
  "edited_at": "2025-10-29T14:30:00Z",
  
  "quality_score": 8,
  "tags": ["corrected", "good-example"],
  "notes": "Fixed overly optimistic rating",
  
  "model": "gemma3-4b-5000-2025",
  "starred_by": "user",
  "starred_at": "2025-10-29T14:35:00Z"
}
```

### **Export Format (ICL)**

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are evaluating a candidate profile..."
    },
    {
      "role": "user",
      "content": "**Candidate:** Min Thet K\n**Current Role:** Software Engineer..."
    },
    {
      "role": "assistant",
      "content": "Here is the evaluation of Min Thet K:\n\n```json\n{\n  \"recommendation\": \"No\",\n  \"reasoning\": \"Actually weak - only 1 year at Bloomberg\",\n  ..."
    }
  ],
  "metadata": {
    "custom_id": "candidate_123",
    "candidate_name": "Min Thet K",
    "quality_score": 8,
    "tags": ["corrected", "good-example"],
    "is_edited": true,
    "model": "gemma3-4b-5000-2025"
  }
}
```

**Note:** Exports use the **edited version** if available, otherwise original LLM output.

---

## 🔧 **API ENDPOINTS**

### **POST /api/gold-star** (Enhanced)

**Request:**
```json
{
  "custom_id": "candidate_123",
  "input_prompt": {...},
  "original_llm_output": "...",
  "edited_llm_output": {...},  // Optional - only if edited
  "is_edited": true,
  "edited_by": "user",
  "edited_at": "2025-10-29T14:30:00Z",
  "quality_score": 8,
  "tags": ["corrected"],
  "notes": "Fixed rating"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Example starred successfully",
  "is_duplicate": false
}
```

### **GET /api/gold-star**

Returns all starred examples (same as before).

### **GET /api/export-gold-star**

**Query params:**
- `format` - 'icl' | 'finetuning' | 'raw'
- `min_quality` - Minimum quality score (default: 9 for ICL, 8 for finetuning)
- `include_edited_only` - true | false (default: false)
- `include_original` - true | false (default: false)

**Response:** JSONL file with formatted examples

---

## 🎨 **IMPLEMENTATION PLAN**

### **Phase 1: Card UI (3 hours)**

1. **Create `curation_app.html`**
   - Single-card layout
   - Left: Candidate profile
   - Right: LLM evaluation
   - Navigation buttons
   - Progress bar

2. **Load data**
   - Fetch batch file (candidates)
   - Fetch results file (LLM outputs)
   - Join by custom_id

3. **Navigation**
   - Next/prev buttons
   - Keyboard shortcuts (n/p)
   - Progress tracking

### **Phase 2: Rating & Starring (1 hour)**

1. **Rating buttons**
   - 1-9 number buttons
   - Keyboard shortcuts (1-9)
   - Auto-advance after rating

2. **Skip functionality**
   - Skip button
   - Keyboard shortcut (s)
   - Track skipped candidates

3. **Save to API**
   - POST to /api/gold-star
   - Update UI state
   - Show confirmation

### **Phase 3: Editing (2 hours)**

1. **Edit mode toggle**
   - Edit button
   - Keyboard shortcut (e)
   - Show/hide save/cancel buttons

2. **Editable fields**
   - Recommendation dropdown
   - Reasoning textarea
   - Rating dropdowns
   - Reasoning textareas for each criterion

3. **Save/cancel**
   - Save button (keyboard: s)
   - Cancel button (keyboard: ESC)
   - Revert to original on cancel

### **Phase 4: Filtering & Search (1 hour)**

1. **Filter dropdown**
   - All / Unreviewed / Starred / Skipped
   - Keyboard shortcuts (a/r/t/k)
   - Update filtered indices

2. **Search**
   - Search by candidate name
   - Real-time filtering
   - Clear search button

3. **Progress tracking**
   - Update counts
   - Update progress bar
   - Show filter status

### **Phase 5: Polish (1 hour)**

1. **Undo/redo**
   - Undo last action (u)
   - History tracking
   - Undo button

2. **Help overlay**
   - Keyboard shortcuts reference
   - Show on "?" key
   - Close on ESC

3. **Visual polish**
   - Smooth transitions
   - Loading states
   - Error handling

**Total time:** 8 hours

---

## ✅ **SUCCESS CRITERIA**

| Criteria | Target | How to Measure |
|----------|--------|----------------|
| Speed | <15s per candidate | Time 100 candidates |
| Ease of use | 9/10 rating | User feedback |
| Edit success | 100% save rate | No data loss |
| Keyboard efficiency | 90% keyboard-only | Track mouse usage |
| Data quality | 100% correct format | Validate exports |

---

## 🚀 **NEXT STEPS**

1. ✅ Get user approval on design
2. ⬜ Create `curation_app.html`
3. ⬜ Implement Phase 1 (Card UI)
4. ⬜ Implement Phase 2 (Rating)
5. ⬜ Implement Phase 3 (Editing)
6. ⬜ Implement Phase 4 (Filtering)
7. ⬜ Implement Phase 5 (Polish)
8. ⬜ Test with real data
9. ⬜ Ship!

**Ready to build?** 🚀


