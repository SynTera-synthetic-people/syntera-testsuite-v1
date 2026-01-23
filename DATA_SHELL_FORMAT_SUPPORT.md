# Data Shell Format Support

## Overview

The SynTera Test Suite now supports the **Data Shell** format, which is commonly used in survey research and data collection. This format has a specific multi-row header structure that requires special parsing.

## Format Structure

The Data Shell format follows this structure:

```
Row 0 (Index 0): Usually empty or metadata
Row 1 (Index 1): "Response ID" in column 0
Row 2 (Index 2): Usually empty or section headers
Row 3 (Index 3): Question labels (Q8, Q6, Q7, etc.) starting from column 1
Row 4 (Index 4): Usually empty
Row 5+ (Index 5+): Actual response data
  - Column 0: Response IDs
  - Column 1+: Response values for each question
```

## Example

```
        Col 0          Col 1                                    Col 2      Col 3
Row 0   (empty)
Row 1   Response ID    (empty)
Row 2   (empty)        (empty)
Row 3   (empty)        Q8. Have you ordered...                  Q6.Gender  Q7. Age
Row 4   (empty)        (empty)
Row 5   60030          Yes                                       Female     18-24
Row 6   60034          Yes                                       Female     31-40
...
```

## Automatic Detection

The parser automatically detects Data Shell format by:
1. Checking if row 1 (index 1), column 0 contains "Response ID"
2. Verifying that row 3 (index 3) contains at least 5 question labels
3. If both conditions are met, the file is parsed as Data Shell format

## Features

### Question Extraction
- Questions are extracted from row 3
- Question IDs are extracted from labels (e.g., "Q8. Question text" → "Q8")
- If no question ID is found, column index is used (e.g., "Q1", "Q2")

### Response Processing
- Response IDs are extracted from column 0 starting from row 5
- Individual responses are extracted for each question column
- Response counts are calculated per question
- Both categorical and numeric responses are handled

### Output Format
The parser returns data in the same format as other file types:
- `question_data`: Array of question objects with:
  - `question_id`: Question identifier
  - `question_name`: Full question text
  - `response_counts`: Dictionary of option → count
  - `response_totals`: Total number of responses
  - `individual_responses`: List of all responses
  - `mean` and `std`: Statistical measures (for numeric data)

## Usage

Simply upload a Data Shell format Excel file (.xlsx or .xls) through the File Upload interface. The system will:
1. Automatically detect the format
2. Extract all questions and responses
3. Process the data for comparison

## Supported File Types

- Excel files: `.xlsx`, `.xls`
- The format is detected automatically - no special configuration needed

## Notes

- The parser handles missing values and empty cells gracefully
- Response IDs are preserved for tracking
- Questions with no responses are still included in the output
- Both "totals" and "all" extraction methods work with Data Shell format
