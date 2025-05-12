"""
Test script to run the Flask API and test the scheduler endpoint
"""
import os
import sys
import subprocess
import time
import json
import requests

def start_flask_api():
    """Start the Flask API in a separate process"""
    print("Starting Flask API...")
    api_process = subprocess.Popen(
        ["python", "-m", "backend.api"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.abspath(".")
    )
    # Give the server time to start
    time.sleep(2)
    return api_process

def test_scheduler_endpoint():
    """Test the scheduler endpoint"""
    print("Testing /api/scheduler/run endpoint...")
    try:
        response = requests.post(
            "http://localhost:5000/api/scheduler/run",
            json={"days": 5}
        )
        
        if response.status_code == 200:
            print("Endpoint returned 200 OK")
            data = response.json()
            
            if data.get("success"):
                print(f"Scheduler returned {len(data.get('daily_plans', []))} daily plans")
                
                # Check output directory for new files
                output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "output")
                print(f"\nOutput files saved to: {output_dir}")
                
                files = os.listdir(output_dir)
                json_files = [f for f in files if f.endswith('.json')]
                latest_files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True)[:5]
                
                print(f"Latest files in output directory:")
                for filename in latest_files:
                    file_path = os.path.join(output_dir, filename)
                    file_size = os.path.getsize(file_path)
                    print(f"- {filename} ({file_size} bytes)")
                
                return True
            else:
                print(f"Scheduler error: {data.get('error')}")
                return False
        else:
            print(f"Endpoint returned status code {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Error testing endpoint: {e}")
        return False

if __name__ == "__main__":
    # Start the Flask API
    api_process = start_flask_api()
    
    try:
        # Test the scheduler endpoint
        success = test_scheduler_endpoint()
        
        if success:
            print("\nTest completed successfully!")
        else:
            print("\nTest failed.")
    finally:
        # Terminate the API process
        print("Shutting down Flask API...")
        api_process.terminate()
        stdout, stderr = api_process.communicate()
        
        print("\nAPI stdout:")
        print(stdout.decode())
        
        print("\nAPI stderr:")
        print(stderr.decode())
