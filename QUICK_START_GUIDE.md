# 🚀 Quick Start Guide - vLLM Batch Server + Aristotle Integration

**Last Updated:** 2025-11-05

---

## 📋 System Overview

You now have **3 systems** running on your computer:

1. **Aristotle Web App** (Port 4002) - Your main application with conquests
2. **vLLM Batch Server** (Port 4080) - Batch inference API for LLMs
3. **Label Studio** (Port 4115) - Data annotation and gold star management

All three are **fully connected** and ready to use!

---

## ⚡ Quick Commands

### **Start the vLLM Batch Server**
```bash
cd /home/zack/Documents/augment-projects/Local/vllm-batch-server
nohup ./venv/bin/python -m core.batch_app.api_server > logs/api_server.log 2>&1 &
```

### **Check Server Status**
```bash
curl http://localhost:4080/health | jq '.'
curl http://localhost:4080/v1/aris/health | jq '.'
```

### **View Logs**
```bash
tail -f logs/api_server.log
```

### **Stop the Server**
```bash
pkill -f "python.*api_server"
```

---

## 🔄 Typical Workflow

### **1. Create a Conquest in Aristotle**

In your Aristotle web app:
1. Create a new conquest (e.g., candidate evaluation)
2. Submit it for processing
3. The conquest is stored in the Aristotle database

### **2. Process with vLLM Batch Server**

The vLLM batch server can:
- List all conquests: `GET /v1/aris/conquests`
- Get conquest details: `GET /v1/aris/conquests/{id}`
- Process batch jobs with vLLM models

### **3. Review Results in Label Studio**

1. Results are imported as tasks in Label Studio
2. Annotators review and rate the quality
3. High-quality results are marked as "gold stars"

### **4. Sync Gold Stars Back to Aristotle**

When a task is marked as gold star in Label Studio:
```bash
curl -X POST http://localhost:4080/v1/aris/sync/victory-to-gold-star \
  -H "Content-Type: application/json" \
  -d '{
    "conquest_id": "your-conquest-id",
    "evaluated_by": "user@example.com",
    "result_notes": "Excellent analysis"
  }'
```

This updates the conquest in Aristotle to `result = VICTORY`.

### **5. Export Training Data**

Get gold star examples for fine-tuning:
```bash
curl "http://localhost:4080/v1/aris/icl/examples?philosopher=user@example.com&domain=your-domain&limit=10&format=chatml" | jq '.'
```

Formats available:
- `chatml` - For Unsloth/vLLM fine-tuning
- `alpaca` - For Axolotl
- `openai` - For OpenAI fine-tuning API

---

## 📊 API Endpoints Reference

### **Health & Status**
- `GET /health` - Server health check
- `GET /v1/aris/health` - Aris integration health check

### **Conquests**
- `GET /v1/aris/conquests` - List all conquests
  - Query params: `status`, `result`, `conquest_type`, `use_as_example`, `limit`, `offset`
- `GET /v1/aris/conquests/{id}` - Get conquest details

### **Gold Stars & Training Data**
- `POST /v1/aris/sync/victory-to-gold-star` - Sync VICTORY to gold star
- `GET /v1/aris/icl/examples` - Get gold star examples for ICL
  - Query params: `philosopher`, `domain`, `conquest_type`, `limit`, `format`

### **Batch Jobs**
- `POST /v1/jobs` - Submit batch job
- `GET /v1/jobs` - List all jobs
- `GET /v1/jobs/{id}` - Get job details
- `GET /v1/jobs/history` - Job history with stats

### **Models**
- `GET /v1/models` - List available models

### **Web UIs**
- `http://localhost:4080/` - Main dashboard
- `http://localhost:4080/queue` - Job queue viewer
- `http://localhost:4080/history` - Job history viewer
- `http://localhost:4080/workbench` - Model testing workbench
- `http://localhost:8001/` - Curation web app

---

## 🧪 Testing the Integration

### **Test 1: Database Connection**
```bash
./venv/bin/python << 'EOF'
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:postgres@localhost:4002/aristotle_dev')
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM conquests"))
    print(f"✅ Conquests in database: {result.fetchone()[0]}")
EOF
```

