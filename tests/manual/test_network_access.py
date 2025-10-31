#!/usr/bin/env python3
"""
Network Access Test - Verify Ollama Batch Server is accessible

Tests:
1. Localhost access (http://localhost:4080)
2. Local network access (http://10.0.0.223:4080)
3. Health endpoint
4. API docs endpoint
5. File upload endpoint
6. Batch creation endpoint
"""

import socket
import sys
from typing import Any

import requests

# Server configuration
LOCALHOST_URL = "http://localhost:4080"
NETWORK_IP = None  # Will auto-detect

def get_local_ip() -> str:
    """Get local network IP address"""
    try:
        # Create a socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"⚠️  Could not determine local IP: {e}")
        return None

def test_endpoint(url: str, endpoint: str, method: str = "GET", **kwargs) -> dict[str, Any]:
    """Test a specific endpoint"""
    full_url = f"{url}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(full_url, timeout=5, **kwargs)
        elif method == "POST":
            response = requests.post(full_url, timeout=5, **kwargs)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}

        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "response_time_ms": int(response.elapsed.total_seconds() * 1000),
            "content_length": len(response.content),
        }
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection refused - server not running or port blocked"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout - server too slow or network issue"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_result(test_name: str, result: dict[str, Any]) -> bool:
    """Print test result"""
    if result.get("success"):
        print(f"✅ {test_name}")
        if "status_code" in result:
            print(f"   Status: {result['status_code']}, Time: {result['response_time_ms']}ms")
        return True
    else:
        print(f"❌ {test_name}")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        return False

def main():
    print("=" * 80)
    print("Ollama Batch Server - Network Access Test")
    print("=" * 80)

    # Detect local IP
    global NETWORK_IP
    NETWORK_IP = get_local_ip()
    if NETWORK_IP:
        NETWORK_URL = f"http://{NETWORK_IP}:4080"
        print(f"\n📍 Detected Local IP: {NETWORK_IP}")
    else:
        NETWORK_URL = None
        print("\n⚠️  Could not detect local IP - skipping network tests")

    print(f"📍 Localhost URL: {LOCALHOST_URL}")
    print()

    all_passed = True

    # Test 1: Localhost Health Check
    print("1️⃣  Testing Localhost Access...")
    result = test_endpoint(LOCALHOST_URL, "/health")
    all_passed &= print_result("Localhost health check", result)
    print()

    # Test 2: Network Health Check
    if NETWORK_URL:
        print("2️⃣  Testing Network Access...")
        result = test_endpoint(NETWORK_URL, "/health")
        all_passed &= print_result(f"Network health check ({NETWORK_IP})", result)
        print()

    # Test 3: API Docs
    print("3️⃣  Testing API Documentation...")
    result = test_endpoint(LOCALHOST_URL, "/docs")
    all_passed &= print_result("API docs endpoint", result)
    print()

    # Test 4: OpenAPI Schema
    print("4️⃣  Testing OpenAPI Schema...")
    result = test_endpoint(LOCALHOST_URL, "/openapi.json")
    all_passed &= print_result("OpenAPI schema", result)
    print()

    # Test 5: File Upload Endpoint (OPTIONS for CORS)
    print("5️⃣  Testing File Upload Endpoint...")
    result = test_endpoint(LOCALHOST_URL, "/v1/files", method="GET")
    # GET should return 405 Method Not Allowed (expected)
    if result.get("status_code") == 405:
        result["success"] = True
        result["error"] = None
    all_passed &= print_result("File upload endpoint exists", result)
    print()

    # Test 6: Batch Endpoint
    print("6️⃣  Testing Batch Endpoint...")
    result = test_endpoint(LOCALHOST_URL, "/v1/batches", method="GET")
    # GET should return 405 Method Not Allowed (expected)
    if result.get("status_code") == 405:
        result["success"] = True
        result["error"] = None
    all_passed &= print_result("Batch endpoint exists", result)
    print()

    # Test 7: Port Binding Check
    print("7️⃣  Testing Port Binding...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('0.0.0.0', 4080))
        sock.close()

        if result == 0:
            print("✅ Port 4080 is open and listening")
        else:
            print("❌ Port 4080 is not accessible")
            all_passed = False
    except Exception as e:
        print(f"❌ Port check failed: {e}")
        all_passed = False
    print()

    # Summary
    print("=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED - Server is accessible!")
        print()
        print("🌐 Access URLs:")
        print(f"   Localhost: {LOCALHOST_URL}")
        if NETWORK_IP:
            print(f"   Network:   {NETWORK_URL}")
        print()
        print("📚 API Documentation:")
        print(f"   {LOCALHOST_URL}/docs")
        print()
        print("🔍 Health Check:")
        print(f"   curl {LOCALHOST_URL}/health")
        if NETWORK_IP:
            print(f"   curl {NETWORK_URL}/health")
        print()
        return 0
    else:
        print("❌ SOME TESTS FAILED - Check errors above")
        print()
        print("🔧 Troubleshooting:")
        print("   1. Is the server running? Check: ps aux | grep uvicorn")
        print("   2. Is Ollama running? Check: curl http://localhost:11434/api/tags")
        print("   3. Is port 4080 blocked? Check: sudo ufw status")
        print("   4. Check server logs for errors")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())

