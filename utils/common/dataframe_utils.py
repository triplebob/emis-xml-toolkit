"""
DataFrame utilities for EMIS XML Convertor
Provides standardized DataFrame operations and formatting
"""

import pandas as pd
from typing import List, Dict, Any, Optional, Union
import numpy as np


def create_standard_dataframe(
    data: Union[List[Dict], Dict, List[List]], 
    columns: Optional[List[str]] = None,
    fill_na_value: str = ''
) -> pd.DataFrame:
    """
    Create a standardized DataFrame with consistent formatting
    
    Args:
        data: Data to convert to DataFrame
        columns: Optional column names
        fill_na_value: Value to use for NaN/None values
        
    Returns:
        pd.DataFrame: Standardized DataFrame
    """
    if isinstance(data, dict):
        # Convert single dict to list
        data = [data]
    
    df = pd.DataFrame(data, columns=columns)
    
    # Fill NaN values for cleaner display
    df = df.fillna(fill_na_value)
    
    return df


def format_dataframe_columns(
    df: pd.DataFrame,
    column_formats: Optional[Dict[str, str]] = None,
    date_columns: Optional[List[str]] = None,
    numeric_columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Apply standardized column formatting to DataFrame
    
    Args:
        df: DataFrame to format
        column_formats: Dict of column_name -> format_string
        date_columns: List of columns to format as dates
        numeric_columns: List of columns to format as numbers
        
    Returns:
        pd.DataFrame: Formatted DataFrame
    """
    df_copy = df.copy()
    
    # Format date columns
    if date_columns:
        for col in date_columns:
            if col in df_copy.columns:
                try:
                    df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
                    df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass  # Keep original format if conversion fails
    
    # Format numeric columns
    if numeric_columns:
        for col in numeric_columns:
            if col in df_copy.columns:
                try:
                    df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                except Exception:
                    pass  # Keep original format if conversion fails
    
    # Apply custom formats
    if column_formats:
        for col, fmt in column_formats.items():
            if col in df_copy.columns:
                try:
                    if 'date' in fmt.lower():
                        df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
                        df_copy[col] = df_copy[col].dt.strftime(fmt.replace('date:', ''))
                    elif 'numeric' in fmt.lower():
                        df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                        precision = int(fmt.split(':')[1]) if ':' in fmt else 2
                        df_copy[col] = df_copy[col].round(precision)
                except Exception:
                    pass  # Keep original format if conversion fails
    
    return df_copy


def validate_dataframe_data(
    df: pd.DataFrame,
    required_columns: Optional[List[str]] = None,
    min_rows: int = 0,
    max_rows: Optional[int] = None
) -> Dict[str, Any]:
    """
    Validate DataFrame structure and content
    
    Args:
        df: DataFrame to validate
        required_columns: List of columns that must be present
        min_rows: Minimum number of rows required
        max_rows: Maximum number of rows allowed
        
    Returns:
        Dict with validation results: {
            'valid': bool,
            'errors': List[str],
            'warnings': List[str],
            'stats': Dict[str, Any]
        }
    """
    errors = []
    warnings = []
    
    # Check if DataFrame is empty
    if df.empty:
        errors.append("DataFrame is empty")
    
    # Check minimum rows
    if len(df) < min_rows:
        errors.append(f"DataFrame has {len(df)} rows, minimum required: {min_rows}")
    
    # Check maximum rows
    if max_rows and len(df) > max_rows:
        warnings.append(f"DataFrame has {len(df)} rows, maximum recommended: {max_rows}")
    
    # Check required columns
    if required_columns:
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")
    
    # Check for completely empty columns
    empty_columns = [col for col in df.columns if df[col].isna().all()]
    if empty_columns:
        warnings.append(f"Columns with all empty values: {empty_columns}")
    
    # Generate statistics
    stats = {
        'rows': len(df),
        'columns': len(df.columns),
        'memory_usage': df.memory_usage(deep=True).sum(),
        'empty_cells': df.isna().sum().sum(),
        'duplicate_rows': df.duplicated().sum()
    }
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'stats': stats
    }


def apply_standard_formatting(
    df: pd.DataFrame,
    title_case_columns: Optional[List[str]] = None,
    strip_whitespace: bool = True,
    standardize_booleans: bool = True
) -> pd.DataFrame:
    """
    Apply standard text formatting to DataFrame
    
    Args:
        df: DataFrame to format
        title_case_columns: Columns to convert to title case
        strip_whitespace: Whether to strip whitespace from string columns
        standardize_booleans: Whether to standardize boolean representations
        
    Returns:
        pd.DataFrame: Formatted DataFrame
    """
    df_copy = df.copy()
    
    # Strip whitespace from string columns
    if strip_whitespace:
        for col in df_copy.columns:
            if df_copy[col].dtype == 'object':
                df_copy[col] = df_copy[col].astype(str).str.strip()
    
    # Apply title case to specified columns
    if title_case_columns:
        for col in title_case_columns:
            if col in df_copy.columns and df_copy[col].dtype == 'object':
                df_copy[col] = df_copy[col].astype(str).str.title()
    
    # Standardize boolean representations
    if standardize_booleans:
        boolean_map = {
            'true': 'Yes', 'false': 'No',
            'True': 'Yes', 'False': 'No',
            '1': 'Yes', '0': 'No',
            'yes': 'Yes', 'no': 'No',
            'y': 'Yes', 'n': 'No'
        }
        
        for col in df_copy.columns:
            if df_copy[col].dtype == 'object':
                df_copy[col] = df_copy[col].map(boolean_map).fillna(df_copy[col])
    
    return df_copy


def create_pivot_summary(
    df: pd.DataFrame,
    index_col: str,
    value_col: str,
    aggfunc: str = 'count',
    fill_value: Any = 0
) -> pd.DataFrame:
    """
    Create a pivot summary table
    
    Args:
        df: Source DataFrame
        index_col: Column to use as index
        value_col: Column to aggregate
        aggfunc: Aggregation function ('count', 'sum', 'mean', etc.)
        fill_value: Value to use for missing combinations
        
    Returns:
        pd.DataFrame: Pivot summary table
    """
    try:
        pivot_df = pd.pivot_table(
            df,
            index=index_col,
            values=value_col,
            aggfunc=aggfunc,
            fill_value=fill_value
        )
        
        # Reset index to make it a regular column
        pivot_df = pivot_df.reset_index()
        
        return pivot_df
    
    except Exception as e:
        # Return empty DataFrame if pivot fails
        return pd.DataFrame()


def split_dataframe_by_column(
    df: pd.DataFrame,
    split_column: str,
    max_rows_per_split: Optional[int] = None
) -> Dict[str, pd.DataFrame]:
    """
    Split DataFrame into multiple DataFrames based on a column value
    
    Args:
        df: DataFrame to split
        split_column: Column to split on
        max_rows_per_split: Optional maximum rows per split
        
    Returns:
        Dict[str, pd.DataFrame]: Dictionary of split_value -> DataFrame
    """
    if split_column not in df.columns:
        return {'all_data': df}
    
    splits = {}
    
    for value in df[split_column].unique():
        subset = df[df[split_column] == value].copy()
        
        if max_rows_per_split and len(subset) > max_rows_per_split:
            # Further split large subsets
            for i in range(0, len(subset), max_rows_per_split):
                chunk = subset.iloc[i:i + max_rows_per_split]
                key = f"{value}_part_{i // max_rows_per_split + 1}"
                splits[key] = chunk
        else:
            splits[str(value)] = subset
    
    return splits


def merge_dataframes_with_validation(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    join_column: str,
    how: str = 'inner',
    validate_merge: bool = True
) -> Dict[str, Any]:
    """
    Merge DataFrames with validation and reporting
    
    Args:
        left_df: Left DataFrame
        right_df: Right DataFrame
        join_column: Column to join on
        how: Type of join ('inner', 'outer', 'left', 'right')
        validate_merge: Whether to validate the merge results
        
    Returns:
        Dict containing:
        - 'result': Merged DataFrame
        - 'stats': Merge statistics
        - 'warnings': Any warnings about the merge
    """
    warnings = []
    
    # Check if join column exists in both DataFrames
    if join_column not in left_df.columns:
        warnings.append(f"Join column '{join_column}' not found in left DataFrame")
        return {'result': pd.DataFrame(), 'stats': {}, 'warnings': warnings}
    
    if join_column not in right_df.columns:
        warnings.append(f"Join column '{join_column}' not found in right DataFrame")
        return {'result': pd.DataFrame(), 'stats': {}, 'warnings': warnings}
    
    # Perform the merge
    try:
        merged_df = pd.merge(left_df, right_df, on=join_column, how=how)
    except Exception as e:
        warnings.append(f"Merge failed: {str(e)}")
        return {'result': pd.DataFrame(), 'stats': {}, 'warnings': warnings}
    
    # Calculate merge statistics
    stats = {
        'left_rows': len(left_df),
        'right_rows': len(right_df),
        'result_rows': len(merged_df),
        'join_column': join_column,
        'merge_type': how
    }
    
    # Validation warnings
    if validate_merge:
        if how == 'inner' and len(merged_df) == 0:
            warnings.append("Inner join resulted in no matching rows")
        
        if how == 'left' and len(merged_df) < len(left_df):
            warnings.append("Left join resulted in fewer rows than left DataFrame")
        
        if len(merged_df) > max(len(left_df), len(right_df)):
            warnings.append("Merge resulted in more rows than expected - possible duplicates")
    
    return {
        'result': merged_df,
        'stats': stats,
        'warnings': warnings
    }
