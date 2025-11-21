"""
Centralized export utilities for EMIS XML Convertor
Provides standardized Excel export functionality across the application
"""

import io
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple
import pandas as pd
from pathlib import Path
import re


def sanitize_excel_value(value: Any) -> Any:
    """
    Sanitize a value to prevent Excel formula injection
    
    Args:
        value: The value to sanitize
        
    Returns:
        Any: Sanitized value safe for Excel export
    """
    if not isinstance(value, str):
        return value
    
    # Check if value starts with formula characters
    if value and len(value) > 0 and value[0] in ('=', '+', '-', '@'):
        # Prefix with single quote to force text interpretation
        return f"'{value}"
    
    return value


def sanitize_dataframe_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize all string columns in a DataFrame for Excel export
    
    Args:
        df: DataFrame to sanitize
        
    Returns:
        pd.DataFrame: Sanitized DataFrame safe for Excel export
    """
    df_copy = df.copy()
    
    # Apply sanitization to all object (string) columns
    for column in df_copy.columns:
        if df_copy[column].dtype == 'object':
            df_copy[column] = df_copy[column].apply(sanitize_excel_value)
    
    return df_copy


def create_excel_workbook() -> io.BytesIO:
    """
    Create a new Excel workbook in memory
    
    Returns:
        io.BytesIO: Empty workbook buffer ready for writing
    """
    return io.BytesIO()


def add_worksheet_with_data(
    writer: pd.ExcelWriter, 
    dataframe: pd.DataFrame, 
    sheet_name: str,
    index: bool = False,
    max_sheet_name_length: int = 31
) -> None:
    """
    Add a worksheet to an Excel writer with standardized formatting
    
    Args:
        writer: Pandas ExcelWriter instance
        dataframe: DataFrame to write
        sheet_name: Name for the worksheet
        index: Whether to include DataFrame index
        max_sheet_name_length: Maximum length for sheet names (Excel limit)
    """
    # Ensure sheet name doesn't exceed Excel limits
    clean_sheet_name = sheet_name[:max_sheet_name_length]
    
    # Remove invalid characters for Excel sheet names
    invalid_chars = ['[', ']', '*', '?', ':', '/', '\\']
    for char in invalid_chars:
        clean_sheet_name = clean_sheet_name.replace(char, '_')
    
    # Write the data
    dataframe.to_excel(writer, sheet_name=clean_sheet_name, index=index)


def generate_export_filename(
    base_name: str,
    search_name: Optional[str] = None,
    timestamp: bool = True,
    extension: str = "xlsx"
) -> str:
    """
    Generate standardized export filename
    
    Args:
        base_name: Base name for the file
        search_name: Optional search name to include
        timestamp: Whether to include timestamp
        extension: File extension (without dot)
    
    Returns:
        str: Formatted filename
    """
    parts = [base_name]
    
    if search_name:
        # Clean search name for filename
        clean_search_name = "".join(c for c in search_name if c.isalnum() or c in (' ', '-', '_')).strip()
        clean_search_name = clean_search_name.replace(' ', '_')
        if clean_search_name:
            parts.append(clean_search_name)
    
    if timestamp:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts.append(timestamp_str)
    
    filename = "_".join(parts)
    return f"{filename}.{extension}"


def validate_export_data(data: Union[pd.DataFrame, List[Dict], Dict]) -> bool:
    """
    Validate data before export
    
    Args:
        data: Data to validate (DataFrame, list of dicts, or dict)
        
    Returns:
        bool: True if data is valid for export
    """
    if data is None:
        return False
    
    if isinstance(data, pd.DataFrame):
        return not data.empty
    
    if isinstance(data, list):
        return len(data) > 0
    
    if isinstance(data, dict):
        return len(data) > 0
    
    return False


def save_workbook_to_bytes(writer: pd.ExcelWriter) -> bytes:
    """
    Finalize and save workbook to bytes
    
    Args:
        writer: ExcelWriter instance
        
    Returns:
        bytes: Excel file content as bytes
    """
    writer.close()
    if hasattr(writer, 'book') and hasattr(writer.book, 'save'):
        # For older pandas versions
        output = io.BytesIO()
        writer.book.save(output)
        return output.getvalue()
    else:
        # For newer pandas versions with context manager
        return writer.handles.handle.getvalue()




def standardize_dataframe_for_export(
    data: Union[List[Dict], Dict], 
    columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Convert various data formats to standardized DataFrame for export
    
    Args:
        data: Data to convert (list of dicts or single dict)
        columns: Optional column order specification
        
    Returns:
        pd.DataFrame: Standardized DataFrame ready for export
    """
    if isinstance(data, dict):
        # Convert single dict to list for consistent handling
        data = [data]
    
    df = pd.DataFrame(data)
    
    if columns and not df.empty:
        # Reorder columns if specified
        available_columns = [col for col in columns if col in df.columns]
        if available_columns:
            df = df[available_columns]
    
    # Fill NaN values with empty strings for cleaner exports
    df = df.fillna('')
    
    return df


