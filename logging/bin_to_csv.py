#!/usr/bin/env python3

import os
import csv
import argparse
from pymavlink import mavutil
from datetime import datetime

def list_message_types(bin_file_path):
    """
    List all message types found in a binary MAVLink log file
    
    Args:
        bin_file_path (str): Path to the binary log file
    
    Returns:
        dict: Dictionary with message types as keys and counts as values
    """
    mlog = mavutil.mavlink_connection(bin_file_path)
    msg_types = {}
    
    # Iterate through all messages
    while True:
        msg = mlog.recv_match(blocking=False)
        if msg is None:
            break
        
        msg_type = msg.get_type()
        if msg_type in msg_types:
            msg_types[msg_type] += 1
        else:
            msg_types[msg_type] = 1
    
    return msg_types

def extract_messages(bin_file_path, output_csv_path, message_type=None):
    """
    Extract messages of specified type from a binary MAVLink log file and save to CSV
    
    Args:
        bin_file_path (str): Path to the binary log file
        output_csv_path (str): Path to save the CSV output
        message_type (str): Type of message to extract (None for optical flow)
    """
    # Open the binary log file
    mlog = mavutil.mavlink_connection(bin_file_path)
    
    # Check if file contains the requested message types
    message_types = list_message_types(bin_file_path)
    print(f"Message types found in {bin_file_path}:")
    for msg_type, count in sorted(message_types.items()):
        print(f"  {msg_type}: {count} messages")
    
    # If message_type is specified, use that
    if message_type:
        target_types = [message_type] if message_type in message_types else []
        if not target_types:
            print(f"Warning: Message type '{message_type}' not found in {bin_file_path}")
            return
    else:
        # Look for optical flow message types as default
        target_types = ['OF'] if 'OF' in message_types else []
        
        # Also check for other possible optical flow message types
        additional_types = [msg_type for msg_type in message_types.keys() 
                            if ('FLOW' in msg_type or 'OPTICAL' in msg_type) and msg_type != 'OF']
        
        if additional_types:
            target_types.extend(additional_types)
        
        if not target_types:
            print(f"Warning: No optical flow messages found in {bin_file_path}")
            return
    
    print(f"Found target message types: {target_types}")
    
    # Reset the file pointer
    mlog = mavutil.mavlink_connection(bin_file_path)
    
    # Prepare CSV file
    with open(output_csv_path, 'w', newline='') as csvfile:
        # First, get a sample message to determine all possible fieldnames
        all_fieldnames = set(['timestamp', 'message_type'])  # Always include these
        
        # Get a sample of each message type to collect all possible fields
        for target_type in target_types:
            mlog_sample = mavutil.mavlink_connection(bin_file_path)
            sample_msg = mlog_sample.recv_match(type=target_type)
            if sample_msg and hasattr(sample_msg, '_fieldnames'):
                all_fieldnames.update(sample_msg._fieldnames)
        
        # Convert to list and sort for consistent output
        fieldnames = sorted(list(all_fieldnames))
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Counter for extracted messages
        extracted_count = 0
        
        # Iterate through all messages
        for target_type in target_types:
            # Reset the file pointer
            mlog = mavutil.mavlink_connection(bin_file_path)
            
            while True:
                msg = mlog.recv_match(type=target_type)
                if msg is None:
                    break
                
                # Create a dictionary for the row data
                row_data = {
                    'timestamp': datetime.fromtimestamp(msg._timestamp).strftime('%Y-%m-%d %H:%M:%S.%f'),
                    'message_type': target_type,
                }
                
                # Add all fields from the message using _fieldnames and _elements
                if hasattr(msg, '_fieldnames') and hasattr(msg, '_elements'):
                    for fieldname, element in zip(msg._fieldnames, msg._elements):
                        row_data[fieldname] = element
                
                # Write message data to CSV
                writer.writerow(row_data)
                extracted_count += 1
        
        print(f"Extracted {extracted_count} messages from {bin_file_path}")
    
    if extracted_count > 0:
        print(f"Data extracted from {bin_file_path} and saved to {output_csv_path}")
    else:
        print(f"Warning: No data could be extracted from {bin_file_path}")

def process_bin_files(file=None, message=None, logs_dir="LOGS"):
    """
    Process specified .BIN file or all files in the directory
    
    Args:
        file (str): Path to a specific .BIN file (optional)
        message (str): Message type to extract (optional)
        logs_dir (str): Directory containing .BIN files (if file not specified)
    """
    # Create output directory for CSV files
    csv_dir = "CSV_OUTPUT"
    os.makedirs(csv_dir, exist_ok=True)
    
    if file:
        # Process a single file
        if not os.path.exists(file):
            print(f"Error: File '{file}' not found")
            return
            
        filename = os.path.basename(file)
        if message:
            csv_filename = f"{os.path.splitext(filename)[0]}.{message}.csv"
        else:
            csv_filename = f"{os.path.splitext(filename)[0]}.csv"
            
        csv_path = os.path.join(csv_dir, csv_filename)
        
        print(f"\nProcessing {file}...")
        try:
            extract_messages(file, csv_path, message)
        except Exception as e:
            print(f"Error processing {file}: {str(e)}")
    else:
        # Process all files in the directory
        if not os.path.exists(logs_dir):
            print(f"Error: Directory '{logs_dir}' not found")
            return
            
        # Process each .BIN file
        for filename in os.listdir(logs_dir):
            if filename.upper().endswith('.BIN'):
                bin_path = os.path.join(logs_dir, filename)
                
                if message:
                    csv_filename = f"{os.path.splitext(filename)[0]}.{message}.csv"
                else:
                    csv_filename = f"{os.path.splitext(filename)[0]}.csv"
                    
                csv_path = os.path.join(csv_dir, csv_filename)
                
                print(f"\nProcessing {bin_path}...")
                try:
                    extract_messages(bin_path, csv_path, message)
                except Exception as e:
                    print(f"Error processing {bin_path}: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract message data from MAVLink binary log files")
    parser.add_argument("--file", help="Path to a specific .BIN file to process")
    parser.add_argument("--message", help="Message type to extract (e.g., 'OF', 'ATTITUDE')")
    parser.add_argument("--logs_dir", default="LOGS", help="Directory containing .BIN files (default: LOGS)")
    
    args = parser.parse_args()
    
    process_bin_files(file=args.file, message=args.message, logs_dir=args.logs_dir)
    print("\nProcessing complete!")
