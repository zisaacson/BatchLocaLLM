# Job History Feature

**Status:** ✅ Production Ready  
**Added:** 2025-11-02  
**Version:** 1.0.0

---

## Overview

The Job History feature provides a comprehensive view of all batch processing jobs with filtering, statistics, and detailed analytics. This is a core feature for the open source release, allowing users to monitor and analyze their GPU processing workload.

---

## Features

### 📊 **Statistics Dashboard**

Real-time statistics displayed at the top of the page:

- **Total Jobs** - Total number of jobs processed
- **Success Rate** - Percentage of successfully completed jobs
- **Average Duration** - Mean processing time per job (seconds)
- **Total Requests** - Total number of inference requests processed

### 🔍 **Filtering**

Filter jobs by:

- **Status** - All, Completed, Failed, In Progress, Queued, Cancelled
- **Model** - Filter by specific model (e.g., google/gemma-3-4b-it)
- **Date Range** - Filter by creation time (via API)

### 📋 **Job List**

Paginated table showing:

- **Batch ID** - Unique identifier for the job
- **Status** - Current job status with color-coded badges
- **Model** - Model used for processing
- **Requests** - Completed/Total requests
- **Duration** - Processing time in seconds
- **Throughput** - Requests per second
- **Created** - Timestamp when job was created

### 🔎 **Job Details Modal**

Click any job to see detailed information:

- Full job metadata
- Request counts (total, completed, failed)
- Timing information (created, completed, duration)
- File IDs (input, output, error)
- Webhook configuration
- Error details (if failed)
- Queue information (if queued)
- Custom metadata

### ⚡ **Auto-Refresh**

The page automatically refreshes every 30 seconds to show the latest data.

---

## API Endpoints

### `GET /v1/jobs/history`

Get paginated job history with filtering.

**Query Parameters:**

- `limit` (int, default: 50, max: 500) - Number of jobs to return
- `offset` (int, default: 0) - Number of jobs to skip (for pagination)
- `status` (string, optional) - Filter by status
- `model` (string, optional) - Filter by model name
- `start_date` (int, optional) - Filter jobs created after this Unix timestamp
- `end_date` (int, optional) - Filter jobs created before this Unix timestamp

**Response:**

```json
{
  "jobs": [
    {
      "batch_id": "batch_abc123",
      "status": "completed",
      "model": "google/gemma-3-4b-it",
      "created_at": 1762097621,
      "completed_at": 1762097631,
      "failed_at": null,
      "cancelled_at": null,
      "total_requests": 10,
      "completed_requests": 10,
      "failed_requests": 0,
      "duration": 10.0,
      "throughput": 1.0,
      "priority": 0,
      "webhook_url": false,
      "has_errors": false
    }
  ],
  "total": 1820,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

**Example:**

```bash
# Get first 50 jobs
curl "http://localhost:4080/v1/jobs/history?limit=50&offset=0"

# Get only failed jobs
curl "http://localhost:4080/v1/jobs/history?status=failed"

# Get jobs for specific model
curl "http://localhost:4080/v1/jobs/history?model=google/gemma-3-4b-it"

# Get jobs from last 24 hours
START_TIME=$(date -d '24 hours ago' +%s)
curl "http://localhost:4080/v1/jobs/history?start_date=$START_TIME"
```

---

### `GET /v1/jobs/stats`

Get aggregate statistics and analytics.

**Query Parameters:**

- `start_date` (int, optional) - Filter jobs created after this Unix timestamp
- `end_date` (int, optional) - Filter jobs created before this Unix timestamp

**Response:**

```json
{
  "total_jobs": 1820,
  "by_status": {
    "completed": 1785,
    "failed": 35
  },
  "by_model": {
    "google/gemma-3-4b-it": 1820
  },
  "success_rate": 0.9808,
  "avg_duration": 13.61,
  "total_requests": 1840,
  "completed_requests": 1805,
  "timeline": [
    {
      "timestamp": 1762011310,
      "jobs": 0
    },
    {
      "timestamp": 1762014910,
      "jobs": 102
    }
  ]
}
```

**Example:**

```bash
# Get overall stats
curl "http://localhost:4080/v1/jobs/stats"

