# Web Viewer System Audit & Standardization Plan

## 📊 Current State Analysis

### Existing HTML Viewers

| File | Purpose | Status | Issues |
|------|---------|--------|--------|
| **index.html** | Main dashboard - shows datasets and models | ✅ Working | Dark theme, no JSON parsing |
| **table_view.html** | Table comparison of models for a dataset | ✅ Updated | Now has light theme + JSON parsing |
| **compare_results.html** | Side-by-side comparison for single candidate | ⚠️ Needs update | Dark theme, no JSON parsing |
| **compare_models.html** | Model comparison dashboard | ⚠️ Needs update | Dark theme, no JSON parsing |
| **compare_models_v2.html** | Alternative comparison view | ❓ Unknown | Duplicate? |
| **view_results.html** | Single model result viewer | ⚠️ Needs update | Dark theme, no JSON parsing |
| **view_results_improved.html** | NEW - improved single model viewer | ✅ New | Light theme + JSON parsing (not integrated) |

### Backend Servers

| File | Purpose | Status | Issues |
|------|---------|--------|--------|
| **serve_results.py** | Original server with all API endpoints | ✅ Working | Complete API |
| **serve_results_fixed.py** | Fixed GPU status tracking | ✅ Working | Better GPU monitoring |

**Recommendation**: Merge improvements from `serve_results_fixed.py` into `serve_results.py` and deprecate the "fixed" version.

### API Endpoints

| Endpoint | Purpose | Used By |
|----------|---------|---------|
| `/api/discover` | Find all datasets and their results | index.html, table_view.html, compare_results.html |
| `/api/results?model=<file>` | Load specific model results | All viewers |
| `/api/candidates?dataset=<file>` | Load original candidate data | compare_results.html, table_view.html |
| `/api/metadata` | Load evaluation criteria metadata | compare_models.html |
| `/api/gpu` | Get GPU status and running jobs | index.html |

### Data Flow

```
User Flow:
1. index.html (Dashboard) 
   ↓ Click dataset
2. table_view.html?dataset=batch_5k.jsonl (Table comparison)
   ↓ Can navigate to
3. compare_results.html (Single candidate comparison)
   OR
4. view_results.html (Single model results)
```

## 🎯 Standardization Goals

### 1. **Unified Design System**

**Current Issues:**
- Mix of dark theme (index.html, compare_results.html, view_results.html) and light theme (table_view.html)
- Inconsistent color schemes
- Different button styles, badges, and UI components

**Solution:**
- Adopt the new **light gradient theme** from table_view.html across all viewers
- Create shared CSS variables for colors, spacing, typography
- Standardize all UI components (buttons, badges, cards, tables)

### 2. **Consistent JSON Parsing**

**Current Issues:**
- Most viewers show raw LLM response text
- Only table_view.html parses the structured JSON evaluation
- No extraction of candidate names from prompts

**Solution:**
- Create shared JavaScript parsing functions:
  - `parseEvaluation(response)` - Extract JSON from markdown code blocks
  - `extractCandidateName(candidate)` - Parse candidate name from prompt
  - `extractModelName(filename)` - Standardize model name display
  - `getRatingClass(rating)` - Color coding for ratings
  - `getRecommendationClass(rec)` - Color coding for recommendations

### 3. **Evaluation Criteria Display**

**Current Issues:**
- Viewers don't show the 4 evaluation criteria:
  - Educational Pedigree (rating + reasoning)
  - Company Pedigree (rating + reasoning)
  - Trajectory (rating + reasoning)
  - Is Software Engineer (Yes/No + reasoning)

**Solution:**
- All viewers should display structured evaluation fields
- Use consistent formatting with icons:
  - 🎓 Educational Pedigree
  - 🏢 Company Pedigree
  - 📈 Trajectory
  - 💻 Is Software Engineer

### 4. **File Organization**

**Current Issues:**
- Result files scattered across root directory and benchmarks/raw/
- Duplicate viewers (compare_models.html vs compare_models_v2.html)
- Temporary/test files mixed with production files

**Proposed Structure:**
```
/viewers/
  ├── index.html              # Main dashboard
  ├── table_view.html         # Table comparison
  ├── compare_results.html    # Single candidate comparison
  └── view_results.html       # Single model viewer

/api/
  └── serve_results.py        # Unified server

/benchmarks/
  ├── raw/                    # Raw JSONL result files
  ├── reports/                # Markdown reports
  └── metadata/               # Benchmark metadata

/batch_data/                  # Input batch files
  ├── batch_5k.jsonl
  ├── batch_50k.jsonl
  └── ...

/static/
  ├── css/
  │   └── shared.css          # Shared styles
  └── js/
      └── parsers.js          # Shared parsing functions
```

## 🔧 Implementation Plan

### Phase 1: Create Shared Components (Priority: HIGH)

**Files to create:**
1. `static/css/shared.css` - Unified design system
2. `static/js/parsers.js` - Shared parsing functions

