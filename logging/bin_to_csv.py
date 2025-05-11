#!/usr/bin/env python3

import os
import csv
import argparse
import threading
from pymavlink import mavutil
from datetime import datetime
import time # Import time for potential future optimizations/debugging

def list_message_types(bin_file_path):
    """
    List all message types found in a binary MAVLink log file
    
    Args:
        bin_file_path (str): Path to the binary log file
    
    Returns:
        dict: Dictionary with message types as keys and counts as values
    """
    msg_types = {}
    mlog = None
    try:
        mlog = mavutil.mavlink_connection(bin_file_path)
        while True:
            # Use blocking=False and add a small sleep to avoid pegging CPU if file is large
            # Or just rely on default blocking=True which might be simpler/more robust
            msg = mlog.recv_match(blocking=True) # Use blocking=True (default)
            if msg is None:
                break # End of file

            msg_type = msg.get_type()
            if msg_type not in ['FMT', 'FMTU', 'MULT', 'PARM', 'EV', 'XKF0']: # Exclude format/metadata types if desired
                 if msg_type in msg_types:
                     msg_types[msg_type] += 1
                 else:
                     msg_types[msg_type] = 1
    except Exception as e:
        print(f"Error listing message types in {bin_file_path}: {e}")
    # mlog doesn't explicitly need closing AFAIK
    return msg_types

# Rename and simplify the extraction function for a single message type
def extract_single_message_type(bin_file_path, output_csv_path, message_type):
    """
    Extract messages of a specific type from a binary MAVLink log file and save to CSV.

    Args:
        bin_file_path (str): Path to the binary log file.
        output_csv_path (str): Path to save the CSV output.
        message_type (str): Type of message to extract.
    """
    print(f"Extracting message type: {message_type} from {bin_file_path} to {output_csv_path}")
    mlog = None
    extracted_count = 0
    first_message = True
    writer = None
    csvfile = None # Define csvfile here to close it in finally block

    try:
        # Open the log file
        mlog = mavutil.mavlink_connection(bin_file_path)
        if mlog is None:
             print(f"Error: Could not open MAVLink log file {bin_file_path}")
             return # Cannot proceed

        # Open CSV file - moved inside the loop condition below
        # to avoid creating empty files if no messages are found

        while True:
            msg = mlog.recv_match(type=message_type, blocking=True) # blocking=True is default
            if msg is None: # End of file
                break

            # On the first message, open CSV, determine headers and initialize writer
            if first_message:
                try:
                    csvfile = open(output_csv_path, 'w', newline='')
                except IOError as e:
                    print(f"Error: Could not open CSV file {output_csv_path} for writing: {e}")
                    return # Cannot proceed

                fieldnames = ['timestamp', 'message_type'] # Base fields
                if hasattr(msg, '_fieldnames'):
                    fieldnames.extend(msg._fieldnames)
                fieldnames = sorted(list(set(fieldnames))) # Ensure uniqueness and order

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                try:
                    writer.writeheader()
                except Exception as e:
                     print(f"Error writing header to {output_csv_path}: {e}")
                     # Attempt to continue without header? Or fail? Let's fail.
                     return

                first_message = False

            # Ensure writer is initialized (should be after first message)
            if writer is None:
                 # This case should ideally not be reached if first_message logic is correct
                 # and at least one message exists. If it occurs, something is wrong.
                 print(f"Error: CSV writer not initialized for {output_csv_path}. Skipping message.")
                 continue # Skip this message

            # Create a dictionary for the row data
            row_data = {
                'timestamp': datetime.fromtimestamp(msg._timestamp).strftime('%Y-%m-%d %H:%M:%S.%f'),
                'message_type': message_type,
            }

            # Add all fields from the message
            if hasattr(msg, '_fieldnames'):
                for fieldname in msg._fieldnames:
                    # Use getattr for safe access
                    row_data[fieldname] = getattr(msg, fieldname, None)

            # Write message data to CSV
            try:
                writer.writerow(row_data)
                extracted_count += 1
            except Exception as e:
                print(f"Error writing row to {output_csv_path}: {e}")
                # Consider stopping or just reporting and continuing
                continue

        # After the loop
        if extracted_count > 0:
            print(f"Extracted {extracted_count} '{message_type}' messages from {bin_file_path} to {output_csv_path}")
        else:
            # If no messages were found, the CSV file was never opened (due to moving open inside loop)
            # or it was opened but nothing written.
            print(f"Warning: No '{message_type}' messages were found or extracted from {bin_file_path}.")
            # If csvfile was opened (meaning header written) but count is 0, it's an empty file with header.
            # If first_message is still True, the file was never opened.
            if not first_message and extracted_count == 0 and csvfile is not None:
                 print(f"CSV file created with only header: {output_csv_path}")
            elif first_message:
                 # No messages found at all, file wasn't created.
                 pass


    except mavutil.mavlink.MAVError as e:
         print(f"MAVLink error processing {message_type} for {bin_file_path}: {str(e)}")
    except Exception as e:
        print(f"General error processing {message_type} for {bin_file_path}: {str(e)}")
    finally:
        # Ensure the CSV file is closed if it was opened
        if csvfile is not None:
            try:
                csvfile.close()
            except Exception as e:
                print(f"Error closing CSV file {output_csv_path}: {e}")
        # mlog doesn't need explicit closing

