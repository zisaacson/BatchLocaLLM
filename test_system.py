#!/usr/bin/env python3
"""
Basic system tests for vLLM batch server.
Tests critical workflows without requiring GPU.
"""

import json
import os
import sys
from pathlib import Path

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from batch_app import database, api_server, worker, webhooks, benchmarks, static_server
        print("✅ All modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_database_schema():
    """Test database schema creation."""
    print("\nTesting database schema...")
    try:
        from batch_app.database import Base, engine, SessionLocal, BatchJob
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Test session
        db = SessionLocal()
        jobs = db.query(BatchJob).all()
        db.close()
        
        print(f"✅ Database schema OK ({len(jobs)} jobs in database)")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_benchmark_manager():
    """Test benchmark manager."""
    print("\nTesting benchmark manager...")
    try:
        from batch_app.benchmarks import get_benchmark_manager

        bm = get_benchmark_manager()

        # Test getting benchmark data
        models = bm.get_available_models()
        if models:
            print(f"✅ Benchmark manager OK ({len(models)} models with benchmarks)")
        else:
            print("✅ Benchmark manager OK (no benchmarks yet)")
        return True
    except Exception as e:
        print(f"❌ Benchmark manager test failed: {e}")
        return False

def test_gold_star_directory():
    """Test gold star directory exists."""
    print("\nTesting gold star directory...")
    try:
        gold_star_dir = Path('data/gold_star')
        gold_star_dir.mkdir(parents=True, exist_ok=True)
        
        starred_file = gold_star_dir / 'starred.jsonl'
        if starred_file.exists():
            with open(starred_file, 'r') as f:
                count = sum(1 for line in f if line.strip())
            print(f"✅ Gold star directory OK ({count} starred examples)")
        else:
            print("✅ Gold star directory OK (no starred examples yet)")
        return True
    except Exception as e:
        print(f"❌ Gold star directory test failed: {e}")
        return False

def test_html_files():
    """Test that all HTML files exist."""
    print("\nTesting HTML files...")
    try:
        required_files = [
            'index.html',
            'curation_app.html',
            'table_view.html',
            'benchmarks.html',
            'compare_models.html',
            'compare_results.html',
            'view_results.html',
            'dashboard.html',
            'api_docs.html',
            'monitor.html',
            'submit_batch.html'
        ]

        missing = []
        for file in required_files:
            if not Path(file).exists():
                missing.append(file)

        if missing:
            print(f"❌ Missing HTML files: {', '.join(missing)}")
            return False
        else:
            print(f"✅ All {len(required_files)} HTML files exist")
            return True
    except Exception as e:
        print(f"❌ HTML files test failed: {e}")
        return False

def test_static_files():
    """Test that static files exist."""
    print("\nTesting static files...")
    try:
        required_files = [
            'static/css/shared.css',
            'static/js/parsers.js'
        ]
        
        missing = []
        for file in required_files:
            if not Path(file).exists():
                missing.append(file)
        
        if missing:
            print(f"❌ Missing static files: {', '.join(missing)}")
            return False
        else:
            print(f"✅ All {len(required_files)} static files exist")
            return True
    except Exception as e:
        print(f"❌ Static files test failed: {e}")
        return False

def test_scripts():
    """Test that start/stop scripts exist."""
    print("\nTesting scripts...")
    try:
        required_files = [
            'start_all.sh',
            'stop_all.sh'
        ]
        
        missing = []
        for file in required_files:
            if not Path(file).exists():
                missing.append(file)
        
        if missing:
            print(f"❌ Missing scripts: {', '.join(missing)}")
            return False
        else:
            print(f"✅ All {len(required_files)} scripts exist")
            return True
    except Exception as e:
        print(f"❌ Scripts test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("vLLM Batch Server - System Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_database_schema,
        test_benchmark_manager,
        test_gold_star_directory,
        test_html_files,
        test_static_files,
        test_scripts
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())

