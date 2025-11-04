#!/bin/bash
# vLLM Batch Server - Repository Cleanup Script
# Removes temporary files, Python cache, and misplaced files
# Safe to run - creates backups before deletion

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$REPO_ROOT/cleanup_backup_$(date +%Y%m%d_%H%M%S)"

echo "🧹 vLLM Batch Server - Repository Cleanup"
echo "=========================================="
echo ""

# Function to print colored output
print_info() {
    echo -e "\033[0;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[0;33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

# Create backup directory
print_info "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Change to repo root
cd "$REPO_ROOT"

# 1. Remove misplaced file in Aris repo
print_info "Checking for misplaced files in Aris repo..."
ARIS_VLLM_DIR="/home/zack/Documents/augment-projects/Local/aris/vllm-batch-server"
if [ -d "$ARIS_VLLM_DIR" ]; then
    print_warning "Found misplaced directory: $ARIS_VLLM_DIR"
    print_info "Backing up to: $BACKUP_DIR/aris_vllm_backup/"
    cp -r "$ARIS_VLLM_DIR" "$BACKUP_DIR/aris_vllm_backup/"
    print_info "Removing misplaced directory..."
    rm -rf "$ARIS_VLLM_DIR"
    print_success "Removed misplaced directory"
else
    print_success "No misplaced files found in Aris repo"
fi

# 2. Backup and remove old SQLite database
print_info "Checking for old SQLite database..."
if [ -f "batch_server.db" ]; then
    print_warning "Found old SQLite database: batch_server.db"
    print_info "Backing up to: $BACKUP_DIR/batch_server.db"
    cp batch_server.db "$BACKUP_DIR/"
    print_info "Removing old database..."
    rm -f batch_server.db batch_server.db-journal batch_server.db-wal batch_server.db-shm
    print_success "Removed old SQLite database"
else
    print_success "No old SQLite database found"
fi

# 3. Remove stale PID file
print_info "Checking for stale PID files..."
if [ -f "worker.pid" ]; then
    print_warning "Found stale PID file: worker.pid"
    cp worker.pid "$BACKUP_DIR/" 2>/dev/null || true
    rm -f worker.pid
    print_success "Removed stale PID file"
else
    print_success "No stale PID files found"
fi

# 4. Remove generated training scripts
print_info "Checking for generated training scripts..."
TRAINING_SCRIPTS=$(find data/training -name "train_*.py" 2>/dev/null | wc -l)
if [ "$TRAINING_SCRIPTS" -gt 0 ]; then
    print_warning "Found $TRAINING_SCRIPTS generated training scripts"
    print_info "Backing up to: $BACKUP_DIR/training_scripts/"
    mkdir -p "$BACKUP_DIR/training_scripts/"
    find data/training -name "train_*.py" -exec cp {} "$BACKUP_DIR/training_scripts/" \; 2>/dev/null || true
    print_info "Removing generated training scripts..."
    find data/training -name "train_*.py" -delete 2>/dev/null || true
    print_success "Removed generated training scripts"
else
    print_success "No generated training scripts found"
fi

# 5. Clean Python cache
print_info "Cleaning Python cache files..."
PYCACHE_DIRS=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
PYC_FILES=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l)
PYO_FILES=$(find . -type f -name "*.pyo" 2>/dev/null | wc -l)
TOTAL_CACHE=$((PYCACHE_DIRS + PYC_FILES + PYO_FILES))

if [ "$TOTAL_CACHE" -gt 0 ]; then
    print_warning "Found $TOTAL_CACHE Python cache files/directories"
    print_info "Removing Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    print_success "Removed Python cache"
else
    print_success "No Python cache found"
fi

# 6. Clean mypy cache
print_info "Cleaning mypy cache..."
if [ -d ".mypy_cache" ]; then
    print_warning "Found mypy cache directory"
    rm -rf .mypy_cache
    print_success "Removed mypy cache"
else
    print_success "No mypy cache found"
fi

# 7. Clean pytest cache
print_info "Cleaning pytest cache..."
if [ -d ".pytest_cache" ]; then
    print_warning "Found pytest cache directory"
    rm -rf .pytest_cache
    print_success "Removed pytest cache"
else
    print_success "No pytest cache found"
fi

# 8. Clean coverage files
print_info "Cleaning coverage files..."
COVERAGE_FILES=0
[ -f "coverage.xml" ] && COVERAGE_FILES=$((COVERAGE_FILES + 1))
[ -f ".coverage" ] && COVERAGE_FILES=$((COVERAGE_FILES + 1))
[ -d "htmlcov" ] && COVERAGE_FILES=$((COVERAGE_FILES + 1))

if [ "$COVERAGE_FILES" -gt 0 ]; then
    print_warning "Found $COVERAGE_FILES coverage artifacts"
    rm -f coverage.xml .coverage
    rm -rf htmlcov
    print_success "Removed coverage files"
else
    print_success "No coverage files found"
fi

# 9. Update .gitignore
print_info "Updating .gitignore..."
GITIGNORE_ADDITIONS="
# Database files
*.db
*.db-journal
*.db-wal
*.db-shm

# PID files
*.pid

# Generated training scripts
data/training/train_*.py

# Python cache
__pycache__/
*.py[cod]
*\$py.class
*.so

# Testing
.pytest_cache/
.coverage
htmlcov/
coverage.xml

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json

# Logs
*.log
logs/*.log
"

if ! grep -q "# Database files" .gitignore 2>/dev/null; then
    print_info "Adding cleanup rules to .gitignore..."
    echo "$GITIGNORE_ADDITIONS" >> .gitignore
    print_success "Updated .gitignore"
else
    print_success ".gitignore already up to date"
fi

# 10. Calculate space saved
print_info "Calculating space saved..."
if [ -d "$BACKUP_DIR" ]; then
    BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
    print_success "Backup created: $BACKUP_DIR ($BACKUP_SIZE)"
fi

# Summary
echo ""
echo "=========================================="
echo "✅ Cleanup Complete!"
echo "=========================================="
echo ""
print_success "Removed:"
echo "  - Misplaced files in Aris repo"
echo "  - Old SQLite database"
echo "  - Stale PID files"
echo "  - Generated training scripts"
echo "  - Python cache files"
echo "  - Mypy cache"
echo "  - Pytest cache"
echo "  - Coverage files"
echo ""
print_success "Updated:"
echo "  - .gitignore with cleanup rules"
echo ""
print_info "Backup location: $BACKUP_DIR"
echo ""
print_warning "Next steps:"
echo "  1. Verify tests still pass: ./scripts/run_tests.sh"
echo "  2. Verify server starts: ./scripts/start_gemma3_conquest.sh"
echo "  3. If everything works, delete backup: rm -rf $BACKUP_DIR"
echo ""

