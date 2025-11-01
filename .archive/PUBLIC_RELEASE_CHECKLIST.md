# Public Release Checklist - vLLM Batch Server

**Target Audience**: Parasail team, open source community  
**Repository**: https://github.com/zisaacson/vllm-batch-server  
**Status**: ❌ **NOT READY FOR PUBLIC RELEASE**

---

## ⚠️ CRITICAL ISSUES - MUST FIX BEFORE RELEASE

### **1. REAL CANDIDATE DATA IN REPOSITORY** 🚨

**Files containing private candidate information:**

```bash
# Batch input files with real candidate names/companies
batch_5k.jsonl                              # 5K real candidates
batch_5k_olmo2_7b.jsonl                     # Same data
batch_5k_olmo2_fp16.jsonl                   # Same data
batch_5k_gptoss_20b.jsonl                   # Same data
batch_5k_gptoss_fp16.jsonl                  # Same data
batch_5k_gptoss_gguf.jsonl                  # Same data

# Benchmark results with candidate data
benchmarks/raw/olmo2-7b-5k-2025-10-31-173546.jsonl
benchmarks/raw/vllm-native-gemma3-4b-5000-2025-10-28.jsonl

# Results with candidate evaluations
results/gemma-3-4b/batch_5k_20241028T084000.jsonl
results/llama-3.2-1b/batch_5k_20241028T104700.jsonl
results/llama-3.2-3b/batch_5k_20241028T120000.jsonl
results/qwen-3-4b/batch_5k_20241028T143300.jsonl

# Data directory (176MB of files!)
data/files/                                 # Uploaded batch files
data/batches/                               # Batch processing data
data/gold_star/                             # Curated training data
```

**Example of private data found:**
```
Candidate: Min Thet K
Current Role: Software Engineer at Bloomberg
Location: New York, New York, United States
Work History: ...
```

**ACTION REQUIRED:**
1. ✅ Add all these files to `.gitignore` (already done for most)
2. ❌ **DELETE from git history** (they're tracked!)
3. ❌ Create synthetic/anonymized test data
4. ❌ Replace real data with synthetic data

---

### **2. ENVIRONMENT FILES WITH SECRETS** 🔑

**Files containing secrets/credentials:**

```bash
.env                    # Current environment (has Sentry DSN, DB passwords)
.env.a100-cloud         # Cloud environment config
.env.rtx4080-home       # Home environment config
```

**Secrets that may be exposed:**
- Sentry DSN (error tracking)
- PostgreSQL passwords
- API keys (if any)
- Webhook URLs (if any)

**ACTION REQUIRED:**
1. ✅ `.env*` already in `.gitignore` (except `.env.example`)
2. ❌ **Check git history** - were they ever committed?
3. ❌ Rotate all secrets if they were committed
4. ✅ `.env.example` is safe (no real secrets)

---

### **3. ARIS-SPECIFIC INTEGRATIONS** 🏢

**Private integration code:**

```bash
integrations/aris/                          # Aris-specific conquest schemas
integrations/aris/conquest_schemas/         # Candidate evaluation, CV parsing, etc.
integrations/aris/curation_app/             # Aris-specific curation UI
integrations/aris/tests/                    # Aris integration tests
```

**ACTION REQUIRED:**
1. ✅ Already in `.gitignore` (`integrations/aris/`)
2. ❌ **Verify not in git history**
3. ✅ Keep `integrations/examples/` for public examples

---

### **4. DATABASE FILES** 💾

**Files containing job history/metadata:**

```bash
batch_server.db                             # SQLite database (old)
data/database/                              # PostgreSQL data
data/batch_server.db                        # Another SQLite DB
```

**ACTION REQUIRED:**
1. ✅ Already in `.gitignore` (`*.db`, `/data/`)
2. ❌ **Check if tracked in git**
3. ❌ Clear any sensitive metadata

---

## 📋 RELEASE PREPARATION STEPS

### **Phase 1: Clean Git History** 🧹

```bash
# 1. Check what's tracked that shouldn't be
git ls-files | grep -E "batch_5k|\.env\.|data/|integrations/aris"

# 2. Remove sensitive files from git history (DESTRUCTIVE!)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch batch_5k*.jsonl" \
  --prune-empty --tag-name-filter cat -- --all

git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch -r benchmarks/raw/" \
  --prune-empty --tag-name-filter cat -- --all

git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch -r results/" \
  --prune-empty --tag-name-filter cat -- --all

git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch -r data/" \
  --prune-empty --tag-name-filter cat -- --all

git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch -r integrations/aris/" \
  --prune-empty --tag-name-filter cat -- --all

git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env .env.a100-cloud .env.rtx4080-home" \
  --prune-empty --tag-name-filter cat -- --all

# 3. Force push (WARNING: Rewrites history!)
git push origin --force --all
git push origin --force --tags

# 4. Clean up local refs
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

**⚠️ WARNING**: This rewrites git history. Anyone who has cloned the repo will need to re-clone.

---

### **Phase 2: Create Synthetic Test Data** 🎭

```bash
# Create synthetic candidate data for testing
cat > test_data/synthetic_candidates.jsonl << 'EOF'
{"custom_id": "test-001", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "google/gemma-3-4b-it", "messages": [{"role": "system", "content": "You are evaluating a candidate."}, {"role": "user", "content": "**Candidate:** Jane Smith\n**Current Role:** Software Engineer at TechCorp\n**Location:** San Francisco, CA\n\n**Work History:**\n• Software Engineer at TechCorp (2020-Present)\n• Junior Developer at StartupXYZ (2018-2020)\n\n**Education:**\n• BS Computer Science, State University (2018)\n\n**Skills:** Python, JavaScript, React, Node.js"}], "max_tokens": 500}}
EOF

