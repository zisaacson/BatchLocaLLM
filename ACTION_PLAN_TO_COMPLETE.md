# 🎯 Action Plan to Complete System

**Date**: 2025-11-05  
**Goal**: Close all gaps and achieve 100% requirements coverage  
**Estimated Time**: 10-14 hours

---

## 🔴 **PHASE 1: CRITICAL GAPS (4-6 hours)**

### **Task 1.1: Create Aris Conquest API Router** (2 hours)

**File to create:** `integrations/aris/conquest_api.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/v1/aris", tags=["aris"])

class VictoryRequest(BaseModel):
    conquest_id: str
    philosopher: str
    domain: str
    result_notes: str | None = None

@router.post("/sync/victory-to-gold-star")
async def sync_victory_to_gold_star(request: VictoryRequest):
    """
    Sync VICTORY conquest from Aristotle to Label Studio gold star.
    
    Called by Aristotle web app when user marks conquest as VICTORY.
    """
    from core.curation.label_studio_client import LabelStudioClient
    from datetime import datetime, timezone
    
    ls_client = LabelStudioClient()
    
    # Find task in Label Studio by conquest_id
    # Search through all projects for task with matching conquest_id in data
    tasks = ls_client.get_tasks(page_size=1000)
    
    matching_task = None
    for task in tasks:
        task_data = task.get('data', {})
        if task_data.get('conquest_id') == request.conquest_id:
            matching_task = task
            break
    
    if not matching_task:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found for conquest_id: {request.conquest_id}"
        )
    
    # Update task metadata to mark as gold star
    task_id = matching_task['id']
    current_meta = matching_task.get('meta', {})
    current_meta['gold_star'] = True
    current_meta['synced_from_aristotle'] = True
    current_meta['result_notes'] = request.result_notes
    current_meta['synced_at'] = datetime.now(timezone.utc).isoformat()
    
    ls_client.update_task(task_id=task_id, meta=current_meta)
    
    return {
        "status": "success",
        "conquest_id": request.conquest_id,
        "task_id": task_id,
        "message": "Successfully synced VICTORY to gold star"
    }


@router.get("/icl/examples")
async def get_icl_examples(
    philosopher: str,
    domain: str,
    conquest_type: str | None = None,
    limit: int = 10,
    format: str = "chatml"
):
    """
    Fetch gold star examples for Eidos in-context learning.
    
    Query Parameters:
    - philosopher: User email (required)
    - domain: Organization domain (required)
    - conquest_type: Filter by conquest type (optional)
    - limit: Max examples to return (default: 10, max: 100)
    - format: Output format - chatml, alpaca, or openai (default: chatml)
    
    Returns:
    List of training examples in requested format.
    """
    from integrations.aris.training.dataset_exporter import AristotleDatasetExporter
    
    if limit > 100:
        limit = 100
    
    exporter = AristotleDatasetExporter()
    
    examples = exporter.fetch_gold_star_conquests(
        philosopher=philosopher,
        domain=domain,
        conquest_type=conquest_type,
        limit=limit
    )
    
    # Convert to requested format
    if format == "chatml":
        return {
            "philosopher": philosopher,
            "domain": domain,
            "conquest_type": conquest_type,
            "format": "chatml",
            "count": len(examples),
            "examples": [ex.to_chatml() for ex in examples]
        }
    elif format == "alpaca":
        return {
            "philosopher": philosopher,
            "domain": domain,
            "conquest_type": conquest_type,
            "format": "alpaca",
            "count": len(examples),
            "examples": [ex.to_alpaca() for ex in examples]
        }
    else:  # openai
        return {
            "philosopher": philosopher,
            "domain": domain,
            "conquest_type": conquest_type,
            "format": "openai",
            "count": len(examples),
            "examples": [ex.to_openai() for ex in examples]
        }
```

---

### **Task 1.2: Mount Aris Router in Main App** (30 minutes)

**File to modify:** `core/batch_app/api_server.py`

Add at the end of the file (before `if __name__ == "__main__"`):

