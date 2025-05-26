#!/usr/bin/env python3
"""
Test script to generate Excel file with hyperlinks
"""

import pandas as pd
from openpyxl.styles import Font
import os

def create_excel_with_hyperlinks(output_file='test_hyperlinks.xlsx'):
    """Create a test Excel file with hyperlinks"""
    
    # Sample data
    data = [
        {
            'Company LinkedIn URL': 'https://www.linkedin.com/company/test-company1',
            'Job URL': 'https://www.linkedin.com/jobs/view/123456789',
            'Hiring Manager URL': 'https://www.linkedin.com/in/test-manager1',
            'Title': 'Python Developer',
            'Company': 'Test Company 1'
        },
        {
            'Company LinkedIn URL': 'https://www.linkedin.com/company/test-company2',
            'Job URL': 'https://www.linkedin.com/jobs/view/987654321',
            'Hiring Manager URL': 'https://www.linkedin.com/in/test-manager2',
            'Title': 'Data Scientist',
            'Company': 'Test Company 2'
        }
    ]
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel writer
    writer = pd.ExcelWriter(output_file, engine='openpyxl')
    
    # Write data to Excel
    df.to_excel(writer, index=False, sheet_name='Jobs')
    
    # Get the worksheet
    worksheet = writer.sheets['Jobs']
    
    # Create hyperlink style
    hyperlink_font = Font(color="0563C1", underline="single")
    
    # Find URL columns
    url_columns = []
    for i, col in enumerate(df.columns):
        if 'url' in col.lower() or 'link' in col.lower():
            url_columns.append((i, col))
            print(f"Found URL column: {col} at index {i}")
    
    # Add hyperlinks
    for row_num in range(2, len(df) + 2):  # Excel is 1-indexed with header row
        for col_idx, col_name in url_columns:
            # Convert to Excel column reference (A, B, C, etc.)
            col_letter = chr(65 + col_idx)
            cell_pos = f"{col_letter}{row_num}"
            
            # Get URL value
            url_value = df.iloc[row_num-2, col_idx]
            
            print(f"Setting hyperlink at {cell_pos}: {url_value}")
            
            # Set hyperlink and formatting
            worksheet[cell_pos].hyperlink = url_value
            worksheet[cell_pos].font = hyperlink_font
    
    # Save the Excel file
    writer.close()
    
    print(f"Created Excel file with hyperlinks: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    create_excel_with_hyperlinks() 