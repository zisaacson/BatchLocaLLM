#!/usr/bin/env python3
"""
Test webhook functionality by creating a simple webhook receiver and submitting a test batch.

Usage:
    python test_webhook.py
"""

import requests
import json
import time
from pathlib import Path
from flask import Flask, request
import threading

# Configuration
API_URL = "http://localhost:4080"
WEBHOOK_PORT = 5555
TEST_BATCH_SIZE = 10  # Small batch for quick testing

# Create Flask app for webhook receiver
app = Flask(__name__)
webhook_received = threading.Event()
webhook_data = {}


@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive webhook from batch server."""
    global webhook_data
    webhook_data = request.json
    
    print("\n" + "=" * 80)
    print("🎉 WEBHOOK RECEIVED!")
    print("=" * 80)
    print(json.dumps(webhook_data, indent=2))
    print("=" * 80)
    
    webhook_received.set()
    return 'OK', 200


def start_webhook_server():
    """Start Flask webhook receiver in background thread."""
    print(f"🌐 Starting webhook receiver on port {WEBHOOK_PORT}...")
    app.run(port=WEBHOOK_PORT, debug=False, use_reloader=False)


def create_test_batch():
    """Create a small test batch file."""
    test_file = Path("test_batch_webhook.jsonl")
    
    print(f"📝 Creating test batch with {TEST_BATCH_SIZE} requests...")
    
    with open(test_file, 'w') as f:
        for i in range(TEST_BATCH_SIZE):
            request_data = {
                "custom_id": f"test_req_{i}",
                "body": {
                    "messages": [
                        {"role": "user", "content": f"Say 'Hello {i}' and nothing else."}
                    ]
                }
            }
            f.write(json.dumps(request_data) + '\n')
    
    print(f"✅ Created {test_file}")
    return test_file


def submit_batch(test_file: Path):
    """Submit batch job with webhook."""
    webhook_url = f"http://localhost:{WEBHOOK_PORT}/webhook"
    
    print(f"\n📤 Submitting batch job...")
    print(f"   File: {test_file}")
    print(f"   Webhook: {webhook_url}")
    
    metadata = {
        "test": True,
        "purpose": "webhook_test",
        "timestamp": time.time()
    }
    
    with open(test_file, 'rb') as f:
        response = requests.post(
            f"{API_URL}/v1/batches",
            files={"file": f},
            data={
                "model": "google/gemma-3-4b-it",
                "webhook_url": webhook_url,
                "metadata": json.dumps(metadata)
            }
        )
    
    if response.status_code != 200:
        print(f"❌ Failed to submit batch: {response.text}")
        return None
    
    batch = response.json()
    print(f"✅ Batch submitted: {batch['batch_id']}")
    print(f"   Status: {batch['status']}")
    print(f"   Total requests: {batch['progress']['total']}")
    
    return batch


def monitor_batch(batch_id: str):
    """Monitor batch progress until completion."""
    print(f"\n⏳ Monitoring batch {batch_id}...")
    
    while True:
        response = requests.get(f"{API_URL}/v1/batches/{batch_id}")
        batch = response.json()
        
        status = batch['status']
        progress = batch['progress']
        
        print(f"   Status: {status} | Progress: {progress['completed']}/{progress['total']} ({progress['percent']:.1f}%)")
        
        if status in ['completed', 'failed']:
            print(f"\n✅ Batch {status}!")
            return batch
        
        time.sleep(2)


def verify_webhook(batch: dict):
    """Verify webhook was received correctly."""
    print(f"\n🔍 Verifying webhook...")
    
    # Wait for webhook (with timeout)
    received = webhook_received.wait(timeout=30)
    
    if not received:
        print("❌ Webhook not received within 30 seconds!")
        return False
    
    # Verify webhook data
    if webhook_data.get('id') != batch['batch_id']:
        print(f"❌ Webhook batch_id mismatch: {webhook_data.get('id')} != {batch['batch_id']}")
        return False
    
    if webhook_data.get('status') != batch['status']:
        print(f"❌ Webhook status mismatch: {webhook_data.get('status')} != {batch['status']}")
        return False
    
    if webhook_data.get('request_counts', {}).get('total') != batch['progress']['total']:
        print(f"❌ Webhook request count mismatch")
        return False
    
    print("✅ Webhook data verified!")
    return True


def download_results(batch_id: str):
    """Download and display results."""
    print(f"\n📥 Downloading results...")
    
    response = requests.get(f"{API_URL}/v1/batches/{batch_id}/results")
    
    if response.status_code != 200:
        print(f"❌ Failed to download results: {response.text}")
        return
    
    results = response.text.strip().split('\n')
    print(f"✅ Downloaded {len(results)} results")
    
    # Show first result
    if results:
        print("\n📄 Sample result:")
        print(json.dumps(json.loads(results[0]), indent=2))


def main():
    """Run webhook test."""
    print("=" * 80)
    print("🧪 WEBHOOK FUNCTIONALITY TEST")
    print("=" * 80)
    
    # Start webhook receiver in background
    webhook_thread = threading.Thread(target=start_webhook_server, daemon=True)
    webhook_thread.start()
    time.sleep(2)  # Wait for server to start
    
    # Create test batch
    test_file = create_test_batch()
    
    # Submit batch
    batch = submit_batch(test_file)
    if not batch:
        return
    
    # Monitor until completion
    batch = monitor_batch(batch['batch_id'])
    
    # Verify webhook
    webhook_ok = verify_webhook(batch)
    
    # Download results
    download_results(batch['batch_id'])
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Batch ID:        {batch['batch_id']}")
    print(f"Status:          {batch['status']}")
    print(f"Requests:        {batch['progress']['completed']}/{batch['progress']['total']}")
    print(f"Webhook:         {'✅ PASSED' if webhook_ok else '❌ FAILED'}")
    print("=" * 80)
    
    # Cleanup
    test_file.unlink()
    print(f"\n🧹 Cleaned up {test_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

