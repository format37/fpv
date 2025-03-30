#!/usr/bin/env python3

import os
import argparse
import pandas as pd

def analyze_csv(file_path):
    """
    Analyzes a single CSV file to report columns, data types, and example values.

    Args:
        file_path (str): The path to the CSV file.
    """
    print(f"\n--- Analyzing: {os.path.basename(file_path)} ---")
    try:
        # Attempt to read the CSV file using pandas
        # Use low_memory=False to potentially improve handling of mixed types,
        # though it might use more memory. Adjust if needed for very large files.
        df = pd.read_csv(file_path, low_memory=False)

        if df.empty:
            print("File is empty (no data rows).")
            # Check if there are columns (i.e., header exists)
            try:
                # Try reading just the header
                header_df = pd.read_csv(file_path, nrows=0)
                if not header_df.columns.empty:
                    print(f"Columns found: {', '.join(header_df.columns)}")
                else:
                    print("File is completely empty.")
            except Exception:
                 print("File is completely empty or unreadable.")
            return

        print(f"Shape: {df.shape}") # (rows, columns)

        # Get column names, inferred data types, and example values (from the first row)
        columns = df.columns.tolist()
        dtypes = df.dtypes
        # Get the first row as a dictionary for examples
        examples = df.iloc[0].to_dict()

        print("Columns Overview:")
        print("-" * (25 + 13 + 50 + 6)) # Adjust width based on formatting below
        print(f"{'Column Name':<25} | {'Data Type':<10} | {'Example Value'}")
        print("-" * (25 + 13 + 50 + 6))

        for col in columns:
            col_dtype = str(dtypes[col])
            example_val = examples.get(col, 'N/A') # Get example, default to N/A

            # Format example value for display (handle potential long strings)
            if pd.isna(example_val):
                example_str = "NaN" # Represent pandas/numpy NaN clearly
            else:
                example_str = str(example_val)
                if len(example_str) > 50:
                    example_str = example_str[:47] + "..." # Truncate long examples

            print(f"  {col:<25} | {col_dtype:<10} | {example_str}")
        print("-" * (25 + 13 + 50 + 6))

    except pd.errors.EmptyDataError:
        # This specific error catches files that are truly empty (0 bytes)
        print("File is completely empty.")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        # Catch other potential errors during file reading or processing
        print(f"Error analyzing file {file_path}: {e}")
        print("The file might be corrupted, have inconsistent columns, or other issues.")

def main(directory):
    """
    Scans a directory for CSV files and analyzes each one.

    Args:
        directory (str): The path to the directory containing CSV files.
    """
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' not found or is not a valid directory.")
        return

    print(f"Scanning directory: {directory} for CSV files...")
    found_csv = False
    # Sort filenames for consistent processing order
    for filename in sorted(os.listdir(directory)):
        if filename.lower().endswith('.csv'):
            found_csv = True
            file_path = os.path.join(directory, filename)
            analyze_csv(file_path) # Analyze each found CSV file

    if not found_csv:
        print(f"No CSV files found in '{directory}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze CSV files in a directory. Provides an overview of columns, data types (inferred by pandas), and example values from the first data row."
    )
    parser.add_argument(
        "directory",
        help="Path to the directory containing the CSV files to analyze (e.g., 'CSV_OUTPUT' or 'LOGS/2/')."
    )
    # Example usage: python csv_analyzer.py CSV_OUTPUT

    args = parser.parse_args()
    main(args.directory)
    print("\nAnalysis complete.") 