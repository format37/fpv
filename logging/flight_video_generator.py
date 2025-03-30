#!/usr/bin/env python3

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import imageio.v2 as iio
import numpy as np
import argparse
import os
import sys
import tempfile
import shutil
from tqdm import tqdm # Progress bar
from datetime import timedelta, datetime # Added datetime
import concurrent.futures # Added for multiprocessing
import gc # Added for potential garbage collection trigger

# Import shared data loading functions
from flight_data_loader import load_and_merge_data, REQUIRED_COLS, OPTIONAL_COLS_TO_SELECT

# --- Constants Specific to Video Generator ---

# Plot definitions matching the dash app, plus battery
PLOT_DEFINITIONS = {
    'roll_att': 'Roll Attitude',
    'roll_ctrl': 'Roll Control',
    'pitch_att': 'Pitch Attitude',
    'pitch_ctrl': 'Pitch Control',
    'yaw_att': 'Yaw Attitude',
    'alt_amsl': 'Altitude AMSL',
    'alt_agl': 'Altitude AGL',
    'speed': 'Speed',
    'battery': 'Battery Voltage & Current' # Added Battery
}

# --- Removed load_and_prepare_csv and load_and_merge_data functions ---
# --- They are now imported from flight_data_loader ---


# --- Frame Generation Function ---
def create_frame_figure(df_window, current_time, loaded_optional_types, active_plots, log_identifier, stall_speed, width, height, window_duration_secs):
    """Creates a Plotly figure for a single frame of the animation."""
    if df_window is None or df_window.empty:
        return None # Skip frame if no data

    rcin_loaded = 'RCIN' in loaded_optional_types
    bat_loaded = 'BAT' in loaded_optional_types # Check if BAT data is loaded
    num_rows = len(active_plots)
    if num_rows == 0:
        return None

    # Generate titles for active plots only
    subplot_titles = []
    plot_row_map = {} # Map plot key to its row index (1-based)
    current_row = 1
    specs = [] # Define specs for secondary y-axis
    for plot_key in PLOT_DEFINITIONS: # Iterate in defined order
        if plot_key in active_plots:
            title = PLOT_DEFINITIONS[plot_key]
            # Add specifics to titles based on loaded data (similar to dash app)
            if plot_key == 'roll_ctrl' and rcin_loaded and 'RCIN_C1_Roll' in df_window.columns: title = 'Roll Ctrl (Rate vs Input)'
            elif plot_key == 'roll_ctrl': title = 'Roll Ctrl (Rate)'
            elif plot_key == 'pitch_ctrl' and rcin_loaded and 'RCIN_C2_Pitch' in df_window.columns: title = 'Pitch Ctrl (Rate vs Input)'
            elif plot_key == 'pitch_ctrl': title = 'Pitch Ctrl (Rate)'
            # Add more title refinements if needed

            subplot_titles.append(title)
            plot_row_map[plot_key] = current_row
            # Add spec for secondary y-axis if this is the battery plot
            specs.append([{"secondary_y": True}] if plot_key == 'battery' else [{"secondary_y": False}])
            current_row += 1

    fig = make_subplots(
        rows=num_rows, cols=1,
        shared_xaxes=True,
        subplot_titles=subplot_titles,
        vertical_spacing=0.05, # Adjust spacing for vertical layout
        specs=specs # Add specs for secondary y-axes
    )

    # --- Add Traces Conditionally ---
    # Get the data point closest to the current time for annotations
    latest_data_point = df_window.iloc[-1] if not df_window.empty else None

    # Helper to add trace and annotation
    def add_trace_with_value(plot_key, row_idx, col_name, trace_name, color, dash=None, legend_group=None, show_legend=False, trace_abbr=None, secondary_y=False): # Added secondary_y
        """Adds a trace and its value annotation."""
        if col_name in df_window.columns:
            # Plot the line segment for the current window
            fig.add_trace(go.Scatter(x=df_window.index, y=df_window[col_name], name=trace_name, mode='lines',
                                     line=dict(color=color, width=1.5, dash=dash), legendgroup=legend_group,
                                     showlegend=show_legend), # Use the show_legend parameter (now defaults to False)
                          row=row_idx, col=1, secondary_y=secondary_y) # Use secondary_y

            # Add annotation for the current value
            if latest_data_point is not None and pd.notna(latest_data_point[col_name]):
                current_value = latest_data_point[col_name]
                # Determine yref base for the primary axis of this subplot
                yref_base = f"y{row_idx}" if row_idx > 1 else "y"

                # Use abbreviation if provided, otherwise use trace_name
                label = trace_abbr if trace_abbr else trace_name

                # Position annotation to the right of the plot area, aligned with the value on the y-axis
                fig.add_annotation(
                    xref="paper",
                    # Always reference the primary y-axis of the subplot for annotation positioning.
                    # The 'y' value itself handles the vertical placement based on the data.
                    yref=yref_base,
                    x=1.02,
                    y=current_value,
                    # Update text to include value and label
                    text=f"{current_value:.2f} {label}",
                    showarrow=False,
                    font=dict(color=color, size=10),
                    bgcolor="rgba(255,255,255,0.7)",
                    xanchor="left",
                    yanchor="middle",
                    align="left"
                )
            return True
        return False

    # Plot 1: Roll Attitude
    if 'roll_att' in plot_row_map:
        row_idx = plot_row_map['roll_att']
        # Provide short abbreviations (trace_abbr)
        add_trace_with_value(plot_key='roll_att', row_idx=row_idx, col_name='Roll', trace_name='Actual', color='blue', trace_abbr='Act')
        add_trace_with_value(plot_key='roll_att', row_idx=row_idx, col_name='DesRoll', trace_name='Desired', color='red', dash='dash', trace_abbr='Des')
        fig.update_yaxes(title_text="Roll (deg)", row=row_idx, col=1)

    # Plot 2: Roll Control
    if 'roll_ctrl' in plot_row_map:
        row_idx = plot_row_map['roll_ctrl']
        y_title = "Rate (deg/s)"
        add_trace_with_value(plot_key='roll_ctrl', row_idx=row_idx, col_name='GyrX', trace_name='Roll Rate', color='green', trace_abbr='Rate')
        if rcin_loaded:
            if add_trace_with_value(plot_key='roll_ctrl', row_idx=row_idx, col_name='RCIN_C1_Roll', trace_name='Pilot In', color='grey', dash='dot', trace_abbr='In'):
                 y_title = "Rate/Input"
        fig.update_yaxes(title_text=y_title, row=row_idx, col=1)

    # Plot 3: Pitch Attitude
    if 'pitch_att' in plot_row_map:
        row_idx = plot_row_map['pitch_att']
        add_trace_with_value(plot_key='pitch_att', row_idx=row_idx, col_name='Pitch', trace_name='Actual', color='blue', trace_abbr='Act')
        add_trace_with_value(plot_key='pitch_att', row_idx=row_idx, col_name='DesPitch', trace_name='Desired', color='red', dash='dash', trace_abbr='Des')
        fig.update_yaxes(title_text="Pitch (deg)", row=row_idx, col=1)

    # Plot 4: Pitch Control
    if 'pitch_ctrl' in plot_row_map:
        row_idx = plot_row_map['pitch_ctrl']
        y_title = "Rate (deg/s)"
        add_trace_with_value(plot_key='pitch_ctrl', row_idx=row_idx, col_name='GyrY', trace_name='Pitch Rate', color='green', trace_abbr='Rate')
        if rcin_loaded:
            if add_trace_with_value(plot_key='pitch_ctrl', row_idx=row_idx, col_name='RCIN_C2_Pitch', trace_name='Pilot In', color='grey', dash='dot', trace_abbr='In'):
                y_title = "Rate/Input"
        fig.update_yaxes(title_text=y_title, row=row_idx, col=1)

    # Plot 5: Yaw Attitude
    if 'yaw_att' in plot_row_map:
        row_idx = plot_row_map['yaw_att']
        add_trace_with_value(plot_key='yaw_att', row_idx=row_idx, col_name='Yaw', trace_name='Actual', color='blue', trace_abbr='Act')
        add_trace_with_value(plot_key='yaw_att', row_idx=row_idx, col_name='DesYaw', trace_name='Desired', color='red', dash='dash', trace_abbr='Des')
        fig.update_yaxes(title_text="Yaw (deg)", row=row_idx, col=1)

    # Plot 6: Altitude AMSL
    if 'alt_amsl' in plot_row_map:
        row_idx = plot_row_map['alt_amsl']
        has_data = False
        if 'POS' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='alt_amsl', row_idx=row_idx, col_name='POS_Alt_AMSL', trace_name='Fused', color='purple', trace_abbr='Fused')
        if 'GPS' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='alt_amsl', row_idx=row_idx, col_name='GPS_Alt_AMSL', trace_name='GPS', color='orange', dash='dot', trace_abbr='GPS')
        if 'BARO' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='alt_amsl', row_idx=row_idx, col_name='BARO_Alt_Raw', trace_name='Baro', color='brown', dash='dashdot', trace_abbr='Baro')
        if has_data: fig.update_yaxes(title_text="Alt AMSL (m)", row=row_idx, col=1)
        else: fig.add_annotation(text="No AMSL data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, row=row_idx, col=1)

    # Plot 7: Altitude AGL
    if 'alt_agl' in plot_row_map:
        row_idx = plot_row_map['alt_agl']
        has_data = False
        if 'XKF5' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='alt_agl', row_idx=row_idx, col_name='XKF5_HAGL', trace_name='Est HAGL', color='cyan', trace_abbr='Est')
        rel_alt_col, rel_alt_name, rel_alt_abbr = (None, None, None)
        if 'POS' in loaded_optional_types:
            if 'POS_RelHomeAlt_AGL' in df_window.columns: rel_alt_col, rel_alt_name, rel_alt_abbr = ('POS_RelHomeAlt_AGL', 'Rel Home', 'Home')
            elif 'POS_RelOriginAlt_AGL' in df_window.columns: rel_alt_col, rel_alt_name, rel_alt_abbr = ('POS_RelOriginAlt_AGL', 'Rel Origin', 'Origin')
            if rel_alt_col: has_data |= add_trace_with_value(plot_key='alt_agl', row_idx=row_idx, col_name=rel_alt_col, trace_name=rel_alt_name, color='magenta', dash='dash', trace_abbr=rel_alt_abbr)
        if 'RFND' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='alt_agl', row_idx=row_idx, col_name='RFND_Dist_AGL', trace_name='Rangefinder', color='lime', dash='dot', trace_abbr='Rngfnd')
        if 'TERR' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='alt_agl', row_idx=row_idx, col_name='TERR_CHeight_AGL', trace_name='Terrain DB', color='gold', dash='dashdot', trace_abbr='TerrDB')
        if has_data: fig.update_yaxes(title_text="Alt AGL (m)", row=row_idx, col=1)
        else: fig.add_annotation(text="No AGL data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, row=row_idx, col=1)

    # Plot 8: Speed
    if 'speed' in plot_row_map:
        row_idx = plot_row_map['speed']
        has_data = False
        # Provide abbreviations: ASPD for Airspeed, GSPD for Ground Speed
        if 'ARSP' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='speed', row_idx=row_idx, col_name='ARSP_Airspeed', trace_name='Airspeed', color='teal', trace_abbr='ASPD')
        if 'GPS' in loaded_optional_types: has_data |= add_trace_with_value(plot_key='speed', row_idx=row_idx, col_name='GPS_Spd_Ground', trace_name='Ground Spd', color='navy', dash='dash', trace_abbr='GSPD')

        if has_data:
            fig.update_yaxes(title_text="Speed (m/s)", row=row_idx, col=1)
            # Add stall speed line if value is provided
            if stall_speed is not None and isinstance(stall_speed, (int, float)) and stall_speed > 0:
                 fig.add_shape(type="line",
                              x0=df_window.index.min(), y0=stall_speed,
                              x1=df_window.index.max(), y1=stall_speed,
                              line=dict(color="OrangeRed", width=2, dash="dot"),
                              row=row_idx, col=1)
                 # Add annotation for stall speed next to the line
                 fig.add_annotation(
                    xref="paper", yref=f"y{row_idx}",
                    x=1.02,
                    y=stall_speed,
                    # Update text format for consistency
                    text=f"{stall_speed:.1f} Stall",
                    showarrow=False,
                    font=dict(color="OrangeRed", size=10),
                    bgcolor="rgba(255,255,255,0.7)",
                    xanchor="left",
                    yanchor="middle",
                    row=row_idx, col=1 # Explicitly specify row/col for annotation positioning relative to subplot
                 )
        else: fig.add_annotation(text="No Speed data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, row=row_idx, col=1)

    # Plot 9: Battery Voltage & Current
    if 'battery' in plot_row_map:
        row_idx = plot_row_map['battery']
        has_data = False
        bat_loaded = 'BAT' in loaded_optional_types # Check if BAT data was loaded initially

        if bat_loaded:
            # Plot Voltage on primary y-axis
            volt_added = add_trace_with_value(plot_key='battery', row_idx=row_idx, col_name='BAT_Volt', trace_name='Voltage', color='goldenrod', trace_abbr='V', secondary_y=False)
            # Plot Current on secondary y-axis
            curr_added = add_trace_with_value(plot_key='battery', row_idx=row_idx, col_name='BAT_Curr', trace_name='Current', color='firebrick', trace_abbr='A', secondary_y=True)
            has_data = volt_added or curr_added

        if has_data:
            # Update y-axis titles for this subplot
            fig.update_yaxes(title_text="Volt (V) Curr (A)", row=row_idx, col=1, secondary_y=False)
            # fig.update_yaxes(title_text="Current (A)", row=row_idx, col=1, secondary_y=True, showgrid=False) # Optionally hide grid for secondary
        else:
            # Add annotation if plot is selected but no data exists *for this window*
            # Check if BAT was loaded at all to differentiate between no data loaded vs no data in window
            no_data_text = "No Battery data loaded" if not bat_loaded else "No Battery data in window"
            fig.add_annotation(text=no_data_text, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, row=row_idx, col=1)
            # Hide secondary y-axis if no data
            fig.update_yaxes(visible=False, secondary_y=True, row=row_idx, col=1)


    # --- Update Layout ---
    frame_time_str = current_time.strftime('%H:%M:%S.%f')[:-3] # Format time
    plot_title = f'{log_identifier} # {frame_time_str}'

    fig.update_layout(
        title_text=plot_title,
        title_x=0.5, # Center title
        width=width,
        height=height,
        margin=dict(l=60, r=80, t=80, b=50), # Keep right margin for annotations
        hovermode=False, # Disable hover for static images
        showlegend=False # Globally disable legend
    )

    # Update x-axis range to show the sliding window
    start_time = current_time - timedelta(seconds=window_duration_secs)
    # Ensure x-axis updates apply to all subplots sharing the axis
    fig.update_xaxes(range=[start_time, current_time])
    fig.update_xaxes(title_text="Time", row=num_rows, col=1) # Add X axis title only to the bottom plot

    # Add vertical line for the current time moment
    fig.add_vline(x=current_time, line_width=1.5, line_dash="dash", line_color="black", row='all', col=1)

    # Ensure y-axes auto-range based *only* on the data visible in the current window
    fig.update_yaxes(fixedrange=False) # Allow y-axis autoranging

    return fig


# --- Worker Function for Multiprocessing ---
def generate_single_frame(args):
    """
    Worker function designed to be called by ProcessPoolExecutor.
    Generates a single frame image.
    """
    # Unpack arguments
    # Note: df_clipped is passed here instead of df_merged
    i, current_time, df_clipped, loaded_optional_types, active_plots, log_identifier, \
    stall_speed, width, height, window_duration_secs, temp_dir = args

    frame_filename = None # Initialize
    fig = None
    df_window = None

    try:
        # Define the window of data to plot for this frame
        window_start = current_time - timedelta(seconds=window_duration_secs)
        # Select data within the time window ending at the current frame time
        # Use the (potentially already clipped) df_clipped passed to the worker
        df_window = df_clipped[(df_clipped.index >= window_start) & (df_clipped.index <= current_time)]

        if df_window.empty:
            # If no data exactly in window (e.g., start of log), try to get the very first point
            # from the clipped data relevant to this worker
            first_point = df_clipped.iloc[[0]]
            if not first_point.empty and first_point.index[0] <= current_time:
                 df_window = first_point
            else:
                # print(f"Warning: No data found for frame {i} at {current_time}. Skipping frame.")
                return i, None # Return index and None for filename to indicate skip

        # Create the figure for this frame
        fig = create_frame_figure(df_window, current_time, loaded_optional_types, active_plots, log_identifier, stall_speed, width, height, window_duration_secs)

        if fig:
            frame_filename = os.path.join(temp_dir, f"frame_{i:06d}.png")
            try:
                # Save the figure as a PNG image
                pio.write_image(fig, frame_filename, format='png', engine='kaleido')
                return i, frame_filename # Return index and filename on success
            except Exception as e:
                print(f"\nError saving frame {i} with Kaleido: {e}")
                # Fall through to return None
        else:
            # create_frame_figure returned None (e.g., no active plots)
            pass # Fall through to return None

    except Exception as e:
        print(f"\nError generating figure for frame {i}: {e}")
        # Fall through to return None
    finally:
        # Explicitly delete large objects to potentially help memory management in worker processes
        del fig
        del df_window
        gc.collect() # Optionally trigger garbage collection

    return i, None # Return index and None for filename to indicate failure/skip


# --- Main Video Generation Logic ---
def create_flight_video(df_merged, loaded_optional_types, active_plots, log_identifier, stall_speed, width, height, output_path, fps, window_duration_secs, start_frame=0, max_frames=None, start_time_str=None, end_time_str=None, disable_cleaning=False): # Added start/end time args
    """Generates frames in parallel and compiles them into a video."""

    print(f"\n--- Starting Video Generation ---")
    print(f"Log: {log_identifier}")
    print(f"Selected Plots: {', '.join(active_plots)}")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    print(f"Time Window: {window_duration_secs} seconds")
    if stall_speed: print(f"Stall Speed: {stall_speed} m/s")

    # --- Time Clipping ---
    # Ensure index is datetime type before proceeding
    if not isinstance(df_merged.index, pd.DatetimeIndex):
        print("Error: DataFrame index is not a DatetimeIndex. Cannot perform time clipping.")
        return

    log_start_time = df_merged.index.min()
    log_end_time = df_merged.index.max()
    clip_start_time = log_start_time
    clip_end_time = log_end_time
    time_clipped = False

    print(f"Original log time range: {log_start_time} to {log_end_time}")
    print(f"Index timezone: {df_merged.index.tz}") # Add info about index timezone

    # Parse start time
    if start_time_str:
        try:
            parsed_start = pd.to_datetime(start_time_str)
            print(f"Parsed --start-time '{start_time_str}' as: {parsed_start} (TZ: {parsed_start.tz})") # Debug print

            # --- Start: Improved Timezone Handling ---
            if df_merged.index.tz is not None: # Index is aware
                if parsed_start.tz is None: # Parsed is naive
                    # Localize naive parsed time to index's timezone
                    try:
                        parsed_start = parsed_start.tz_localize(df_merged.index.tz)
                    except Exception as tz_err:
                         print(f"Warning: Could not localize naive start time to index timezone ({df_merged.index.tz}): {tz_err}. Trying UTC.")
                         # Fallback: Assume naive time is UTC and convert
                         parsed_start = parsed_start.tz_localize('UTC').tz_convert(df_merged.index.tz)

                else: # Parsed is aware, convert to index's timezone
                    parsed_start = parsed_start.tz_convert(df_merged.index.tz)
            else: # Index is naive
                if parsed_start.tz is not None: # Parsed is aware
                    # Convert aware parsed time to naive UTC for comparison
                    print(f"Warning: Index is timezone-naive, but --start-time was parsed as aware. Converting start time to naive UTC.")
                    parsed_start = parsed_start.tz_convert('UTC').tz_localize(None)
            # --- End: Improved Timezone Handling ---

            clip_start_time = max(log_start_time, parsed_start)
            time_clipped = True
            print(f"Effective clip start time: {clip_start_time}") # Debug print
        except ValueError:
            print(f"Error: Invalid --start-time format '{start_time_str}'. Please use a format pandas can parse (e.g., 'YYYY-MM-DD HH:MM:SS.fff').")
            return
        except Exception as e: # Catch other potential errors like timezone issues
             print(f"Error processing --start-time '{start_time_str}': {e}")
             return

    # Parse end time
    if end_time_str:
        try:
            parsed_end = pd.to_datetime(end_time_str)
            print(f"Parsed --end-time '{end_time_str}' as: {parsed_end} (TZ: {parsed_end.tz})") # Debug print

            # --- Start: Improved Timezone Handling ---
            if df_merged.index.tz is not None: # Index is aware
                if parsed_end.tz is None: # Parsed is naive
                    # Localize naive parsed time to index's timezone
                    try:
                        parsed_end = parsed_end.tz_localize(df_merged.index.tz)
                    except Exception as tz_err:
                        print(f"Warning: Could not localize naive end time to index timezone ({df_merged.index.tz}): {tz_err}. Trying UTC.")
                        # Fallback: Assume naive time is UTC and convert
                        parsed_end = parsed_end.tz_localize('UTC').tz_convert(df_merged.index.tz)
                else: # Parsed is aware, convert to index's timezone
                    parsed_end = parsed_end.tz_convert(df_merged.index.tz)
            else: # Index is naive
                if parsed_end.tz is not None: # Parsed is aware
                    # Convert aware parsed time to naive UTC for comparison
                    print(f"Warning: Index is timezone-naive, but --end-time was parsed as aware. Converting end time to naive UTC.")
                    parsed_end = parsed_end.tz_convert('UTC').tz_localize(None)
            # --- End: Improved Timezone Handling ---

            clip_end_time = min(log_end_time, parsed_end)
            time_clipped = True
            print(f"Effective clip end time: {clip_end_time}") # Debug print
        except ValueError:
            print(f"Error: Invalid --end-time format '{end_time_str}'. Please use a format pandas can parse (e.g., 'YYYY-MM-DD HH:MM:SS.fff').")
            return
        except Exception as e: # Catch other potential errors
             print(f"Error processing --end-time '{end_time_str}': {e}")
             return

    # Validate clipped time range
    if clip_start_time >= clip_end_time:
        print(f"Error: Calculated start time ({clip_start_time}) is not before end time ({clip_end_time}). Check --start-time and --end-time values.")
        return

    # Filter DataFrame based on time clipping
    # Ensure comparison happens correctly even with mixed timezone states after handling above
    # If index is naive, clip times should now be naive UTC. If index is aware, clip times match index tz.
    df_clipped = df_merged[(df_merged.index >= clip_start_time) & (df_merged.index <= clip_end_time)].copy() # Use .copy() to avoid SettingWithCopyWarning later if needed

    if df_clipped.empty:
        print(f"Error: No data found within the specified time range: {clip_start_time} to {clip_end_time}.")
        return

    if time_clipped:
        print(f"Using clipped time range: {df_clipped.index.min()} to {df_clipped.index.max()}")
    # --- End Time Clipping ---


    # Determine time range and frame times *from the clipped data*
    start_time = df_clipped.index.min()
    end_time = df_clipped.index.max()
    total_duration = (end_time - start_time).total_seconds()
    total_possible_frames = int(total_duration * fps)
    all_frame_timestamps = pd.to_datetime(np.linspace(start_time.value, end_time.value, total_possible_frames))

    print(f"Selected data duration: {total_duration:.2f} seconds")
    print(f"Total possible frames in selected range: {total_possible_frames}")

    if total_possible_frames <= 0:
        print("Error: No frames to generate based on selected data time range.")
        return

    # Apply frame limits (start_frame, max_frames) relative to the clipped range
    frame_indices_to_process = list(range(total_possible_frames))
    if start_frame > 0:
        if start_frame >= len(frame_indices_to_process):
             print(f"Warning: --start-frame ({start_frame}) is beyond the number of possible frames ({total_possible_frames}) in the selected time range. No frames will be generated.")
             frame_indices_to_process = []
        else:
            frame_indices_to_process = frame_indices_to_process[start_frame:]
    if max_frames is not None:
        frame_indices_to_process = frame_indices_to_process[:max_frames]

    if not frame_indices_to_process:
        print(f"Error: No frames selected after applying time clipping and frame limits (start_frame={start_frame}, max_frames={max_frames}).")
        return

    # Adjust frame timestamps and calculate num_frames based on limits
    frame_timestamps_to_process = all_frame_timestamps[frame_indices_to_process]
    num_frames_to_generate = len(frame_timestamps_to_process)
    # Keep track of the original index *within the clipped range* for file naming and ordering
    original_indices = frame_indices_to_process

    print(f"Frames to generate after limits: {num_frames_to_generate} (Indices {original_indices[0]} to {original_indices[-1]} relative to clipped range)")
    # Print frame limits if used
    if start_frame > 0 or max_frames is not None:
        print(f"Frame Index Limits: Start={start_frame}, Max Count={max_frames if max_frames is not None else 'None'}")
    print(f"Output File: {output_path}")


    # Create temporary directory for frames
    temp_dir = tempfile.mkdtemp(prefix="flight_video_frames_")
    print(f"Using temporary directory for frames: {temp_dir}")

    # Prepare arguments for each task
    tasks = []
    # Use enumerate over the selected timestamps, but pass the original index
    for i, original_index in enumerate(original_indices):
        current_time = frame_timestamps_to_process[i]
        # Bundle arguments for the worker function, using original_index for file naming
        # Pass df_clipped instead of df_merged
        task_args = (
            original_index, current_time, df_clipped, loaded_optional_types,
            active_plots, log_identifier, stall_speed, width, height,
            window_duration_secs, temp_dir
        )
        tasks.append(task_args)

    # Dictionary to store results (frame filenames) keyed by original index
    frame_results = {}

    # Determine number of workers
    # Leave 1-2 cores free for system responsiveness if needed, default to 1 if cpu_count fails
    cpu_cores = os.cpu_count()
    num_workers = max(1, cpu_cores - 1 if cpu_cores else 1)
    print(f"Starting frame generation with {num_workers} workers...")

    try:
        # Use ProcessPoolExecutor for CPU-bound tasks
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            future_to_task_args = {executor.submit(generate_single_frame, task): task for task in tasks}

            # Process results as they complete with a progress bar
            for future in tqdm(concurrent.futures.as_completed(future_to_task_args), total=len(tasks), desc="Generating Frames"):
                task_args = future_to_task_args[future]
                task_index = task_args[0] # Get the original index 'i'
                try:
                    idx, result_filename = future.result()
                    if idx == task_index: # Sanity check
                        frame_results[idx] = result_filename # Store filename or None
                    else:
                         print(f"Warning: Mismatched index from worker! Expected {task_index}, got {idx}. Storing result anyway.")
                         frame_results[task_index] = result_filename # Store under expected index
                except Exception as exc:
                    print(f'\nFrame generation task {task_index} generated an exception: {exc}')
                    frame_results[task_index] = None # Mark as failed

        # Collect successful and valid frame filenames in the correct order
        successful_frame_files = []
        print("\nValidating generated frames...")
        # Iterate through the original indices we intended to generate
        for i in tqdm(original_indices, desc="Validating Frames"):
            filename = frame_results.get(i) # Get filename using the original index
            if filename:
                # --- Validation Step ---
                try:
                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        successful_frame_files.append(filename)
                    elif not os.path.exists(filename):
                         print(f"Warning: Frame file for index {i} reported but not found: {filename}. Skipping.")
                    else: # Exists but size is 0
                         print(f"Warning: Frame file for index {i} is empty: {filename}. Skipping.")
                except OSError as e:
                     print(f"Warning: Error accessing frame file for index {i} ({filename}): {e}. Skipping.")
            # else: # Optional: report skipped/failed frames from generation phase
            #     print(f"Frame {i} was skipped or failed during generation.")


        # --- Compile Video ---
        num_valid_frames = len(successful_frame_files)
        print(f"\nCompiling {num_valid_frames} valid frames into video...")
        if not successful_frame_files:
            print("Error: No valid frames were generated or found.")
            # Cleanup happens in finally block
            return

        # Use imageio to create the video
        # Ensure macro_block_size is compatible with video dimensions and codec (often 16 for H.264)
        # Using None lets imageio choose, which is generally safer.
        # Use pixelformat='yuv420p' for broad compatibility, required by many players/codecs
        with iio.get_writer(output_path, fps=fps, macro_block_size=None, pixelformat='yuv420p', codec='libx264') as writer:
             # Use tqdm on the validated list
             for filename in tqdm(successful_frame_files, desc="Writing Video"):
                 try:
                     # Read the image data using iio (imageio v2)
                     image = iio.imread(filename)
                     # Append data to the video file
                     writer.append_data(image)
                 except FileNotFoundError:
                     # This shouldn't happen after our validation, but handle defensively
                     print(f"Warning: Frame file disappeared before compilation: {filename}. Skipping.")
                 except Exception as e:
                     # Catch other potential errors during imread or append_data
                     # Provide more specific error info
                     print(f"Warning: Error processing frame {filename} during compilation: {type(e).__name__} - {e}. Skipping.")


        print(f"\nVideo saved successfully to: {output_path}")

    finally:
        # Clean up temporary directory only if disable_cleaning is False
        if not disable_cleaning:
            print(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            print(f"Temporary directory preserved: {temp_dir}")


# --- Main Execution Block ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an animated video of MAVLink flight data plots using multiprocessing.")

    # Required arguments (same as dash app)
    parser.add_argument("--att-csv", required=True, help="Path to ATT CSV")
    parser.add_argument("--imu-csv", required=True, help="Path to IMU CSV")

    # Optional arguments (same as dash app + BAT)
    parser.add_argument("--rcin-csv", help="Path to RCIN CSV")
    parser.add_argument("--pos-csv", help="Path to POS CSV")
    parser.add_argument("--gps-csv", help="Path to GPS CSV")
    parser.add_argument("--arsp-csv", help="Path to ARSP CSV")
    parser.add_argument("--xkf5-csv", help="Path to XKF5 CSV")
    parser.add_argument("--rfnd-csv", help="Path to RFND CSV")
    parser.add_argument("--baro-csv", help="Path to BARO CSV")
    parser.add_argument("--terr-csv", help="Path to TERR CSV")
    parser.add_argument("--bat-csv", help="Path to BAT CSV") # Added BAT

    # Video specific arguments
    parser.add_argument("--plots", required=True, nargs='+', choices=list(PLOT_DEFINITIONS.keys()),
                        help=f"Space-separated list of plot keys to include. Choices: {', '.join(PLOT_DEFINITIONS.keys())}")
    parser.add_argument("--width", type=int, default=720, help="Video width in pixels (must be even).")
    parser.add_argument("--height", type=int, default=1280, help="Video height in pixels (must be even).")
    parser.add_argument("--fps", type=int, default=15, help="Frames per second for the output video.")
    parser.add_argument("--window", type=float, default=15.0, help="Duration of the time window shown in seconds (how much past data is visible).")
    parser.add_argument("--output", default="flight_analysis_video.mp4", help="Output video file path (e.g., video.mp4).")
    parser.add_argument("--stall-speed", type=float, default=None, help="Optional stall speed (m/s) to draw on the speed plot.")
    # --- Added Time Limit Arguments ---
    parser.add_argument("--start-time", type=str, default=None, help="Start time for video generation (e.g., 'YYYY-MM-DD HH:MM:SS.fff' or other format pandas.to_datetime understands). Clips data before this time.")
    parser.add_argument("--end-time", type=str, default=None, help="End time for video generation (e.g., 'YYYY-MM-DD HH:MM:SS.fff'). Clips data after this time.")
    # --- Frame Limit Arguments (applied *after* time clipping) ---
    parser.add_argument("--start-frame", type=int, default=0, help="Frame number to start generation from (0-based index, relative to the time-clipped range).")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum number of frames to generate (relative to the time-clipped range).")
    # --- Added disable-cleaning Argument ---
    parser.add_argument("--disable-cleaning", action='store_true', help="Prevent deletion of the temporary frame directory.")


    args = parser.parse_args()

    # --- Validate Dimensions ---
    if args.width % 2 != 0:
        print(f"Error: Video width (--width) must be an even number. Received: {args.width}")
        sys.exit(1)
    if args.height % 2 != 0:
        print(f"Error: Video height (--height) must be an even number. Received: {args.height}")
        sys.exit(1)


    # --- Prepare Filepaths Dictionary ---
    csv_files = {
        'ATT': args.att_csv, 'IMU': args.imu_csv, 'RCIN': args.rcin_csv,
        'POS': args.pos_csv, 'GPS': args.gps_csv, 'ARSP': args.arsp_csv,
        'XKF5': args.xkf5_csv, 'RFND': args.rfnd_csv, 'BARO': args.baro_csv,
        'TERR': args.terr_csv, 'BAT': args.bat_csv # Added BAT
    }
    csv_files_provided = {k: v for k, v in csv_files.items() if v is not None}

    # --- Determine Log Identifier ---
    att_basename = os.path.basename(args.att_csv)
    log_identifier = att_basename.split('.')[0] if '.' in att_basename else att_basename

    # --- Load and Merge Data using the imported function ---
    print("Loading and merging data...")
    df_merged, loaded_opts = load_and_merge_data(csv_files_provided)

    if df_merged is None or df_merged.empty:
        print("Failed to load or merge sufficient data. Cannot create video.")
        sys.exit(1)

    # --- Validate Selected Plots ---
    valid_plots = [p for p in args.plots if p in PLOT_DEFINITIONS]
    if not valid_plots:
        print("Error: No valid plots selected from the provided list.")
        sys.exit(1)
    if len(valid_plots) != len(args.plots):
        print(f"Warning: Some requested plots are invalid and were ignored. Using: {', '.join(valid_plots)}")


    # --- Create Video ---
    try:
        create_flight_video(
            df_merged=df_merged,
            loaded_optional_types=loaded_opts,
            active_plots=valid_plots,
            log_identifier=log_identifier,
            stall_speed=args.stall_speed,
            width=args.width,
            height=args.height,
            output_path=args.output,
            fps=args.fps,
            window_duration_secs=args.window,
            # --- Pass Time/Frame Limit Arguments ---
            start_time_str=args.start_time,
            end_time_str=args.end_time,
            start_frame=args.start_frame,
            max_frames=args.max_frames,
            # --- Pass disable_cleaning Argument ---
            disable_cleaning=args.disable_cleaning
        )
    except Exception as e:
        print(f"\nAn unexpected error occurred during video generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\nVideo generation process finished.") 