def create_summary_sheet(
    title: str,
    description: str,
    metadata: Dict[str, Any],
    additional_info: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Create a standardized summary/overview sheet
    
    Args:
        title: Title for the export
        description: Description of the export content
        metadata: Metadata about the export (timestamps, counts, etc.)
        additional_info: Optional additional information
        
    Returns:
        pd.DataFrame: Summary sheet data
    """
    summary_data = [
        ['Export Title', title],
        ['Description', description],
        ['Generated On', datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ['', '']  # Spacer
    ]
    
    # Add metadata
    for key, value in metadata.items():
        summary_data.append([key, str(value)])
    
    if additional_info:
        summary_data.append(['', ''])  # Spacer
        summary_data.append(['Additional Information', ''])
        for key, value in additional_info.items():
            summary_data.append([f'  {key}', str(value)])
    
    return pd.DataFrame(summary_data, columns=['Property', 'Value'])


def apply_excel_formatting(
    writer: pd.ExcelWriter,
    sheet_name: str,
    header_format: Optional[Dict] = None,
    column_widths: Optional[Dict[str, int]] = None
) -> None:
    """
    Apply standardized formatting to Excel worksheets
    
    Args:
        writer: ExcelWriter instance
        sheet_name: Name of the sheet to format
        header_format: Optional header formatting options
        column_widths: Optional column width specifications
    """
    try:
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        # Default header formatting
        if header_format is None:
            header_format = {
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            }
        
        # Apply header formatting
        header_fmt = workbook.add_format(header_format)
        
        # Get the last row and column with data
        max_row = worksheet.max_row
        max_col = worksheet.max_column
        
        if max_row > 0 and max_col > 0:
            # Format header row
            for col in range(1, max_col + 1):
                cell = worksheet.cell(row=1, column=col)
                cell.font = cell.font.copy(bold=True)
        
        # Apply column widths
        if column_widths:
            for col_letter, width in column_widths.items():
                worksheet.column_dimensions[col_letter].width = width
        else:
            # Auto-adjust column widths
            for col in range(1, max_col + 1):
                column_letter = worksheet.cell(row=1, column=col).column_letter
                worksheet.column_dimensions[column_letter].width = 15
    
    except Exception as e:
        # Formatting is optional - don't fail the export if it doesn't work
        print(f"Warning: Could not apply Excel formatting: {e}")



class ExcelExportBuilder:
    """
    Builder class for creating complex Excel exports with multiple sheets
    """
    
    def __init__(self, base_filename: str):
        self.base_filename = base_filename
        self.output = io.BytesIO()
        self.writer = None
        self.sheets_added = 0
    
    def __enter__(self):
        self.writer = pd.ExcelWriter(self.output, engine='openpyxl')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.writer:
            self.writer.close()
    
    def add_summary_sheet(self, title: str, description: str, metadata: Dict[str, Any]) -> 'ExcelExportBuilder':
        """Add a summary sheet to the export"""
        summary_df = create_summary_sheet(title, description, metadata)
        add_worksheet_with_data(self.writer, summary_df, 'Summary')
        self.sheets_added += 1
        return self
    
    def add_data_sheet(self, data: pd.DataFrame, sheet_name: str) -> 'ExcelExportBuilder':
        """Add a data sheet to the export"""
        add_worksheet_with_data(self.writer, data, sheet_name)
        self.sheets_added += 1
        return self
    
    def get_content(self) -> bytes:
        """Get the final Excel content as bytes"""
        self.writer.close()
        return self.output.getvalue()
    
    def get_filename(self) -> str:
        """Get the generated filename"""
        return generate_export_filename(self.base_filename)
