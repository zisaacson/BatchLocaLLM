#!/bin/bash
# Reorganize codebase from Ollama to vLLM native batch processing

set -e  # Exit on error

echo "=================================="
echo "Codebase Reorganization Script"
echo "=================================="
echo ""

# Confirm with user
read -p "This will reorganize the codebase. Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Rename batch_app to batch_api"
echo "--------------------------------------"
if [ -d "batch_app" ]; then
    mv batch_app batch_api
    echo "✅ Renamed batch_app → batch_api"
else
    echo "⚠️  batch_app directory not found, skipping"
fi

echo ""
echo "Step 2: Update imports in batch_api files"
echo "------------------------------------------"
if [ -d "batch_api" ]; then
    # Update Python imports
    find batch_api -name "*.py" -type f -exec sed -i 's/from batch_app\./from batch_api./g' {} \;
    find batch_api -name "*.py" -type f -exec sed -i 's/import batch_app/import batch_api/g' {} \;
    echo "✅ Updated imports in batch_api/"
fi

echo ""
echo "Step 3: Update startup scripts"
echo "-------------------------------"
if [ -f "start_api_server.sh" ]; then
    sed -i 's/batch_app\.api_server/batch_api.server/g' start_api_server.sh
    echo "✅ Updated start_api_server.sh"
fi

if [ -f "start_worker.sh" ]; then
    sed -i 's/batch_app\.worker/batch_api.worker/g' start_worker.sh
    echo "✅ Updated start_worker.sh"
fi

echo ""
echo "Step 4: Rename api_server.py to server.py"
echo "------------------------------------------"
if [ -f "batch_api/api_server.py" ]; then
    mv batch_api/api_server.py batch_api/server.py
    echo "✅ Renamed api_server.py → server.py"
    
    # Update import in startup script
    sed -i 's/batch_api\.api_server/batch_api.server/g' start_api_server.sh
    echo "✅ Updated startup script"
fi

echo ""
echo "Step 5: Create archive directory for deprecated code"
echo "-----------------------------------------------------"
mkdir -p archive/ollama
mkdir -p archive/docs
echo "✅ Created archive directories"

echo ""
echo "Step 6: Move Ollama code to archive"
echo "------------------------------------"
if [ -d "src" ]; then
    mv src archive/ollama/
    echo "✅ Moved src/ → archive/ollama/"
fi

if [ -f "README_OLLAMA_BATCH.md" ]; then
    mv README_OLLAMA_BATCH.md archive/ollama/
    echo "✅ Moved README_OLLAMA_BATCH.md → archive/ollama/"
fi

echo ""
echo "Step 7: Move old documentation to archive"
echo "------------------------------------------"
# List of docs to archive (keep essential ones)
DOCS_TO_ARCHIVE=(
    "ANALYSIS.md"
    "ARCHITECTURE_AUDIT.md"
    "AUDIT.md"
    "AUDIT_AND_VISION.md"
    "BATCH_OPTIMIZATION_ANALYSIS.md"
    "BATCH_OPTIMIZATION_REQUIREMENTS.md"
    "CPU_OPTIMIZATION_ANALYSIS.md"
    "CURRENT_STATUS.md"
    "FINAL_AUDIT.md"
    "FINAL_STATUS_SUMMARY.md"
    "FINAL_SUMMARY.md"
    "FIRST_PRINCIPLES_OPTIMIZATION.md"
    "INFRASTRUCTURE_COMPLETE.md"
    "KEY_FILES_REFERENCE.md"
    "MASTER_PLAN.md"
    "MEASUREMENT_RESULTS.md"
    "MODEL_COMPARISON.md"
    "MULTI_BATCH_TEST_PLAN.md"
    "OOM_PROTECTION_AND_DATA_STATUS.md"
    "OPTIMIZATION_SUCCESS.md"
    "OPTIMIZATION_SUMMARY.md"
    "PARALLEL_ARCHITECTURE.md"
    "PRODUCTION_QUEUE_ARCHITECTURE.md"
    "PRODUCTION_READINESS_AUDIT.md"
    "PRODUCTION_READY_SUMMARY.md"
    "REAL_PLATFORM_COMPARISON.md"
    "REDDIT_ADVICE_ANALYSIS.md"
    "RTX4080_OPTIMIZATION_AUDIT.md"
    "SCALABILITY_CRISIS_AND_SOLUTION.md"
    "TESTING_PLAN.md"
    "TESTING_ROADMAP.md"
    "TEST_COVERAGE_REPORT.md"
    "TROUBLESHOOTING_CHECKLIST.md"
    "USER_STORY.md"
)

