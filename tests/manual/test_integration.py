#!/usr/bin/env python3
"""
Integration tests for vLLM batch server.
Tests API endpoints, database queries, and system integration.
"""

import sys

import requests

# Base URLs
API_BASE = "http://localhost:4080"
VIEWER_BASE = "http://localhost:8001"

def test_api_health():
    """Test API server health endpoint."""
    print("Testing API health endpoint...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert 'status' in data, "Missing 'status' field"
        assert 'gpu' in data, "Missing 'gpu' field"
        assert 'worker' in data, "Missing 'worker' field"
        assert 'queue' in data, "Missing 'queue' field"

        print(f"✅ API health OK - Status: {data['status']}, GPU: {data['gpu']['healthy']}")
        return True
    except Exception as e:
        print(f"❌ API health test failed: {e}")
        return False

def test_gpu_monitoring():
    """Test GPU monitoring endpoint."""
    print("\nTesting GPU monitoring endpoint...")
    try:
        response = requests.get(f"{VIEWER_BASE}/api/gpu", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert 'gpus' in data, "Missing 'gpus' field"
        assert 'processes' in data, "Missing 'processes' field"
        assert 'progress' in data, "Missing 'progress' field"

        # Verify GPU data structure
        if data['gpus']:
            gpu = data['gpus'][0]
            assert 'name' in gpu, "Missing GPU name"
            assert 'memory_used' in gpu, "Missing GPU memory_used"
            assert 'temperature' in gpu, "Missing GPU temperature"
            print(f"✅ GPU monitoring OK - {gpu['name']}, Temp: {gpu['temperature']}°C")
        else:
            print("✅ GPU monitoring OK (no GPUs detected)")

        return True
    except Exception as e:
        print(f"❌ GPU monitoring test failed: {e}")
        return False

def test_running_jobs_endpoint():
    """Test running jobs endpoint."""
    print("\nTesting running jobs endpoint...")
    try:
        response = requests.get(f"{VIEWER_BASE}/api/running-jobs", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert 'count' in data, "Missing 'count' field"
        assert 'jobs' in data, "Missing 'jobs' field"
        assert isinstance(data['jobs'], list), "'jobs' should be a list"

        print(f"✅ Running jobs endpoint OK - {data['count']} jobs running")
        return True
    except Exception as e:
        print(f"❌ Running jobs test failed: {e}")
        return False

def test_benchmarks_endpoint():
    """Test benchmarks endpoint."""
    print("\nTesting benchmarks endpoint...")
    try:
        response = requests.get(f"{VIEWER_BASE}/api/benchmarks", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert isinstance(data, list), "Benchmarks should be a list"

        print(f"✅ Benchmarks endpoint OK - {len(data)} benchmarks found")
        return True
    except Exception as e:
        print(f"❌ Benchmarks test failed: {e}")
        return False

def test_database_connection():
    """Test database connection and queries."""
    print("\nTesting database connection...")
    try:
        from batch_app.database import BatchJob, SessionLocal, WorkerHeartbeat

        db = SessionLocal()
        try:
            # Test batch jobs query
            jobs = db.query(BatchJob).all()
            print(f"  - Found {len(jobs)} batch jobs in database")

            # Test worker heartbeat query
            heartbeat = db.query(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen.desc()).first()
            if heartbeat:
                print(f"  - Worker last seen: {heartbeat.last_seen}")
            else:
                print("  - No worker heartbeat found")

            print("✅ Database connection OK")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_export_endpoint():
    """Test gold-star export endpoint."""
    print("\nTesting export endpoint...")
    try:
        response = requests.get(
            f"{VIEWER_BASE}/api/export-gold-star",
            params={'format': 'icl', 'min_quality': 7},
            timeout=5
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert 'count' in data, "Missing 'count' field"
        assert 'data' in data, "Missing 'data' field"
        assert 'filename' in data, "Missing 'filename' field"

        print(f"✅ Export endpoint OK - {data['count']} examples exported")
        return True
    except Exception as e:
        print(f"❌ Export test failed: {e}")
        return False

def test_html_pages():
    """Test that HTML pages are accessible."""
    print("\nTesting HTML pages...")
    try:
        pages = [
            ('/', 'Index'),
            ('/curate', 'Curation App'),
            ('/benchmarks.html', 'Benchmarks'),
            ('/dashboard.html', 'Dashboard')
        ]

        for path, name in pages:
            response = requests.get(f"{VIEWER_BASE}{path}", timeout=5)
            assert response.status_code == 200, f"{name} returned {response.status_code}"
            assert len(response.text) > 0, f"{name} returned empty content"

        print(f"✅ HTML pages OK - {len(pages)} pages accessible")
        return True
    except Exception as e:
        print(f"❌ HTML pages test failed: {e}")
        return False

def test_static_files():
    """Test that static files are accessible."""
    print("\nTesting static files...")
    try:
        files = [
            '/static/css/shared.css',
            '/static/js/parsers.js'
        ]

        for path in files:
            response = requests.get(f"{VIEWER_BASE}{path}", timeout=5)
            assert response.status_code == 200, f"{path} returned {response.status_code}"
            assert len(response.text) > 0, f"{path} returned empty content"

        print(f"✅ Static files OK - {len(files)} files accessible")
        return True
    except Exception as e:
        print(f"❌ Static files test failed: {e}")
        return False

def test_gpu_progress_not_stale():
    """Test that GPU progress shows real-time data, not stale logs."""
    print("\nTesting GPU progress data freshness...")
    try:
        response = requests.get(f"{VIEWER_BASE}/api/gpu", timeout=5)
        data = response.json()

        progress = data.get('progress', {})

        # If there's progress data, it should be from database (dict format)
        # not from log files (string format)
        if progress:
            for key, value in progress.items():
                # New format: dict with model, status, percent
                # Old format: string from log file
                if isinstance(value, str):
                    print("⚠️  Warning: Progress data appears to be from log files (stale)")
                    print(f"    Key: {key}, Value: {value[:50]}...")
                    return False
                elif isinstance(value, dict):
                    assert 'model' in value, "Progress should have 'model' field"
                    assert 'status' in value, "Progress should have 'status' field"
                    print(f"  - Job {key[:20]}...: {value['status']} - {value.get('percent', 0)}%")

        print("✅ GPU progress data is real-time (not stale)")
        return True
    except Exception as e:
        print(f"❌ GPU progress freshness test failed: {e}")
        return False

def main():
    """Run all integration tests."""
    print("=" * 60)
    print("vLLM Batch Server - Integration Tests")
    print("=" * 60)

    tests = [
        test_api_health,
        test_gpu_monitoring,
        test_running_jobs_endpoint,
        test_benchmarks_endpoint,
        test_database_connection,
        test_export_endpoint,
        test_html_pages,
        test_static_files,
        test_gpu_progress_not_stale
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✅ All integration tests passed!")
        return 0
    else:
        print("\n❌ Some integration tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())

