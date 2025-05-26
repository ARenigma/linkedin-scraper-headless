#!/usr/bin/env python3
"""
Script to add hyperlinks to an existing LinkedIn jobs Excel file
"""

import os
import pandas as pd
from openpyxl.styles import Font
import glob

def find_latest_excel_file(output_dir="output"):
    """Find the most recent Excel file in the output directory"""
    excel_files = []
    
    # Walk through the output directory and find Excel files
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith(".xlsx") and "linkedin_jobs" in file.lower() and not file.endswith("_with_hyperlinks.xlsx"):
                excel_files.append(os.path.join(root, file))
    
    if not excel_files:
        return None
    
    # Sort by modification time (newest first)
    excel_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return excel_files[0]

def add_hyperlinks_to_excel(input_file):
    """Add hyperlinks to URL columns in an existing Excel file"""
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return False
    
    # Create output filename
    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_with_hyperlinks{ext}"
    
    print(f"Processing file: {input_file}")
    print(f"Output will be saved to: {output_file}")
    
    # Read the Excel file
    df = pd.read_excel(input_file)
    
    # Create a new Excel writer
    writer = pd.ExcelWriter(output_file, engine='openpyxl')
    
    # Write data to Excel
    df.to_excel(writer, index=False, sheet_name='LinkedIn Jobs')
    
    # Get the worksheet
    worksheet = writer.sheets['LinkedIn Jobs']
    
    # Create hyperlink style
    hyperlink_font = Font(color="0563C1", underline="single")
    
    # Find URL columns
    url_columns = []
    for i, col in enumerate(df.columns):
        if 'url' in col.lower() or 'link' in col.lower():
            url_columns.append((i, col))
            print(f"Found URL column: {col} at index {i}")
    
    if not url_columns:
        print("No URL columns found in the file!")
        return False
    
    # Add hyperlinks
    rows_processed = 0
    for row_num in range(2, len(df) + 2):  # Excel is 1-indexed with header row
        for col_idx, col_name in url_columns:
            # Convert to Excel column reference (A, B, C, etc.)
            col_letter = chr(65 + col_idx)
            cell_pos = f"{col_letter}{row_num}"
            
            # Get URL value
            url_value = df.iloc[row_num-2, col_idx]
            
            # Only process valid URLs
            if isinstance(url_value, str) and url_value and (url_value.startswith('http://') or url_value.startswith('https://')):
                worksheet[cell_pos].hyperlink = url_value
                worksheet[cell_pos].font = hyperlink_font
                rows_processed += 1
    
    # Save the Excel file
    writer.close()
    
    print(f"Processed {rows_processed} hyperlinks across {len(df)} rows")
    print(f"Created Excel file with hyperlinks: {os.path.abspath(output_file)}")
    return True

def main():
    # Find the latest Excel file
    latest_file = find_latest_excel_file()
    
    if not latest_file:
        print("No LinkedIn jobs Excel files found in the output directory")
        
        # Try to look for a specific file if provided as a fallback
        test_file = os.path.join("output", "2025-05-05", "linkedin_jobs_05-05-2025_0203_COMPLETE.xlsx")
        if os.path.exists(test_file):
            latest_file = test_file
            print(f"Using fallback file: {latest_file}")
        else:
            return False
    
    # Add hyperlinks to the file
    success = add_hyperlinks_to_excel(latest_file)
    
    if success:
        # Show success message with file paths
        print("\nSuccess! Hyperlinks have been added to the Excel file.")
        print(f"Original file: {latest_file}")
        
        base, ext = os.path.splitext(latest_file)
        output_file = f"{base}_with_hyperlinks{ext}"
        print(f"New file with hyperlinks: {output_file}")
        
        # Open the file for the user
        try:
            print("\nOpening the new file...")
            os.system(f'start {output_file}')
        except:
            print("Could not automatically open the file. Please open it manually.")
    
    return success

if __name__ == "__main__":
    main() 