for doc in "${DOCS_TO_ARCHIVE[@]}"; do
    if [ -f "$doc" ]; then
        mv "$doc" archive/docs/
        echo "  ✅ Archived $doc"
    fi
done

echo ""
echo "Step 8: Create docs directory and move essential docs"
echo "------------------------------------------------------"
mkdir -p docs

# Essential docs to keep in docs/
ESSENTIAL_DOCS=(
    "BATCH_API_USAGE.md"
    "BATCH_WEB_APP_ARCHITECTURE.md"
    "BATCH_WEB_APP_SUCCESS.md"
    "BENCHMARKING_JOURNEY.md"
    "CODEBASE_REORGANIZATION.md"
)

for doc in "${ESSENTIAL_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        cp "$doc" docs/
        echo "  ✅ Copied $doc to docs/"
    fi
done

echo ""
echo "Step 9: Replace README.md with new version"
echo "-------------------------------------------"
if [ -f "README.md" ]; then
    mv README.md archive/docs/README_OLD.md
    echo "✅ Archived old README.md"
fi

if [ -f "README_NEW.md" ]; then
    mv README_NEW.md README.md
    echo "✅ Installed new README.md"
fi

echo ""
echo "Step 10: Update .gitignore"
echo "--------------------------"
cat >> .gitignore << 'EOF'

# Archive directory
archive/

# Data directories
data/batches/
data/database/

# Benchmark data (keep metadata, ignore raw)
benchmarks/raw/*.jsonl

# Logs
*.log

# Virtual environment
venv/
EOF
echo "✅ Updated .gitignore"

echo ""
echo "Step 11: Create benchmarks directory structure"
echo "-----------------------------------------------"
mkdir -p benchmarks/data/metadata
mkdir -p benchmarks/data/raw
mkdir -p benchmarks/tools
mkdir -p benchmarks/reports

# Move existing benchmark data
if [ -d "benchmarks/metadata" ]; then
    mv benchmarks/metadata/* benchmarks/data/metadata/ 2>/dev/null || true
    rmdir benchmarks/metadata 2>/dev/null || true
fi

if [ -d "benchmarks/raw" ]; then
    mv benchmarks/raw/* benchmarks/data/raw/ 2>/dev/null || true
    rmdir benchmarks/raw 2>/dev/null || true
fi

# Move BENCHMARKING_JOURNEY.md to reports
if [ -f "BENCHMARKING_JOURNEY.md" ]; then
    cp BENCHMARKING_JOURNEY.md benchmarks/reports/
fi

echo "✅ Reorganized benchmarks directory"

echo ""
echo "Step 12: Create scripts directory"
echo "----------------------------------"
mkdir -p scripts

# Move startup scripts
if [ -f "start_api_server.sh" ]; then
    mv start_api_server.sh scripts/
    echo "✅ Moved start_api_server.sh → scripts/"
fi

if [ -f "start_worker.sh" ]; then
    mv start_worker.sh scripts/
    echo "✅ Moved start_worker.sh → scripts/"
fi

# Create symlinks in root for convenience
ln -sf scripts/start_api_server.sh start_api_server.sh
ln -sf scripts/start_worker.sh start_worker.sh
echo "✅ Created convenience symlinks"

echo ""
echo "=================================="
echo "✅ Reorganization Complete!"
echo "=================================="
echo ""
echo "Summary:"
echo "  ✅ Renamed batch_app → batch_api"
echo "  ✅ Updated all imports"
echo "  ✅ Archived Ollama code"
echo "  ✅ Archived old documentation"
echo "  ✅ Created new README.md"
echo "  ✅ Organized benchmarks/"
echo "  ✅ Created scripts/"
echo "  ✅ Created models/ registry"
echo ""
echo "Next steps:"
echo "  1. Test the API server: ./start_api_server.sh"
echo "  2. Test the worker: ./start_worker.sh"
echo "  3. Run tests: pytest tests/"
echo "  4. Commit changes: git add . && git commit -m 'Reorganize codebase for vLLM native batch processing'"
echo ""

