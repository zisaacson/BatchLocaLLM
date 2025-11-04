# vLLM Batch Server - Troubleshooting Guide

This guide helps you diagnose and fix common issues with the vLLM Batch Server.

---

## 📚 **Table of Contents**

1. [Service Issues](#service-issues)
2. [GPU Issues](#gpu-issues)
3. [Batch Job Issues](#batch-job-issues)
4. [Fine-Tuning Issues](#fine-tuning-issues)
5. [Label Studio Issues](#label-studio-issues)
6. [Performance Issues](#performance-issues)
7. [Database Issues](#database-issues)

---

## 🔧 **Service Issues**

### **Services Not Starting**

**Symptoms**:
- `docker compose up` fails
- Services exit immediately
- Port conflicts

**Diagnosis**:
```bash
# Check Docker logs
docker compose logs -f

# Check specific service
docker logs vllm-batch-server

# Check port usage
sudo lsof -i :4000
sudo lsof -i :4115
```

**Solutions**:

1. **Port already in use**:
   ```bash
   # Kill process using port
   sudo kill -9 $(sudo lsof -t -i:4000)
   
   # Or change port in docker-compose.yml
   ports:
     - "4001:4000"  # Use different host port
   ```

2. **Docker daemon not running**:
   ```bash
   sudo systemctl start docker
   ```

3. **Insufficient permissions**:
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

4. **Corrupted containers**:
   ```bash
   docker compose down -v
   docker compose up -d
   ```

---

## 🎮 **GPU Issues**

### **GPU Not Detected**

**Symptoms**:
- vLLM fails to start
- Error: "No CUDA devices found"
- Models load on CPU instead of GPU

**Diagnosis**:
```bash
# Check NVIDIA drivers
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Check vLLM logs
docker logs vllm-server | grep -i cuda
```

**Solutions**:

1. **Install NVIDIA drivers**:
   ```bash
   # Ubuntu
   sudo apt update
   sudo apt install nvidia-driver-535
   sudo reboot
   ```

2. **Install NVIDIA Container Toolkit**:
   ```bash
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
     sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt update
   sudo apt install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```

3. **Verify GPU in Docker**:
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

### **Out of Memory (OOM)**

**Symptoms**:
- vLLM crashes with "CUDA out of memory"
- Model fails to load
- Batch jobs fail randomly

**Diagnosis**:
```bash
# Check GPU memory usage
nvidia-smi

# Check vLLM memory usage
docker stats vllm-server
```

**Solutions**:

1. **Reduce model size**:
   - Use quantized models (4-bit, 8-bit)
   - Use smaller models (7B instead of 13B)

2. **Reduce batch size**:
   ```python
   # In vLLM config
   max_num_seqs = 32  # Reduce from default
   ```

3. **Enable GPU memory fraction**:
   ```python
   # In vLLM config
   gpu_memory_utilization = 0.8  # Use 80% of GPU memory
   ```

4. **Use CPU offloading**:
   ```python
   # In vLLM config
   cpu_offload_gb = 8  # Offload 8GB to CPU
   ```

---

## 📦 **Batch Job Issues**

### **Batch Job Stuck in "Validating"**

**Symptoms**:
- Batch job status never changes from "validating"
- No progress after hours

**Diagnosis**:
```bash
# Check batch job status
curl http://localhost:4000/v1/batches/{batch_id}

# Check vLLM logs
docker logs vllm-server | grep -i batch

# Check database
sqlite3 data/database/batch_jobs.db "SELECT * FROM batch_jobs WHERE id='batch_abc123';"
```

**Solutions**:

1. **Restart vLLM server**:
   ```bash
   docker restart vllm-server
   ```

2. **Check input file format**:
   ```bash
   # Validate JSONL format
   cat batch_requests.jsonl | jq .
   ```

3. **Verify model is loaded**:
   ```bash
   curl http://localhost:4000/v1/models
   ```

### **Batch Job Fails with "Model Not Found"**

**Symptoms**:
- Batch job fails immediately
- Error: "Model 'xyz' not found"

**Diagnosis**:
```bash
# List available models
curl http://localhost:4000/v1/models

# Check model registry
curl http://localhost:4000/v1/models/registry
```

**Solutions**:

1. **Load the model**:
   ```bash
   # Via API
   curl -X POST http://localhost:4000/v1/models/load \
     -H "Content-Type: application/json" \
     -d '{"model_name": "gemma-3-12b"}'
   ```

2. **Add the model**:
   - Go to http://localhost:4000/static/model-management.html
   - Click "Add Model"
   - Enter model name and HuggingFace ID

### **Batch Job Results Missing**

**Symptoms**:
- Batch job completes but no output file
- Output file is empty

**Diagnosis**:
```bash
# Check output file
curl http://localhost:4000/v1/files/{output_file_id}/content

# Check failed requests
sqlite3 data/database/batch_jobs.db "SELECT * FROM failed_requests WHERE batch_id='batch_abc123';"
```

**Solutions**:

1. **Check failed requests**:
   ```bash
   # Get failed requests
   curl http://localhost:4000/v1/batches/{batch_id}/failed_requests
   ```

2. **Retry failed requests**:
   ```bash
   # Resubmit batch with failed requests only
   curl -X POST http://localhost:4000/v1/batches \
     -H "Content-Type: application/json" \
     -d '{"input_file_id": "file_failed_abc123", ...}'
   ```

---

## 🎓 **Fine-Tuning Issues**

### **Fine-Tuning Job Fails**

**Symptoms**:
- Training job fails immediately
- Error: "CUDA out of memory"
- Error: "Dataset format invalid"

**Diagnosis**:
```bash
# Check training logs
docker logs vllm-batch-server | grep -i "fine_tuning"

# Check GPU memory
nvidia-smi

# Validate dataset
cat training_data.jsonl | jq .
```

**Solutions**:

1. **Reduce batch size**:
   ```json
   {
     "hyperparameters": {
       "per_device_train_batch_size": 1,
       "gradient_accumulation_steps": 4
     }
   }
   ```

2. **Use gradient checkpointing**:
   ```json
   {
     "hyperparameters": {
       "gradient_checkpointing": true
     }
   }
   ```

3. **Reduce LoRA rank**:
   ```json
   {
     "hyperparameters": {
       "lora_r": 8,
       "lora_alpha": 16
     }
   }
   ```

4. **Fix dataset format**:
   ```jsonl
   {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
   ```

### **Fine-Tuned Model Not Loading**

**Symptoms**:
- Model training succeeds but deployment fails
- Error: "Model not found"

**Diagnosis**:
```bash
# Check model files
ls -lh models/fine_tuned/

# Check model registry
curl http://localhost:4000/v1/models/registry
```

**Solutions**:

1. **Verify model path**:
   ```bash
   # Check model directory
   ls -lh models/fine_tuned/my_model/
   
   # Should contain:
   # - adapter_config.json
   # - adapter_model.bin
   # - tokenizer files
   ```

2. **Reload model**:
   ```bash
   curl -X POST http://localhost:4000/v1/fine_tuning/jobs/{job_id}/deploy
   ```

---

## 🏷️ **Label Studio Issues**

### **Label Studio Not Accessible**

**Symptoms**:
- Cannot access http://localhost:4115
- Connection refused

**Diagnosis**:
```bash
# Check if Label Studio is running
docker ps | grep label-studio

# Check logs
docker logs label-studio
```

**Solutions**:

1. **Start Label Studio**:
   ```bash
   docker compose up -d label-studio
   ```

2. **Check port binding**:
   ```bash
   sudo lsof -i :4115
   ```

### **Webhook Not Syncing**

**Symptoms**:
- Annotations in Label Studio don't sync to Aristotle
- No webhook events in logs

**Diagnosis**:
```bash
# Check webhook configuration in Label Studio
# Settings → Webhooks

# Check Aristotle logs
docker logs aristotle-web | grep -i webhook

# Test webhook manually
curl -X POST http://localhost:4000/api/webhooks/label-studio \
  -H "Content-Type: application/json" \
  -d '{"action": "ANNOTATION_CREATED", ...}'
```

**Solutions**:

1. **Verify webhook URL**:
   - Should be: `http://localhost:4000/api/webhooks/label-studio`
   - Or: `http://host.docker.internal:4000/api/webhooks/label-studio` (from Docker)

2. **Check webhook secret**:
   ```bash
   # In .env.local
   LABEL_STUDIO_WEBHOOK_SECRET=your-secret-here
   ```

3. **Verify webhook events**:
   - Enable: ANNOTATION_CREATED, ANNOTATION_UPDATED

4. **Check firewall**:
   ```bash
   sudo ufw allow 4000
   ```

---

## ⚡ **Performance Issues**

### **Slow Batch Processing**

**Symptoms**:
- Batch jobs take hours to complete
- Low GPU utilization

**Diagnosis**:
```bash
# Check GPU utilization
nvidia-smi -l 1

# Check vLLM metrics
curl http://localhost:4000/metrics | grep vllm
```

**Solutions**:

1. **Increase batch size**:
   ```python
   max_num_seqs = 128  # Increase from default
   ```

2. **Enable tensor parallelism**:
   ```python
   tensor_parallel_size = 2  # Use 2 GPUs
   ```

3. **Use faster model**:
   - Use quantized models (4-bit, 8-bit)
   - Use smaller models

### **High Memory Usage**

**Symptoms**:
- Server runs out of memory
- OOM killer terminates processes

**Diagnosis**:
```bash
# Check memory usage
free -h

# Check Docker memory
docker stats
```

**Solutions**:

1. **Limit Docker memory**:
   ```yaml
   # docker-compose.yml
   services:
     vllm-server:
       mem_limit: 32g
   ```

2. **Enable swap**:
   ```bash
   sudo fallocate -l 32G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

---

## 🗄️ **Database Issues**

### **Database Locked**

**Symptoms**:
- Error: "database is locked"
- Queries timeout

**Diagnosis**:
```bash
# Check database file
ls -lh data/database/batch_jobs.db

# Check processes using database
lsof data/database/batch_jobs.db
```

**Solutions**:

1. **Restart services**:
   ```bash
   docker compose restart
   ```

2. **Migrate to PostgreSQL**:
   - SQLite has concurrency limitations
   - Use PostgreSQL for production

### **Database Corruption**

**Symptoms**:
- Error: "database disk image is malformed"
- Cannot query database

**Diagnosis**:
```bash
# Check database integrity
sqlite3 data/database/batch_jobs.db "PRAGMA integrity_check;"
```

**Solutions**:

1. **Restore from backup**:
   ```bash
   cp data/database/batch_jobs.db.backup data/database/batch_jobs.db
   ```

2. **Rebuild database**:
   ```bash
   # Export data
   sqlite3 data/database/batch_jobs.db ".dump" > backup.sql
   
   # Delete corrupted database
   rm data/database/batch_jobs.db
   
   # Recreate database
   sqlite3 data/database/batch_jobs.db < backup.sql
   ```

---

## 📞 **Getting Help**

If you're still experiencing issues:

1. **Check logs**:
   ```bash
   docker compose logs -f
   ```

2. **Search GitHub issues**:
   - https://github.com/your-org/vllm-batch-server/issues

3. **Create a new issue**:
   - Include logs, error messages, and steps to reproduce
   - Use the issue template

4. **Join Discord**:
   - Get help from the community

---

**Good luck!** 🍀

