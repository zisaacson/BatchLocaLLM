# ⭐ Label Studio Setup Guide

## 🎯 Overview

Label Studio is now configured for gold-star candidate curation with:
- **5,000 candidates** from batch_5k.jsonl
- **Gemma 3 12B evaluations** pre-loaded
- **Professional labeling interface** with LinkedIn-style display
- **Keyboard shortcuts** for fast curation

---

## ✅ What's Ready

### 1. **Label Studio Container**
- Running on: http://localhost:4015
- Container: `aristotle-label-studio`
- Status: ✅ Running (5 hours uptime)

### 2. **Data Files**
- ✅ `label_studio_tasks.json` - 5,000 candidates ready to import
- ✅ `label_studio_config.xml` - Labeling interface configuration
- ✅ `prepare_label_studio_data.py` - Data conversion script

### 3. **Features**
- LinkedIn-style candidate profile display
- LLM evaluation pre-loaded (Gemma 3 12B)
- 1-10 star rating system
- Categorical evaluations (Educational Pedigree, Company Pedigree, Trajectory, Is SWE)
- Notes field for additional observations

---

## 🚀 Setup Steps

### Step 1: Log In to Label Studio

1. Open http://localhost:4015 in your browser
2. If first time:
   - Create an account (stored locally in Docker)
   - Username: your choice
   - Password: your choice
3. If already set up:
   - Log in with existing credentials

### Step 2: Create New Project

1. Click **"Create Project"**
2. Project Name: **"Gold Star Candidate Curation"**
3. Click **"Save"**

### Step 3: Configure Labeling Interface

1. In the project, go to **"Settings"** → **"Labeling Interface"**
2. Click **"Code"** (top right)
3. Delete all existing XML
4. Copy and paste the contents of `label_studio_config.xml`
5. Click **"Save"**

### Step 4: Import Data

1. Go to **"Import"** tab
2. Click **"Upload Files"**
3. Select `label_studio_tasks.json`
4. Click **"Import"**
5. Wait for import to complete (5,000 tasks)

### Step 5: Start Labeling!

1. Click **"Label All Tasks"**
2. You'll see:
   - **Left side**: Candidate profile (LinkedIn-style)
   - **Right side**: LLM evaluation + Your rating controls
3. Rate each candidate:
   - ⭐ Overall rating (1-10 stars)
   - 📊 Recommendation (Strong Yes → Strong No)
   - 🎓 Educational Pedigree
   - 🏢 Company Pedigree
   - 📈 Trajectory
   - 💻 Is Software Engineer
   - 📝 Notes (optional)
4. Click **"Submit"** to save and move to next

---

## ⌨️ Keyboard Shortcuts

Label Studio has built-in shortcuts:
- **Ctrl+Enter** or **Cmd+Enter**: Submit and next
- **Ctrl+Backspace**: Skip task
- **Arrow keys**: Navigate between fields
- **Number keys**: Quick select in choice fields

---

## 📊 Export Results

When you're done labeling:

1. Go to **"Export"** tab
2. Choose format:
   - **JSON**: For training data
   - **CSV**: For analysis in Excel/Sheets
3. Click **"Export"**
4. Download file

---

## 🎨 Interface Preview

```
┌─────────────────────────────────────────────────────────┐
│ Min Thet K                                              │
│ Software Engineer at Bloomberg                          │
│ 📍 New York, NY                                         │
├─────────────────────────────────────────────────────────┤
│ 🎓 EDUCATION                                            │
│ • MEng Computer Science from MIT                        │
│ • BS Computer Science from MIT                          │
│                                                         │
│ 💼 EXPERIENCE (TOP 5)                                   │
│ • Software Engineer at Bloomberg (2023-07 - Present)    │
│ • Software Engineer at Microsoft (2021-04 - 2022-01)    │
│                                                         │
│ 🤖 LLM EVALUATION                                       │
│ Recommendation: Strong Yes                              │
│ Reasoning: Exceptional educational background...        │
│                                                         │
│ ⭐ YOUR EVALUATION                                      │
│ Overall Rating: ★★★★★★★★★★ (1-10)                      │
│ Recommendation: ○ Strong Yes ○ Yes ○ Maybe ○ No        │
│ Educational Pedigree: ○ Exceptional ○ Strong...        │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### Container Not Running
```bash
docker start aristotle-label-studio
```

### Reset Data
```bash
docker exec aristotle-label-studio rm /label-studio/data/label_studio.sqlite3
docker restart aristotle-label-studio
```

### Re-generate Tasks
```bash
python3 prepare_label_studio_data.py
```

### Use Different Model Results
```bash
python3 prepare_label_studio_data.py qwen3_4b_5k_offline_results.jsonl
```

---

## 📈 Progress Tracking

Label Studio automatically tracks:
- ✅ Total tasks labeled
- ⏳ Tasks in progress
- ⏭️ Tasks skipped
- 📊 Label distribution
- ⏱️ Time per task
- 📅 Labeling history

View in **"Dashboard"** tab.

---

## 💾 Data Persistence

All data is stored in Docker volume:
- Labels/annotations
- User accounts
- Project settings
- Import history

**Survives container restarts!**

---

## 🎯 Tips for Fast Curation

1. **Use keyboard shortcuts** - Much faster than mouse
2. **Focus on LLM disagreements** - Where you differ from model
3. **Add notes sparingly** - Only for edge cases
4. **Batch similar candidates** - Get into a rhythm
5. **Take breaks** - Avoid decision fatigue

---

## 📊 Expected Performance

- **Time per candidate**: 10-15 seconds (with practice)
- **Candidates per hour**: 240-360
- **Total time for 5,000**: 14-21 hours
- **Sessions recommended**: 10-20 sessions of 1-2 hours each

---

## ✅ Ready to Start!

Everything is set up and ready to go:

1. ✅ Label Studio running
2. ✅ Data converted (5,000 candidates)
3. ✅ Interface configured
4. ✅ LLM evaluations loaded

**Next step:** Open http://localhost:4015 and follow the setup steps above!

🚀 Happy curating!