# Create benchmark metadata without real data
cat > benchmarks/metadata/synthetic_5k.json << 'EOF'
{
  "dataset": "synthetic_5k",
  "description": "5000 synthetic candidate evaluations for benchmarking",
  "created_at": "2025-11-01",
  "total_requests": 5000,
  "models_tested": ["gemma-3-4b", "llama-3.2-3b", "qwen-3-4b"],
  "note": "This is synthetic data for demonstration purposes"
}
EOF
```

---

### **Phase 3: Update Documentation** 📚

**Files to update:**

1. **README.md**
   - Remove Aris-specific references
   - Add "Open Source" badge
   - Update installation instructions
   - Add contribution guidelines
   - Add license information

2. **docs/ARCHITECTURE.md**
   - Remove Aris integration details
   - Keep generic "conquest" concept
   - Document public API

3. **docs/API.md**
   - Ensure no private endpoints documented
   - Add OpenAPI/Swagger spec

4. **Create new files:**
   - `LICENSE` (MIT or Apache 2.0?)
   - `CONTRIBUTING.md`
   - `CODE_OF_CONDUCT.md`
   - `SECURITY.md`

---

### **Phase 4: Update .gitignore** ✅

```bash
# Add to .gitignore (most already there)
cat >> .gitignore << 'EOF'

# Private data (NEVER COMMIT)
batch_5k*.jsonl
benchmarks/raw/*.jsonl
results/**/*.jsonl
data/
*.db

# Environment files (NEVER COMMIT)
.env
.env.*
!.env.example

# Aris-specific (NEVER COMMIT)
integrations/aris/
EOF
```

---

### **Phase 5: Code Cleanup** 🧼

**Remove Aris-specific code:**

1. **core/batch_app/worker.py**
   - Remove Aris webhook calls
   - Remove conquest-specific logic (or make it generic)

2. **core/batch_app/api_server.py**
   - Remove Aris-specific endpoints
   - Keep generic batch API

3. **static/**
   - Remove `conquest-curation.html`
   - Remove `css/conquest-ui.css`
   - Remove `js/conquest-*.js`
   - Keep generic UI files

4. **tests/**
   - Remove Aris integration tests
   - Keep generic batch processing tests

---

### **Phase 6: Security Audit** 🔒

**Check for hardcoded secrets:**

```bash
# Search for potential secrets
grep -r "password" --include="*.py" --include="*.js" --include="*.yml"
grep -r "api_key" --include="*.py" --include="*.js" --include="*.yml"
grep -r "secret" --include="*.py" --include="*.js" --include="*.yml"
grep -r "token" --include="*.py" --include="*.js" --include="*.yml"
grep -r "sentry" --include="*.py" --include="*.js" --include="*.yml"

