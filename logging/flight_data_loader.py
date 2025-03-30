#!/usr/bin/env python3

import pandas as pd
import sys
import os

# --- Constants and Column Definitions ---
MIN_ROWS_THRESHOLD = 10 # Minimum number of rows to consider a CSV useful

# Define required columns for each message type
REQUIRED_COLS = {
    'ATT': ['timestamp', 'Roll', 'DesRoll', 'Pitch', 'DesPitch', 'Yaw', 'DesYaw'],
    'IMU': ['timestamp', 'GyrX', 'GyrY', 'GyrZ']
}

# Define columns to select and rename for optional message types
# Includes BAT from the dash app version
OPTIONAL_COLS_TO_SELECT = {
    'RCIN': {'timestamp': 'timestamp', 'C1': 'RCIN_C1_Roll', 'C2': 'RCIN_C2_Pitch'},
    'POS': {'timestamp': 'timestamp', 'Alt': 'POS_Alt_AMSL', 'RelHomeAlt': 'POS_RelHomeAlt_AGL', 'RelOriginAlt': 'POS_RelOriginAlt_AGL'},
    'GPS': {'timestamp': 'timestamp', 'Alt': 'GPS_Alt_AMSL', 'Spd': 'GPS_Spd_Ground'},
    'ARSP': {'timestamp': 'timestamp', 'Airspeed': 'ARSP_Airspeed'},
    'XKF5': {'timestamp': 'timestamp', 'HAGL': 'XKF5_HAGL'},
    'RFND': {'timestamp': 'timestamp', 'Dist': 'RFND_Dist_AGL'},
    'BARO': {'timestamp': 'timestamp', 'Alt': 'BARO_Alt_Raw'},
    'TERR': {'timestamp': 'timestamp', 'CHeight': 'TERR_CHeight_AGL'},
    'BAT': {'timestamp': 'timestamp', 'Volt': 'BAT_Volt', 'Curr': 'BAT_Curr'}
}

# --- Helper Function for Loading Data ---
def load_and_prepare_csv(filepath, msg_type, required_cols=None, optional_cols_select=None):
    """Loads a single CSV, prepares timestamp, checks minimum rows and required columns."""
    print(f"Reading {msg_type} data from: {filepath}")
    try:
        df = pd.read_csv(filepath)
        if df.empty:
            print(f"Warning: CSV file is empty: {filepath}. Skipping.")
            return None

        # Timestamp handling
        if 'timestamp' not in df.columns:
            print(f"Warning: Missing 'timestamp' column in {filepath}. Skipping.")
            return None
        # Try multiple formats for timestamp parsing
        try:
            # Try standard format first
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        except (ValueError, TypeError):
            try:
                # Try with explicit format if the first fails (e.g., from different logging versions)
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', errors='coerce')
            except Exception as e_fmt:
                 print(f"Warning: Could not parse timestamp in {filepath} with standard or ISO8601 format: {e_fmt}. Attempting numeric conversion.")
                 # Final attempt: Treat as numeric (e.g., microseconds since epoch) if conversion fails
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='us', errors='coerce') # Common ArduPilot unit

        df.dropna(subset=['timestamp'], inplace=True)
        df.sort_values('timestamp', inplace=True)

        if len(df) < MIN_ROWS_THRESHOLD:
            print(f"Warning: Found only {len(df)} {msg_type} data points (minimum {MIN_ROWS_THRESHOLD} required). Skipping.")
            return None

        # Check required columns if specified
        if required_cols:
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                print(f"Error: Missing required columns in {msg_type} CSV ({filepath}): {', '.join(missing)}")
                sys.exit(1) # Exit for required files

        # Select and rename optional columns if specified
        if optional_cols_select:
            cols_to_use = list(optional_cols_select.keys())
            present_cols = [col for col in cols_to_use if col in df.columns]
            missing_optional = [col for col in cols_to_use if col not in df.columns]

            if missing_optional:
                print(f"Warning: Missing expected columns in {msg_type} CSV ({filepath}): {', '.join(missing_optional)}. Skipping these columns.")

            if not present_cols:
                 print(f"Warning: No usable data columns found in {msg_type} ({filepath}) after checking. Skipping file.")
                 return None

            # Ensure timestamp is always included if present in the original file
            if 'timestamp' in df.columns and 'timestamp' not in present_cols:
                present_cols.insert(0, 'timestamp') # Add timestamp if missing from selection but present in file

            if 'timestamp' not in present_cols:
                 print(f"Warning: Cannot proceed with {msg_type} ({filepath}) without timestamp. Skipping file.")
                 return None

            # Create rename mapping only for present columns
            rename_map = {k: v for k, v in optional_cols_select.items() if k in present_cols}
            df = df[present_cols].rename(columns=rename_map)


        print(f"Successfully loaded and prepared {len(df)} {msg_type} data points.")
        return df

    except FileNotFoundError:
        if required_cols:
            print(f"Error: Required file not found at {filepath}")
            sys.exit(1)
        else:
            print(f"Info: Optional file not found at {filepath}. Skipping.")
            return None
    except pd.errors.EmptyDataError:
        print(f"Warning: CSV file is empty: {filepath}. Skipping.")
        return None
    except Exception as e:
        if required_cols:
            print(f"An unexpected error occurred while loading required file {filepath}: {e}")
            sys.exit(1)
        else:
            print(f"Warning: An error occurred while loading optional file {filepath}: {e}. Skipping.")
            return None


