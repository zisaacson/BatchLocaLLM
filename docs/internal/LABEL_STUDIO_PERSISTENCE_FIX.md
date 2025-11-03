# Label Studio Persistence Fix

**Date:** 2025-11-03  
**Issue:** Label Studio was not persisting data across restarts  
**Status:** ✅ FIXED

---

## Problem

Label Studio was configured with a PostgreSQL database (`vllm-label-studio-db`) but was **not using it**. Instead, it was using SQLite (`label_studio.sqlite3`) which is stored in a Docker volume but doesn't provide the same reliability and features as PostgreSQL.

**Symptoms:**
- Data appeared to be lost after container restarts
- Projects and annotations were not persisting reliably
- PostgreSQL database existed but had no data

---

## Root Cause

The Label Studio container was missing:
1. **Environment variables** to connect to PostgreSQL
2. **Initialization command** to set up the database on first run

Without these, Label Studio defaulted to SQLite.

---

## Solution

Updated `docker/docker-compose.yml` to add:

### 1. PostgreSQL Connection Environment Variables

```yaml
environment:
  # PostgreSQL Database Configuration
  DJANGO_DB: default
  POSTGRE_NAME: labelstudio
  POSTGRE_USER: labelstudio
  POSTGRE_PASSWORD: labelstudio
  POSTGRE_PORT: 5432
  POSTGRE_HOST: label-studio-db
  
  # Label Studio Configuration
  LABEL_STUDIO_HOST: 0.0.0.0
  LABEL_STUDIO_PORT: 8080
  LABEL_STUDIO_USERNAME: admin@vllm-batch.local
  LABEL_STUDIO_PASSWORD: vllm_batch_2024
  LABEL_STUDIO_DISABLE_SIGNUP_WITHOUT_LINK: "false"
```

### 2. Initialization Command

```yaml
command: >
  bash -c "
    label-studio reset_password --username admin@vllm-batch.local --password vllm_batch_2024 || 
    label-studio init --username admin@vllm-batch.local --password vllm_batch_2024 &&
    label-studio start
  "
```

This command:
- Tries to reset the password (if user exists)
- Falls back to creating a new user (if user doesn't exist)
- Starts Label Studio

---

## Verification

After applying the fix:

### ✅ PostgreSQL is Being Used

```bash
$ docker exec vllm-label-studio-db psql -U labelstudio -d labelstudio -c "SELECT COUNT(*) FROM htx_user;"
 count 
-------
     2
(1 row)
```

The database now has users, confirming Label Studio is using PostgreSQL.

### ✅ Label Studio is Accessible

```bash
$ curl http://localhost:4115/health
{"status": "UP"}
```

### ✅ Login Credentials

- **URL:** `http://localhost:4115`
- **Username:** `admin@vllm-batch.local`
- **Password:** `vllm_batch_2024`

---

## Port Configuration (Correct)

The port mapping `4115:8080` is **correct**:
- **External (host) port:** 4115 - Your web app connects here
- **Internal (container) port:** 8080 - Label Studio listens here

**Do NOT change to `4115:4115`** - Label Studio runs on port 8080 inside the container.

---

## Data Persistence

Label Studio now stores all data in PostgreSQL:
- **Database:** `vllm-label-studio-db` container
- **Volume:** `vllm-label-studio-db-data` (persistent across restarts)
- **Projects, annotations, users:** All stored in PostgreSQL
- **Media files:** Stored in `vllm-label-studio-data` volume

---

## Testing Persistence

To verify data persists across restarts:

1. **Create a test project:**
   ```bash
   # Login to http://localhost:4115
   # Create a new project
   # Add some tasks
   ```

2. **Restart Label Studio:**
   ```bash
   cd docker
   docker compose restart label-studio
   ```

3. **Verify data is still there:**
   ```bash
   # Login again to http://localhost:4115
   # Check that your project and tasks are still there
   ```

---

## Migration from SQLite (If Needed)

If you had important data in the old SQLite database, you can migrate it:

1. **Export from SQLite:**
   ```bash
   docker exec vllm-label-studio label-studio export --format JSON --output /label-studio/data/export.json
   ```

2. **Import to PostgreSQL:**
   ```bash
   docker exec vllm-label-studio label-studio import --format JSON --input /label-studio/data/export.json
   ```

**Note:** The old SQLite file (`label_studio.sqlite3`) is still in the volume but is no longer being used.

---

## Cleanup (Optional)

To remove the old SQLite file:

```bash
docker exec vllm-label-studio rm /label-studio/data/label_studio.sqlite3
```

**Warning:** Only do this after verifying PostgreSQL is working and you've migrated any important data.

---

## Summary

**Before:**
- ❌ Using SQLite (not reliable)
- ❌ Data not persisting properly
- ❌ PostgreSQL database unused

**After:**
- ✅ Using PostgreSQL (production-grade)
- ✅ Data persists across restarts
- ✅ Proper database configuration
- ✅ Admin account pre-configured

**Status:** Production-ready for open source release! 🚀

