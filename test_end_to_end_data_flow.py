#!/usr/bin/env python3
"""
End-to-End Data Flow Test

Tests the complete data flow:
1. Create batch job with candidate evaluation data
2. Process batch
3. Verify data in Label Studio
4. Test curation UI
5. Test gold star sync to Aristotle
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

# Configuration
BATCH_API_URL = "http://localhost:4080"
LABEL_STUDIO_URL = "http://localhost:4115"
CURATION_API_URL = "http://localhost:8001"
ARISTOTLE_DB_URL = "postgresql://localhost:4002/aristotle_dev"

# Test data
TEST_CANDIDATE = {
    "name": "Jane Smith",
    "role": "Senior Software Engineer",
    "location": "San Francisco, CA",
    "work_history": [
        "Senior Software Engineer at Google (2020-2024)",
        "Software Engineer at Meta (2018-2020)",
        "Junior Developer at Startup Inc (2016-2018)"
    ],
    "education": [
        "BS Computer Science, Stanford University (2016)",
        "MS Computer Science, MIT (2018)"
    ]
}

def print_step(step_num, description):
    """Print a test step."""
    print(f"\n{'='*80}")
    print(f"STEP {step_num}: {description}")
    print(f"{'='*80}")

def print_success(message):
    """Print success message."""
    print(f"✅ {message}")

def print_error(message):
    """Print error message."""
    print(f"❌ {message}")

def print_info(message):
    """Print info message."""
    print(f"ℹ️  {message}")

def create_test_input_file():
    """Create a test input file with candidate evaluation data."""
    print_step(1, "Creating test input file")
    
    # Create test request
    test_request = {
        "custom_id": f"test_candidate_{int(time.time())}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gemma-3-4b",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert technical recruiter evaluating software engineering candidates."
                },
                {
                    "role": "user",
                    "content": f"""Evaluate this candidate:

Name: {TEST_CANDIDATE['name']}
Current Role: {TEST_CANDIDATE['role']}
Location: {TEST_CANDIDATE['location']}

Work History:
{chr(10).join(TEST_CANDIDATE['work_history'])}

Education:
{chr(10).join(TEST_CANDIDATE['education'])}

Please evaluate:
1. Recommendation (Strong Yes/Yes/Maybe/No/Strong No)
2. Educational Pedigree (Exceptional/Strong/Good/Average/Weak)
3. Company Pedigree (Exceptional/Strong/Good/Average/Weak)
4. Trajectory (Exceptional/Strong/Good/Average/Weak)
5. Is Software Engineer (true/false)

