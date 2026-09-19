import sys
import json
import requests

API_BASE = "http://localhost:8000"
TEST_EMAIL = "eval_runner@example.com"
TEST_PASSWORD = "evalpass123"

SAMPLE_CASES = [
    {
        "case_id": "S01",
        "message": "My order worth 3500 rupees arrived damaged yesterday.",
        "expected_action": "REQUEST_PHOTOS",
    },
    {
        "case_id": "S02",
        "message": "I changed my mind about this unopened non-food product. It arrived 10 days ago.",
        "expected_action": "APPROVE_RETURN",
    },
    {
        "case_id": "S03",
        "message": "My parcel has still not arrived and it was dispatched 9 days ago.",
        "expected_action": "OPEN_SHIPPING_INVESTIGATION",
    },
    {
        "case_id": "S04",
        "message": "I ordered strawberry but received chocolate 2 days ago.",
        "expected_action": "REPLACE_CORRECT_ITEM",
    },
    {
        "case_id": "S05",
        "message": "I want to return this.",
        "expected_action": "NEEDS_MORE_INFORMATION",
    },
]


def get_token() -> str:
    resp = requests.post(f"{API_BASE}/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    resp = requests.post(f"{API_BASE}/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    if resp.status_code != 201:
        print(f"ERROR: Could not create eval user: {resp.text}")
        sys.exit(1)
    resp = requests.post(f"{API_BASE}/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    return resp.json()["access_token"]


def run_evaluation():
    print("Connecting to API...")
    health = requests.get(f"{API_BASE}/health")
    if health.status_code != 200:
        print(f"ERROR: API is not running at {API_BASE}")
        sys.exit(1)

    print("Authenticating eval user...")
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\nRunning {len(SAMPLE_CASES)} test cases...\n")
    print("-" * 60)

    correct = 0
    results = []

    for case in SAMPLE_CASES:
        resp = requests.post(
            f"{API_BASE}/tickets",
            json={"message": case["message"]},
            headers=headers,
        )
        if resp.status_code != 201:
            print(f"ERROR on {case['case_id']}: {resp.text}")
            results.append({"case_id": case["case_id"], "passed": False, "got": "ERROR"})
            continue

        data = resp.json()
        got_action = data["decision"]["action"]
        expected = case["expected_action"]
        passed = got_action == expected

        if passed:
            correct += 1

        status = "PASS" if passed else "FAIL"
        print(f"{status}  [{case['case_id']}]  Expected: {expected}")
        if not passed:
            print(f"            Got:      {got_action}")
        results.append({"case_id": case["case_id"], "passed": passed, "got": got_action})

    total = len(SAMPLE_CASES)
    accuracy = correct / total * 100

    print("-" * 60)
    print(f"\nEvaluation Results")
    print(f"------------------")
    print(f"Total cases : {total}")
    print(f"Correct     : {correct}")
    print(f"Incorrect   : {total - correct}")
    print(f"Accuracy    : {accuracy:.0f}%")

    return correct, total


if __name__ == "__main__":
    correct, total = run_evaluation()
    sys.exit(0 if correct == total else 1)
