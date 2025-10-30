# 📊 vLLM Batch Server Monitoring Setup

Complete monitoring solution for your vLLM batch processing system using Grafana, Prometheus, and Loki.

---

## 🎯 What You Get

### **Real-Time Dashboards**
- 🎮 **GPU Metrics**: Temperature, memory, power, utilization
- 📊 **vLLM Performance**: Requests/sec, latency (P50/P95/P99), throughput
- 🔄 **Batch Processing**: Active requests, queue depth, batch sizes
- 💾 **KV Cache**: Usage percentage, prefix cache hit rate
- 📈 **Token Generation**: Tokens/sec, total tokens generated

### **Centralized Logging**
- 📝 All vLLM server logs in one place
- 🔍 Searchable and filterable
- ⏱️ Time-correlated with metrics
- 🎯 Request tracing

---

## 🚀 Quick Setup (2 Steps)

### **Step 1: Install GPU Monitoring**
```bash
./setup_gpu_monitoring.sh
```

This installs `nvidia_gpu_exporter` which exposes GPU metrics to Prometheus.

### **Step 2: Configure Grafana & Prometheus**
```bash
./setup_monitoring.sh
```

This:
- Updates Prometheus to scrape vLLM metrics
- Installs Grafana dashboards
- Configures Loki datasource
- Restarts services

---

## 📊 Access Your Dashboards

### **Grafana** (Main Dashboard)
- **URL**: http://localhost:4020
- **Username**: `admin`
- **Password**: `admin` (change on first login)

### **Prometheus** (Metrics Database)
- **URL**: http://localhost:4022
- **Query Interface**: http://localhost:4022/graph

### **Loki** (Logs)
- **URL**: http://localhost:4021
- **Access via**: Grafana → Explore → Loki datasource

---

## 🎨 Available Dashboards

### **1. vLLM Batch Server - GPU & Performance**

**Location**: Grafana → Dashboards → vLLM

**Panels**:
1. **GPU Temperature** - Real-time GPU temp with thresholds
2. **GPU Memory Usage** - VRAM utilization percentage
3. **GPU Power Usage** - Current power draw in watts
4. **GPU Utilization** - GPU compute usage
5. **Requests Per Second** - Success/failure rates
6. **Request Latency** - P50, P95, P99 percentiles
7. **Tokens Generated/sec** - Throughput metric
8. **Active Requests** - Currently processing
9. **Queued Requests** - Waiting in queue
10. **KV Cache Usage** - Memory efficiency
11. **Prefix Cache Hit Rate** - Caching effectiveness
12. **Batch Size Distribution** - Heatmap of batch sizes

---

## 📈 Key Metrics Explained

### **GPU Metrics** (from nvidia_gpu_exporter)
```
nvidia_gpu_temperature_celsius       # GPU temperature
nvidia_gpu_memory_used_bytes         # VRAM used
nvidia_gpu_memory_total_bytes        # Total VRAM
nvidia_gpu_power_usage_milliwatts    # Power consumption
nvidia_gpu_duty_cycle                # GPU utilization %
```

### **vLLM Metrics** (from vLLM server)
```
vllm:request_success_total           # Successful requests
vllm:request_failure_total           # Failed requests
vllm:request_duration_seconds        # Request latency histogram
vllm:generation_tokens_total         # Total tokens generated
vllm:num_requests_running            # Active requests
vllm:num_requests_waiting            # Queued requests
vllm:gpu_cache_usage_perc            # KV cache usage
vllm:prefix_cache_hit_total          # Prefix cache hits
vllm:prefix_cache_miss_total         # Prefix cache misses
vllm:batch_size_bucket               # Batch size distribution
```

---

## 🔍 Viewing Logs in Grafana

