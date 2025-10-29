# ⚡ Label Studio Quick Start

## 🚀 5-Minute Setup

### 1. Open Label Studio
```
http://localhost:4015
```

### 2. Create Project
- Click **"Create Project"**
- Name: **"Gold Star Candidate Curation"**
- Click **"Save"**

### 3. Configure Interface
- Go to **Settings** → **Labeling Interface**
- Click **"Code"** (top right)
- Delete all XML
- Copy/paste from `label_studio_config.xml`
- Click **"Save"**

### 4. Import Data
- Go to **"Import"** tab
- Upload `label_studio_tasks.json`
- Wait for 5,000 tasks to import

### 5. Start Labeling
- Click **"Label All Tasks"**
- Rate candidates
- Press **Ctrl+Enter** to submit and next

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Ctrl+Enter** | Submit & Next |
| **Ctrl+Backspace** | Skip |
| **1-9** | Quick select in choice fields |
| **Arrow keys** | Navigate fields |

---

## 📊 What You'll See

**Left Side:**
- Candidate name, role, location
- Education (schools + degrees)
- Experience (top 5 positions)
- LLM evaluation (Gemma 3 12B)

**Right Side:**
- ⭐ Overall rating (1-10 stars)
- 📊 Recommendation (Strong Yes → Strong No)
- 🎓 Educational Pedigree
- 🏢 Company Pedigree
- 📈 Trajectory
- 💻 Is Software Engineer
- 📝 Notes (optional)

---

## 🎯 Goal

Curate **5,000 candidates** to create gold-star training data for fine-tuning.

**Estimated time:** 14-21 hours (10-15 seconds per candidate)

---

## 💡 Tips

1. Use keyboard shortcuts (3x faster)
2. Focus on where you disagree with LLM
3. Take breaks every hour
4. Export progress regularly

---

## 📤 Export Results

When done:
1. Go to **"Export"** tab
2. Choose **JSON** format
3. Click **"Export"**
4. Download file

---

## 🆘 Help

Full guide: `LABEL_STUDIO_SETUP.md`

Container not running?
```bash
docker start aristotle-label-studio
```

---

**Ready? Go to http://localhost:4015 and start curating! 🚀**

