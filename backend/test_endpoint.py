#!/usr/bin/env python3
"""Quick test to verify candidate creation endpoint."""

import requests
import json

BASE_URL = "http://localhost:8080/api/v1"

# Test candidate creation endpoint
def test_create_candidate():
    endpoint = f"{BASE_URL}/candidates/create"

    payload = {
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "mobile": "+1234567890"
    }

    headers = {
        "Content-Type": "application/json",
        # Add auth token if needed
        "Authorization": "Bearer <token>"  # Replace with actual token
    }

    print(f"Testing POST {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        print(f"\nStatus: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            result = response.json()
            if 'message_id' in result:
                print(f"\n✅ SUCCESS: message_id created: {result['message_id']}")
            else:
                print(f"\n❌ FAIL: Response missing 'message_id' field")
        else:
            print(f"\n❌ FAIL: Unexpected status code {response.status_code}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_create_candidate()