### **Test 2: List Conquests**
```bash
curl "http://localhost:4080/v1/aris/conquests?limit=5" | jq '.'
```

### **Test 3: ICL Examples**
```bash
curl "http://localhost:4080/v1/aris/icl/examples?philosopher=test@example.com&domain=software_engineering&limit=5" | jq '.'
```

---

## 🔧 Configuration

### **Environment Variables** (`.env`)
```bash
# Aristotle Database
ARISTOTLE_DATABASE_URL=postgresql://postgres:postgres@localhost:4002/aristotle_dev

# vLLM Batch Database
DATABASE_URL=postgresql://vllm_batch_user:vllm_batch_password_dev@localhost:5432/vllm_batch

# Aris Integration
ENABLE_ARIS_INTEGRATION=true

# Label Studio
LABEL_STUDIO_URL=http://localhost:4115
LABEL_STUDIO_API_KEY=your-api-key-here
```

### **Ports**
- **4002** - Aristotle PostgreSQL database
- **4080** - vLLM Batch Server API
- **4115** - Label Studio
- **5432** - vLLM Batch PostgreSQL database
- **8001** - Curation Web App

---

## 📁 Important Files

### **Configuration**
- `.env` - Environment variables (gitignored)
- `core/batch_app/config.py` - Server configuration

### **Integration Code**
- `integrations/aris/conquest_api.py` - Aris API endpoints
- `integrations/aris/aristotle_db.py` - Database models
- `integrations/aris/training/dataset_exporter.py` - Training data export

### **Documentation**
- `ARISTOTLE_INTEGRATION_COMPLETE.md` - Integration details
- `FEATURE_PARITY_REPORT.md` - Complete feature inventory
- `CURRENT_STATUS_REALITY_CHECK.md` - System status

### **Web UIs**
- `static/index.html` - Main dashboard
- `static/queue.html` - Job queue viewer
- `static/history.html` - Job history viewer
- `static/workbench.html` - Model testing workbench

---

## 🐛 Troubleshooting

### **Server won't start**
```bash
# Check for zombie processes
ps aux | grep -E "python|vllm" | grep -v grep

# Kill zombie processes
pkill -f "python.*api_server"
pkill -f vllm

# Check GPU memory
nvidia-smi
```

### **Database connection errors**
```bash
# Test Aristotle database
psql -h localhost -p 4002 -U postgres -d aristotle_dev -c "SELECT COUNT(*) FROM conquests"

# Test vLLM batch database
psql -h localhost -p 5432 -U vllm_batch_user -d vllm_batch -c "SELECT COUNT(*) FROM jobs"
```

### **Endpoints returning errors**
```bash
# Check server logs
tail -50 logs/api_server.log

# Test health endpoint
curl http://localhost:4080/health

# Test Aris health endpoint
curl http://localhost:4080/v1/aris/health
```

---

## 📚 Additional Resources

### **Documentation**
- [vLLM Documentation](https://docs.vllm.ai/)
- [Label Studio Documentation](https://labelstud.io/guide/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### **Project Files**
- `README.md` - Project overview
- `FEATURE_PARITY_REPORT.md` - Complete feature list
- `PLUGIN_SYSTEM_COMPLETE.md` - Plugin system guide

---

## ✅ Checklist

Before running your first conquest:

- [ ] vLLM Batch Server is running (`curl http://localhost:4080/health`)
- [ ] Aristotle database is accessible (`psql -h localhost -p 4002 -U postgres -d aristotle_dev`)
- [ ] Aris integration is enabled (`curl http://localhost:4080/v1/aris/health`)
- [ ] Label Studio is running (optional, for gold stars)
- [ ] Environment variables are configured (`.env` file)

---

## 🎉 You're Ready!

Your vLLM Batch Server is fully integrated with Aristotle and ready for production use!

**Next Steps:**
1. Run your first conquest in Aristotle
2. Check it appears in `/v1/aris/conquests`
3. Process it with vLLM models
4. Review results in Label Studio
5. Mark high-quality results as gold stars
6. Export training data for fine-tuning

**Questions?** Check the documentation files or the API at `http://localhost:4080/docs`

Happy conquesting! 🚀

