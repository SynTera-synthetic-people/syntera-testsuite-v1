# File Upload Guide - Excel/CSV Questionnaire Comparison

## Overview

You can now compare two questionnaire files (Excel or CSV) directly in the SynTera Test Suite. The system will automatically extract numeric responses and compare them using statistical tests.

## Supported File Formats

- **Excel**: `.xlsx`, `.xls`
- **CSV**: `.csv`

## File Format Requirements

### Option 1: Response Counts per Question/Option (Recommended)

Your file should have columns representing different questions or response options, with rows containing response counts or frequencies.

**Example Excel/CSV structure:**
```
Question 1 | Question 2 | Question 3 | Question 4
-----------|-----------|-----------|-----------
42         | 33        | 18        | 7
40         | 35        | 20        | 5
```

**Extraction Method: "Totals"** - Sums each column to get total responses per question/option.

### Option 2: Individual Responses

Your file should contain individual response values (one per row).

**Example Excel/CSV structure:**
```
Response
--------
7.2
8.1
6.5
7.8
8.3
```

**Extraction Method: "All"** - Extracts all individual numeric values for distribution comparison.

## How to Use

### Step 1: Prepare Your Files

1. **Questionnaire 1 (Synthetic/File A)**: Your first questionnaire output
2. **Questionnaire 2 (Real/File B)**: Your second questionnaire output

Both files should:
- Contain numeric data (response counts, ratings, scores, etc.)
- Have the same structure (same columns/format)
- Be saved as Excel (.xlsx, .xls) or CSV (.csv)

### Step 2: Upload Files

1. Go to **Validation Runs** tab
2. Click **📁 File Upload** tab (if not already selected)
3. Click **Choose File** for Questionnaire 1 and select your first file
4. Click **Choose File** for Questionnaire 2 and select your second file
5. Select extraction method:
   - **Totals**: Sum per column (good for frequency/count data)
   - **All**: All individual responses (good for distribution data)
6. (Optional) Check "Link to existing survey" and enter a Survey ID
7. Click **Compare Files**

### Step 3: View Results

After processing, you'll see:
- **Overall Accuracy**: Percentage match between the two questionnaires
- **Confidence Tier**: TIER_1 (excellent), TIER_2 (good), or TIER_3 (needs improvement)
- **Test Details**: Individual statistical test results (Chi-square, KS test)
- **File Information**: Details about the uploaded files

### Step 4: Download Report

Click **📄 Download HTML Report** to get a client-ready formatted report, or **📋 Download JSON** for programmatic access.

## Example Files

### Example 1: Response Counts (CSV)

**questionnaire1.csv:**
```csv
Q1_Option1,Q1_Option2,Q1_Option3,Q2_Option1,Q2_Option2
42,33,18,25,31
40,35,20,27,29
```

**questionnaire2.csv:**
```csv
Q1_Option1,Q1_Option2,Q1_Option3,Q2_Option1,Q2_Option2
40,35,20,27,29
38,37,22,28,27
```

Use **Extraction Method: "Totals"** to sum each column.

### Example 2: Rating Scale (Excel)

**questionnaire1.xlsx:**
```
Rating
------
7.2
8.1
6.5
7.8
8.3
```

**questionnaire2.xlsx:**
```
Rating
------
7.0
8.0
6.7
7.6
8.1
```

Use **Extraction Method: "All"** to extract all individual values.

## Tips

1. **File Structure**: Ensure both files have similar structure (same columns or same data format)
2. **Numeric Data**: The system looks for numeric columns. Text columns are ignored unless they can be converted to numbers
3. **Empty Cells**: Empty cells are automatically skipped
4. **Large Files**: Files with thousands of rows may take a few seconds to process
5. **File Size**: Recommended file size under 10MB for best performance

## Troubleshooting

**"Could not extract numeric responses"**
- Ensure your files contain numeric data
- Check that at least one column has numeric values
- Try the other extraction method

**"Unsupported file type"**
- Use `.xlsx`, `.xls`, or `.csv` files only
- Ensure file extensions are correct

**"File comparison failed"**
- Check browser console for detailed error messages
- Ensure files are not corrupted
- Try re-saving your files in Excel/CSV format

## What Gets Compared?

The system extracts numeric responses from both files and compares:
- **Frequency distributions** (Chi-square test)
- **Cumulative distributions** (Kolmogorov-Smirnov test)

Results show how well the two questionnaires match statistically.

