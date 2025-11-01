"""
Test the workbench API endpoints

Tests:
1. Upload dataset
2. List datasets
3. Run benchmark
4. Check active benchmarks
5. Get results
"""

import requests
import json
import time
from pathlib import Path

API_BASE = "http://localhost:4080/admin"


def test_upload_dataset():
    """Test dataset upload."""
    print("\n1. Testing dataset upload...")
    
    # Use existing batch_5k.jsonl
    dataset_path = Path("batch_5k.jsonl")
    
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return None
    
    with open(dataset_path, "rb") as f:
        files = {"file": (dataset_path.name, f, "application/json")}
        response = requests.post(f"{API_BASE}/datasets/upload", files=files)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Uploaded dataset: {data['name']} ({data['count']} requests)")
        return data['dataset_id']
    else:
        print(f"❌ Upload failed: {response.status_code} - {response.text}")
        return None


def test_list_datasets():
    """Test listing datasets."""
    print("\n2. Testing list datasets...")
    
    response = requests.get(f"{API_BASE}/datasets")
    
    if response.status_code == 200:
        data = response.json()
        datasets = data.get('datasets', [])
        print(f"✅ Found {len(datasets)} datasets:")
        for ds in datasets:
            print(f"   - {ds['name']} ({ds['count']} requests)")
        return datasets
    else:
        print(f"❌ List failed: {response.status_code} - {response.text}")
        return []


def test_list_models():
    """Test listing models."""
    print("\n3. Testing list models...")
    
    response = requests.get(f"{API_BASE}/models")
    
    if response.status_code == 200:
        data = response.json()
        models = data.get('models', [])
        print(f"✅ Found {len(models)} models:")
        for model in models:
            print(f"   - {model['name']} ({model['model_id']})")
        return models
    else:
        print(f"❌ List failed: {response.status_code} - {response.text}")
        return []


def test_run_benchmark(dataset_id, model_id):
    """Test running a benchmark."""
    print(f"\n4. Testing run benchmark...")
    print(f"   Model: {model_id}")
    print(f"   Dataset: {dataset_id}")
    
    response = requests.post(
        f"{API_BASE}/benchmarks/run",
        json={
            "model_id": model_id,
            "dataset_id": dataset_id
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Started benchmark: {data['benchmark_id']}")
        return data['benchmark_id']
    else:
        print(f"❌ Run failed: {response.status_code} - {response.text}")
        return None


def test_active_benchmarks():
    """Test listing active benchmarks."""
    print("\n5. Testing active benchmarks...")
    
    response = requests.get(f"{API_BASE}/benchmarks/active")
    
    if response.status_code == 200:
        data = response.json()
        jobs = data.get('jobs', [])
        print(f"✅ Found {len(jobs)} active benchmarks:")
        for job in jobs:
            print(f"   - {job['model_name']} on {job['dataset_name']}")
            print(f"     Progress: {job['completed']}/{job['total']} ({job['progress']}%)")
            print(f"     Throughput: {job['throughput']:.1f} tok/s")
        return jobs
    else:
        print(f"❌ List failed: {response.status_code} - {response.text}")
        return []


def test_get_results(dataset_id):
    """Test getting results."""
    print(f"\n6. Testing get results for dataset {dataset_id}...")
    
    response = requests.get(f"{API_BASE}/workbench/results?dataset_id={dataset_id}")
    
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])
        print(f"✅ Found {len(results)} results")
        
        if results:
            print(f"\nSample result:")
            sample = results[0]
            print(f"   Candidate: {sample.get('candidate_name', sample['candidate_id'])}")
            print(f"   Models: {list(sample.get('models', {}).keys())}")
        
        return results
    else:
        print(f"❌ Get results failed: {response.status_code} - {response.text}")
        return []


def main():
    """Run all tests."""
    print("=" * 60)
    print("WORKBENCH API TESTS")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:4080/health")
        if response.status_code != 200:
            print("❌ Server not running! Start with: python -m core.batch_app.api_server")
            return
    except:
        print("❌ Server not running! Start with: python -m core.batch_app.api_server")
        return
    
    print("✅ Server is running")
    
    # Run tests
    dataset_id = test_upload_dataset()
    datasets = test_list_datasets()
    models = test_list_models()
    
    if not dataset_id and datasets:
        dataset_id = datasets[0]['id']
    
    if dataset_id and models:
        model_id = models[0]['model_id']
        benchmark_id = test_run_benchmark(dataset_id, model_id)
        
        if benchmark_id:
            # Wait a bit and check progress
            print("\nWaiting 10 seconds to check progress...")
            time.sleep(10)
            test_active_benchmarks()
    
    if dataset_id:
        test_get_results(dataset_id)
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

