"""Test script to verify CSV parser with summary format files"""
import sys
from pathlib import Path
from ml_engine.file_parser import FileParser

def test_parser(file_path):
    """Test parsing a CSV file"""
    print(f"\n{'='*60}")
    print(f"Testing: {file_path}")
    print(f"{'='*60}")
    
    parser = FileParser()
    
    # Read file as bytes
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    try:
        # Parse the file
        result = parser.parse_file(file_content, file_path.name)
        
        print(f"\n[OK] File parsed successfully!")
        print(f"  - Total rows: {result['total_rows']}")
        print(f"  - Total columns: {result['total_columns']}")
        print(f"  - Numeric columns: {result['numeric_columns']}")
        print(f"  - Response totals count: {len(result['response_totals'])}")
        print(f"  - All responses count: {len(result['all_responses'])}")
        print(f"  - Question data count: {len(result['question_data'])}")
        
        # Test extraction methods
        print(f"\n  Extraction Methods:")
        totals = parser.extract_response_array(result, method='totals')
        all_responses = parser.extract_response_array(result, method='all')
        print(f"    - 'totals' method: {len(totals)} values")
        print(f"      First 10: {totals[:10]}")
        print(f"    - 'all' method: {len(all_responses)} values")
        print(f"      First 10: {all_responses[:10]}")
        
        # Show question breakdown
        if result['question_data']:
            print(f"\n  Question Breakdown (first 3):")
            for q in result['question_data'][:3]:
                print(f"    - {q['question_id']}: {q['question_name']}")
                print(f"      Total: {q['response_totals']}, Responses: {len(q['individual_responses'])}")
        
        return result
        
    except Exception as e:
        print(f"\n[ERROR] Error parsing file: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test with the provided CSV files
    base_path = Path("Test generation/paired_ouput_tests")
    
    ai_file = base_path / "Banking_Fintech_Adoption_AI_Summary.csv"
    human_file = base_path / "Banking_Fintech_Adoption_Human_Summary.csv"
    
    if not ai_file.exists():
        print(f"Error: {ai_file} not found")
        sys.exit(1)
    
    if not human_file.exists():
        print(f"Error: {human_file} not found")
        sys.exit(1)
    
    print("Testing CSV Parser with Summary Format Files")
    print("=" * 60)
    
    ai_result = test_parser(ai_file)
    human_result = test_parser(human_file)
    
    if ai_result and human_result:
        print(f"\n{'='*60}")
        print("Comparison Summary:")
        print(f"{'='*60}")
        print(f"AI Summary - Totals: {len(ai_result['response_totals'])}, All: {len(ai_result['all_responses'])}")
        print(f"Human Summary - Totals: {len(human_result['response_totals'])}, All: {len(human_result['all_responses'])}")
        print(f"\n[OK] Both files parsed successfully! Ready for comparison.")
