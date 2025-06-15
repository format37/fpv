#!/usr/bin/env python3

import pandas as pd
import sys
import os
import numpy as np

# --- Constants and Column Definitions ---
MIN_ROWS_THRESHOLD = 2 # Minimum number of rows to consider a CSV useful

# Define required columns for each message type
REQUIRED_COLS = {
    'ATT': ['timestamp', 'Roll', 'DesRoll', 'Pitch', 'DesPitch', 'Yaw', 'DesYaw'],
    'IMU': ['timestamp', 'GyrX', 'GyrY', 'GyrZ']
}

# Define columns to select and rename for optional message types
# Includes BAT from the dash app version
OPTIONAL_COLS_TO_SELECT = {
    'RCIN': {'timestamp': 'timestamp', 'C1': 'RCIN_C1_Roll', 'C2': 'RCIN_C2_Pitch'},
    'POS': {'timestamp': 'timestamp', 'Lat': 'POS_Lat', 'Lng': 'POS_Lng',
            'Alt': 'POS_Alt_AMSL', 'RelHomeAlt': 'POS_RelHomeAlt_AGL',
            'RelOriginAlt': 'POS_RelOriginAlt_AGL'},
    'GPS': {'timestamp': 'timestamp', 'Alt': 'GPS_Alt_AMSL', 'Spd': 'GPS_Spd_Ground'},
    'ARSP': {'timestamp': 'timestamp', 'Airspeed': 'ARSP_Airspeed'},
    'XKF5': {'timestamp': 'timestamp', 'HAGL': 'XKF5_HAGL'},
    'RFND': {'timestamp': 'timestamp', 'Dist': 'RFND_Dist_AGL'},
    'BARO': {'timestamp': 'timestamp', 'Alt': 'BARO_Alt_Raw'},
    'TERR': {'timestamp': 'timestamp', 'CHeight': 'TERR_CHeight_AGL'},
    'BAT': {'timestamp': 'timestamp', 'Volt': 'BAT_Volt', 'Curr': 'BAT_Curr'},
    'PIDP': {'timestamp': 'timestamp', 'Act': 'PIDP_Act', 'Tar': 'PIDP_Tar', 'P': 'PIDP_P', 'I': 'PIDP_I', 'D': 'PIDP_D', 'Err': 'PIDP_Err'},
    'PIDR': {'timestamp': 'timestamp', 'Act': 'PIDR_Act', 'Tar': 'PIDR_Tar', 'P': 'PIDR_P', 'I': 'PIDR_I', 'D': 'PIDR_D', 'Err': 'PIDR_Err'},
    'MODE': {'timestamp': 'timestamp', 'ModeNum': 'ModeNum'},
    'MSG': {'timestamp': 'timestamp', 'Message': 'MSG_Message', 'Severity': 'MSG_Severity'},
    'OF': {
        'timestamp': 'timestamp',
        'flowX': 'OF_flowX',
        'flowY': 'OF_flowY',
        'bodyX': 'OF_bodyX',
        'bodyY': 'OF_bodyY',
        'Qual': 'OF_Qual'
    },
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
def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on Earth in meters."""
    # Handle potential NaN inputs gracefully
    if np.isnan(lat1) or np.isnan(lon1) or np.isnan(lat2) or np.isnan(lon2):
        return np.nan
    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    # Earth's radius in meters (mean radius)
    R = 6371000
    return c * R

def load_and_merge_data(csv_filepaths):
    """
    Loads required and optional flight data CSVs, calculates distance from home
    if POS data is available, merges them based on timestamp, and returns a
    single DataFrame along with a list of loaded optional message types.
    """
    dataframes = {}
    loaded_optional_types = []

    print("Loading and preparing data...")

    # --- Load Required Data ---
    for msg_type in REQUIRED_COLS.keys():
        filepath = csv_filepaths.get(msg_type)
        if not filepath:
            print(f"Error: Path for required data {msg_type} not provided.")
            return None, []
        df = load_and_prepare_csv(filepath, msg_type, required_cols=REQUIRED_COLS[msg_type])
        if df is not None:
            # Ensure only required columns are kept initially
            dataframes[msg_type] = df[REQUIRED_COLS[msg_type]].copy()
        else:
            print(f"Error: Failed to load required data {msg_type}. Cannot proceed.")
            return None, []


    # --- Load Optional Data ---
    for msg_type, cols_select in OPTIONAL_COLS_TO_SELECT.items():
        filepath = csv_filepaths.get(msg_type)
        if filepath:
            df = load_and_prepare_csv(filepath, msg_type, optional_cols_select=cols_select)
            if df is not None and not df.empty:
                # Check if there are columns other than just 'timestamp'
                if len(df.columns) > 1:
                    dataframes[msg_type] = df
                    loaded_optional_types.append(msg_type)
                else:
                    print(f"Warning: No data columns loaded for optional type {msg_type} from {filepath}. Skipping.")


    # --- Calculate Distance from Home (New Section) ---
    home_lat, home_lng = None, None
    if 'POS' in dataframes and 'POS_Lat' in dataframes['POS'].columns and 'POS_Lng' in dataframes['POS'].columns:
        pos_df = dataframes['POS']
        # Find the first row with valid Lat/Lng
        first_valid_pos = pos_df.dropna(subset=['POS_Lat', 'POS_Lng']).iloc[0] if not pos_df.dropna(subset=['POS_Lat', 'POS_Lng']).empty else None

        if first_valid_pos is not None:
            home_lat = first_valid_pos['POS_Lat']
            home_lng = first_valid_pos['POS_Lng']
            print(f"Home position set from first valid POS: Lat={home_lat:.6f}, Lng={home_lng:.6f}")

            # Apply haversine function row-wise
            pos_df['Distance_From_Home'] = pos_df.apply(
                lambda row: haversine(home_lat, home_lng, row['POS_Lat'], row['POS_Lng']),
                axis=1
            )
            # Ensure the new column is added back to the dictionary
            dataframes['POS'] = pos_df
            # Add 'Distance_From_Home' to the list of columns to keep if POS is loaded
            # This isn't strictly necessary with the current merge logic but good practice
            if 'POS' in OPTIONAL_COLS_TO_SELECT:
                 # We modify the dataframe in place, no need to change OPTIONAL_COLS_TO_SELECT
                 pass
        else:
            print("Warning: POS data loaded, but no valid Lat/Lng found to set home position.")
    elif 'POS' in loaded_optional_types:
         print("Warning: POS data loaded, but 'POS_Lat' or 'POS_Lng' columns are missing. Cannot calculate distance from home.")


    # --- Print Loaded Types ---
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
        return None, loaded_optional_types # Return loaded types even on failure

    df_merged = dataframes['ATT'] # Start with ATT
    # Consider making tolerance configurable or slightly larger if needed
    tolerance = pd.Timedelta('50ms')

    # Merge IMU (Required)
    if 'IMU' in dataframes:
         # Use suffixes to avoid column name collisions if IMU had overlapping names (though unlikely here)
         df_merged = pd.merge_asof(df_merged, dataframes['IMU'], on='timestamp', direction='nearest', tolerance=tolerance, suffixes=('', '_IMU'))
    else:
        print("Error: IMU data missing, cannot proceed with merge.")
        return None, loaded_optional_types # Return loaded types

    # Merge Optional Data
    for msg_type in loaded_optional_types:
        if msg_type in dataframes: # Double check df exists
            print(f"Merging {msg_type}...")
            # Use suffixes to prevent column name collisions, especially if multiple sources provide e.g., 'Alt'
            df_merged = pd.merge_asof(df_merged, dataframes[msg_type], on='timestamp', direction='nearest', tolerance=tolerance, suffixes=('', f'_{msg_type}'))

    print("Finished merging.")


    # --- Final Processing ---
    # Define essential columns for dropping rows if they are missing AFTER merge
    # Note: Column names might have suffixes if there were overlaps, adjust if necessary
    # For now, assume original names are preserved for ATT, IMU, RCIN essentials
    essential_dropna_subset = REQUIRED_COLS['ATT'] + [col for col in REQUIRED_COLS['IMU'] if col != 'timestamp']
    # Add RCIN if it was loaded and the specific columns exist after merge
    if 'RCIN' in loaded_optional_types and 'RCIN_C1_Roll' in df_merged.columns and 'RCIN_C2_Pitch' in df_merged.columns:
         essential_dropna_subset.extend(['RCIN_C1_Roll', 'RCIN_C2_Pitch'])

    original_len = len(dataframes['ATT']) # Or use df_merged length before drop
    pre_drop_len = len(df_merged)
    # Drop rows where ANY of the essential columns are NaN
    df_merged.dropna(subset=essential_dropna_subset, how='any', inplace=True)
    post_drop_len = len(df_merged)

    print(f"Original ATT points: {original_len}")
    print(f"Merged dataframe size before essential dropna: {pre_drop_len}")
    print(f"Merged dataframe size after essential dropna: {post_drop_len}")

    # Add a check for significant data loss during merge/drop
    if pre_drop_len > 0 and post_drop_len < pre_drop_len * 0.8: # Check if more than 20% lost in dropna
        print(f"Warning: Significant data loss ({pre_drop_len - post_drop_len} rows) during essential dropna. Check data quality.")
    elif post_drop_len < original_len * 0.8: # Check if significant loss compared to original ATT
         print(f"Warning: Significant data loss compared to original ATT points. Timestamps might be misaligned or merge tolerance too small.")


    if df_merged.empty:
        print("Error: No valid merged data remaining after dropping essential NaNs.")
        return None, loaded_optional_types

    print(f"Proceeding with {len(df_merged)} data points.")
    # Set index AFTER merge and dropna
    df_merged.set_index('timestamp', inplace=True)
    df_merged.sort_index(inplace=True) # Ensure time order

    return df_merged, loaded_optional_types 