# Update worker to call the new function
def extract_message_worker(bin_file_path, csv_path, message_type):
    """
    Worker function for thread to extract a single message type
    """
    try:
        # Call the renamed and simplified function
        extract_single_message_type(bin_file_path, csv_path, message_type)
    except Exception as e:
        # Catch exceptions during the extraction process itself
        print(f"Error in worker thread for {message_type} from {bin_file_path}: {str(e)}")

def process_bin_files(file=None, message=None, logs_dir="LOGS"):
    """
    Process specified .BIN file or all files in the directory
    """
    csv_dir = "CSV_OUTPUT"
    os.makedirs(csv_dir, exist_ok=True)

    files_to_process = []
    if file:
        if os.path.exists(file):
            files_to_process.append(file)
        else:
            print(f"Error: File '{file}' not found")
            return
    else:
        if not os.path.exists(logs_dir):
            print(f"Error: Directory '{logs_dir}' not found")
            return
        for filename in os.listdir(logs_dir):
            if filename.upper().endswith('.BIN'):
                files_to_process.append(os.path.join(logs_dir, filename))

    if not files_to_process:
        print("No .BIN files found to process.")
        return

    for bin_path in files_to_process:
        filename = os.path.basename(bin_path)
        print(f"\nProcessing {bin_path}...")

        if message:
            # User specified a single message type
            csv_filename = f"{os.path.splitext(filename)[0]}.{message}.csv"
            csv_path = os.path.join(csv_dir, csv_filename)
            try:
                # Call the extraction function directly (no threading needed)
                extract_single_message_type(bin_path, csv_path, message)
            except Exception as e:
                print(f"Error processing {message} for {bin_path}: {str(e)}")
        else:
            # Process all message types found in the file using threads
            print(f"Listing message types in {bin_path}...")
            try:
                message_types = list_message_types(bin_path)
                if not message_types:
                    print(f"No relevant message types found in {bin_path}.")
                    continue # Skip to next file

                print(f"Found {len(message_types)} message types to extract: {', '.join(message_types.keys())}")

                threads = []
                for msg_type, count in message_types.items():
                    # We already filtered unwanted types in list_message_types
                    # if count > 0: # Check count just in case
                    csv_filename = f"{os.path.splitext(filename)[0]}.{msg_type}.csv"
                    csv_path = os.path.join(csv_dir, csv_filename)
                    # print(f"Starting extraction thread for {msg_type} ({count} messages) to {csv_filename}...") # Verbose logging

                    thread = threading.Thread(
                        target=extract_message_worker,
                        args=(bin_path, csv_path, msg_type),
                        daemon=True # Consider making threads daemonic
                    )
                    threads.append(thread)
                    thread.start()

                # Wait for all threads for this file to complete
                print(f"Waiting for {len(threads)} extraction threads to complete for {bin_path}...")
                for thread in threads:
                    thread.join() # Add a timeout? thread.join(timeout=300) # e.g., 5 minutes

                print(f"Completed extraction of all message types from {bin_path}")

            except Exception as e:
                print(f"Error processing all message types for {bin_path}: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract message data from MAVLink binary log files (.BIN)")
    parser.add_argument("--file", help="Path to a specific .BIN file to process")
    parser.add_argument("--message", help="Specific message type to extract (e.g., 'ATT', 'GPS', 'XKFM'). If omitted, extracts all types to separate CSVs.")
    parser.add_argument("--logs_dir", default="LOGS", help="Directory containing .BIN files (used if --file is not specified, default: LOGS)")

    args = parser.parse_args()

    # Check if required parameters are provided
    if not args.file and not args.logs_dir:
        print("Error: Either --file or --logs_dir must be specified.")
        parser.print_help()
        exit(1)
        
    # Validate that the specified file or directory exists
    if args.file and not os.path.isfile(args.file):
        print(f"Error: Specified file '{args.file}' does not exist.")
        exit(1)
    elif args.logs_dir and not os.path.isdir(args.logs_dir):
        print(f"Error: Specified logs directory '{args.logs_dir}' does not exist.")
        exit(1)

    start_time = time.time()
    process_bin_files(file=args.file, message=args.message, logs_dir=args.logs_dir)
    end_time = time.time()
    print(f"\nProcessing complete! Total time: {end_time - start_time:.2f} seconds")