```python
# ============================================================================
# Aris Integration (Optional)
# ============================================================================

if os.getenv("ENABLE_ARIS_INTEGRATION") == "true":
    try:
        from integrations.aris.conquest_api import router as aris_router
        app.include_router(aris_router)
        logger.info("✅ Aris integration enabled")
    except ImportError:
        logger.warning("⚠️  Aris integration enabled but module not found")
```

---

### **Task 1.3: Update .env File** (5 minutes)

Add to `.env`:

```bash
# Aris Integration
ENABLE_ARIS_INTEGRATION=true
```

---

### **Task 1.4: Test Endpoints** (1 hour)

**Test Victory → Gold Star:**
```bash
# 1. Create a test conquest in Aristotle
# 2. Process it through vLLM batch server
# 3. Mark as VICTORY in Aristotle
# 4. Aristotle calls:
curl -X POST http://localhost:4080/v1/aris/sync/victory-to-gold-star \
  -H "Content-Type: application/json" \
  -d '{
    "conquest_id": "conquest_abc123",
    "philosopher": "user@example.com",
    "domain": "software_engineering",
    "result_notes": "Excellent analysis"
  }'

# 5. Verify gold star appears in Label Studio
curl http://localhost:8001/api/tasks | jq '.tasks[] | select(.meta.gold_star == true)'
```

**Test Eidos ICL:**
```bash
# Fetch gold star examples for Eidos
curl "http://localhost:4080/v1/aris/icl/examples?philosopher=user@example.com&domain=software_engineering&limit=5&format=chatml" | jq .

# Should return:
# {
#   "philosopher": "user@example.com",
#   "domain": "software_engineering",
#   "format": "chatml",
#   "count": 5,
#   "examples": [...]
# }
```

---

### **Task 1.5: Update Aristotle Web App** (30 minutes)

**File to modify:** Aristotle web app (Next.js)

Add webhook call when marking conquest as VICTORY:

```typescript
// In Aristotle web app
async function markConquestAsVictory(conquestId: string) {
  // 1. Update local database
  await prisma.conquest.update({
    where: { id: conquestId },
    data: { result: 'VICTORY' }
  });
  
  // 2. Sync to vLLM batch server
  try {
    await fetch('http://localhost:4080/v1/aris/sync/victory-to-gold-star', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conquest_id: conquestId,
        philosopher: user.email,
        domain: user.domain,
        result_notes: 'Marked as VICTORY in Aristotle'
      })
    });
  } catch (error) {
    console.error('Failed to sync to Label Studio:', error);
  }
}
```

---

### **Task 1.6: Update Eidos to Use ICL Endpoint** (30 minutes)

**File to modify:** Eidos in-context learning system

```typescript
// In Eidos
async function fetchICLExamples(
  philosopher: string,
  domain: string,
  conquestType: string,
  limit: number = 10
) {
  const response = await fetch(
    `http://localhost:4080/v1/aris/icl/examples?` +
    `philosopher=${philosopher}&` +
    `domain=${domain}&` +
    `conquest_type=${conquestType}&` +
    `limit=${limit}&` +
    `format=chatml`
  );
  
  const data = await response.json();
  return data.examples;
}

// Use in prompt construction
const examples = await fetchICLExamples(
  user.email,
  user.domain,
  'candidate_evaluation',
  5
);

