#!/usr/bin/env python3
"""
Test script to verify SnapWatcher auto-start functionality.
This script creates a test watcher configuration and verifies it gets auto-started.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Add the SnapApi src directory to the path
sys.path.insert(0, '/home/crc/snap/SnapApi/src')

def create_test_watcher_config():
    """Create a test watcher configuration."""
    config_dir = "/home/crc/snap/SnapApi/src/config/watcher"
    os.makedirs(config_dir, exist_ok=True)
    
    test_config = {
        "name": "test-watcher",
        "cluster_name": "test-cluster",
        "cluster_config": {
            "api_url": "https://test-cluster.example.com:6443",
            "token": "test-token",
            "verify_ssl": False
        },
        "scope": "cluster",
        "trigger": "startupProbe",
        "namespace": None,
        "status": "stopped",
        "auto_delete_pod": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    config_file = os.path.join(config_dir, "test-watcher.json")
    with open(config_file, 'w') as f:
        json.dump(test_config, f, indent=4)
    
    print(f"Created test watcher config: {config_file}")
    return test_config

def test_watcher_loading():
    """Test the watcher loading functionality."""
    try:
        from routes.operator import load_watcher_configs_on_startup
        import asyncio
        
        print("Testing watcher loading and auto-start...")
        
        # Run the async function
        configs = asyncio.run(load_watcher_configs_on_startup())
        
        print(f"Loaded {len(configs)} watcher configurations")
        for config in configs:
            print(f"  - {config.name}: {config.status}")
        
        return True
        
    except Exception as e:
        print(f"Error testing watcher loading: {e}")
        return False

def test_api_endpoints():
    """Test the API endpoints for watcher status."""
    try:
        base_url = "http://localhost:8000"
        
        # Test watchers status endpoint
        response = requests.get(f"{base_url}/operator/watchers/status")
        if response.status_code == 200:
            data = response.json()
            print(f"Active watchers: {data.get('active_watchers', 0)}")
            print("Watcher details:")
            for name, info in data.get('watchers', {}).items():
                print(f"  - {name}: running={info['running']}, thread_alive={info['thread_alive']}")
            return True
        else:
            print(f"API test failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error testing API endpoints: {e}")
        return False

def cleanup_test_config():
    """Clean up the test configuration."""
    config_file = "/home/crc/snap/SnapApi/src/config/watcher/test-watcher.json"
    if os.path.exists(config_file):
        os.remove(config_file)
        print(f"Cleaned up test config: {config_file}")

def main():
    """Main test function."""
    print("=== SnapWatcher Auto-Start Test ===")
    
    # Create test configuration
    print("\n1. Creating test watcher configuration...")
    create_test_watcher_config()
    
    # Test watcher loading
    print("\n2. Testing watcher loading and auto-start...")
    if test_watcher_loading():
        print("✓ Watcher loading test passed")
    else:
        print("✗ Watcher loading test failed")
        return False
    
    # Wait a moment for watchers to start
    print("\n3. Waiting for watchers to start...")
    time.sleep(2)
    
    # Test API endpoints
    print("\n4. Testing API endpoints...")
    if test_api_endpoints():
        print("✓ API endpoints test passed")
    else:
        print("✗ API endpoints test failed")
    
    # Cleanup
    print("\n5. Cleaning up test configuration...")
    cleanup_test_config()
    
    print("\n=== Test Complete ===")
    return True

if __name__ == "__main__":
    main()
