# Label Studio Setup Guide

**Complete setup guide for Label Studio integration with vLLM Batch Server**

---

## 🎯 Overview

Label Studio is used for:
1. **Data Curation** - Review and edit LLM responses
2. **Quality Control** - Mark high-quality examples with gold stars
3. **Training Data** - Export curated data for fine-tuning/ICL

---

## 📋 Prerequisites

- Docker and Docker Compose installed
- vLLM Batch Server running
- Port 4115 available

---

## 🚀 Quick Start (Automated)

Run the automated setup script:

```bash
./scripts/setup_label_studio.sh
```

This will:
1. Start Label Studio container
2. Create admin account
3. Create project with correct labeling interface
4. Generate API token
5. Update .env file
6. Test the connection

---

## 🔧 Manual Setup (Step-by-Step)

### **Step 1: Start Label Studio**

```bash
cd docker
docker compose up -d label-studio
```

Wait 30-60 seconds for Label Studio to start.

### **Step 2: Access Label Studio**

Open in browser: http://localhost:4115

### **Step 3: Create Admin Account**

**IMPORTANT:** Use these exact credentials (stored in password manager):

- **Email:** `admin@vllm-batch.local`
- **Password:** `VllmBatch2024!` (or your secure password)

**⚠️ Write these down!** This is the ONLY time you'll set this up if you do it right.

### **Step 4: Create Project**

1. Click **"Create Project"**
2. **Project Name:** `vLLM Batch Results`
3. **Description:** `Curation and quality control for vLLM batch processing results`
4. Click **"Save"**

### **Step 5: Configure Labeling Interface**

1. Go to **Settings** → **Labeling Interface**
2. Click **"Code"** tab
3. Paste this XML configuration:

```xml
<View>
  <Header value="Candidate Evaluation Review"/>
  
  <!-- Input Data Display -->
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Candidate Information"/>
    <Text name="candidate_name" value="$candidate_name"/>
    <Text name="candidate_title" value="$candidate_title"/>
    <Text name="candidate_company" value="$candidate_company"/>
  </View>
  
  <!-- Model Response Display -->
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Model Response"/>
    <Text name="model_name" value="Model: $model_name"/>
    <TextArea name="response" value="$response" rows="10" editable="true"/>
  </View>
  
  <!-- Evaluation Fields -->
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Evaluation"/>
    
    <Choices name="recommendation" toName="response" choice="single" showInline="true">
      <Header value="Recommendation"/>
      <Choice value="Strong Yes"/>
      <Choice value="Yes"/>
      <Choice value="Maybe"/>
      <Choice value="No"/>
      <Choice value="Strong No"/>
    </Choices>
    
    <Choices name="trajectory" toName="response" choice="single" showInline="true">
      <Header value="Career Trajectory"/>
      <Choice value="Exceptional"/>
      <Choice value="Strong"/>
      <Choice value="Good"/>
      <Choice value="Average"/>
      <Choice value="Weak"/>
    </Choices>
    
    <Choices name="company_pedigree" toName="response" choice="single" showInline="true">
      <Header value="Company Pedigree"/>
      <Choice value="Exceptional"/>
      <Choice value="Strong"/>
      <Choice value="Good"/>
      <Choice value="Average"/>
      <Choice value="Weak"/>
    </Choices>
    
    <Choices name="educational_pedigree" toName="response" choice="single" showInline="true">
      <Header value="Educational Pedigree"/>
      <Choice value="Exceptional"/>
      <Choice value="Strong"/>
      <Choice value="Good"/>
      <Choice value="Average"/>
      <Choice value="Weak"/>
    </Choices>
    
    <Checkbox name="is_software_engineer" toName="response">
      <Label value="Is Software Engineer"/>
    </Checkbox>
  </View>
  
  <!-- Quality Rating -->
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Quality Control"/>
    <Rating name="quality" toName="response" maxRating="5" icon="star" size="large"/>
    <TextArea name="notes" toName="response" placeholder="Notes or corrections..." rows="3"/>
  </View>
</View>
```

4. Click **"Save"**

### **Step 6: Get API Token**

1. Click your profile icon (top right)
2. Go to **"Account & Settings"**
3. Scroll to **"Access Token"**
4. Click **"Copy Token"**
5. Save this token - you'll need it!

### **Step 7: Update .env File**

Update your `.env` file with the token:

```bash
LABEL_STUDIO_URL=http://localhost:4115
LABEL_STUDIO_TOKEN=<YOUR_TOKEN_HERE>
LABEL_STUDIO_PROJECT_ID=1
AUTO_IMPORT_TO_CURATION=true
CURATION_API_URL=http://localhost:4115
```

### **Step 8: Get Project ID**

1. In Label Studio, go to your project
2. Look at the URL: `http://localhost:4115/projects/1/`
3. The number is your project ID (usually `1`)
4. Update `LABEL_STUDIO_PROJECT_ID=1` in `.env`

### **Step 9: Test Connection**

```bash
curl -H "Authorization: Token YOUR_TOKEN_HERE" \
  http://localhost:4115/api/projects/1/
```

Should return project details in JSON.

