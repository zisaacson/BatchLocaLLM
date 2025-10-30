# 🏗️ Monitoring Architecture - Single Source of Truth

## 🎯 Your Question: Should we standardize on one monitoring system?

**YES. Absolutely. Here's why and how:**

---

## ❌ Current Problem: Duplicate Instrumentation

**What you have now:**
```
vLLM Server
  ├─ Exposes /metrics (Prometheus format)
  └─ batch_app/api_server.py has check_gpu_health() using pynvml

Your Web App (serve_results.py)
  └─ Would need to duplicate GPU monitoring code
```

**Problems:**
- 🔴 Duplicate code (pynvml in multiple places)
- 🔴 Inconsistent data (different sampling times)
- 🔴 More maintenance burden
- 🔴 Web app doesn't show same data as Grafana

---

## ✅ Better Architecture: Prometheus as Single Source of Truth

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                              │
├─────────────────────────────────────────────────────────────┤
│  vLLM Server          nvidia_gpu_exporter    Your Batch API │
│  :4080/metrics        :9835/metrics          :4081/metrics  │
└────────┬──────────────────────┬──────────────────┬──────────┘
         │                      │                  │
         └──────────────────────┼──────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │     PROMETHEUS        │
                    │   (Single Source)     │
                    │    :4022/api/v1       │
                    └───────────┬───────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼──────┐  ┌────▼────┐  ┌──────▼──────┐
        │   GRAFANA    │  │  LOKI   │  │  YOUR WEB   │
        │  (For You)   │  │ (Logs)  │  │     APP     │
        │   :4020      │  │  :4021  │  │   :4080     │
        └──────────────┘  └─────────┘  └─────────────┘
```

**Benefits:**
- ✅ **Single instrumentation point** - vLLM and nvidia_gpu_exporter expose metrics once
- ✅ **Consistent data** - Everyone reads from Prometheus
- ✅ **No duplicate code** - Web app queries Prometheus API, doesn't run pynvml
- ✅ **Historical data** - Prometheus stores 15 days of metrics
- ✅ **Same data everywhere** - Grafana and your web app show identical numbers

---

## 🔧 Implementation Plan

### **Step 1: Remove Duplicate GPU Monitoring**

**Current (batch_app/api_server.py):**
```python
def check_gpu_health() -> dict:
    import pynvml
    pynvml.nvmlInit()
    # ... duplicate code ...
```

**New (query Prometheus instead):**
```python
import requests

def check_gpu_health() -> dict:
    """Query Prometheus for GPU metrics."""
    prom_url = "http://localhost:4022/api/v1/query"
    
    # Get GPU temperature
    temp_query = "nvidia_gpu_temperature_celsius"
    temp_resp = requests.get(prom_url, params={"query": temp_query})
    temp = float(temp_resp.json()["data"]["result"][0]["value"][1])
    
    # Get GPU memory
    mem_query = "nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes * 100"
    mem_resp = requests.get(prom_url, params={"query": mem_query})
    mem_percent = float(mem_resp.json()["data"]["result"][0]["value"][1])
    
    healthy = mem_percent < 95 and temp < 85
    
    return {
        "healthy": healthy,
        "memory_percent": mem_percent,
        "temperature_c": temp
    }
```

### **Step 2: Add Prometheus Client to Your Web App**

**Update serve_results.py to expose real-time metrics:**
```python
import requests

class ResultsHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # ... existing code ...
        
        # NEW: Real-time metrics endpoint
        elif parsed_path.path == '/api/metrics/gpu':
            metrics = self.get_gpu_metrics()
            self.send_json(metrics)
        
        elif parsed_path.path == '/api/metrics/vllm':
            metrics = self.get_vllm_metrics()
            self.send_json(metrics)
    
    def get_gpu_metrics(self):
        """Query Prometheus for GPU metrics."""
        prom = "http://localhost:4022/api/v1/query"
        return {
            "temperature": self.query_prom(prom, "nvidia_gpu_temperature_celsius"),
            "memory_percent": self.query_prom(prom, "nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes * 100"),
            "utilization": self.query_prom(prom, "nvidia_gpu_duty_cycle"),
            "power_watts": self.query_prom(prom, "nvidia_gpu_power_usage_milliwatts / 1000")
        }
    
    def get_vllm_metrics(self):
        """Query Prometheus for vLLM metrics."""
        prom = "http://localhost:4022/api/v1/query"
        return {
            "requests_per_sec": self.query_prom(prom, "rate(vllm:request_success_total[1m])"),
            "active_requests": self.query_prom(prom, "vllm:num_requests_running"),
            "queued_requests": self.query_prom(prom, "vllm:num_requests_waiting"),
            "kv_cache_usage": self.query_prom(prom, "vllm:gpu_cache_usage_perc"),
            "tokens_per_sec": self.query_prom(prom, "rate(vllm:generation_tokens_total[1m])")
        }
    
    def query_prom(self, url, query):
        """Helper to query Prometheus."""
        try:
            resp = requests.get(url, params={"query": query})
            data = resp.json()
            if data["data"]["result"]:
                return float(data["data"]["result"][0]["value"][1])
            return 0
        except:
            return 0
