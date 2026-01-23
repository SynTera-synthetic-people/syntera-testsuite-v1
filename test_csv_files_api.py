"""Test the file comparison API endpoint with actual CSV files"""
import requests
from pathlib import Path

BASE_URL = "http://localhost:8000"

# Paths to test files
ai_file = Path("Test generation/paired_ouput_tests/Banking_Fintech_Adoption_AI_Summary.csv")
human_file = Path("Test generation/paired_ouput_tests/Banking_Fintech_Adoption_Human_Summary.csv")

print("Testing File Comparison API with CSV Files")
print("=" * 60)

# Check if files exist
if not ai_file.exists():
    print(f"[ERROR] File not found: {ai_file}")
    exit(1)

if not human_file.exists():
    print(f"[ERROR] File not found: {human_file}")
    exit(1)

print(f"[OK] Files found:")
print(f"  Synthetic/AI: {ai_file}")
print(f"  Real/Human: {human_file}\n")

# Test file comparison
print("Sending files to comparison endpoint...")
try:
    with open(ai_file, 'rb') as f1, open(human_file, 'rb') as f2:
        files = {
            'synthetic_file': (ai_file.name, f1, 'text/csv'),
            'real_file': (human_file.name, f2, 'text/csv')
        }
        data = {
            'method': 'totals'  # Use totals method for summary data
        }
        
        response = requests.post(
            f"{BASE_URL}/api/validation/compare-files",
            files=files,
            data=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print("[OK] Comparison successful!\n")
            print("=" * 60)
            print("RESULTS:")
            print("=" * 60)
            print(f"Survey ID: {result.get('survey_id', 'N/A')}")
            print(f"Overall Accuracy: {result.get('overall_accuracy', 0):.1%}")
            print(f"Overall Tier: {result.get('overall_tier', 'N/A')}")
            print(f"\nFile Info:")
            if 'file_info' in result:
                fi = result['file_info']
                print(f"  Synthetic file: {fi.get('synthetic_file', 'N/A')}")
                print(f"  Real file: {fi.get('real_file', 'N/A')}")
                print(f"  Extraction method: {fi.get('extraction_method', 'N/A')}")
                print(f"  Synthetic responses: {fi.get('synthetic_responses_count', 0)}")
                print(f"  Real responses: {fi.get('real_responses_count', 0)}")
            
            print(f"\nTest Summary:")
            if 'test_summary' in result:
                ts = result['test_summary']
                print(f"  Total tests: {ts.get('total_tests', 0)}")
                print(f"  Successful: {ts.get('successful_tests', 0)}")
                print(f"  Failed: {ts.get('failed_tests', 0)}")
                print(f"  TIER_1: {ts.get('tier_1_count', 0)}")
                print(f"  TIER_2: {ts.get('tier_2_count', 0)}")
                print(f"  TIER_3: {ts.get('tier_3_count', 0)}")
            
            if 'recommendations' in result and result['recommendations']:
                print(f"\nRecommendations:")
                for rec in result['recommendations']:
                    print(f"  - {rec}")
            
            if 'question_comparisons' in result and result['question_comparisons']:
                print(f"\nQuestion Comparisons: {len(result['question_comparisons'])} questions")
                # Show first 3 questions
                for q in result['question_comparisons'][:3]:
                    print(f"  - {q.get('question_name', q.get('question_id'))}: "
                          f"Match Score: {q.get('match_score', 0):.1%}, Tier: {q.get('tier', 'N/A')}")
            
            print("=" * 60)
            print(f"\n[OK] Test completed successfully!")
            print(f"Survey ID: {result.get('survey_id')}")
            print(f"View results at: {BASE_URL}")
            
        else:
            print(f"[ERROR] API request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            exit(1)
            
except Exception as e:
    print(f"[ERROR] Exception occurred: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