# Get stats for last 7 days
START_TIME=$(date -d '7 days ago' +%s)
curl "http://localhost:4080/v1/jobs/stats?start_date=$START_TIME"
```

---

## Web UI

### Access

Open in your browser:

```
http://localhost:4080/history
```

Or navigate from the main page:

```
http://localhost:4080/
```

Click **"📜 Job History"** card.

### Features

1. **Statistics Cards** - Top of page shows key metrics
2. **Filters** - Dropdown menus to filter by status and model
3. **Job Table** - Paginated list of all jobs
4. **Pagination** - Navigate through pages with Previous/Next buttons
5. **Job Details** - Click any row to see full details in a modal
6. **Auto-Refresh** - Page updates every 30 seconds

### Status Badges

Jobs are color-coded by status:

- 🟢 **Completed** - Green badge
- 🔴 **Failed** - Red badge
- 🔵 **In Progress** - Blue badge
- 🟡 **Queued** - Orange badge
- ⚪ **Cancelled** - Gray badge

---

## Use Cases

### 1. **Monitor GPU Utilization**

Track how many jobs are being processed and identify peak usage times.

```bash
curl "http://localhost:4080/v1/jobs/stats" | jq '.timeline'
```

### 2. **Identify Failed Jobs**

Find and investigate jobs that failed.

```bash
curl "http://localhost:4080/v1/jobs/history?status=failed" | jq '.jobs'
```

### 3. **Compare Model Performance**

Analyze throughput and duration across different models.

```bash
curl "http://localhost:4080/v1/jobs/stats" | jq '.by_model'
```

### 4. **Track Success Rate**

Monitor system reliability over time.

```bash
curl "http://localhost:4080/v1/jobs/stats" | jq '.success_rate'
```

### 5. **Audit Job History**

Review all jobs processed in a specific time period.

```bash
START=$(date -d '2025-11-01' +%s)
END=$(date -d '2025-11-02' +%s)
curl "http://localhost:4080/v1/jobs/history?start_date=$START&end_date=$END"
```

---

## Integration Examples

### Python

```python
import requests

# Get job history
response = requests.get('http://localhost:4080/v1/jobs/history', params={
    'limit': 100,
    'status': 'completed'
})
jobs = response.json()['jobs']

# Get statistics
stats = requests.get('http://localhost:4080/v1/jobs/stats').json()
print(f"Success rate: {stats['success_rate'] * 100:.1f}%")
print(f"Average duration: {stats['avg_duration']:.1f}s")
```

### JavaScript

```javascript
// Get job history
const response = await fetch('http://localhost:4080/v1/jobs/history?limit=50');
const data = await response.json();
console.log(`Total jobs: ${data.total}`);

// Get statistics
const stats = await fetch('http://localhost:4080/v1/jobs/stats').then(r => r.json());
console.log(`Success rate: ${(stats.success_rate * 100).toFixed(1)}%`);
```

### cURL

```bash
# Export job history to JSON
curl "http://localhost:4080/v1/jobs/history?limit=1000" > jobs.json

# Get stats and format with jq
curl "http://localhost:4080/v1/jobs/stats" | jq '.'

# Monitor in real-time
watch -n 5 'curl -s "http://localhost:4080/v1/jobs/stats" | jq ".total_jobs, .success_rate"'
```

---

## Database Schema

Job history is stored in the `batch_jobs` table:

```sql
SELECT 
  batch_id,
  status,
  model,
  created_at,
  completed_at,
  total_requests,
  completed_requests,
  failed_requests
FROM batch_jobs
ORDER BY created_at DESC
LIMIT 50;
```

---

## Performance

- **Pagination** - Efficient queries with LIMIT/OFFSET
- **Indexing** - Database indexes on `created_at`, `status`, `model`
- **Caching** - Statistics cached for 30 seconds
- **Auto-Refresh** - Client-side refresh every 30 seconds (not polling)

---

## Future Enhancements

Potential improvements for future versions:

1. **Charts** - Visual timeline charts using Chart.js
2. **Export** - Download job history as CSV/JSON
3. **Advanced Filters** - Date range picker, multiple status selection
4. **Search** - Search by batch ID or metadata
5. **Sorting** - Sort by any column (duration, throughput, etc.)
6. **Comparison** - Compare multiple jobs side-by-side
7. **Alerts** - Email/webhook notifications for failed jobs
8. **Retention** - Automatic cleanup of old job records

---

## Troubleshooting

### Jobs Not Showing

**Problem:** No jobs appear in the history

**Solution:**
1. Check database connection: `docker exec vllm-batch-postgres psql -U vllm_batch_user -d vllm_batch -c "SELECT COUNT(*) FROM batch_jobs;"`
2. Verify API server is running: `curl http://localhost:4080/health`
3. Check browser console for errors

### Stats Not Loading

**Problem:** Statistics show "-" or don't load

**Solution:**
1. Check API endpoint: `curl http://localhost:4080/v1/jobs/stats`
2. Verify database has data
3. Check browser network tab for errors

### Pagination Not Working

**Problem:** Can't navigate to next page

**Solution:**
1. Check `has_more` field in API response
2. Verify `offset` parameter is being sent correctly
3. Check browser console for JavaScript errors

---

## Files

- **Backend API:** `core/batch_app/api_server.py` (lines 2668-2886)
- **Frontend HTML:** `core/batch_app/static/history.html`
- **Frontend JS:** `core/batch_app/static/history.js`
- **Documentation:** `docs/JOB_HISTORY_FEATURE.md` (this file)

---

## Summary

The Job History feature provides:

✅ **Complete visibility** into all batch processing jobs  
✅ **Real-time statistics** for monitoring GPU utilization  
✅ **Filtering and pagination** for large datasets  
✅ **Detailed job information** with modal view  
✅ **RESTful API** for programmatic access  
✅ **Beautiful web UI** for visual monitoring  
✅ **Auto-refresh** for live updates  

**Perfect for the open source release!** 🚀

