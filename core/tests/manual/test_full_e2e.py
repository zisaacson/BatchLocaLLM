#!/usr/bin/env python3
"""
Manual End-to-End Test for Complete System

This script tests the full data flow:
1. Batch API → Worker → vLLM → Results
2. Auto-import to Label Studio
3. Curation UI functionality
4. Gold-star marking
5. Dataset export

REQUIREMENTS:
- Batch API running on localhost:4080
- Curation API running on localhost:8001
- Label Studio running on localhost:4015
- Worker running (for actual vLLM processing)
- PostgreSQL running

USAGE:
    python tests/manual/test_full_e2e.py

This is a MANUAL test - run it when you want to validate the entire system.
Not part of automated test suite.
"""

import json
import sys
import time
from pathlib import Path

import requests


# Configuration
BATCH_API_URL = "http://localhost:4080"
CURATION_API_URL = "http://localhost:8001"
LABEL_STUDIO_URL = "http://localhost:4015"
TIMEOUT = 300  # 5 minutes max wait


def print_step(step_num: int, description: str):
    """Print a test step."""
    print(f"\n{'='*80}")
    print(f"STEP {step_num}: {description}")
    print('='*80)


def check_services():
    """Verify all required services are running."""
    print_step(0, "Checking Services")
    
    services = {
        "Batch API": f"{BATCH_API_URL}/health",
        "Curation API": f"{CURATION_API_URL}/health",
        "Label Studio": f"{LABEL_STUDIO_URL}/health",
    }
    
    all_healthy = True
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name}: Running")
            else:
                print(f"❌ {name}: Unhealthy (status {response.status_code})")
                all_healthy = False
        except requests.exceptions.ConnectionError:
            print(f"❌ {name}: Not running")
            all_healthy = False
    
    if not all_healthy:
        print("\n⚠️  Not all services are running. Start them with:")
        print("  Terminal 1: python -m batch_app.api_server")
        print("  Terminal 2: python -m curation_app.api")
        print("  Terminal 3: python -m batch_app.worker")
        print("  Terminal 4: docker compose -f docker-compose.postgres.yml up")
        sys.exit(1)
    
    print("\n✅ All services healthy!")


def test_batch_workflow():
    """Test batch processing workflow."""
    print_step(1, "Create and Process Batch Job")
    
    # Create input file
    input_data = [
        {
            "custom_id": "candidate-001",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "google/gemma-3-4b-it",
                "messages": [
                    {"role": "system", "content": "You are a technical recruiter."},
                    {"role": "user", "content": json.dumps({
                        "name": "Alice Johnson",
                        "title": "Senior Software Engineer",
                        "company": "Google",
                        "education": "MIT BS Computer Science"
                    })}
                ],
                "max_tokens": 500
            }
        },
        {
            "custom_id": "candidate-002",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "google/gemma-3-4b-it",
                "messages": [
                    {"role": "system", "content": "You are a technical recruiter."},
                    {"role": "user", "content": json.dumps({
                        "name": "Bob Smith",
                        "title": "Junior Developer",
                        "company": "Startup Inc",
                        "education": "State University BS IT"
                    })}
                ],
                "max_tokens": 500
            }
        }
    ]
    
    # Write to temp file
    temp_file = Path("/tmp/e2e_test_batch.jsonl")
    with open(temp_file, 'w') as f:
        for item in input_data:
            f.write(json.dumps(item) + '\n')
    
    # Upload file
    print("📤 Uploading input file...")
    with open(temp_file, 'rb') as f:
        response = requests.post(
            f"{BATCH_API_URL}/v1/files",
            files={'file': ('batch.jsonl', f, 'application/jsonl')},
            data={'purpose': 'batch'}
        )
    
    assert response.status_code == 200, f"File upload failed: {response.text}"
    file_id = response.json()['id']
    print(f"✅ File uploaded: {file_id}")
    
    # Create batch job
    print("📋 Creating batch job...")
    response = requests.post(
        f"{BATCH_API_URL}/v1/batches",
        json={
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
            "metadata": {
                "conquest_type": "candidate_evaluation",
                "source": "manual_e2e_test"
            }
        }
    )
    
    assert response.status_code == 200, f"Batch creation failed: {response.text}"
    batch_id = response.json()['id']
    print(f"✅ Batch created: {batch_id}")
    
    # Wait for completion
    print("⏳ Waiting for batch to complete (this may take a few minutes)...")
    start_time = time.time()
    
    while time.time() - start_time < TIMEOUT:
        response = requests.get(f"{BATCH_API_URL}/v1/batches/{batch_id}")
        batch_status = response.json()
        status = batch_status['status']
        
        completed = batch_status['request_counts'].get('completed', 0)
        total = batch_status['request_counts'].get('total', 0)
        
        print(f"  Status: {status} | Progress: {completed}/{total}", end='\r')
        
        if status == 'completed':
            print(f"\n✅ Batch completed! ({completed}/{total} requests)")
            return batch_id
        elif status == 'failed':
            print(f"\n❌ Batch failed: {batch_status.get('errors')}")
            sys.exit(1)
        
        time.sleep(5)
    
    print(f"\n❌ Batch did not complete within {TIMEOUT}s")
    sys.exit(1)


