"""File Parser for Excel and CSV Survey Data"""
import io
import logging
import math
import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FileParser:
    """Parse Excel and CSV files to extract survey response data."""

    @staticmethod
    def _is_likely_metadata_column(col_name: Any) -> bool:
        """Heuristic: columns that look like IDs/timestamps/row metadata, not survey responses."""
        c = str(col_name or "").strip().lower()
        if not c:
            return False
        patterns = (
            "id",
            "response id",
            "respondent id",
            "record id",
            "uuid",
            "guid",
            "timestamp",
            "time",
            "date",
            "created",
            "updated",
            "email",
            "phone",
            "mobile",
            "name",
            "serial",
            "index",
            "row",
        )
        return any(p in c for p in patterns)

    @staticmethod
    def _select_numeric_response_columns(df: pd.DataFrame) -> list[Any]:
        """
        Pick numeric columns likely to be actual survey response fields.
        Excludes likely metadata and very sparse/almost-empty numeric columns.
        """
        if df is None or df.empty:
            return []
        n_rows = max(len(df), 1)
        min_non_null = max(2, int(math.ceil(n_rows * 0.05)))
        out: list[Any] = []
        for col in df.columns:
            ser = pd.to_numeric(df[col], errors="coerce")
            nn = int(ser.notna().sum())
            if nn < min_non_null:
                continue
            if FileParser._is_likely_metadata_column(col):
                # Keep classic survey IDs like Q1 only if they are short Q-codes.
                col_s = str(col).strip()
                if not re.match(r"^Q\d+$", col_s, re.IGNORECASE):
                    continue
            out.append(col)
        return out

    @staticmethod
    def _normalize_aggregate_headers(df: pd.DataFrame) -> pd.DataFrame:
        """
        Best-effort normalization for aggregate survey exports.
        Canonical target headers:
          Q No. | Question Description | Options | Count
        If headers are missing/blank/unnamed, assign by position/content heuristics.
        """
        if df is None or df.empty:
            return df
        if len(df.columns) < 3:
            return df

        cols = list(df.columns)
        norm = [str(c or "").strip().lower() for c in cols]

        def is_blankish(h: str) -> bool:
            return (not h) or h in {"nan", "none"} or h.startswith("unnamed:")

        has_q = any(h in {"q no.", "q no", "qno", "questionno", "question no.", "question number", "question_id"} for h in norm)
        has_opt = any(h in {"options", "option", "response", "answer"} for h in norm)
        has_cnt = any(h in {"count", "value from report", "valuefromreport", "frequency", "n"} for h in norm)
        blankish_present = any(is_blankish(h) for h in norm)

        # Trigger normalization only when headers are clearly incomplete/noisy.
        if not (blankish_present or not has_cnt or not has_q or not has_opt):
            return df

        # Positional default for common 4-column uploads.
        # Q No. | Question Description | Options | Count
        mapping: dict[Any, str] = {}
        if len(cols) >= 4:
            mapping[cols[0]] = "Q No."
            mapping[cols[1]] = "Question Description"
            mapping[cols[2]] = "Options"
            mapping[cols[3]] = "Count"
        elif len(cols) == 3:
            mapping[cols[0]] = "Q No."
            mapping[cols[1]] = "Options"
            mapping[cols[2]] = "Count"

        out = df.rename(columns=mapping).copy()
        return out

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

            if not is_data_shell_format:
                df = FileParser._normalize_aggregate_headers(df)

            # Aggregated export: one row per option, repeated question number / text forward-filled
            # (e.g. "Q No., Question Description, Options, Value from report" or "... , Count")
            if not is_data_shell_format:
                agg_parsed = FileParser._try_parse_aggregate_option_row_export(df, filename)
                if agg_parsed is not None:
                    return agg_parsed
            
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
                numeric_cols = FileParser._select_numeric_response_columns(df.select_dtypes(include=[np.number]))
                
                # If no numeric columns, try to convert string columns
                if not numeric_cols:
                    for col in df.columns:
                        try:
                            converted = pd.to_numeric(df[col], errors='coerce')
                            if converted.notna().any():
                                df[col] = converted
                                numeric_cols.append(col)
                        except:
                            pass
                    numeric_cols = FileParser._select_numeric_response_columns(df[numeric_cols]) if numeric_cols else []

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
    def _column_lookup(df: pd.DataFrame) -> dict[str, str]:
        """Map normalized header (no spaces, lower) -> original column name."""
        out: dict[str, str] = {}
        for c in df.columns:
            key = re.sub(r"\s+", "", str(c).strip().lower())
            out[key] = str(c)
        return out

    @staticmethod
    def _try_parse_aggregate_option_row_export(df: pd.DataFrame, filename: str) -> Optional[Dict[str, Any]]:
        """
        Detect tabular exports where each option is a row and question number / stem repeat
        or are forward-filled (common for SPSS-style summaries and Excel crosstabs).
        """
        lookup = FileParser._column_lookup(df)
        aliases_q = ("qno.", "qno", "questionno.", "questionno", "questionnumber", "questionid", "q_id", "qnumber")
        aliases_opt = ("options", "option", "response", "answer", "category", "label")
        aliases_cnt = (
            "valuefromreport",
            "count",
            "value",
            "n",
            "frequency",
            "responses",
            "respondents",
            "weightedcount",
        )
        aliases_txt = (
            "questiondescription",
            "questiontext",
            "question_text",
            "question",
            "questiontitle",
            "stem",
        )

        def pick(cands: tuple[str, ...]) -> Optional[str]:
            for a in cands:
                if a in lookup:
                    return lookup[a]
            return None

        def _is_blankish_header(col_name: Any) -> bool:
            s = str(col_name or "").strip().lower()
            if not s or s in {"nan", "none"}:
                return True
            # Pandas often labels blank CSV headers as "Unnamed: 3"
            return s.startswith("unnamed:")

        q_col = pick(aliases_q)
        opt_col = pick(aliases_opt)
        cnt_col = pick(aliases_cnt)
        txt_col = pick(aliases_txt)

        # Explicit fallback for human files where count header is blank.
        if not cnt_col:
            sample = df.head(min(len(df), 120))
            blankish_numeric_candidates: list[tuple[float, str]] = []
            for c in df.columns:
                if not _is_blankish_header(c):
                    continue
                ser = pd.to_numeric(sample[c], errors="coerce")
                non_nan = ser[~pd.isna(ser)]
                ratio = float(len(non_nan)) / max(1, len(sample))
                if ratio > 0:
                    blankish_numeric_candidates.append((ratio, str(c)))
            if blankish_numeric_candidates:
                blankish_numeric_candidates.sort(key=lambda x: x[0], reverse=True)
                cnt_col = blankish_numeric_candidates[0][1]

        # Header-light fallback: infer likely columns by content profile.
        def _norm(v: Any) -> str:
            return str(v or "").strip().lower()

        def _is_qid_like(v: Any) -> bool:
            s = _norm(v)
            if not s or s == "nan":
                return False
            return bool(re.match(r"^q?\s*[\-:._ ]*\d+(\.0+)?$", s))

        def _is_numeric_like(v: Any) -> bool:
            s = str(v or "").strip()
            if not s or s.lower() == "nan":
                return False
            s = s.replace(",", "").replace(" ", "")
            s = re.sub(r"[^0-9.\-]", "", s)
            if not s or s in {"-", ".", "-."}:
                return False
            try:
                float(s)
                return True
            except ValueError:
                return False

        if df is not None and len(df.columns) >= 2:
            sample = df.head(min(len(df), 120))
            profiles: list[tuple[str, float, float, float]] = []
            for c in df.columns:
                vals = sample[c].tolist()
                non_empty = [v for v in vals if str(v).strip() and str(v).strip().lower() != "nan"]
                denom = max(1, len(non_empty))
                qid_ratio = sum(1 for v in non_empty if _is_qid_like(v)) / denom
                num_ratio = sum(1 for v in non_empty if _is_numeric_like(v)) / denom
                text_ratio = sum(
                    1
                    for v in non_empty
                    if not _is_numeric_like(v) and not _is_qid_like(v) and len(str(v).strip()) >= 2
                ) / denom
                profiles.append((str(c), qid_ratio, num_ratio, text_ratio))

            if not cnt_col:
                maybe = sorted(profiles, key=lambda t: t[2], reverse=True)
                if maybe and maybe[0][2] >= 0.55:
                    cnt_col = maybe[0][0]
                # Relaxed fallback for messy exports: pick best numeric-like column even at lower confidence.
                elif maybe and maybe[0][2] >= 0.22:
                    cnt_col = maybe[0][0]

            if not q_col:
                maybe = sorted(profiles, key=lambda t: t[1], reverse=True)
                if maybe and maybe[0][1] >= 0.35:
                    q_col = maybe[0][0]
                # Header-less fallback: first text-heavy column often carries Q ids/stems.
                elif maybe:
                    q_col = maybe[0][0]

            if not opt_col:
                # Prefer a text-heavy non-count, non-qid column.
                candidates = [p for p in profiles if p[0] not in {cnt_col, q_col}]
                if candidates:
                    best = sorted(candidates, key=lambda t: (t[3], -t[2]), reverse=True)[0]
                    if best[3] >= 0.25 or best[2] < 0.45:
                        opt_col = best[0]

            if not txt_col:
                candidates = [p for p in profiles if p[0] not in {cnt_col, q_col, opt_col}]
                if candidates:
                    best = sorted(candidates, key=lambda t: t[3], reverse=True)[0]
                    if best[3] >= 0.35:
                        txt_col = best[0]

            # Final positional fallback for semi-structured CSVs:
            # [Q No | Question | Option | Value] or similar.
            if not cnt_col:
                cnt_col = str(df.columns[-1])
            if not opt_col and len(df.columns) >= 2:
                # Prefer penultimate as option-like in common templates.
                penultimate = str(df.columns[-2])
                if penultimate != cnt_col:
                    opt_col = penultimate

        # Some exports omit question text header but still contain valid rows.
        # For severe header issues, at least count + option is enough; qid can be synthesized.
        if not (opt_col and cnt_col):
            return None

        cols = ([q_col] if q_col else []) + [opt_col, cnt_col] + ([txt_col] if txt_col else [])
        work = df[cols].copy()
        work = work.dropna(how="all")
        if len(work) < 3:
            return None

        if q_col:
            work[q_col] = work[q_col].ffill()
        if txt_col:
            work[txt_col] = work[txt_col].ffill()

        def _coerce_count(v: Any) -> float:
            """
            Robust count coercion for CSV exports that contain separators/suffixes
            (e.g. '1,234', '52%', '1 234', '\u20B91,234').
            """
            try:
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    return float("nan")
                if isinstance(v, (int, float)):
                    return float(v)
                s = str(v).strip()
                if not s:
                    return float("nan")
                s = s.replace(",", "").replace(" ", "")
                s = re.sub(r"[^0-9.\-]", "", s)
                if not s or s in {"-", ".", "-."}:
                    return float("nan")
                return float(s)
            except (TypeError, ValueError):
                return float("nan")

        def row_qid(val: Any) -> Optional[str]:
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return None
            s = str(val).strip()
            if not s or s.lower() == "nan":
                return None
            s_up = s.upper().replace(" ", "")
            if s_up.startswith("Q"):
                tail = s_up[1:].lstrip(":-._")
                m = re.match(r"^(\d+)", tail)
                if m:
                    return f"Q{int(m.group(1))}"
                return s_up
            try:
                return f"Q{int(float(s))}"
            except (TypeError, ValueError):
                return None

        if q_col:
            work["_qid"] = work[q_col].map(row_qid)
            # If many rows fail qid parse, synthesize sequential blocks by text transitions.
            if work["_qid"].notna().sum() == 0:
                if txt_col:
                    # New question when question text changes (after forward fill).
                    qseq = 0
                    prev = None
                    qids: list[str] = []
                    for v in work[txt_col].tolist():
                        cur = str(v).strip().lower()
                        if cur != prev:
                            qseq += 1
                            prev = cur
                        qids.append(f"Q{qseq}")
                    work["_qid"] = qids
                else:
                    # Final fallback: single synthetic question bucket.
                    work["_qid"] = "Q1"
            else:
                work = work[work["_qid"].notna()]
                if work.empty:
                    return None
        else:
            if txt_col:
                # Build ids from text-group transitions.
                qseq = 0
                prev = None
                qids: list[str] = []
                for v in work[txt_col].tolist():
                    cur = str(v).strip().lower()
                    if cur != prev:
                        qseq += 1
                        prev = cur
                    qids.append(f"Q{qseq}")
                work["_qid"] = qids
            else:
                work["_qid"] = "Q1"

        question_data: list[dict[str, Any]] = []
        all_responses: list[float] = []
        response_totals: list[float] = []

        for qid, g in work.groupby("_qid", sort=False):
            if txt_col:
                qname = str(g[txt_col].iloc[0]).strip()
            else:
                qname = str(qid).strip()
            response_counts: dict[str, float] = {}
            individual: list[float] = []
            q_codes: dict[str, int] = {}
            for _, r in g.iterrows():
                opt = str(r[opt_col]).strip()
                if not opt or opt.lower() == "nan":
                    continue
                cnt = _coerce_count(r[cnt_col])
                if pd.isna(cnt) or float(cnt) <= 0:
                    continue
                fv = float(cnt)
                response_counts[opt] = fv
                response_totals.append(fv)
                try:
                    opt_num = float(opt)
                    individual.extend([opt_num] * int(fv))
                except (TypeError, ValueError):
                    if opt not in q_codes:
                        q_codes[opt] = len(q_codes) + 1
                    individual.extend([float(q_codes[opt])] * int(fv))

            if not response_counts:
                continue
            q_counts = pd.Series(list(response_counts.values()))
            question_data.append(
                {
                    "question_id": str(qid),
                    "question_name": qname,
                    "response_totals": float(q_counts.sum()),
                    "response_counts": {str(k): float(v) for k, v in response_counts.items()},
                    "individual_responses": individual[: min(len(individual), 500000)],
                    "mean": float(q_counts.mean()) if len(q_counts) > 0 else 0.0,
                    "std": float(q_counts.std()) if len(q_counts) > 1 else 0.0,
                }
            )
            all_responses.extend([float(x) for x in individual[: min(len(individual), 500000)]])

        # Single-question parse with many option rows is still valid for question-level display.
        if len(question_data) < 1:
            return None

        def _qsort_key(q: dict[str, Any]) -> tuple[int, str]:
            m = re.match(r"Q(\d+)", str(q.get("question_id", "")))
            return (int(m.group(1)), str(q.get("question_id"))) if m else (9999, str(q.get("question_id")))

        question_data.sort(key=_qsort_key)

        logger.info(
            "Detected aggregate option-row export in %s (%s questions)",
            filename,
            len(question_data),
        )

        return {
            "filename": filename,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "numeric_columns": [cnt_col],
            "response_totals": [float(x) for x in response_totals if x is not None],
            "all_responses": [float(x) for x in all_responses if x is not None],
            "question_data": question_data,
            "dataframe_preview": df.head(10).to_dict("records") if len(df) > 0 else [],
            "column_names": df.columns.tolist(),
            "format": "aggregate_option_rows",
        }

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

