# Sample Test Data for SynTera Test Suite

## Quick Start Guide

1. **Start your backend** (if not already running):
   ```powershell
   cd "C:\Users\Poornachand\Downloads\SynTera\syntera-test-suite-v5"
   .\.venv\Scripts\Activate.ps1
   python -m backend.main
   ```

2. **Open** `http://localhost:8000/` in your browser

3. **Create a survey**:
   - Go to "Surveys" tab
   - Click "+ New Survey"
   - Enter title: "Sample Test Survey"
   - Copy the Survey ID that appears

4. **Go to Validation tab** and use the sample data below

---

## Sample Data Sets

### Test Case 1: High Accuracy (TIER_1) - Very Similar Distributions

**Synthetic Responses:**
```json
[42, 33, 18, 7, 25, 31, 22, 15, 28, 19]
```

**Real Responses:**
```json
[40, 35, 20, 5, 27, 29, 24, 17, 26, 21]
```

**Expected Result:** TIER_1 (97.8% accuracy) - These are very similar distributions

---

### Test Case 2: Medium Accuracy (TIER_2) - Somewhat Different

**Synthetic Responses:**
```json
[50, 30, 15, 5, 35, 25, 20, 10, 30, 20]
```

**Real Responses:**
```json
[40, 35, 20, 5, 27, 29, 24, 17, 26, 21]
```

**Expected Result:** TIER_2 (85% accuracy) - Moderate differences

---

### Test Case 3: Lower Accuracy (TIER_3) - Very Different Distributions

**Synthetic Responses:**
```json
[80, 10, 5, 5, 0, 0, 0, 0, 0, 0]
```

**Real Responses:**
```json
[40, 35, 20, 5, 27, 29, 24, 17, 26, 21]
```

**Expected Result:** TIER_3 (85% accuracy) - Significant differences detected

---

### Test Case 4: Survey Response Counts (Realistic Scenario)

**Synthetic Responses (Response counts per option):**
```json
[120, 85, 45, 30, 20]
```

**Real Responses (Response counts per option):**
```json
[115, 90, 50, 28, 17]
```

**Expected Result:** TIER_1 or TIER_2 - Close match

---

### Test Case 5: Continuous Values (Rating Scale 1-10)

**Synthetic Responses:**
```json
[7.2, 8.1, 6.5, 7.8, 8.3, 6.9, 7.5, 8.0, 7.1, 7.6, 8.2, 6.8, 7.4, 7.9, 8.1]
```

**Real Responses:**
```json
[7.0, 8.0, 6.7, 7.6, 8.1, 7.1, 7.3, 7.8, 7.2, 7.5, 8.0, 6.9, 7.2, 7.7, 8.0]
```

**Expected Result:** TIER_1 - Very similar distributions

---

## How to Use in UI

1. **Copy the Survey ID** from the Surveys tab
2. **Paste it** into "Survey ID" field in Validation tab
3. **Copy one of the Synthetic Responses arrays** above
4. **Paste it** into "Synthetic responses" textarea
5. **Copy the matching Real Responses array**
6. **Paste it** into "Real responses" textarea
7. **Click "Run Validation"**
8. **View results** - You'll see:
   - Overall accuracy score
   - Overall tier (TIER_1, TIER_2, or TIER_3)
   - Individual test results (chi-square, KS test)
   - Test statistics and p-values

---

## Understanding the Results

- **TIER_1**: Excellent match (97.8% accuracy) - Synthetic data closely matches real data
- **TIER_2**: Good match (85% accuracy) - Some differences but generally aligned
- **TIER_3**: Poor match (85% accuracy) - Significant differences detected

The test suite runs:
- **Chi-square test**: Compares frequency distributions
- **KS test (Kolmogorov-Smirnov)**: Compares cumulative distributions

Both tests contribute to the overall tier assessment.

