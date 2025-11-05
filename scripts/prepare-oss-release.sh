#!/bin/bash
set -e

echo "================================================================================"
echo "🧹 PREPARING FOR OPEN SOURCE RELEASE"
echo "================================================================================"
echo ""

# Create ZACKSNOTES directory
echo "📁 Creating ZACKSNOTES directory..."
mkdir -p ZACKSNOTES

# Move status/audit docs
echo "📦 Moving internal documentation to ZACKSNOTES/..."

# Move all *_COMPLETE.md files
for file in *_COMPLETE.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_STATUS.md files
for file in *_STATUS.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_AUDIT.md files
for file in *_AUDIT.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_REPORT.md files
for file in *_REPORT.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_ANALYSIS.md files
for file in *_ANALYSIS.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_SUMMARY.md files
for file in *_SUMMARY.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_PLAN.md files
for file in *_PLAN.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_PROGRESS.md files
for file in *_PROGRESS.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_DIAGNOSIS.md files
for file in *_DIAGNOSIS.md; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move all *_GUIDE.md files (except QUICK_START_GUIDE.md which is a duplicate)
for file in *_GUIDE.md; do
    if [ -f "$file" ] && [ "$file" != "QUICK_START_GUIDE.md" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

# Move specific files
specific_files=(
    "503_ERROR_DIAGNOSIS.md"
    "ABSTRACTION_PROGRESS.md"
    "ARCHITECTURE.md"
    "IMPLEMENTATION_PLAN.md"
    "QUICK_START_GUIDE.md"
)

for file in "${specific_files[@]}"; do
    if [ -f "$file" ]; then
        echo "  Moving $file"
        mv "$file" ZACKSNOTES/
    fi
done

echo ""
echo "✅ Documentation moved to ZACKSNOTES/"
echo ""

# Update .gitignore
echo "📝 Updating .gitignore..."
if ! grep -q "ZACKSNOTES/" .gitignore; then
    echo "" >> .gitignore
    echo "# Internal notes (not for OSS release)" >> .gitignore
    echo "ZACKSNOTES/" >> .gitignore
    echo "✅ Added ZACKSNOTES/ to .gitignore"
else
    echo "✅ ZACKSNOTES/ already in .gitignore"
fi

echo ""
echo "================================================================================"
echo "📊 CLEANUP SUMMARY"
echo "================================================================================"
echo ""

# Count files in root
root_md_count=$(ls -1 *.md 2>/dev/null | wc -l)
echo "📄 Markdown files in root: $root_md_count"
echo ""
echo "Files remaining in root:"
ls -1 *.md 2>/dev/null || echo "  (none)"

echo ""
echo "📁 Files moved to ZACKSNOTES/:"
ls -1 ZACKSNOTES/*.md 2>/dev/null | wc -l

echo ""
echo "================================================================================"
echo "✅ CLEANUP COMPLETE!"
echo "================================================================================"
echo ""
echo "🎯 Next steps:"
echo "  1. Review files in ZACKSNOTES/"
echo "  2. Add screenshots to docs/screenshots/"
echo "  3. Simplify README.md"
echo "  4. Create GitHub templates"
echo "  5. Run final verification"
echo ""