```

### **Step 3: Update Your Web UI to Show Metrics**

**Add to your HTML (table_view.html, dashboard.html, etc.):**
```html
<div id="system-status">
  <div class="metric">
    <span class="label">GPU Temp:</span>
    <span id="gpu-temp">--</span>°C
  </div>
  <div class="metric">
    <span class="label">GPU Memory:</span>
    <span id="gpu-memory">--</span>%
  </div>
  <div class="metric">
    <span class="label">Active Requests:</span>
    <span id="active-requests">--</span>
  </div>
  <div class="metric">
    <span class="label">Tokens/sec:</span>
    <span id="tokens-per-sec">--</span>
  </div>
</div>

<script>
// Update metrics every 5 seconds
setInterval(async () => {
  const gpu = await fetch('/api/metrics/gpu').then(r => r.json());
  const vllm = await fetch('/api/metrics/vllm').then(r => r.json());
  
  document.getElementById('gpu-temp').textContent = gpu.temperature.toFixed(1);
  document.getElementById('gpu-memory').textContent = gpu.memory_percent.toFixed(1);
  document.getElementById('active-requests').textContent = vllm.active_requests;
  document.getElementById('tokens-per-sec').textContent = vllm.tokens_per_sec.toFixed(1);
}, 5000);
</script>
```

---

## 🧹 Docker Cleanup Recommendations

### **What You NEED for vLLM Batch Server:**

```yaml
# KEEP THESE:
✅ aristotle-prometheus       # Metrics database
✅ aristotle-grafana          # Dashboards for you
✅ aristotle-loki             # Logs
✅ aristotle-nvidia-gpu-exporter  # GPU metrics
✅ aristotle-label-studio     # Training data curation
```

### **What You DON'T NEED (for this workstation):**

```yaml
# REMOVE THESE (Aristotle app stuff, not needed for vLLM):
❌ aristotle-resume-ner       # Your Aristotle app service
❌ aristotle-docmost          # Documentation (use GitHub instead)
❌ aristotle-docmost-db       # Docmost database
❌ aristotle-docmost-redis    # Docmost cache
❌ aristotle-mlflow           # ML experiment tracking (overkill)
❌ aristotle-dev-db           # Aristotle dev database
❌ aristotle-test-db          # Aristotle test database
❌ aristotle-qdrant           # Vector DB (not using)
❌ aristotle-prefect          # Workflow orchestration (using Inngest)
❌ aristotle-chromadb         # Vector DB (not using)
❌ aristotle-neo4j            # Graph DB (not using)
❌ aristotle-inngest          # Workflow engine (for Aristotle app)
❌ aristotle-alloy            # Grafana agent (not needed)
❌ aristotle-duckdb           # Analytics DB (not using)
```

### **Cleanup Script:**

```bash
#!/bin/bash
# cleanup_docker.sh

echo "🧹 Cleaning up unnecessary Docker containers..."

# Stop and remove Aristotle app containers
docker stop aristotle-resume-ner aristotle-docmost aristotle-docmost-db \
  aristotle-docmost-redis aristotle-mlflow aristotle-dev-db aristotle-test-db \
  aristotle-qdrant aristotle-prefect aristotle-chromadb aristotle-neo4j \
  aristotle-inngest aristotle-alloy aristotle-duckdb

docker rm aristotle-resume-ner aristotle-docmost aristotle-docmost-db \
  aristotle-docmost-redis aristotle-mlflow aristotle-dev-db aristotle-test-db \
  aristotle-qdrant aristotle-prefect aristotle-chromadb aristotle-neo4j \
  aristotle-inngest aristotle-alloy aristotle-duckdb

echo "✅ Cleanup complete!"
echo ""
echo "📊 Remaining containers (for vLLM monitoring):"
docker ps --format "table {{.Names}}\t{{.Status}}"
```

**After cleanup, you'll have:**
- Prometheus (metrics)
- Grafana (dashboards)
- Loki (logs)
- nvidia_gpu_exporter (GPU metrics)
- Label Studio (data curation)

**Total: 5 containers instead of 19** 🎉

---

## 📊 Final Architecture

```
Your vLLM Batch Server Workstation
├─ vLLM Server (native Python, not Docker)
│  └─ Exposes /metrics
├─ nvidia_gpu_exporter (systemd service)
│  └─ Exposes /metrics
├─ Your Web App (serve_results.py)
│  └─ Queries Prometheus API
└─ Docker Containers (5 total):
   ├─ Prometheus (scrapes metrics)
   ├─ Grafana (dashboards)
   ├─ Loki (logs)
   ├─ nvidia-gpu-exporter (GPU metrics)
   └─ Label Studio (data curation)
```

---

## 🎯 Summary

**Your instinct is 100% correct:**

1. ✅ **Standardize on Prometheus/Grafana** - Single source of truth
2. ✅ **Web apps query Prometheus** - No duplicate instrumentation
3. ✅ **Clean up Docker** - Remove 14 unnecessary containers
4. ✅ **Keep it simple** - 5 containers for monitoring + Label Studio

**Next steps:**
1. Run cleanup script to remove unused containers
2. Update your web apps to query Prometheus API
3. Enjoy consistent metrics everywhere

---

**Want me to implement this architecture now?**

