# Web UI Evolution Analysis - vLLM Batch Server

## Executive Summary

**You're absolutely right** - we've lost significant functionality through multiple UI rewrites. 

**Total Features Lost: ~30**  
**Features Restored: ~10**  
**Restoration Rate: 33%**

The "enterprise cleanup" (commit 4aff072) deleted **11 HTML files totaling ~7,000 lines** of feature-rich UI code. While the new UIs are cleaner and more maintainable, we lost critical power-user features.

---

## Timeline of Major UI Changes

### Phase 1: Original Feature-Rich UIs (Pre-Oct 30, 2025)
**Deleted in commit 4aff072 "enterprise cleanup"**

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `curation_app.html` | 1,774 | Gold-star curation with quality ratings | ⚠️ Partially restored |
| `table_view.html` | 992 | Advanced table view with candidate parsing | ❌ Not restored |
| `benchmarks.html` | 748 | Multi-run benchmark comparison | ⚠️ Partially restored |
| `api_docs.html` | 486 | Interactive API documentation | ❌ Not restored |
| `dashboard.html` | 474 | System health dashboard | ⚠️ Partially restored |
| `compare_models.html` | 607 | Model comparison UI | ❌ Not restored |
| `compare_results.html` | 416 | Results comparison | ❌ Not restored |
| `view_results.html` | 350 | Results viewer | ❌ Not restored |
| `submit_batch.html` | 354 | Batch submission form | ❌ Not restored |
| `monitor.html` | 236 | Real-time job monitoring | ⚠️ Partially restored |
| `index.html` | 394 | Original landing page | ✅ Replaced |

**Total deleted: ~6,831 lines of UI code**

### Phase 2: Conquest-Focused UI (Oct 30 - Nov 2025)
**Created in commit 4aff072, deleted in commit c18ec22**

- `static/conquest-viewer.html` (390 lines) - Aris-specific conquest viewer
- **Deleted during OSS genericization** to remove Aris dependencies

### Phase 3: OSS Generic UIs (Nov 2025)
**Created during OSS preparation**

- ✅ `static/index.html` - New landing page
- ✅ `static/model-management.html` - Model installation/testing
- ✅ `static/workbench.html` - Dataset workbench
- ✅ `static/fine-tuning.html` - Fine-tuning interface
- ✅ `static/queue-monitor.html` - Queue monitoring
- ✅ `static/benchmark-runner.html` - Benchmark runner
- ✅ `static/settings.html` - System settings

### Phase 4: Enhanced Features (Today - Dec 2025)
**Just created**

- ✅ `static/metrics.html` - Metrics dashboard with charts
- ✅ `static/enhanced-workbench.html` - Advanced workbench with keyboard shortcuts
- ✅ `static/curation.html` - Data curation UI

---

## Critical Missing Features

### 🔴 High Priority (Should Restore ASAP)

#### 1. Quality Rating System (from curation_app.html)
**Impact: Critical for training data curation**

Lost features:
- ❌ 1-10 star rating scale for each task
- ❌ Good/Bad sample categorization
- ❌ Export with quality thresholds:
  - ICL examples: quality ≥ 9
  - Fine-tuning data: quality ≥ 8
  - All starred: quality ≥ 1
- ❌ Keyboard shortcuts for quick rating (1-9 keys)
- ❌ Visual quality indicators

**Why it matters:** The original system let you rate responses 1-10 and export different quality tiers for different use cases. This is essential for building high-quality training datasets.

#### 2. Candidate Detail Extraction (from table_view.html)
**Impact: Critical for candidate evaluation workflow**

Lost features:
- ❌ Parse candidate name, title, company from LLM responses
- ❌ Display structured candidate info in table
- ❌ Expandable row details with full candidate data
- ❌ Multi-model comparison in single table view

**Why it matters:** The Aris use case requires viewing candidate information (name, title, company) alongside model evaluations. Current UI just shows raw JSON.

#### 3. Multi-Model Table Comparison (from table_view.html)
**Impact: High for model evaluation**

Lost features:
- ❌ Side-by-side model outputs in table format
- ❌ Sortable columns by model, quality, rating
- ❌ Column visibility toggles
- ❌ Pagination with configurable page size

**Why it matters:** Comparing 3-5 models on the same candidates is core to the benchmarking workflow.

#### 4. Batch Submission Form (from submit_batch.html)
**Impact: High for usability**

Lost features:
- ❌ Web form to submit new batch jobs
- ❌ File upload for JSONL datasets
- ❌ Model selection dropdown
- ❌ Parameter configuration (temperature, max_tokens, etc.)
- ❌ Validation before submission

**Why it matters:** Currently users must use curl/API to submit jobs. A web form makes it accessible to non-technical users.