const prompt = buildPromptWithExamples(examples, newCandidate);
```

---

## 🟡 **PHASE 2: METRICS DASHBOARD (6-8 hours)**

### **Task 2.1: Create Metrics API Endpoint** (2 hours)

**File to modify:** `core/curation/api.py`

```python
@app.get("/api/metrics/overview")
async def get_metrics_overview(
    schema_type: str | None = None,
    days: int = 30
) -> dict[str, Any]:
    """Get metrics overview for dashboard."""
    from datetime import datetime, timedelta, timezone
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Fetch tasks from Label Studio
    if schema_type:
        project_id = await get_or_create_project(schema_type)
        tasks = label_studio.get_tasks(project_id=project_id, page_size=1000)
    else:
        tasks = []
        # Fetch from all projects
        # ... implementation
    
    # Calculate metrics
    total_tasks = len(tasks)
    gold_star_tasks = len([t for t in tasks if t.get('meta', {}).get('gold_star')])
    annotated_tasks = len([t for t in tasks if t.get('annotations')])
    
    # Time series data (gold stars over time)
    gold_star_timeline = {}
    for task in tasks:
        if task.get('meta', {}).get('gold_star'):
            created_at = task.get('created_at', '')
            date = created_at[:10]  # YYYY-MM-DD
            gold_star_timeline[date] = gold_star_timeline.get(date, 0) + 1
    
    return {
        "schema_type": schema_type,
        "period_days": days,
        "total_tasks": total_tasks,
        "gold_star_tasks": gold_star_tasks,
        "annotated_tasks": annotated_tasks,
        "pending_tasks": total_tasks - annotated_tasks,
        "gold_star_timeline": gold_star_timeline,
        "annotation_rate": annotated_tasks / total_tasks if total_tasks > 0 else 0,
        "gold_star_rate": gold_star_tasks / total_tasks if total_tasks > 0 else 0
    }
```

---

### **Task 2.2: Create Metrics Dashboard UI** (4-6 hours)

**File to create:** `static/metrics.html`

Features:
- Chart.js for visualizations
- Gold star count over time (line chart)
- Annotation progress (pie chart)
- Quality distribution (bar chart)
- Model comparison table
- Export functionality

---

## 🟢 **PHASE 3: ENHANCED CURATION UI (Optional, 8-10 hours)**

### **Task 3.1: Add Conquest Template Selector**
### **Task 3.2: Inline Response Editing**
### **Task 3.3: Keyboard Shortcuts**
### **Task 3.4: Bulk Operations**

---

## 📋 **TESTING CHECKLIST**

### **End-to-End Flow 1: Conquest → Gold Star → Victory**
- [ ] Create conquest in Aristotle
- [ ] Process through vLLM batch server
- [ ] View in Label Studio
- [ ] Mark as gold star in Curation UI
- [ ] Verify conquest.result = 'VICTORY' in Aristotle
- [ ] Verify ml_analysis_rating created

### **End-to-End Flow 2: Victory → Gold Star**
- [ ] Create conquest in Aristotle
- [ ] Process through vLLM batch server
- [ ] Mark as VICTORY in Aristotle
- [ ] Verify gold star appears in Label Studio
- [ ] Verify gold star appears in Curation UI

### **End-to-End Flow 3: Eidos ICL**
- [ ] Create 5+ gold star conquests
- [ ] Call `/v1/aris/icl/examples` endpoint
- [ ] Verify examples returned in ChatML format
- [ ] Verify Eidos can use examples for ICL

---

## 🎯 **SUCCESS CRITERIA**

- [x] All 7 requirements implemented
- [ ] Eidos ICL endpoint working
- [ ] Victory → Gold Star sync working
- [ ] Metrics dashboard created
- [ ] End-to-end tests passing
- [ ] Documentation updated
- [ ] Code committed and pushed

---

## ⏱️ **TIMELINE**

**Day 1 (4-6 hours):**
- Create Aris conquest API router
- Mount router in main app
- Test endpoints
- Update Aristotle web app
- Update Eidos

**Day 2 (6-8 hours):**
- Create metrics API endpoint
- Create metrics dashboard UI
- Test metrics dashboard
- Documentation

**Day 3 (Optional, 8-10 hours):**
- Enhanced curation UI features
- Inline editing
- Keyboard shortcuts
- Bulk operations

**Total:** 10-24 hours depending on scope

---

## 🚀 **NEXT STEPS**

1. **Review this plan** with the team
2. **Prioritize tasks** (Phase 1 is critical, Phase 2 is important, Phase 3 is optional)
3. **Start with Task 1.1** (Create Aris conquest API router)
4. **Test incrementally** after each task
5. **Document as you go**

**Ready to start?** Let's close these gaps and achieve 100%! 🎯


