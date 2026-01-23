"""
Quick test script to create a survey and run validation with sample data.
Run this after starting the backend server.
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Sample data - High accuracy test case
SYNTHETIC = [42, 33, 18, 7, 25, 31, 22, 15, 28, 19]
REAL = [40, 35, 20, 5, 27, 29, 24, 17, 26, 21]

print("🧪 SynTera Test Suite - Sample Data Test\n")

# Step 1: Create a survey
print("1. Creating survey...")
response = requests.post(
    f"{BASE_URL}/api/surveys/",
    json={"title": "Sample Test Survey", "description": "Automated test with sample data"}
)
if response.status_code != 200:
    print(f"❌ Error creating survey: {response.text}")
    exit(1)

survey = response.json()
survey_id = survey["id"]
print(f"✅ Survey created: {survey['title']} (ID: {survey_id})\n")

# Step 2: Run validation with sample data
print("2. Running validation with sample data...")
print(f"   Synthetic: {SYNTHETIC}")
print(f"   Real:      {REAL}\n")

response = requests.post(
    f"{BASE_URL}/api/validation/attach-and-compare/{survey_id}",
    json={
        "synthetic_responses": SYNTHETIC,
        "real_responses": REAL
    }
)

if response.status_code != 200:
    print(f"❌ Error running validation: {response.text}")
    exit(1)

results = response.json()
print("✅ Validation complete!\n")
print("=" * 60)
print("RESULTS:")
print("=" * 60)
print(f"Overall Accuracy: {results['overall_accuracy']:.1%}")
print(f"Overall Tier:     {results['overall_tier']}")
print(f"\nTest Details:")
for test in results.get("tests", []):
    if "error" in test:
        print(f"  ❌ {test['test']}: {test['error']}")
    else:
        print(f"  ✅ {test['test']}:")
        for key, value in test.items():
            if key != "test":
                if isinstance(value, float):
                    print(f"      {key}: {value:.4f}")
                else:
                    print(f"      {key}: {value}")
print("=" * 60)
print(f"\n🌐 View in browser: {BASE_URL}")
print(f"   Survey ID: {survey_id}")

