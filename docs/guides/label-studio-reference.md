# Label Studio Quick Reference

**One-page reference for Label Studio with vLLM Batch Server**

---

## 🚀 Quick Start

```bash
# Automated setup (recommended)
./scripts/setup_label_studio.sh

# Manual start
cd docker && docker compose up -d label-studio
```

---

## 🔑 Default Credentials

**URL:** http://localhost:4115

**Admin Account:**
- Email: `admin@vllm-batch.local`
- Password: `VllmBatch2024!` (or your custom password)

**⚠️ Store in password manager!**

---

## 📋 Configuration

### **.env Settings**

```bash
LABEL_STUDIO_URL=http://localhost:4115
LABEL_STUDIO_TOKEN=<get from Account & Settings>
LABEL_STUDIO_PROJECT_ID=1
AUTO_IMPORT_TO_CURATION=true
CURATION_API_URL=http://localhost:4115
```

### **For Remote Access (Main App on Different Computer)**

```bash
LABEL_STUDIO_URL=http://10.0.0.223:4115  # Use server IP
LABEL_STUDIO_TOKEN=<same token>
LABEL_STUDIO_PROJECT_ID=1
CURATION_API_URL=http://10.0.0.223:4115
```

---

## 🔧 Common Commands

### **Start/Stop**

```bash
# Start
cd docker && docker compose up -d label-studio

# Stop
cd docker && docker compose down label-studio

# Restart
cd docker && docker compose restart label-studio

# View logs
docker logs vllm-label-studio -f
```

### **Health Check**

```bash
# Check if running
curl http://localhost:4115/health

# Should return: {"status": "UP"}
```

### **Get API Token**

1. Go to http://localhost:4115
2. Log in
3. Click profile icon → Account & Settings
4. Scroll to "Access Token"
5. Copy token

### **Test API Connection**

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:4115/api/projects/1/
```

---

## 💾 Data Persistence

### **Storage Location**

Docker volume: `vllm-label-studio-data`

Physical location: `/var/lib/docker/volumes/vllm-label-studio-data/_data`

### **Backup**

```bash
# Create backup
docker run --rm \
  -v vllm-label-studio-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/label-studio-$(date +%Y%m%d).tar.gz /data

# Restore backup
docker run --rm \
  -v vllm-label-studio-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/label-studio-YYYYMMDD.tar.gz -C /
```

### **Reset (Nuclear Option)**

```bash
# ⚠️ WARNING: This deletes ALL data!
cd docker
docker compose down label-studio
docker volume rm vllm-label-studio-data
docker compose up -d label-studio
# Then run setup script again
```

---

## 🔄 Integration Flow

```
Batch Job → Worker → Label Studio API → Tasks in UI
                                            ↓
                                    Human Review
                                            ↓
                                    Export Data
```

---

## 🚨 Troubleshooting

### **Problem: Can't log in**

```bash
# Reset password
docker exec -it vllm-label-studio \
  python manage.py changepassword admin@vllm-batch.local
```

### **Problem: Container keeps restarting**

```bash
# Check logs
docker logs vllm-label-studio

# Common issue: Database connection
# Solution: Remove PostgreSQL env vars (already fixed in docker-compose.yml)
```

### **Problem: Data not persisting**

```bash
# Check volume is mounted
docker inspect vllm-label-studio | jq '.[0].Mounts'

# Should show: vllm-label-studio-data mounted to /label-studio/data
```

### **Problem: Token expired**

1. Log in to Label Studio
2. Generate new token (Account & Settings)
3. Update `.env` file
4. Restart batch server: `cd docker && docker compose restart api-server worker`

### **Problem: Can't access from main app**

1. Check firewall allows port 4115
2. Use server IP, not localhost
3. Update main app's `.env` with server IP
4. Test: `curl http://SERVER_IP:4115/health`

---

## 📊 Usage

### **Review Tasks**

1. Go to http://localhost:4115
2. Click project name
3. Click "Label All Tasks"
4. Review → Edit → Rate → Submit

### **Export Data**

1. Go to project
2. Click "Export" button
3. Choose format (JSON recommended)
4. Download file

### **Filter Tasks**

- **Completed:** Already reviewed
- **Incomplete:** Need review
- **Starred:** High quality (5-star rating)

---

## 🔐 Security Checklist

- [ ] Changed default password
- [ ] Stored credentials in password manager
- [ ] Backed up API token
- [ ] `.env` file not committed to git
- [ ] Using HTTPS in production (if deployed)
- [ ] Regular backups scheduled

---

## 📞 Support

- **Full Documentation:** `docs/LABEL_STUDIO_SETUP.md`
- **Setup Script:** `./scripts/setup_label_studio.sh`
- **Config File:** `config/label_studio_interface.xml`
- **Label Studio Docs:** https://labelstud.io/guide/

---

## ✅ Quick Verification

After setup, verify:

```bash
# 1. Container running
docker ps | grep label-studio

# 2. Health check
curl http://localhost:4115/health

# 3. Can log in
# Open http://localhost:4115 in browser

# 4. API works
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:4115/api/projects/1/

# 5. Data persists
docker compose restart label-studio
# Wait 30 seconds, then log in again - should not ask for signup
```

---

**Last Updated:** 2025-11-02