### **Method 1: Explore View**
1. Open Grafana: http://localhost:4020
2. Click **Explore** (compass icon)
3. Select **Loki** datasource
4. Query examples:
   ```
   {job="vllm-server"}                    # All vLLM logs
   {job="vllm-server"} |= "ERROR"         # Only errors
   {job="vllm-benchmarks"}                # Benchmark logs
   {job="vllm-batch"}                     # Batch processing logs
   ```

### **Method 2: Dashboard Logs Panel**
- Logs are automatically linked to metrics
- Click on a metric spike to see related logs

---

## 🎯 Monitoring Your Benchmark

While your benchmark is running, watch these metrics:

### **Performance**
- **Tokens/sec**: Should be high and stable
- **Request Latency P95**: Should stay low
- **GPU Utilization**: Should be >90% during processing

### **Efficiency**
- **Prefix Cache Hit Rate**: Higher = better (reusing cached prompts)
- **KV Cache Usage**: Should be <90% (avoid OOM)
- **Batch Size**: Larger batches = better throughput

### **Health**
- **GPU Temperature**: Should stay <85°C
- **GPU Memory**: Should not hit 100%
- **Failed Requests**: Should be 0

---

## 🔧 Troubleshooting

### **No GPU Metrics?**
```bash
# Check if nvidia_gpu_exporter is running
sudo systemctl status nvidia-gpu-exporter

# Test metrics endpoint
curl http://localhost:9835/metrics | grep nvidia_gpu
```

### **No vLLM Metrics?**
```bash
# Check if vLLM server is running
curl http://localhost:4080/health

# Test metrics endpoint
curl http://localhost:4080/metrics | grep vllm
```

### **Prometheus Not Scraping?**
```bash
# Check Prometheus targets
open http://localhost:4022/targets

# Should see:
# - vllm-server (UP)
# - nvidia-gpu (UP)
```

### **Grafana Dashboard Not Loading?**
```bash
# Restart Grafana
docker restart aristotle-grafana

# Check logs
docker logs aristotle-grafana
```

---

## 📊 Example Queries

### **Prometheus Queries**

**Average GPU Temperature**:
```promql
avg(nvidia_gpu_temperature_celsius)
```

**Total Tokens Generated (last 5 min)**:
```promql
increase(vllm:generation_tokens_total[5m])
```

**Request Success Rate**:
```promql
rate(vllm:request_success_total[1m]) / 
(rate(vllm:request_success_total[1m]) + rate(vllm:request_failure_total[1m])) * 100
```

**Average Batch Size**:
```promql
avg(vllm:batch_size)
```

### **Loki Queries**

**All errors in last hour**:
```logql
{job="vllm-server"} |= "ERROR" | json
```

**Request latency over 1 second**:
```logql
{job="vllm-server"} |= "latency" | json | latency > 1.0
```

---

## 🎨 Customizing Dashboards

1. Open dashboard in Grafana
2. Click **⚙️ Dashboard settings**
3. Click **JSON Model**
4. Edit and save
5. Or use the UI to add/modify panels

---

## 📦 What Was Installed

```
monitoring/
├── prometheus.yml                    # Prometheus config (scrape targets)
├── promtail-config.yml              # Log collection config
├── grafana/
│   ├── dashboards/
│   │   ├── dashboard-provider.yml   # Dashboard auto-loading
│   │   └── vllm-dashboard.json      # Main vLLM dashboard
│   └── datasources/
│       └── datasources.yml          # Prometheus + Loki datasources
```

---

## 🚀 Next Steps

1. **Run your benchmark**: `python3 benchmark_vllm_modes.py`
2. **Open Grafana**: http://localhost:4020
3. **Watch metrics in real-time**
4. **Analyze results** after benchmark completes

---

## 💡 Pro Tips

- **Set up alerts**: Configure Grafana alerts for high GPU temp, OOM, etc.
- **Export dashboards**: Save your customized dashboards as JSON
- **Historical analysis**: Prometheus retains metrics for 15 days by default
- **Log retention**: Configure Loki retention in docker-compose.yml

---

**Your monitoring stack is ready! 🎉**

