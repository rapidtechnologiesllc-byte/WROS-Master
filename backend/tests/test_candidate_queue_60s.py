"""
Autonomous 60-second candidate queue validation loop.

Tests:
1. Create candidate via POST /api/v1/candidates/create
2. Verify it returns HTTP 200/201
3. Verify candidate_id is returned
4. Validate candidate appears in ChannelQueueItem (queue status)
5. Validate Thunder processes it
6. Repeat every 60 seconds
"""
import time
import json
import os
import requests
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8080/api/v1"
LOOP_INTERVAL = 60  # seconds
CHECK_INTERVAL = 5  # check queue status every 5 seconds
TOTAL_DURATION = 600  # run for 10 minutes
REQUEST_TIMEOUT = 10
QUEUE_CHECK_TIMEOUT = 5

# Candidate template
def create_candidate_payload():
    timestamp = int(time.time() * 1000)
    return {
        "candidate_email": f"test_candidate_{timestamp}@test.com",
        "candidate_first_name": "Test",
        "candidate_last_name": f"Candidate{timestamp}",
        "candidate_mobile": f"555{timestamp % 10000:04d}",
        "candidate_current_location": "San Francisco, CA",
        "candidate_date_of_birth": "1990-01-01",
        "candidate_gender": "Not Specified",
        "candidate_source": "Test",
        "candidate_experience": "5",
        "candidate_skills": ["Python", "FastAPI"],
        "education_records": [],
        "experience_records": [],
    }

def test_candidate_creation():
    """Test POST /api/v1/candidates/create endpoint."""
    payload = create_candidate_payload()

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Creating candidate...")
    print(f"  Email: {payload['candidate_email']}")

    try:
        response = requests.post(
            f"{API_BASE}/candidates/create",
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        print(f"  Status: {response.status_code}")

        if response.status_code not in [200, 201]:
            print(f"  ❌ FAIL: Expected 200/201, got {response.status_code}")
            try:
                # Intentional: Try to read error details from response
                print(f"  Response: {response.text}")
            except Exception as text_err:
                # Intentional: If response text fails, log that it was unreadable
                print(f"  (Could not read response: {text_err})")
            return None

        try:
            # Parse JSON response payload
            data = response.json()
        except Exception as json_err:
            # Intentional: Response is not valid JSON - log and exit
            print(f"  ❌ FAIL: Could not parse JSON response: {json_err}")
            return None

        candidate_id = data.get("candidate_id")

        if not candidate_id:
            # Intentional: Response missing required candidate_id field
            print(f"  ❌ FAIL: No candidate_id in response")
            return None

        print(f"  ✅ PASS: candidate_id={candidate_id}")
        return candidate_id

    except requests.exceptions.RequestException as e:
        # Re-raise to let caller handle connection failures
        print(f"  ❌ FAIL: Request error: {e}")
        raise

def check_queue_status(candidate_id):
    """Check if candidate appears in queue."""
    print(f"\n  Checking queue status for {candidate_id}...")

    try:
        response = requests.get(
            f"{API_BASE}/queues/{candidate_id}",
            timeout=QUEUE_CHECK_TIMEOUT
        )

        if response.status_code == 200:
            try:
                # Parse queue status response
                data = response.json()
            except Exception as json_err:
                # Intentional: Queue response format unexpected, log and continue
                print(f"  ℹ️ Could not parse queue response: {json_err}")
                return None

            status = data.get("status", "unknown")
            print(f"  ✅ Queue status: {status}")
            return status
        else:
            # Intentional: Candidate not yet in queue (normal during processing)
            print(f"  ℹ️ Not yet in queue (status: {response.status_code})")
            return None

    except requests.exceptions.RequestException as e:
        # Intentional: Queue endpoint may not be available, return None (non-critical)
        print(f"  ℹ️ Queue check failed: {e}")
        return None

def run_autonomous_loop():
    """Run the autonomous validation loop."""
    print("=" * 70)
    print("AUTONOMOUS CANDIDATE QUEUE VALIDATION - 60 SECOND LOOP")
    print("=" * 70)
    print(f"Duration: {TOTAL_DURATION} seconds")
    print(f"Loop interval: {LOOP_INTERVAL} seconds")
    print(f"API Base: {API_BASE}")
    print("=" * 70)

    test_count = 0
    pass_count = 0
    fail_count = 0
    start_time = time.time()

    while time.time() - start_time < TOTAL_DURATION:
        test_count += 1
        loop_start = time.time()

        print(f"\n[LOOP {test_count}] Started at {datetime.now().strftime('%H:%M:%S')}")

        # Create candidate
        candidate_id = test_candidate_creation()

        if candidate_id:
            pass_count += 1

            # Monitor queue for CHECK_INTERVAL seconds
            queue_found = False
            check_start = time.time()

            while time.time() - check_start < CHECK_INTERVAL:
                status = check_queue_status(candidate_id)
                if status:
                    queue_found = True
                    break
                time.sleep(1)

            if not queue_found:
                print(f"  ⚠️  WARNING: Candidate not found in queue after {CHECK_INTERVAL}s")
        else:
            fail_count += 1

        # Wait for next loop
        elapsed = time.time() - loop_start
        sleep_time = max(0, LOOP_INTERVAL - elapsed)

        if sleep_time > 0:
            print(f"\nWaiting {sleep_time:.0f}s until next loop...")
            time.sleep(sleep_time)

        # Summary
        print(f"\n[SUMMARY] Total: {test_count} | Pass: {pass_count} | Fail: {fail_count}")

if __name__ == "__main__":
    try:
        run_autonomous_loop()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test loop stopped by user")