# --- Data Analysis Function ---
def load_and_merge_data(csv_filepaths):
    """
    Loads, prepares, and merges flight data CSVs based on provided filepaths.
    Returns the merged DataFrame and a list of successfully loaded optional types.
    """
    dataframes = {}
    loaded_optional_types = [] # Keep track of successfully loaded optional data

    print("Loading and preparing data...")

    # --- Load Required Data ---
    for msg_type in REQUIRED_COLS.keys():
        filepath = csv_filepaths.get(msg_type)
        if not filepath:
             print(f"Error: Path for required data {msg_type} not provided.")
             sys.exit(1)
        df = load_and_prepare_csv(filepath, msg_type, required_cols=REQUIRED_COLS[msg_type])
        if df is not None:
            # Select only the required columns for required types before merge
            dataframes[msg_type] = df[REQUIRED_COLS[msg_type]].copy()
        else:
             print(f"Error: Failed to load required data {msg_type}. Exiting.") # Should not happen
             sys.exit(1)


    # --- Load Optional Data ---
    for msg_type, cols_select in OPTIONAL_COLS_TO_SELECT.items():
        filepath = csv_filepaths.get(msg_type)
        if filepath:
            df = load_and_prepare_csv(filepath, msg_type, optional_cols_select=cols_select)
            if df is not None and not df.empty:
                # Check if we actually got any data columns besides timestamp
                if len(df.columns) > 1:
                    dataframes[msg_type] = df
                    loaded_optional_types.append(msg_type)
                else:
                    print(f"Warning: No data columns loaded for optional type {msg_type} from {filepath}. Skipping.")

    print("-" * 20)
    print(f"Loaded required types: {', '.join(REQUIRED_COLS.keys())}")
    if loaded_optional_types:
        print(f"Loaded optional types: {', '.join(loaded_optional_types)}")
    else:
        print("No optional data types were successfully loaded.")
    print("-" * 20)

    # --- Merge DataFrames ---
    print("Merging dataframes based on timestamp...")
    if 'ATT' not in dataframes:
        print("Error: ATT data missing, cannot proceed with merge.")
        return None, [] # Return None if essential data is missing

    df_merged = dataframes['ATT'] # Start with ATT
    tolerance = pd.Timedelta('50ms') # Keep existing tolerance

    # Merge IMU (Required)
    if 'IMU' in dataframes:
         df_merged = pd.merge_asof(df_merged, dataframes['IMU'], on='timestamp', direction='nearest', tolerance=tolerance)
    else:
        print("Error: IMU data missing, cannot proceed with merge.")
        return None, [] # Return None if essential data is missing

    # Merge Optional Data
    for msg_type in loaded_optional_types:
        if msg_type in dataframes: # Double check df exists
            print(f"Merging {msg_type}...")
            df_merged = pd.merge_asof(df_merged, dataframes[msg_type], on='timestamp', direction='nearest', tolerance=tolerance)

    print("Finished merging.")

    # --- Drop Rows with Missing *Essential* Data ---
    # Define essential columns for dropping rows if they are missing
    essential_dropna_subset = REQUIRED_COLS['ATT'] + [col for col in REQUIRED_COLS['IMU'] if col != 'timestamp']
    # Add RCIN if it was loaded and the specific columns exist after merge
    if 'RCIN' in loaded_optional_types and 'RCIN_C1_Roll' in df_merged.columns and 'RCIN_C2_Pitch' in df_merged.columns:
         essential_dropna_subset.extend(['RCIN_C1_Roll', 'RCIN_C2_Pitch'])

    original_len = len(dataframes['ATT'])
    pre_drop_len = len(df_merged)
    df_merged.dropna(subset=essential_dropna_subset, how='any', inplace=True) # Use how='any'
    post_drop_len = len(df_merged)

    print(f"Original ATT points: {original_len}")
    print(f"Merged dataframe size before essential dropna: {pre_drop_len}")
    print(f"Merged dataframe size after essential dropna: {post_drop_len}")

    if post_drop_len < original_len * 0.8:
         print("Warning: Significant data loss during merge or essential dropna. Timestamps might be misaligned or tolerance too small.")

    if df_merged.empty:
        print("Error: No valid merged data remaining after dropping essential NaNs.")
        return None, loaded_optional_types # Return None but keep loaded types for potential notes

    print(f"Proceeding with {len(df_merged)} data points.")
    # Ensure timestamp is the index for easier time-based slicing later
    # Do this *after* merging and cleaning
    df_merged.set_index('timestamp', inplace=True)
    df_merged.sort_index(inplace=True)

    return df_merged, loaded_optional_types 