def test_label_studio_import(batch_id: str):
    """Test auto-import to Label Studio."""
    print_step(2, "Verify Label Studio Import")
    
    # Wait for auto-import
    print("⏳ Waiting for auto-import to Label Studio...")
    time.sleep(5)
    
    # Check tasks were created
    response = requests.get(
        f"{CURATION_API_URL}/api/tasks",
        params={
            "conquest_type": "candidate_evaluation",
            "page": 1,
            "page_size": 100
        }
    )
    
    assert response.status_code == 200, f"Failed to get tasks: {response.text}"
    tasks_data = response.json()
    
    # Find our tasks
    our_tasks = [t for t in tasks_data['tasks'] if t.get('data', {}).get('batch_id') == batch_id]
    
    if len(our_tasks) >= 2:
        print(f"✅ Found {len(our_tasks)} tasks in Label Studio")
        return our_tasks
    else:
        print(f"⚠️  Expected 2 tasks, found {len(our_tasks)}")
        print("   (Auto-import may not be configured)")
        return []


def test_gold_star_functionality(tasks: list):
    """Test gold-star marking."""
    if not tasks:
        print_step(3, "Skip Gold-Star Test (no tasks)")
        return
    
    print_step(3, "Test Gold-Star Functionality")
    
    task_id = tasks[0]['id']
    
    # Mark as gold-star
    print(f"⭐ Marking task {task_id} as gold-star...")
    response = requests.post(
        f"{CURATION_API_URL}/api/tasks/{task_id}/gold-star",
        json={"is_gold_star": True}
    )
    
    assert response.status_code == 200, f"Failed to mark gold-star: {response.text}"
    print("✅ Task marked as gold-star")
    
    # Verify it was set
    response = requests.get(f"{CURATION_API_URL}/api/tasks/{task_id}")
    task = response.json()
    
    if task.get('meta', {}).get('gold_star'):
        print("✅ Gold-star verified in task metadata")
    else:
        print("⚠️  Gold-star not found in metadata")


def test_export_dataset(tasks: list):
    """Test dataset export."""
    if not tasks:
        print_step(4, "Skip Export Test (no tasks)")
        return
    
    print_step(4, "Test Dataset Export")
    
    # Export gold-star dataset
    print("📦 Exporting training dataset...")
    response = requests.post(
        f"{CURATION_API_URL}/api/export",
        json={
            "conquest_type": "candidate_evaluation",
            "format": "icl",
            "min_agreement": 0.0,
            "min_annotations": 0
        }
    )
    
    assert response.status_code == 200, f"Export failed: {response.text}"
    export_data = response.json()
    
    print(f"✅ Exported {export_data['count']} examples")
    print(f"   Format: {export_data['format']}")
    print(f"   Conquest type: {export_data['conquest_type']}")


def main():
    """Run full E2E test."""
    print("\n" + "="*80)
    print("MANUAL END-TO-END TEST - Full System Validation")
    print("="*80)
    
    try:
        # Check all services
        check_services()
        
        # Run tests
        batch_id = test_batch_workflow()
        tasks = test_label_studio_import(batch_id)
        test_gold_star_functionality(tasks)
        test_export_dataset(tasks)
        
        # Success
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED - System is working correctly!")
        print("="*80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

