# 📸 Screenshot Capture Guide

This guide will help you capture all the screenshots needed for the documentation.

---

## 🚀 Quick Start

### **Option 1: Automated Helper Script** (Recommended)

```bash
# Make sure services are running
./scripts/start-services.sh

# Run the screenshot helper
chmod +x scripts/capture-screenshots.sh
./scripts/capture-screenshots.sh
```

The script will:
- Open each page in your browser
- Tell you exactly what to capture
- Wait for you to save each screenshot
- Guide you through the entire process

### **Option 2: Manual Capture**

Follow the checklist below and capture each screenshot manually.

---

## 📋 Screenshot Checklist

### **1. Swagger UI - API Documentation**

**URL:** http://localhost:4080/docs

**What to capture:**
- Full Swagger UI interface
- Expand "Batch Operations" section to show endpoints
- Make sure "vLLM Batch Server" title is visible

**Save to:** `docs/screenshots/swagger-ui/api-docs.png`

**Recommended size:** 1920x1080 or full browser window

---

### **2. Queue Monitor - Empty State**

**URL:** http://localhost:4080/queue

**What to capture:**
- Queue monitor with no jobs
- "No jobs in queue" message
- Header and stats visible

**Save to:** `docs/screenshots/queue-monitor/empty-state.png`

**Recommended size:** 1920x1080

---

### **3. Queue Monitor - With Jobs**

**URL:** http://localhost:4080/queue

**Setup:**
```bash
# Submit a test batch first
curl -X POST http://localhost:4080/v1/batches \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-test-quickstart",
    "metadata": {"model": "google/gemma-3-4b-it"}
  }'
```

**What to capture:**
- Queue monitor with test job visible
- Job ID, status, model, progress
- Stats (total jobs, processing, etc.)

**Save to:** `docs/screenshots/queue-monitor/with-jobs.png`

**Recommended size:** 1920x1080

---

### **4. Grafana - Main Dashboard**

**URL:** http://localhost:4220/d/vllm-batch-server/vllm-batch-server?orgId=1&refresh=5s

**Login:** admin/admin (if prompted)

**What to capture:**
- Main Grafana dashboard
- GPU metrics, job throughput, queue depth
- Make sure graphs have some data (wait a bit if needed)

**Save to:** `docs/screenshots/grafana/main-dashboard.png`

**Recommended size:** 1920x1080

---

### **5. Label Studio - Projects List**

**URL:** http://localhost:4115/projects

**Login:** Use your Label Studio credentials

**What to capture:**
- Label Studio projects page
- Any existing projects
- "Create Project" button visible

**Save to:** `docs/screenshots/label-studio/projects-list.png`

**Recommended size:** 1920x1080

---

### **6. Label Studio - Project View**

**URL:** http://localhost:4115/projects/{project_id}

**What to capture:**
- Task list view with imported batch results
- Show task status, annotations, predictions

**Save to:** `docs/screenshots/label-studio/project-view.png`

**Recommended size:** 1920x1080

---

### **7. Label Studio - Labeling Interface**

**URL:** Open any task in Label Studio

**What to capture:**
- Individual labeling task interface
- Show input data, predictions, annotation controls

**Save to:** `docs/screenshots/label-studio/labeling-interface.png`

**Recommended size:** 1920x1080

---

### **8. Model Management - Installation UI**

**URL:** http://localhost:4080/models/install

**What to capture:**
- Model installation interface
- HuggingFace URL input field
- "Analyze Model" button
- Clean, empty state

**Save to:** `docs/screenshots/model-management/install-ui.png`

**Recommended size:** 1920x1080

---

### **9. Model Management - Analysis Results**

**URL:** http://localhost:4080/models/install

**Setup:**
```
1. Paste a HuggingFace model URL (e.g., https://huggingface.co/google/gemma-3-4b-it)
2. Click "Analyze Model"
3. Wait for analysis to complete
```

**What to capture:**
- Analysis results showing model size, memory requirements
- Compatibility check (will it fit on GPU?)
- Install button

**Save to:** `docs/screenshots/model-management/analysis-results.png`

**Recommended size:** 1920x1080

---

### **10. Benchmark Results**

**Option A:** If you have existing benchmark results:
- Open `benchmarks/results/` folder
- Find a comparison chart or results table
- Screenshot it

**Option B:** Run a quick benchmark:
```bash
# Run a small benchmark
python -m core.benchmarks.run_benchmark \
  --models "google/gemma-3-4b-it" \
  --dataset examples/datasets/candidate_evaluation_sample.jsonl \
  --max-samples 10
```

**What to capture:**
- Benchmark comparison table or chart
- Show model names, throughput, quality metrics

**Save to:** `docs/screenshots/benchmarks/comparison.png`

**Recommended size:** 1920x1080

---

## 🎨 Screenshot Best Practices

### **Resolution**
- **Recommended:** 1920x1080 (Full HD)
- **Minimum:** 1200x800
- **Maximum:** 2560x1440 (4K is too large)

### **Format**
- **Use PNG** (not JPG) for crisp text
- **Compress** if file size > 500KB (use `pngquant` or similar)

### **Content**
- **Show the full interface** - don't crop too tightly
- **Include browser chrome** (optional) - shows it's a real web app
- **Use light theme** if available (better for docs)
- **Hide personal info** - no real names, emails, etc.

### **Naming**
- Use descriptive names: `queue-monitor-with-jobs.png` not `screenshot1.png`
- Use kebab-case: `label-studio-projects.png` not `Label Studio Projects.png`
- Be consistent

---

## 🛠️ Tools

### **Linux**
- **Flameshot** (recommended): `sudo apt install flameshot`
- **GNOME Screenshot**: Built-in
- **Spectacle** (KDE): Built-in

### **macOS**
- **Cmd+Shift+4**: Select area
- **Cmd+Shift+3**: Full screen
- **Cmd+Shift+5**: Advanced options

### **Windows**
- **Snipping Tool**: Built-in
- **Win+Shift+S**: Quick screenshot
- **ShareX** (recommended): Free, powerful

---

## 📦 After Capturing

### **1. Review Quality**
- Check that text is readable
- Ensure no personal information is visible
- Verify colors look good

### **2. Optimize File Size**
```bash
# Install pngquant (optional)
sudo apt install pngquant  # Linux
brew install pngquant      # macOS

# Compress all screenshots
find docs/screenshots -name "*.png" -exec pngquant --ext .png --force {} \;
```

### **3. Update Documentation**
The screenshots will be automatically referenced in the docs. Just make sure they're in the right folders!

---

## ✅ Verification

Check that you have all screenshots:

```bash
# List all screenshots
find docs/screenshots -name "*.png" | sort

# Expected output:
# docs/screenshots/benchmarks/comparison.png
# docs/screenshots/grafana/main-dashboard.png
# docs/screenshots/label-studio/labeling-interface.png
# docs/screenshots/label-studio/project-view.png
# docs/screenshots/label-studio/projects-list.png
# docs/screenshots/model-management/analysis-results.png
# docs/screenshots/model-management/install-ui.png
# docs/screenshots/queue-monitor/empty-state.png
# docs/screenshots/queue-monitor/with-jobs.png
# docs/screenshots/swagger-ui/api-docs.png
```

---

## 🚀 Next Steps

Once you have all screenshots:

1. **Verify quality** - Check each screenshot
2. **Optimize size** - Compress if needed
3. **Update docs** - Screenshots are already referenced in guides
4. **Commit** - Add screenshots to git

```bash
git add docs/screenshots/
git commit -m "docs: Add screenshots for all guides"
```

---

**Need help?** Open an issue or ask in discussions!