# Check for IP addresses
grep -rE "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" --include="*.py" --include="*.js" --include="*.yml"

# Check for email addresses
grep -rE "\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b" --include="*.py" --include="*.js" --include="*.yml"
```

**Rotate secrets if found:**
- Sentry DSN
- Database passwords
- API keys
- Webhook URLs

---

## ✅ FINAL CHECKLIST

Before making repository public:

- [ ] **Git history cleaned** (no candidate data, no secrets)
- [ ] **Synthetic test data created** (replaces real data)
- [ ] **All secrets rotated** (if any were committed)
- [ ] **Aris-specific code removed** (or made generic)
- [ ] **Documentation updated** (no private references)
- [ ] **License added** (MIT/Apache 2.0)
- [ ] **Contributing guidelines added**
- [ ] **Security policy added**
- [ ] **README updated** (installation, usage, examples)
- [ ] **.gitignore verified** (all sensitive files ignored)
- [ ] **CI/CD configured** (GitHub Actions for tests)
- [ ] **Code of Conduct added**
- [ ] **Issue templates created**
- [ ] **PR templates created**

---

## 🚀 RELEASE PROCESS

### **Option 1: Clean Slate (Recommended)**

Create a new repository with clean history:

```bash
# 1. Create new repo on GitHub
# 2. Clone this repo to a temp location
git clone https://github.com/zisaacson/vllm-batch-server.git vllm-batch-server-clean

# 3. Remove .git directory
cd vllm-batch-server-clean
rm -rf .git

# 4. Remove all sensitive files
rm -rf data/ batch_5k*.jsonl benchmarks/raw/ results/ integrations/aris/
rm .env .env.a100-cloud .env.rtx4080-home

# 5. Initialize new git repo
git init
git add .
git commit -m "Initial public release"

# 6. Push to new repo
git remote add origin https://github.com/YOUR_ORG/vllm-batch-server-public.git
git push -u origin main
```

### **Option 2: Rewrite History (Risky)**

Use git-filter-branch as shown in Phase 1 above.

---

## 📊 CURRENT STATUS

**Repository Structure:**
- ✅ Monorepo setup (core/, integrations/, tools/, scripts/)
- ✅ Docker support
- ✅ Monitoring stack (Grafana, Prometheus, Loki)
- ✅ Label Studio integration
- ✅ OpenAI-compatible API
- ✅ Model hot-swapping
- ✅ Queue monitoring UI

**What's Ready:**
- ✅ Core batch processing engine
- ✅ vLLM integration
- ✅ PostgreSQL database
- ✅ API server
- ✅ Worker process
- ✅ Monitoring/logging
- ✅ Documentation structure

**What's NOT Ready:**
- ❌ Real candidate data still in repo
- ❌ Aris-specific integrations not removed
- ❌ Secrets may be in git history
- ❌ No synthetic test data
- ❌ No LICENSE file
- ❌ No CONTRIBUTING.md
- ❌ No public-facing README

---

## 🎯 RECOMMENDATION

**DO NOT make the current repo public yet.**

**Instead:**

1. **Create a new public repository** with clean history
2. **Copy only the public-safe code** (no data, no secrets, no Aris code)
3. **Add synthetic test data** for demonstrations
4. **Write public-facing documentation**
5. **Add proper open source files** (LICENSE, CONTRIBUTING, etc.)
6. **Keep the current repo private** for Aris-specific work

**Timeline:**
- **Phase 1-2**: 2-4 hours (clean history, create synthetic data)
- **Phase 3-4**: 2-3 hours (update docs, verify .gitignore)
- **Phase 5-6**: 3-4 hours (code cleanup, security audit)
- **Total**: 1-2 days of focused work

**Want me to help with any of these phases?**

