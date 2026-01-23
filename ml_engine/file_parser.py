"""File Parser for Excel and CSV Survey Data"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import logging
import io

logger = logging.getLogger(__name__)


class FileParser:
    """Parse Excel and CSV files to extract survey response data."""

    @staticmethod
    def parse_file(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse Excel or CSV file and extract response data.
        
        Args:
            file_content: File bytes
            filename: Original filename (for extension detection)
            
        Returns:
            Dictionary with parsed data including response arrays
        """
        try:
            # Create BytesIO object from file content
            file_buffer = io.BytesIO(file_content)
            file_buffer.seek(0)  # Ensure we're at the start
            
            # Determine file type and convert bytes to appropriate format
            # For Data Shell format detection, we need to read without headers first
            if filename.endswith(('.xlsx', '.xls')):
                # Read Excel file without headers to preserve row structure
                df_raw = pd.read_excel(file_buffer, engine='openpyxl', header=None)
                file_buffer.seek(0)  # Reset for potential re-read
            elif filename.endswith('.csv'):
                # For CSV files, reset buffer position and handle encoding
                file_buffer.seek(0)
                try:
                    # Try UTF-8 first, read without headers
                    df_raw = pd.read_csv(file_buffer, encoding='utf-8', header=None)
                except UnicodeDecodeError:
                    # Fallback to latin-1
                    file_buffer.seek(0)
                    df_raw = pd.read_csv(file_buffer, encoding='latin-1', header=None)
            else:
                raise ValueError(f"Unsupported file type: {filename}. Use .xlsx, .xls, or .csv")

            # Clean the dataframe
            df_raw = df_raw.dropna(how='all')  # Remove completely empty rows
            df_raw = df_raw.dropna(axis=1, how='all')  # Remove completely empty columns

            # Check for Data Shell format (multi-row header with Response ID)
            # Format: Row 1 (index 1) has "Response ID", Row 3 (index 3) has question labels, Row 5+ (index 5+) has data
            is_data_shell_format = False
            if len(df_raw) > 5 and len(df_raw.columns) > 0:
                try:
                    # Check if row 1 (index 1) contains "Response ID" in column 0
                    first_col_val = str(df_raw.iloc[1, 0]).strip() if pd.notna(df_raw.iloc[1, 0]) else ""
                    logger.debug(f"Row 1, Col 0 value: '{first_col_val}'")
                    if first_col_val and "response id" in first_col_val.lower():
                        # Check if row 3 (index 3) contains question labels
                        question_row = df_raw.iloc[3]
                        question_count = question_row[question_row.notna()].count()
                        logger.debug(f"Row 3 question count: {question_count}")
                        if question_count > 5:  # At least 5 questions
                            is_data_shell_format = True
                            logger.info(f"Detected Data Shell format in {filename} with {question_count} questions")
                except (IndexError, KeyError) as e:
                    logger.debug(f"Error checking Data Shell format: {e}")
                    pass
            
            # If not Data Shell format, read normally with headers
            if not is_data_shell_format:
                if filename.endswith(('.xlsx', '.xls')):
                    file_buffer.seek(0)
                    df = pd.read_excel(file_buffer, engine='openpyxl')
                elif filename.endswith('.csv'):
                    file_buffer.seek(0)
                    try:
                        df = pd.read_csv(file_buffer, encoding='utf-8')
                    except UnicodeDecodeError:
                        file_buffer.seek(0)
                        df = pd.read_csv(file_buffer, encoding='latin-1')
                df = df.dropna(how='all')
                df = df.dropna(axis=1, how='all')
            else:
                df = df_raw  # Use raw dataframe for Data Shell format
            
            # Check if this is a summary/aggregated format (has Question_ID and Count columns)
            # Case-insensitive check (only if not Data Shell format)
            col_names_lower = [str(c).lower() for c in df.columns] if not is_data_shell_format else []
            
            # Check for summary/aggregated format
            is_summary_format = (
                'question_id' in col_names_lower
            ) and (
                'count' in col_names_lower
            ) and not is_data_shell_format

            if is_data_shell_format:
                # Handle Data Shell format (e.g., training data)
                logger.info(f"Processing Data Shell format in {filename}")
                
                # Data Shell format structure:
                # Row 1 (index 1): "Response ID" in column 0
                # Row 3 (index 3): Question labels starting from column 1
                # Row 5+ (index 5+): Response data (Response IDs in column 0, responses in other columns)
                
                question_row = df.iloc[3]  # Row 3 (index 3) contains question labels
                data_start_row = 5  # Data starts from row 5 (index 5)
                
                # Ensure we have enough rows
                if len(df) <= data_start_row:
                    raise ValueError("Data Shell format detected but insufficient rows. Need at least 6 rows.")
                
                # Initialize categorical options mapping
                categorical_options = {}
                
                # Extract questions (skip column 0 which is Response ID)
                questions = {}
                for col_idx in range(1, len(df.columns)):
                    q_label = question_row.iloc[col_idx]
                    if pd.notna(q_label) and str(q_label).strip():
                        q_text = str(q_label).strip()
                        # Extract question ID if present (e.g., "Q8. Have you ordered...")
                        q_id = None
                        if q_text.startswith('Q') and '.' in q_text:
                            q_id = q_text.split('.')[0].strip()
                        else:
                            # Use column index as question ID
                            q_id = f"Q{col_idx}"
                        
                        questions[col_idx] = {
                            "question_id": q_id,
                            "question_name": q_text,
                            "column_index": col_idx
                        }
                
                logger.info(f"Found {len(questions)} questions in Data Shell format")
                
                # Extract response data
                response_data = df.iloc[data_start_row:].copy()
                
                # Get Response IDs (column 0)
                response_ids = response_data.iloc[:, 0].dropna().tolist()
                
                # Build question_data with response counts
                question_data = []
                all_responses = []
                
                for col_idx, q_info in questions.items():
                    q_id = q_info["question_id"]
                    q_name = q_info["question_name"]
                    
                    # Get all responses for this question
                    q_responses = response_data.iloc[:, col_idx].dropna().tolist()
                    
                    # Count responses
                    response_counts = {}
                    for resp in q_responses:
                        resp_str = str(resp).strip()
                        if resp_str:
                            response_counts[resp_str] = response_counts.get(resp_str, 0) + 1
                    
                    # Calculate totals and stats
                    q_totals = len(q_responses)
                    q_values = [float(x) for x in q_responses if str(x).replace('.', '').replace('-', '').isdigit()]
                    
                    question_data.append({
                        "question_id": q_id,
                        "question_name": q_name,
                        "response_totals": float(q_totals),
                        "response_counts": {str(k): float(v) for k, v in response_counts.items()},
                        "individual_responses": q_responses,
                        "mean": float(np.mean(q_values)) if len(q_values) > 0 else 0.0,
                        "std": float(np.std(q_values)) if len(q_values) > 0 else 0.0,
                    })
                    
                    all_responses.extend(q_responses)
                
                # For "totals" method: use response counts from all questions
                all_response_counts = {}
                for q_data in question_data:
                    for opt, count in q_data.get("response_counts", {}).items():
                        all_response_counts[opt] = all_response_counts.get(opt, 0) + count
                response_totals = [float(v) for v in all_response_counts.values()] if all_response_counts else []
                
                # For "all" method: use individual responses
                # Convert to numeric where possible
                numeric_responses = []
                for resp in all_responses:
                    resp_str = str(resp).strip()
                    if not resp_str:
                        continue
                    try:
                        # Try to convert to float
                        numeric_responses.append(float(resp_str))
                    except (ValueError, TypeError):
                        # For categorical, assign numeric code
                        if resp_str not in categorical_options:
                            categorical_options[resp_str] = len(categorical_options) + 1
                        numeric_responses.append(float(categorical_options[resp_str]))
                
                numeric_cols = list(questions.keys())  # All question columns are numeric-capable
                
                logger.info(f"Data Shell format: Extracted {len(questions)} questions, {len(response_ids)} responses")
                
                return {
                    "total_rows": len(response_data),
                    "total_columns": len(questions),
                    "numeric_columns": numeric_cols,
                    "response_totals": response_totals,
                    "all_responses": numeric_responses,
                    "question_data": question_data,
                    "format": "data_shell",
                    "response_ids": response_ids,
                }
                
            elif is_summary_format:
                # Handle summary/aggregated format (e.g., Banking_Fintech_Adoption_AI_Summary.csv)
                logger.info(f"Detected summary format in {filename}")
                
                # Normalize column names to lowercase for case-insensitive access
                df.columns = [col.lower() for col in df.columns]
                
                # Ensure we have the required columns
                if 'count' not in df.columns:
                    raise ValueError("Summary format detected but 'Count' column not found")
                
                question_id_col = 'question_id' if 'question_id' in df.columns else None
                option_col = 'option' if 'option' in df.columns else None
                question_text_col = 'question_text' if 'question_text' in df.columns else None
                
                # Extract all numeric values from Count column
                count_values = pd.to_numeric(df['count'], errors='coerce')
                count_values = count_values.dropna()
                
                # For "totals" method: use all count values (represents aggregated responses)
                response_totals = count_values.tolist()
                
                # For "all" method: expand counts into individual responses
                # For numeric options (like ratings 1-5), repeat the option value by count
                # For categorical options, assign numeric codes and repeat by count
                # For statistical summaries (MEAN, MEDIAN, STD), use the count value itself
                all_responses = []
                categorical_options = {}  # Track categorical options to assign consistent codes
                
                for idx, row in df.iterrows():
                    count_val = pd.to_numeric(row.get('count', 0), errors='coerce')
                    if pd.notna(count_val) and count_val > 0:
                        option_val = str(row.get(option_col, '')) if option_col else ''
                        
                        # Check if option is a numeric value (like "1", "2", "3" for ratings)
                        try:
                            option_numeric = float(option_val)
                            # For numeric options, repeat the option value by count
                            # This handles rating scales (1-5) and similar
                            all_responses.extend([option_numeric] * int(count_val))
                        except (ValueError, TypeError):
                            # For non-numeric options, check if it's a statistical summary
                            option_upper = option_val.upper()
                            if option_upper in ['MEAN', 'MEDIAN', 'STD', 'TOTAL_RESPONSES']:
                                # For statistical summaries, use the count value itself
                                all_responses.append(float(count_val))
                            else:
                                # For categorical options (like "Rural", "Semi-Urban"), 
                                # assign numeric codes based on order of appearance
                                question_id_val = str(row.get(question_id_col, 'all')) if question_id_col else 'all'
                                cat_key = f"{question_id_val}_{option_val}"
                                
                                if cat_key not in categorical_options:
                                    # Assign next available code (starting from 1)
                                    categorical_options[cat_key] = len(categorical_options) + 1
                                
                                cat_code = categorical_options[cat_key]
                                # Repeat the categorical code by count
                                all_responses.extend([float(cat_code)] * int(count_val))
                
                # Extract question-by-question data
                question_data = []
                if question_id_col:
                    for question_id in df[question_id_col].dropna().unique():
                        q_rows = df[df[question_id_col] == question_id]
                        question_name = q_rows[question_text_col].iloc[0] if question_text_col and question_text_col in q_rows.columns else str(question_id)
                        
                        # Get all counts for this question
                        q_counts = pd.to_numeric(q_rows['count'], errors='coerce').dropna()
                        q_totals = q_counts.sum()
                        
                        # Build response counts dictionary
                        response_counts = {}
                        if option_col:
                            for _, row in q_rows.iterrows():
                                option = str(row.get(option_col, ''))
                                count = pd.to_numeric(row.get('count', 0), errors='coerce')
                                if pd.notna(count):
                                    response_counts[option] = float(count)
                        
                        # Get individual responses (expanded from counts)
                        individual_responses = []
                        q_categorical_options = {}  # Track categorical options for this question
                        
                        for _, row in q_rows.iterrows():
                            count_val = pd.to_numeric(row.get('count', 0), errors='coerce')
                            if pd.notna(count_val) and count_val > 0:
                                option_val = str(row.get(option_col, '')) if option_col else ''
                                try:
                                    option_numeric = float(option_val)
                                    # For numeric options, repeat the option value by count
                                    individual_responses.extend([option_numeric] * int(count_val))
                                except (ValueError, TypeError):
                                    # For non-numeric options
                                    option_upper = option_val.upper()
                                    if option_upper in ['MEAN', 'MEDIAN', 'STD', 'TOTAL_RESPONSES']:
                                        # Statistical summaries: use count value
                                        individual_responses.append(float(count_val))
                                    else:
                                        # Categorical: assign code and repeat
                                        if option_val not in q_categorical_options:
                                            q_categorical_options[option_val] = len(q_categorical_options) + 1
                                        cat_code = q_categorical_options[option_val]
                                        individual_responses.extend([float(cat_code)] * int(count_val))
                        
                        question_data.append({
                            "question_id": str(question_id),
                            "question_name": question_name,
                            "response_totals": float(q_totals) if pd.notna(q_totals) else 0.0,
                            "response_counts": response_counts,
                            "individual_responses": individual_responses,
                            "mean": float(q_counts.mean()) if len(q_counts) > 0 else 0.0,
                            "std": float(q_counts.std()) if len(q_counts) > 0 else 0.0,
                        })
                else:
                    # No question_id column, treat entire file as one question
                    question_data.append({
                        "question_id": "all",
                        "question_name": "All Questions",
                        "response_totals": float(count_values.sum()) if len(count_values) > 0 else 0.0,
                        "response_counts": {},
                        "individual_responses": all_responses,
                        "mean": float(count_values.mean()) if len(count_values) > 0 else 0.0,
                        "std": float(count_values.std()) if len(count_values) > 0 else 0.0,
                    })
                
                numeric_cols = ['count']  # Mark count as numeric column
                
            else:
                # Handle raw response format (original logic)
                # Extract numeric responses
                # Strategy: Find columns with numeric data (survey responses)
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                
                # If no numeric columns, try to convert string columns
                if not numeric_cols:
                    for col in df.columns:
                        try:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                            if df[col].notna().any():
                                numeric_cols.append(col)
                        except:
                            pass

                # Extract response arrays
                # Option 1: Sum across rows (total responses per question/option)
                response_totals = []
                if numeric_cols:
                    # Sum each numeric column (represents responses per question/option)
                    response_totals = df[numeric_cols].sum().tolist()
                else:
                    # Fallback: Count occurrences of each value
                    for col in df.columns:
                        value_counts = df[col].value_counts().sort_index()
                        response_totals.extend(value_counts.tolist())

                # Option 2: Flatten all responses into a single array
                all_responses = []
                if numeric_cols:
                    all_responses = df[numeric_cols].values.flatten()
                    all_responses = [float(x) for x in all_responses if pd.notna(x)]
                else:
                    # Convert all values to numeric where possible
                    for col in df.columns:
                        numeric_vals = pd.to_numeric(df[col], errors='coerce')
                        all_responses.extend([float(x) for x in numeric_vals if pd.notna(x)])

                # Extract question-by-question data (each column = question/option)
                question_data = []
                for col in numeric_cols:
                    col_data = df[col].dropna()
                    question_data.append({
                        "question_id": col,
                        "question_name": str(col),
                        "response_totals": float(df[col].sum()) if len(col_data) > 0 else 0.0,
                        "response_counts": df[col].value_counts().to_dict(),
                        "individual_responses": [float(x) for x in col_data if pd.notna(x)],
                        "mean": float(df[col].mean()) if len(col_data) > 0 else 0.0,
                        "std": float(df[col].std()) if len(col_data) > 0 else 0.0,
                    })
            
            return {
                "filename": filename,
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "numeric_columns": numeric_cols,
                "response_totals": response_totals,  # Sum per column (good for frequency comparison)
                "all_responses": all_responses,  # All individual responses (good for distribution comparison)
                "question_data": question_data,  # Per-question breakdown
                "dataframe_preview": df.head(10).to_dict('records') if len(df) > 0 else [],
                "column_names": df.columns.tolist(),
            }

        except Exception as e:
            logger.error(f"Error parsing file {filename}: {str(e)}")
            raise ValueError(f"Failed to parse file: {str(e)}")

    @staticmethod
    def extract_response_array(file_data: Dict[str, Any], method: str = "totals") -> List[float]:
        """
        Extract response array from parsed file data.
        
        Args:
            file_data: Parsed file data from parse_file()
            method: "totals" (sum per column) or "all" (all individual responses)
            
        Returns:
            List of float values for comparison
        """
        if method == "totals":
            return [float(x) for x in file_data.get("response_totals", []) if x is not None]
        else:  # method == "all"
            return [float(x) for x in file_data.get("all_responses", []) if x is not None]