---

## 🔐 Persistence & Backup

### **Data Storage**

Label Studio data is stored in Docker volume: `vllm-label-studio-data`

**Location:** `/var/lib/docker/volumes/vllm-label-studio-data/_data`

### **Backup Label Studio Data**

```bash
# Backup
docker run --rm \
  -v vllm-label-studio-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/label-studio-backup-$(date +%Y%m%d).tar.gz /data

# Restore
docker run --rm \
  -v vllm-label-studio-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/label-studio-backup-YYYYMMDD.tar.gz -C /
```

### **Export Project Configuration**

Save your project configuration to version control:

1. Go to **Settings** → **Labeling Interface**
2. Copy the XML configuration
3. Save to `config/label_studio_interface.xml`
4. Commit to git

---

## 🔄 Integration with vLLM Batch Server

### **How It Works**

1. **Batch Job Completes** → Worker sends results to Label Studio
2. **Auto-Import** → Results appear as tasks in Label Studio
3. **Human Review** → Annotators review and correct responses
4. **Export** → Curated data exported for training

### **Data Flow**

```
vLLM Batch Job → Worker → Label Studio API → Label Studio UI
                                                    ↓
                                            Human Annotation
                                                    ↓
                                            Export Training Data
```

### **API Integration**

The batch server automatically imports results if `AUTO_IMPORT_TO_CURATION=true`:

```python
# In worker.py
if settings.AUTO_IMPORT_TO_CURATION:
    import_to_label_studio(
        batch_id=job.batch_id,
        results=results,
        model_name=job.model_name
    )
```

---

## 📊 Using Label Studio

### **Review Tasks**

1. Go to your project
2. Click **"Label All Tasks"**
3. Review each response
4. Edit if needed
5. Select ratings
6. Click **"Submit"**

### **Filter Tasks**

- **Completed:** Tasks you've reviewed
- **Incomplete:** Tasks needing review
- **Starred:** High-quality examples

### **Export Data**

1. Go to project
2. Click **"Export"**
3. Choose format: **JSON** or **CSV**
4. Download curated dataset

---

## 🚨 Troubleshooting

### **Problem: Label Studio won't start**

```bash
# Check logs
docker logs vllm-label-studio

# Restart
cd docker
docker compose restart label-studio
```

### **Problem: Lost admin password**

```bash
# Reset password via Django shell
docker exec -it vllm-label-studio python manage.py changepassword admin@vllm-batch.local
```

### **Problem: Token expired**

1. Log in to Label Studio
2. Go to Account & Settings
3. Generate new token
4. Update `.env` file
5. Restart batch server

### **Problem: Data not persisting**

```bash
# Check volume exists
docker volume ls | grep label-studio

# Check volume is mounted
docker inspect vllm-label-studio | jq '.[0].Mounts'

# Should show: /label-studio/data mounted to vllm-label-studio-data
```

### **Problem: Can't access from other computer**

Update main app's `.env`:

```bash
LABEL_STUDIO_URL=http://10.0.0.223:4115  # Use this computer's IP
```

---

## 🔒 Security Best Practices

1. **Change default password** immediately after setup
2. **Use strong password** (20+ characters, mixed case, numbers, symbols)
3. **Store credentials** in password manager (1Password, LastPass, etc.)
4. **Backup token** to secure location
5. **Don't commit** `.env` file to git (already in `.gitignore`)
6. **Use HTTPS** in production (behind reverse proxy)

---

## 📝 Configuration Files

### **Docker Compose**

Location: `docker/docker-compose.yml`

```yaml
label-studio:
  image: heartexlabs/label-studio:latest
  container_name: vllm-label-studio
  ports:
    - "4115:8080"
  volumes:
    - label-studio-data:/label-studio/data
```

### **Environment Variables**

Location: `.env`

```bash
LABEL_STUDIO_URL=http://localhost:4115
LABEL_STUDIO_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
LABEL_STUDIO_PROJECT_ID=1
AUTO_IMPORT_TO_CURATION=true
```

---

## ✅ Verification Checklist

After setup, verify:

- [ ] Label Studio accessible at http://localhost:4115
- [ ] Can log in with admin credentials
- [ ] Project created with correct name
- [ ] Labeling interface configured
- [ ] API token generated and saved
- [ ] `.env` file updated with token
- [ ] Project ID is correct
- [ ] API connection works (curl test)
- [ ] Data persists after container restart
- [ ] Credentials backed up securely

---

## 🎓 Next Steps

1. **Test the integration** - Run a small batch job and verify it appears in Label Studio
2. **Train annotators** - Show team how to use the interface
3. **Set up backup schedule** - Automate weekly backups
4. **Monitor usage** - Check Label Studio logs regularly
5. **Export training data** - Build your curated dataset

---

## 📚 Resources

- **Label Studio Docs:** https://labelstud.io/guide/
- **API Reference:** https://labelstud.io/api/
- **Labeling Config:** https://labelstud.io/tags/
- **Docker Hub:** https://hub.docker.com/r/heartexlabs/label-studio

---

**Questions?** Check the troubleshooting section or review the logs.