**Design System Variables:**
```css
:root {
  /* Colors */
  --bg-gradient: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  --primary-color: #667eea;
  --secondary-color: #764ba2;
  --text-primary: #2c3e50;
  --text-secondary: #6a737d;
  
  /* Ratings */
  --rating-great: linear-gradient(135deg, #4caf50 0%, #66bb6a 100%);
  --rating-good: linear-gradient(135deg, #2196f3 0%, #42a5f5 100%);
  --rating-average: linear-gradient(135deg, #ff9800 0%, #ffa726 100%);
  --rating-weak: linear-gradient(135deg, #f44336 0%, #ef5350 100%);
  --rating-none: linear-gradient(135deg, #9e9e9e 0%, #bdbdbd 100%);
  
  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  
  /* Border radius */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 20px;
}
```

### Phase 2: Update All Viewers (Priority: HIGH)

**Update order:**
1. ✅ **table_view.html** - Already updated with light theme + JSON parsing
2. **index.html** - Update to light theme, keep dataset discovery
3. **compare_results.html** - Update to light theme + add JSON parsing
4. **view_results.html** - Update to light theme + add JSON parsing
5. **compare_models.html** - Update to light theme + add JSON parsing

**Delete:**
- `compare_models_v2.html` (duplicate)
- `view_results_improved.html` (merge into view_results.html)

### Phase 3: Enhance Features (Priority: MEDIUM)

**Add to all viewers:**
1. Candidate name extraction from prompts
2. Structured display of all 4 evaluation criteria
3. Overall reasoning display
4. Token usage statistics
5. Search/filter functionality
6. Export to CSV/JSON

### Phase 4: Backend Consolidation (Priority: LOW)

**Merge servers:**
1. Combine `serve_results.py` + `serve_results_fixed.py`
2. Add `/api/discover` endpoint to find datasets automatically
3. Add caching for better performance
4. Add error handling and logging

### Phase 5: File Organization (Priority: LOW)

**Reorganize:**
1. Move viewers to `/viewers/` directory
2. Move result files to `/benchmarks/raw/`
3. Move batch input files to `/batch_data/`
4. Create `/static/` for shared assets
5. Update all file paths in code

## 📋 Detailed Task List

### Immediate Actions (Do Now)

- [ ] Create `static/css/shared.css` with design system
- [ ] Create `static/js/parsers.js` with shared functions
- [ ] Update `index.html` to light theme
- [ ] Update `compare_results.html` to light theme + JSON parsing
- [ ] Update `view_results.html` to light theme + JSON parsing
- [ ] Update `compare_models.html` to light theme + JSON parsing
- [ ] Delete `compare_models_v2.html`
- [ ] Delete `view_results_improved.html` (merge into view_results.html)

### Short-term (This Week)

- [ ] Add candidate name extraction to all viewers
- [ ] Add structured evaluation criteria display to all viewers
- [ ] Test all viewers with different datasets
- [ ] Add export functionality (CSV/JSON)
- [ ] Improve search/filter across all viewers

### Long-term (Next Sprint)

- [ ] Merge serve_results.py + serve_results_fixed.py
- [ ] Reorganize file structure
- [ ] Add caching to API endpoints
- [ ] Add automated tests for viewers
- [ ] Create user documentation

## 🎨 Design Mockup

### Standardized Card Layout

```
┌─────────────────────────────────────────────────────┐
│ 🎯 Candidate Name                    [Strong Yes]   │
│ Software Engineer at Google                         │
│ ID: abc-123-def                                     │
├─────────────────────────────────────────────────────┤
│ Overall Reasoning:                                  │
│ Strong pedigree with MIT CS degree and Google       │
│ experience. Rapid promotion trajectory.             │
├─────────────────────────────────────────────────────┤
│ 🎓 Educational Pedigree    [Great]                  │
│ MIT CS degree is top-tier signal...                 │
│                                                     │
│ 🏢 Company Pedigree        [Good]                   │
│ Google is tier-1 tech company...                    │
│                                                     │
│ 📈 Trajectory              [Great]                  │
│ Promoted to Senior in 4 years...                    │
│                                                     │
│ 💻 Is Software Engineer    [Yes]                    │
│ Titles confirm SWE focus...                         │
└─────────────────────────────────────────────────────┘
```

## 🚀 Success Metrics

**After standardization, we should have:**

1. ✅ **Consistent UX** - All viewers use same light theme and design system
2. ✅ **Structured Data** - All viewers parse and display evaluation criteria
3. ✅ **Easy Navigation** - Clear flow from dashboard → table → details
4. ✅ **Better Insights** - Can compare models across all 4 evaluation dimensions
5. ✅ **Maintainable Code** - Shared CSS/JS reduces duplication
6. ✅ **Clean Organization** - Files organized by purpose

## 📝 Notes

- Keep backward compatibility during migration
- Test with all existing datasets (batch_5k.jsonl, etc.)
- Ensure mobile responsiveness
- Add loading states and error handling
- Document all API endpoints