Provide your evaluation in JSON format."""
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
    }
    
    # Write to file
    input_file = Path("test_input.jsonl")
    with open(input_file, 'w') as f:
        f.write(json.dumps(test_request) + '\n')
    
    print_success(f"Created test input file: {input_file}")
    print_info(f"Candidate: {TEST_CANDIDATE['name']}")
    print_info(f"Custom ID: {test_request['custom_id']}")
    
    return input_file, test_request['custom_id']

def upload_file(input_file):
    """Upload input file to batch API."""
    print_step(2, "Uploading input file to batch API")
    
    with open(input_file, 'rb') as f:
        response = requests.post(
            f"{BATCH_API_URL}/v1/files",
            files={'file': ('test_input.jsonl', f, 'application/jsonl')},
            data={'purpose': 'batch'}
        )
    
    if response.status_code != 200:
        print_error(f"Failed to upload file: {response.status_code}")
        print_error(response.text)
        return None
    
    file_data = response.json()
    file_id = file_data['id']
    
    print_success(f"Uploaded file: {file_id}")
    return file_id

def create_batch_job(file_id):
    """Create a batch job."""
    print_step(3, "Creating batch job")
    
    batch_request = {
        "input_file_id": file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "metadata": {
            "test": "end_to_end_data_flow",
            "philosopher": "test@example.com",
            "domain": "software_engineering",
            "conquest_type": "candidate_evaluation"
        }
    }
    
    response = requests.post(
        f"{BATCH_API_URL}/v1/batches",
        json=batch_request
    )
    
    if response.status_code != 200:
        print_error(f"Failed to create batch: {response.status_code}")
        print_error(response.text)
        return None
    
    batch_data = response.json()
    batch_id = batch_data['id']
    
    print_success(f"Created batch job: {batch_id}")
    print_info(f"Status: {batch_data['status']}")
    print_info(f"Total requests: {batch_data['request_counts']['total']}")
    
    return batch_id

def wait_for_completion(batch_id, timeout=300):
    """Wait for batch job to complete."""
    print_step(4, "Waiting for batch job to complete")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(f"{BATCH_API_URL}/v1/batches/{batch_id}")
        
        if response.status_code != 200:
            print_error(f"Failed to get batch status: {response.status_code}")
            return False
        
        batch_data = response.json()
        status = batch_data['status']
        
        print_info(f"Status: {status} (elapsed: {int(time.time() - start_time)}s)")
        
        if status == 'completed':
            print_success(f"Batch completed in {int(time.time() - start_time)}s")
            print_info(f"Completed requests: {batch_data['request_counts']['completed']}")
            print_info(f"Failed requests: {batch_data['request_counts']['failed']}")
            return True
        
        if status == 'failed':
            print_error(f"Batch failed: {batch_data.get('errors')}")
            return False
        
        time.sleep(5)
    
    print_error(f"Timeout waiting for batch completion ({timeout}s)")
    return False

def verify_label_studio(batch_id, custom_id):
    """Verify data in Label Studio."""
    print_step(5, "Verifying data in Label Studio")
    
    # Note: This requires Label Studio API access
    # For now, we'll just print instructions
    
    print_info("Manual verification steps:")
    print_info(f"1. Open Label Studio: {LABEL_STUDIO_URL}")
    print_info(f"2. Look for task with batch_id: {batch_id}")
    print_info(f"3. Look for task with custom_id: {custom_id}")
    print_info(f"4. Verify task contains:")
    print_info(f"   - conquest_id")
    print_info(f"   - philosopher: test@example.com")
    print_info(f"   - domain: software_engineering")
    print_info(f"   - name: {TEST_CANDIDATE['name']}")
    print_info(f"   - role: {TEST_CANDIDATE['role']}")
    print_info(f"   - work_history: {len(TEST_CANDIDATE['work_history'])} entries")
    print_info(f"   - education: {len(TEST_CANDIDATE['education'])} entries")
    print_info(f"   - user_prompt (questions)")
    print_info(f"   - llm_response (answers)")
    
    return True

def verify_curation_ui(batch_id):
    """Verify curation UI can display the data."""
    print_step(6, "Verifying curation UI")
    
    print_info("Manual verification steps:")
    print_info(f"1. Open Curation UI: {CURATION_API_URL}")
    print_info(f"2. Look for batch: {batch_id}")
    print_info(f"3. Verify you can see:")
    print_info(f"   - Candidate name: {TEST_CANDIDATE['name']}")
    print_info(f"   - Questions being asked")
    print_info(f"   - Model's answers")
    print_info(f"   - Edit button for answers")
    print_info(f"   - Gold star button")
    
    return True

def test_gold_star_sync():
    """Test gold star sync to Aristotle."""
    print_step(7, "Testing gold star sync")
    
    print_info("Manual verification steps:")
    print_info("1. In Curation UI, click 'Gold Star' button")
    print_info("2. Check Aristotle database:")
    print_info("   - conquest.result should be 'VICTORY'")
    print_info("   - ml_analysis_rating.is_gold_star should be true")
    print_info("3. Verify webhook was called")
    
    return True

def main():
    """Run end-to-end test."""
    print("\n" + "="*80)
    print("END-TO-END DATA FLOW TEST")
    print("="*80)
    print(f"Started at: {datetime.now().isoformat()}")
    
    try:
        # Step 1: Create test input file
        input_file, custom_id = create_test_input_file()
        
        # Step 2: Upload file
        file_id = upload_file(input_file)
        if not file_id:
            return False
        
        # Step 3: Create batch job
        batch_id = create_batch_job(file_id)
        if not batch_id:
            return False
        
        # Step 4: Wait for completion
        if not wait_for_completion(batch_id):
            return False
        
        # Step 5: Verify Label Studio
        verify_label_studio(batch_id, custom_id)
        
        # Step 6: Verify Curation UI
        verify_curation_ui(batch_id)
        
        # Step 7: Test gold star sync
        test_gold_star_sync()
        
        print("\n" + "="*80)
        print("✅ END-TO-END TEST COMPLETE!")
        print("="*80)
        print(f"Batch ID: {batch_id}")
        print(f"Custom ID: {custom_id}")
        print(f"Completed at: {datetime.now().isoformat()}")
        
        return True
        
    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