#### 5. Real-time Dashboard (from dashboard.html)
**Impact: Medium for monitoring**

Lost features:
- ❌ System health indicators (healthy/degraded/dead)
- ❌ Worker health metrics with status colors
- ❌ GPU utilization display
- ❌ Recent jobs list with live status
- ❌ Auto-refresh every 5 seconds

**Why it matters:** The current metrics dashboard is static. The original had live updates and health indicators.

#### 6. Advanced Benchmark Comparison (from benchmarks.html)
**Impact: Medium for evaluation**

Lost features:
- ❌ Multi-run comparison mode (compare 5+ benchmark runs)
- ❌ Live current job status during benchmarking
- ❌ Benchmark selector with test details
- ❌ Side-by-side comparison charts
- ❌ Quality comparison (5 identical samples across models)

**Why it matters:** The original let you compare multiple benchmark runs to see model performance trends over time.

---

### 🟡 Medium Priority (Nice to Have)

7. **Search Functionality** - Global search across all tasks/results
8. **Advanced Filtering** - Filter by quality score, model, date, status
9. **Expandable Row Details** - Click to see full task/candidate info
10. **Live Progress Tracking** - Real-time job progress with ETA and throughput graphs
11. **Job Cancellation Controls** - Cancel running jobs from UI
12. **Column Visibility Toggles** - Show/hide columns in table views

---

### 🟢 Low Priority (Can Skip)

13. **API Docs Viewer** - Can use Swagger/OpenAPI instead
14. **Separate compare_results.html** - Covered by workbench
15. **Separate view_results.html** - Covered by curation

---

## Recommendations

### Immediate Actions (This Week)

1. **Restore Quality Rating System** to `curation.html`
   - Add 1-10 star rating UI component
   - Add Good/Bad toggle buttons
   - Update export endpoint to support quality thresholds
   - Add keyboard shortcuts (1-9 for rating, G for good, B for bad)

2. **Add Candidate Detail Extraction** to `workbench.html`
   - Parse name, title, company from LLM responses
   - Display in structured table format
   - Add expandable row details

3. **Create Batch Submission Page** (`static/submit-batch.html`)
   - Simple form with file upload
   - Model selection dropdown
   - Parameter inputs (temperature, max_tokens, etc.)
   - Submit to `/v1/batches` endpoint

### Short-term (Next 2 Weeks)

4. **Enhance Metrics Dashboard**
   - Add real-time health indicators
   - Add auto-refresh (configurable interval)
   - Add GPU metrics display
   - Add recent jobs list with live status

5. **Add Multi-Model Table Comparison** to `workbench.html`
   - Side-by-side model outputs
   - Sortable columns
   - Column visibility controls
   - Export comparison results

### Long-term (Future)

6. **Add Search & Advanced Filtering**
   - Global search across all tasks
   - Filter by quality, model, date, status
   - Save filter presets
   - Search history

7. **Restore Benchmark Comparison**
   - Multi-run comparison mode
   - Quality comparison (identical samples)
   - Trend analysis over time

---

## Feature Restoration Checklist

### Curation Features
- [ ] Quality rating system (1-10 scale)
- [ ] Good/Bad categorization
- [ ] Export with quality thresholds (ICL ≥9, fine-tuning ≥8)
- [ ] Keyboard shortcuts for rating
- [ ] Inline editing of responses
- [ ] Search functionality

### Table/Comparison Features
- [ ] Candidate detail extraction (name, title, company)
- [ ] Multi-model comparison table
- [ ] Sortable columns
- [ ] Expandable row details
- [ ] Column visibility toggles
- [ ] Pagination controls

### Monitoring Features
- [ ] Real-time health indicators
- [ ] Worker health metrics
- [ ] GPU utilization display
- [ ] Auto-refresh dashboard
- [ ] Live progress bars
- [ ] Throughput graphs
- [ ] ETA calculations

### Workflow Features
- [ ] Batch submission form
- [ ] File upload interface
- [ ] Model selection dropdown
- [ ] Parameter configuration
- [ ] Job cancellation controls

### Benchmark Features
- [ ] Multi-run comparison mode
- [ ] Live job status during benchmarking
- [ ] Quality comparison (identical samples)
- [ ] Side-by-side comparison charts

---

## Conclusion

The enterprise cleanup was necessary for maintainability and OSS preparation, but we lost ~70% of the original UI functionality. The most critical missing features are:

1. **Quality rating system** - Essential for training data curation
2. **Candidate detail extraction** - Core to the Aris use case
3. **Batch submission form** - Makes the system accessible to non-technical users

We should prioritize restoring these three features first, then gradually add back the monitoring and comparison features as time permits.

The good news: All the backend APIs still exist! We just need to rebuild the UIs to expose them.

