#!/usr/bin/env python3

import dash
# Older versions of Dash might require:
# import dash_core_components as dcc
# import dash_html_components as html
# Newer versions (Dash 2.0+):
from dash import dcc, html, Input, Output, State, callback, no_update # Added no_update
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse
import os
import sys # For exiting on critical errors
import json # For serializing data for dcc.Store

# Import shared data loading functions and constants
from flight_data_loader import load_and_merge_data, REQUIRED_COLS, OPTIONAL_COLS_TO_SELECT

# --- Constants Specific to Dash App ---

# --- Define Plot Types ---
# Used for checklist and dynamic plot creation
# Keys should be stable identifiers, values are display names
PLOT_DEFINITIONS = {
    'roll_att': 'Roll Attitude',
    'roll_ctrl': 'Roll Control',
    'pitch_att': 'Pitch Attitude',
    'pitch_ctrl': 'Pitch Control',
    'yaw_att': 'Yaw Attitude',
    'alt_amsl': 'Altitude AMSL',
    'alt_agl': 'Altitude AGL',
    'speed': 'Speed',
    'battery': 'Battery Voltage & Current',
    'dist_home': 'Distance from Home',  # New plot type
    'pidp': 'Pitch PID Output',         # New
    'pidr': 'Roll PID Output',           # New
    'flight_mode': 'Flight Mode',  # New plot type
    'optical_flow': 'Optical Flow (OF)',
    'of_calib_roll': 'OF Roll Calibration (flowX, bodyX, GyrX)',
    'of_calib_pitch': 'OF Pitch Calibration (flowY, bodyY, GyrY)',
}
# DEFAULT_PLOTS = list(PLOT_DEFINITIONS.keys()) # Initially show all plots
DEFAULT_PLOTS = [] # No plots selected by default

# Flight Mode Mapping
FLIGHT_MODES = {
    0: 'MANUAL',
    1: 'CIRCLE',
    2: 'STABILIZE',
    3: 'TRAINING',
    4: 'ACRO',
    5: 'FLY_BY_WIRE_A',
    6: 'FLY_BY_WIRE_B',
    7: 'CRUISE',
    8: 'AUTOTUNE',
    9: '(Reserved)',
    10: 'AUTO',
    11: 'RTL',
    12: 'LOITER',
    13: 'TAKEOFF',
    14: '(Reserved)',
    15: 'GUIDED',
    16: '(Reserved)',
    17: 'QSTABILIZE',
    18: 'QHOVER',
    19: 'QLOITER',
    20: 'QLAND',
    21: 'QRTL',
    22: 'QAUTOTUNE',
    23: 'QACRO',
    24: 'THERMAL',
    25: 'LOITER_ALT_QLAND'
}

# --- Removed load_and_prepare_csv and load_and_merge_data functions ---
# --- They are now imported from flight_data_loader ---


# --- Plotting Function (Modified for dynamic plots and stall speed) ---
def create_flight_figure(df_merged, loaded_optional_types, active_plots, log_identifier, stall_speed=None):
    """Creates the Plotly figure with selected subplots."""
    # df_merged index is expected to be DateTimeIndex here
    if df_merged is None or df_merged.empty:
        # Return an empty figure or a message if no data
        fig = go.Figure()
        fig.update_layout(title_text=f"No data to display for {log_identifier}", xaxis = {"visible": False}, yaxis = {"visible": False})
        return fig

    rcin_loaded = 'RCIN' in loaded_optional_types
    bat_loaded = 'BAT' in loaded_optional_types # Added check
    num_rows = len(active_plots)

    if num_rows == 0:
        fig = go.Figure()
        fig.update_layout(title_text=f"No plots selected for {log_identifier}", xaxis = {"visible": False}, yaxis = {"visible": False})
        return fig

    # Generate titles for active plots only
    subplot_titles = []
    plot_row_map = {} # Map plot key to its row index (1-based)
    current_row = 1
    specs = [] # Define specs for secondary y-axis
    for plot_key in PLOT_DEFINITIONS: # Iterate in defined order
        if plot_key in active_plots:
            title = PLOT_DEFINITIONS[plot_key]
            # Add specifics to titles based on loaded data
            if plot_key == 'roll_ctrl' and rcin_loaded and 'RCIN_C1_Roll' in df_merged.columns:
                title = 'Roll Control (Rate vs Pilot Input)'
            elif plot_key == 'roll_ctrl':
                 title = 'Roll Control (Rate)'
            elif plot_key == 'pitch_ctrl' and rcin_loaded and 'RCIN_C2_Pitch' in df_merged.columns:
                title = 'Pitch Control (Rate vs Pilot Input)'
            elif plot_key == 'pitch_ctrl':
                 title = 'Pitch Control (Rate)'
            # Add more title refinements for Alt/Speed if needed based on loaded_optional_types

            subplot_titles.append(title)
            plot_row_map[plot_key] = current_row
            # Add spec for secondary y-axis if this is the battery plot
            specs.append([{"secondary_y": True}] if plot_key == 'battery' else [{"secondary_y": False}])
            current_row += 1

    fig = make_subplots(
        rows=num_rows, cols=1,
        shared_xaxes=True,
        subplot_titles=subplot_titles,
        vertical_spacing=0.03, # Adjust spacing as needed
        # Define secondary y-axis for plots that need it (like Battery)
        specs=specs # Add specs for secondary y-axes
    )

    # --- Add Traces Conditionally ---
    # Plot 1: Roll Attitude
    if 'roll_att' in plot_row_map:
        row_idx = plot_row_map['roll_att']
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['Roll'], name='Actual Roll', mode='lines', line=dict(color='blue', width=1), legendgroup='att'), row=row_idx, col=1)
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['DesRoll'], name='Desired Roll', mode='lines', line=dict(color='red', dash='dash', width=1), legendgroup='att'), row=row_idx, col=1)
        fig.update_yaxes(title_text="Roll (deg)", row=row_idx, col=1)

    # Plot 2: Roll Control
    if 'roll_ctrl' in plot_row_map:
        row_idx = plot_row_map['roll_ctrl']
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['GyrX'], name='Roll Rate (GyrX)', mode='lines', line=dict(color='green', width=1), legendgroup='rate'), row=row_idx, col=1)
        y_title = "Rate (deg/s)"
        if rcin_loaded and 'RCIN_C1_Roll' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['RCIN_C1_Roll'], name='Pilot Roll In (RCIN C1)', mode='lines', line=dict(color='grey', dash='dot', width=1), legendgroup='rcin'), row=row_idx, col=1)
            y_title = "Rate (deg/s) / Input (PWM)"
        fig.update_yaxes(title_text=y_title, row=row_idx, col=1)

    # Plot 3: Pitch Attitude
    if 'pitch_att' in plot_row_map:
        row_idx = plot_row_map['pitch_att']
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['Pitch'], name='Actual Pitch', mode='lines', line=dict(color='blue', width=1), legendgroup='att', showlegend=False), row=row_idx, col=1)
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['DesPitch'], name='Desired Pitch', mode='lines', line=dict(color='red', dash='dash', width=1), legendgroup='att', showlegend=False), row=row_idx, col=1)
        fig.update_yaxes(title_text="Pitch (deg)", row=row_idx, col=1)

    # Plot 4: Pitch Control
    if 'pitch_ctrl' in plot_row_map:
        row_idx = plot_row_map['pitch_ctrl']
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['GyrY'], name='Pitch Rate (GyrY)', mode='lines', line=dict(color='green', width=1), legendgroup='rate', showlegend=False), row=row_idx, col=1)
        y_title = "Rate (deg/s)"
        if rcin_loaded and 'RCIN_C2_Pitch' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['RCIN_C2_Pitch'], name='Pilot Pitch In (RCIN C2)', mode='lines', line=dict(color='grey', dash='dot', width=1), legendgroup='rcin', showlegend=False), row=row_idx, col=1)
            y_title = "Rate (deg/s) / Input (PWM)"
        fig.update_yaxes(title_text=y_title, row=row_idx, col=1)

    # Plot 5: Yaw Attitude
    if 'yaw_att' in plot_row_map:
        row_idx = plot_row_map['yaw_att']
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['Yaw'], name='Actual Yaw', mode='lines', line=dict(color='blue', width=1), legendgroup='att', showlegend=False), row=row_idx, col=1)
        fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['DesYaw'], name='Desired Yaw', mode='lines', line=dict(color='red', dash='dash', width=1), legendgroup='att', showlegend=False), row=row_idx, col=1)
        fig.update_yaxes(title_text="Yaw (deg)", row=row_idx, col=1)

    # Plot 6: Altitude AMSL
    if 'alt_amsl' in plot_row_map:
        row_idx = plot_row_map['alt_amsl']
        has_amsl_data = False
        # Check for columns potentially renamed during merge (e.g., POS_Alt_AMSL_POS)
        pos_alt_col = next((col for col in df_merged.columns if col.startswith('POS_Alt_AMSL')), None)
        gps_alt_col = next((col for col in df_merged.columns if col.startswith('GPS_Alt_AMSL')), None)
        baro_alt_col = next((col for col in df_merged.columns if col.startswith('BARO_Alt_Raw')), None)

        if 'POS' in loaded_optional_types and pos_alt_col:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[pos_alt_col], name='Fused Alt (POS.Alt)', mode='lines', line=dict(color='purple', width=1), legendgroup='alt_amsl'), row=row_idx, col=1)
            has_amsl_data = True
        if 'GPS' in loaded_optional_types and gps_alt_col:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[gps_alt_col], name='GPS Alt (GPS.Alt)', mode='lines', line=dict(color='orange', dash='dot', width=1), legendgroup='alt_amsl'), row=row_idx, col=1)
            has_amsl_data = True
        if 'BARO' in loaded_optional_types and baro_alt_col:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[baro_alt_col], name='Raw Baro Alt (BARO.Alt)', mode='lines', line=dict(color='brown', dash='dashdot', width=1), legendgroup='alt_amsl'), row=row_idx, col=1)
            has_amsl_data = True
        if has_amsl_data:
            fig.update_yaxes(title_text="Altitude AMSL (m)", row=row_idx, col=1)
        else:
             # Add annotation if plot is selected but no data exists
             fig.add_annotation(text="No AMSL data loaded", xref="paper", yref="paper",
                                x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                                row=row_idx, col=1)


    # Plot 7: Altitude AGL
    if 'alt_agl' in plot_row_map:
        row_idx = plot_row_map['alt_agl']
        has_agl_data = False
        # Check for columns potentially renamed during merge
        xkf5_hagl_col = next((col for col in df_merged.columns if col.startswith('XKF5_HAGL')), None)
        pos_relhome_col = next((col for col in df_merged.columns if col.startswith('POS_RelHomeAlt_AGL')), None)
        pos_relorigin_col = next((col for col in df_merged.columns if col.startswith('POS_RelOriginAlt_AGL')), None)
        rfnd_dist_col = next((col for col in df_merged.columns if col.startswith('RFND_Dist_AGL')), None)
        terr_cheight_col = next((col for col in df_merged.columns if col.startswith('TERR_CHeight_AGL')), None)

        if 'XKF5' in loaded_optional_types and xkf5_hagl_col:
             fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[xkf5_hagl_col], name='Est HAGL (XKF5.HAGL)', mode='lines', line=dict(color='cyan', width=1), legendgroup='alt_agl'), row=row_idx, col=1)
             has_agl_data = True
        # Check both RelHomeAlt and RelOriginAlt as alternatives for AGL based on POS
        rel_alt_col = None
        rel_alt_name = None
        if 'POS' in loaded_optional_types:
            if pos_relhome_col:
                rel_alt_col = pos_relhome_col
                rel_alt_name = 'Rel Home Alt (POS.RelHomeAlt)'
            elif pos_relorigin_col:
                rel_alt_col = pos_relorigin_col
                rel_alt_name = 'Rel Origin Alt (POS.RelOriginAlt)'
            if rel_alt_col and rel_alt_name:
                fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[rel_alt_col], name=rel_alt_name, mode='lines', line=dict(color='magenta', dash='dash', width=1), legendgroup='alt_agl'), row=row_idx, col=1)
                has_agl_data = True
        if 'RFND' in loaded_optional_types and rfnd_dist_col:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[rfnd_dist_col], name='Rangefinder (RFND.Dist)', mode='lines', line=dict(color='lime', dash='dot', width=1), legendgroup='alt_agl'), row=row_idx, col=1)
            has_agl_data = True
        if 'TERR' in loaded_optional_types and terr_cheight_col:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[terr_cheight_col], name='Terrain DB Alt (TERR.CHeight)', mode='lines', line=dict(color='gold', dash='dashdot', width=1), legendgroup='alt_agl'), row=row_idx, col=1)
            has_agl_data = True
        if has_agl_data:
            fig.update_yaxes(title_text="Altitude AGL (m)", row=row_idx, col=1)
        else:
             fig.add_annotation(text="No AGL data loaded", xref="paper", yref="paper",
                                x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                                row=row_idx, col=1)


    # Plot 8: Speed
    if 'speed' in plot_row_map:
        row_idx = plot_row_map['speed']
        has_speed_data = False
        min_time = df_merged.index.min() # Use index directly
        max_time = df_merged.index.max() # Use index directly
        # Check for columns potentially renamed during merge
        arsp_speed_col = next((col for col in df_merged.columns if col.startswith('ARSP_Airspeed')), None)
        gps_speed_col = next((col for col in df_merged.columns if col.startswith('GPS_Spd_Ground')), None)

        if 'ARSP' in loaded_optional_types and arsp_speed_col:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[arsp_speed_col], name='Airspeed (ARSP)', mode='lines', line=dict(color='teal', width=1), legendgroup='speed'), row=row_idx, col=1)
            has_speed_data = True
        if 'GPS' in loaded_optional_types and gps_speed_col:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[gps_speed_col], name='Ground Speed (GPS)', mode='lines', line=dict(color='navy', dash='dash', width=1), legendgroup='speed'), row=row_idx, col=1)
            has_speed_data = True

        if has_speed_data:
            fig.update_yaxes(title_text="Speed (m/s)", row=row_idx, col=1)
            # Add stall speed line if value is provided
            if stall_speed is not None and isinstance(stall_speed, (int, float)) and stall_speed > 0:
                fig.add_shape(type="line",
                              x0=min_time, y0=stall_speed,
                              x1=max_time, y1=stall_speed,
                              line=dict(color="OrangeRed", width=2, dash="dot"),
                              row=row_idx, col=1)
                # Add annotation for the stall speed line
                fig.add_annotation(x=max_time, y=stall_speed,
                                   text=f"Stall: {stall_speed:.2f} m/s",
                                   showarrow=False,
                                   yshift=5, # Shift text slightly above the line
                                   xanchor="right",
                                   font=dict(color="OrangeRed", size=10),
                                   row=row_idx, col=1)
        else:
             fig.add_annotation(text="No Speed data loaded", xref="paper", yref="paper",
                                x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                                row=row_idx, col=1)


    # Plot 9: Battery Voltage & Current
    if 'battery' in plot_row_map:
        row_idx = plot_row_map['battery']
        has_bat_data = False
        # Check for columns potentially renamed during merge
        bat_volt_col = next((col for col in df_merged.columns if col.startswith('BAT_Volt')), None)
        bat_curr_col = next((col for col in df_merged.columns if col.startswith('BAT_Curr')), None)

        if bat_loaded and bat_volt_col and bat_curr_col:
            # Plot Voltage on primary y-axis
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[bat_volt_col], name='Voltage (BAT.Volt)',
                                     mode='lines', line=dict(color='goldenrod', width=1), legendgroup='battery'),
                          row=row_idx, col=1, secondary_y=False) # Explicitly primary axis

            # Plot Current on secondary y-axis
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[bat_curr_col], name='Current (BAT.Curr)',
                                     mode='lines', line=dict(color='firebrick', width=1), legendgroup='battery'),
                          row=row_idx, col=1, secondary_y=True) # Explicitly secondary axis
            has_bat_data = True

        if has_bat_data:
            # Update y-axis titles for this subplot
            fig.update_yaxes(title_text="Voltage (V)", row=row_idx, col=1, secondary_y=False)
            fig.update_yaxes(title_text="Current (A)", row=row_idx, col=1, secondary_y=True, showgrid=False) # Optionally hide grid for secondary
        else:
            fig.add_annotation(text="No Battery (BAT) data loaded", xref="paper", yref="paper",
                               x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                               row=row_idx, col=1)
            # Hide secondary y-axis if no data
            fig.update_yaxes(visible=False, secondary_y=True, row=row_idx, col=1)


    # --- New Plot: Distance from Home ---
    if 'dist_home' in plot_row_map:
        row_idx = plot_row_map['dist_home']
        has_dist_data = False
        # Check for the calculated column (should not have suffix from merge)
        dist_col = 'Distance_From_Home'
        if 'POS' in loaded_optional_types and dist_col in df_merged.columns:
            # Check if the column actually contains non-NaN data
            if df_merged[dist_col].notna().any():
                fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged[dist_col],
                                         name='Distance from Home', # Simpler name for legend
                                         mode='lines', line=dict(color='darkcyan', width=1.5), # Adjusted color/width
                                         legendgroup='dist_home', showlegend=True), # Show this legend item
                              row=row_idx, col=1)
                has_dist_data = True

        if has_dist_data:
            fig.update_yaxes(title_text="Distance (m)", row=row_idx, col=1)
        else:
            # Provide a more informative message if POS was loaded but distance couldn't be calculated
            reason = "(requires POS with valid Lat/Lng)" if 'POS' in loaded_optional_types else "(requires POS data)"
            fig.add_annotation(text=f"No Distance from Home data {reason}",
                               xref="paper", yref="paper",
                               x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                               row=row_idx, col=1)

    # --- New Plot: Pitch PID Output ---
    if 'pidp' in plot_row_map:
        row_idx = plot_row_map['pidp']
        has_pidp = False
        # Plot Act (actual output to servo), Tar (target), and optionally P/I/D/Effort
        if 'PIDP_Act' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDP_Act'], name='PIDP Actual Output', mode='lines', line=dict(color='blue', width=1), legendgroup='pidp'), row=row_idx, col=1)
            has_pidp = True
        if 'PIDP_Tar' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDP_Tar'], name='PIDP Target', mode='lines', line=dict(color='red', dash='dash', width=1), legendgroup='pidp'), row=row_idx, col=1)
            has_pidp = True
        if 'PIDP_P' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDP_P'], name='PIDP P', mode='lines', line=dict(color='green', dash='dot', width=1), legendgroup='pidp'), row=row_idx, col=1)
        if 'PIDP_I' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDP_I'], name='PIDP I', mode='lines', line=dict(color='orange', dash='dot', width=1), legendgroup='pidp'), row=row_idx, col=1)
        if 'PIDP_D' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDP_D'], name='PIDP D', mode='lines', line=dict(color='purple', dash='dot', width=1), legendgroup='pidp'), row=row_idx, col=1)
        if 'PIDP_Err' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDP_Err'], name='PIDP Error', mode='lines', line=dict(color='brown', dash='dash', width=1), legendgroup='pidp'), row=row_idx, col=1)
        if has_pidp:
            fig.update_yaxes(title_text="PIDP Output", row=row_idx, col=1)
        else:
            fig.add_annotation(text="No PIDP data loaded", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=14), row=row_idx, col=1)
    # --- New Plot: Roll PID Output ---
    if 'pidr' in plot_row_map:
        row_idx = plot_row_map['pidr']
        has_pidr = False
        if 'PIDR_Act' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDR_Act'], name='PIDR Actual Output', mode='lines', line=dict(color='blue', width=1), legendgroup='pidr'), row=row_idx, col=1)
            has_pidr = True
        if 'PIDR_Tar' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDR_Tar'], name='PIDR Target', mode='lines', line=dict(color='red', dash='dash', width=1), legendgroup='pidr'), row=row_idx, col=1)
            has_pidr = True
        if 'PIDR_P' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDR_P'], name='PIDR P', mode='lines', line=dict(color='green', dash='dot', width=1), legendgroup='pidr'), row=row_idx, col=1)
        if 'PIDR_I' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDR_I'], name='PIDR I', mode='lines', line=dict(color='orange', dash='dot', width=1), legendgroup='pidr'), row=row_idx, col=1)
        if 'PIDR_D' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDR_D'], name='PIDR D', mode='lines', line=dict(color='purple', dash='dot', width=1), legendgroup='pidr'), row=row_idx, col=1)
        if 'PIDR_Err' in df_merged.columns:
            fig.add_trace(go.Scatter(x=df_merged.index, y=df_merged['PIDR_Err'], name='PIDR Error', mode='lines', line=dict(color='brown', dash='dash', width=1), legendgroup='pidr'), row=row_idx, col=1)
        if has_pidr:
            fig.update_yaxes(title_text="PIDR Output", row=row_idx, col=1)
        else:
            fig.add_annotation(text="No PIDR data loaded", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=14), row=row_idx, col=1)

    # --- New Plot: Flight Mode ---
    if 'flight_mode' in plot_row_map:
        row_idx = plot_row_map['flight_mode']
        has_flight_mode_data = False
        # Check for the flight mode column - using ModeNum instead of MODE_FlightMode
        flight_mode_col = 'ModeNum'  # Direct column name from MODE.csv

        if flight_mode_col in df_merged.columns:
            # Create a copy of the mode data for plotting
            mode_data = df_merged[flight_mode_col].copy()
            
            # Plot the mode line
            fig.add_trace(go.Scatter(x=df_merged.index, y=mode_data, name='Flight Mode', 
                                   mode='lines', line=dict(color='purple', width=1), 
                                   legendgroup='flight_mode'), row=row_idx, col=1)
            
            # Add annotations for mode changes
            mode_changes = mode_data.diff().ne(0)
            for idx in mode_data[mode_changes].index:
                mode_value = mode_data[idx]
                # Skip NaN values
                if pd.isna(mode_value):
                    continue
                mode_num = int(mode_value)
                mode_name = FLIGHT_MODES.get(mode_num, f'Unknown Mode {mode_num}')
                fig.add_annotation(
                    x=idx,
                    y=mode_num,
                    text=mode_name,
                    showarrow=True,
                    arrowhead=1,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor='purple',
                    ax=0,
                    ay=-40,
                    font=dict(size=10, color='purple'),
                    row=row_idx,
                    col=1
                )
            
            has_flight_mode_data = True

        if has_flight_mode_data:
            # Update y-axis to show mode names
            fig.update_yaxes(
                title_text="Flight Mode",
                ticktext=list(FLIGHT_MODES.values()),
                tickvals=list(FLIGHT_MODES.keys()),
                row=row_idx,
                col=1
            )
        else:
            fig.add_annotation(text="No Flight Mode data loaded", xref="paper", yref="paper",
                              x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                              row=row_idx, col=1)

    # --- New Plot: Optical Flow ---
    if 'optical_flow' in plot_row_map:
        row_idx = plot_row_map['optical_flow']
        has_of_data = False
        if 'OF' in loaded_optional_types:
            if 'OF_flowX' in df_merged.columns and 'OF_flowY' in df_merged.columns:
                fig.add_trace(go.Scatter(
                    x=df_merged.index, y=df_merged['OF_flowX'],
                    name='Optical Flow X', mode='lines', line=dict(color='blue', width=1),
                    legendgroup='optical_flow'
                ), row=row_idx, col=1)
                fig.add_trace(go.Scatter(
                    x=df_merged.index, y=df_merged['OF_flowY'],
                    name='Optical Flow Y', mode='lines', line=dict(color='red', width=1),
                    legendgroup='optical_flow'
                ), row=row_idx, col=1)
                has_of_data = True
            if 'OF_bodyX' in df_merged.columns and 'OF_bodyY' in df_merged.columns:
                fig.add_trace(go.Scatter(
                    x=df_merged.index, y=df_merged['OF_bodyX'],
                    name='Body X', mode='lines', line=dict(color='orange', width=1, dash='dot'),
                    legendgroup='optical_flow'
                ), row=row_idx, col=1)
                fig.add_trace(go.Scatter(
                    x=df_merged.index, y=df_merged['OF_bodyY'],
                    name='Body Y', mode='lines', line=dict(color='green', width=1, dash='dot'),
                    legendgroup='optical_flow'
                ), row=row_idx, col=1)
                has_of_data = True
            if 'OF_Qual' in df_merged.columns:
                fig.add_trace(go.Scatter(
                    x=df_merged.index, y=df_merged['OF_Qual'],
                    name='Quality', mode='lines', line=dict(color='purple', width=1, dash='dash'),
                    legendgroup='optical_flow'
                ), row=row_idx, col=1)
                has_of_data = True
        if has_of_data:
            fig.update_yaxes(title_text="Optical Flow", row=row_idx, col=1)
        else:
            fig.add_annotation(
                text="No Optical Flow data loaded", xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                row=row_idx, col=1
            )

    # --- OF Roll Calibration Plot ---
    if 'of_calib_roll' in plot_row_map:
        row_idx = plot_row_map['of_calib_roll']
        has_data = False
        # Check for required columns
        if 'OF_flowX' in df_merged.columns and 'OF_bodyX' in df_merged.columns and 'GyrX' in df_merged.columns:
            fig.add_trace(go.Scatter(
                x=df_merged.index, y=df_merged['OF_flowX'],
                name='flowX', mode='lines', line=dict(color='red', width=1),
                legendgroup='of_calib_roll'
            ), row=row_idx, col=1)
            fig.add_trace(go.Scatter(
                x=df_merged.index, y=df_merged['OF_bodyX'],
                name='bodyX', mode='lines', line=dict(color='green', width=1),
                legendgroup='of_calib_roll'
            ), row=row_idx, col=1)
            fig.add_trace(go.Scatter(
                x=df_merged.index, y=df_merged['GyrX'],
                name='GyrX', mode='lines', line=dict(color='blue', width=1),
                legendgroup='of_calib_roll'
            ), row=row_idx, col=1)
            has_data = True
        if has_data:
            fig.update_yaxes(title_text="Output", row=row_idx, col=1)
        else:
            fig.add_annotation(
                text="OF.flowX, OF.bodyX, or IMU.GyrX missing", xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                row=row_idx, col=1
            )
    # --- OF Pitch Calibration Plot ---
    if 'of_calib_pitch' in plot_row_map:
        row_idx = plot_row_map['of_calib_pitch']
        has_data = False
        if 'OF_flowY' in df_merged.columns and 'OF_bodyY' in df_merged.columns and 'GyrY' in df_merged.columns:
            fig.add_trace(go.Scatter(
                x=df_merged.index, y=df_merged['OF_flowY'],
                name='flowY', mode='lines', line=dict(color='red', width=1),
                legendgroup='of_calib_pitch'
            ), row=row_idx, col=1)
            fig.add_trace(go.Scatter(
                x=df_merged.index, y=df_merged['OF_bodyY'],
                name='bodyY', mode='lines', line=dict(color='green', width=1),
                legendgroup='of_calib_pitch'
            ), row=row_idx, col=1)
            fig.add_trace(go.Scatter(
                x=df_merged.index, y=df_merged['GyrY'],
                name='GyrY', mode='lines', line=dict(color='blue', width=1),
                legendgroup='of_calib_pitch'
            ), row=row_idx, col=1)
            has_data = True
        if has_data:
            fig.update_yaxes(title_text="Output", row=row_idx, col=1)
        else:
            fig.add_annotation(
                text="OF.flowY, OF.bodyY, or IMU.GyrY missing", xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False, font=dict(size=14),
                row=row_idx, col=1
            )

    # --- Update Layout ---
    plot_title = f'Flight Analysis: {log_identifier}'
    fig.update_layout(
        title_text=plot_title,
        # Height is now controlled dynamically via style prop of dcc.Graph
        hovermode='x unified',
        legend_title_text='Measurements',
        legend=dict(tracegroupgap=10), # Add gap between legend groups
        margin=dict(l=60, r=20, t=50, b=50) # Adjust margins
    )

    # Update x-axis title on the bottom-most plot
    fig.update_xaxes(title_text="Timestamp", row=num_rows, col=1)


    return fig # Return the figure object


# --- Create Notes Section for Dash Layout ---
def create_notes_section(loaded_optional_types):
    """Generates HTML components for notes."""
    notes_list = []
    if 'RCIN' in loaded_optional_types:
        notes_list.extend([
            html.H3("--- Channel Assumptions ---", style={'margin-top': '20px'}),
            html.P("RCIN: Assumed C1=Roll, C2=Pitch"),
            html.P("Verify these against your ArduPilot RCMAP parameters."),
            html.Hr()
        ])

    notes_list.extend([
        html.H3("--- Altitude & Distance Notes ---", style={'margin-top': '20px'}), # Updated Title
        html.P("AMSL = Above Mean Sea Level, AGL = Above Ground Level (estimated or measured)"),
        html.P("POS.Alt = Fused Altitude (EKF), GPS.Alt = Raw GPS Altitude"),
        html.P("XKF5.HAGL = EKF Height Above Ground Estimate"),
        html.P("POS.RelHomeAlt/RelOriginAlt = Altitude relative to takeoff point (AGL)"), # Clarified AGL
        html.P("RFND.Dist = Raw Rangefinder distance (AGL)"), # Clarified AGL
        html.P("BARO.Alt = Raw Barometer altitude (can drift with temperature, relative to power-on)"), # Added context
        html.P("TERR.CHeight = Altitude relative to terrain database (AGL)"), # Clarified AGL
        # Add note for Distance from Home
        html.P("Distance from Home = Horizontal distance calculated from first valid POS Lat/Lng (meters)."),
        html.Hr()
    ])

    # Add Battery Notes if BAT data was loaded
    if 'BAT' in loaded_optional_types:
        notes_list.extend([
            html.H3("--- Battery Notes ---", style={'margin-top': '20px'}),
            html.P("BAT.Volt: Measured battery voltage."),
            html.P("BAT.Curr: Measured total current draw from the battery."),
            html.Hr()
        ])

    if 'OF' in loaded_optional_types:
        notes_list.extend([
            html.H3("--- Optical Flow Notes ---", style={'margin-top': '20px'}),
            html.P("OF_flowX/Y: Optical flow sensor readings (X/Y axes)."),
            html.P("OF_bodyX/Y: Body frame optical flow (X/Y axes)."),
            html.P("OF_Qual: Quality metric for optical flow."),
            html.Hr()
        ])

    return html.Div(notes_list, style={'textAlign': 'left', 'marginLeft': '20px', 'marginRight': '20px'})


# --- Create Messages Table Function ---
def create_messages_table(df_merged):
    """Creates a Dash DataTable component for displaying messages."""
    if df_merged is None or df_merged.empty:
        return html.Div("No message data available")
        
    # Check for message columns
    msg_col = 'MSG_Message'
    if msg_col not in df_merged.columns:
        return html.Div("No message data available")
        
    # Create a copy of the message data
    msg_data = df_merged[[msg_col]].copy()
    msg_data = msg_data.dropna(subset=[msg_col])
    
    if msg_data.empty:
        return html.Div("No messages found")
    
    # Format timestamps for display
    msg_data = msg_data.reset_index()
    msg_data['timestamp'] = msg_data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]  # Format with milliseconds
    
    # Create the table with styling
    return html.Div([
        dash.dash_table.DataTable(
            id='messages-table',
            columns=[
                {'name': 'Timestamp', 'id': 'timestamp', 'type': 'text'},
                {'name': 'Message', 'id': msg_col, 'type': 'text'}  # Use msg_col as the id
            ],
            data=msg_data.to_dict('records'),
            style_table={
                'overflowX': 'auto',
                'border': '1px solid #ddd',
                'borderRadius': '5px',
                'marginTop': '20px'
            },
            style_cell={
                'textAlign': 'left',
                'padding': '10px',
                'whiteSpace': 'normal',
                'height': 'auto',
                'fontFamily': 'monospace',  # Use monospace font for better readability
                'fontSize': '14px'
            },
            style_header={
                'backgroundColor': 'rgb(230, 230, 230)',
                'fontWeight': 'bold',
                'border': '1px solid #ddd',
                'textAlign': 'center'
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': 'rgb(248, 248, 248)'
                },
                {
                    'if': {'row_index': 'even'},
                    'backgroundColor': 'white'
                }
            ],
            sort_action='native',
            sort_mode='single',
            filter_action='native',
            style_data={
                'whiteSpace': 'normal',
                'height': 'auto',
                'lineHeight': '15px',
                'border': '1px solid #ddd'
            },
            # Add tooltips for long messages
            tooltip_data=[
                {
                    msg_col: {'value': str(row[msg_col]), 'type': 'markdown'}  # Use msg_col here too
                } for row in msg_data.to_dict('records')
            ],
            tooltip_delay=0,
            tooltip_duration=None,
            # Enable column resizing
            column_selectable=False,
            row_selectable=False,
            # Add export button
            export_format='csv',
            export_headers='display',
            # Add search box
            filter_options={'case': 'insensitive'},
            # Add sorting controls
            sort_by=[{'column_id': 'timestamp', 'direction': 'desc'}],  # Sort by timestamp descending by default
        ),
        # Add a note about the table
        html.Div([
            html.P("Note: Messages are sorted by timestamp in descending order. Use the search box to filter messages.",
                  style={'fontStyle': 'italic', 'marginTop': '10px', 'color': '#666'})
        ])
    ])


# --- Main Application Logic ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze MAVLink flight data using a Dash web application.")

    # Required arguments
    parser.add_argument("--att-csv", required=True, help="Path to the input ATT CSV file (e.g., CSV_OUTPUT/log.ATT.csv)")
    parser.add_argument("--imu-csv", required=True, help="Path to the input IMU CSV file (e.g., CSV_OUTPUT/log.IMU.csv)")

    # Optional arguments (Uses OPTIONAL_COLS_TO_SELECT keys implicitly via csv_files dict)
    parser.add_argument("--rcin-csv", help="Path to the input RCIN CSV file (e.g., CSV_OUTPUT/log.RCIN.csv)")
    parser.add_argument("--pos-csv", help="Path to the input POS CSV file (e.g., CSV_OUTPUT/log.POS.csv)")
    parser.add_argument("--gps-csv", help="Path to the input GPS CSV file (e.g., CSV_OUTPUT/log.GPS.csv)")
    parser.add_argument("--arsp-csv", help="Path to the input ARSP CSV file (e.g., CSV_OUTPUT/log.ARSP.csv)")
    parser.add_argument("--xkf5-csv", help="Path to the input XKF5 CSV file (e.g., CSV_OUTPUT/log.XKF5.csv)")
    parser.add_argument("--rfnd-csv", help="Path to the input RFND CSV file (e.g., CSV_OUTPUT/log.RFND.csv)")
    parser.add_argument("--baro-csv", help="Path to the input BARO CSV file (e.g., CSV_OUTPUT/log.BARO.csv)")
    parser.add_argument("--terr-csv", help="Path to the input TERR CSV file (e.g., CSV_OUTPUT/log.TERR.csv)")
    parser.add_argument("--bat-csv", help="Path to the input BAT CSV file (e.g., CSV_OUTPUT/log.BAT.csv)")
    parser.add_argument("--pidp-csv", help="Path to the input PIDP CSV file (e.g., CSV_OUTPUT/log.PIDP.csv)")
    parser.add_argument("--pidr-csv", help="Path to the input PIDR CSV file (e.g., CSV_OUTPUT/log.PIDR.csv)")
    parser.add_argument("--mode-csv", help="Path to the input MODE CSV file (e.g., CSV_OUTPUT/log.MODE.csv)")
    parser.add_argument("--msg-csv", help="Path to the input MSG CSV file (e.g., CSV_OUTPUT/log.MSG.csv)")  # Added MSG argument
    parser.add_argument("--of-csv", help="Path to the input OF CSV file (e.g., CSV_OUTPUT/log.OF.csv)")

    # Dash specific arguments
    parser.add_argument("--host", default="127.0.0.1", help="Host address to run the Dash server on.")
    parser.add_argument("--port", default="8050", type=int, help="Port to run the Dash server on.")


    args = parser.parse_args()

    # --- Prepare Filepaths Dictionary ---
    csv_files = {
        'ATT': args.att_csv,
        'IMU': args.imu_csv,
        'RCIN': args.rcin_csv,
        'POS': args.pos_csv,
        'GPS': args.gps_csv,
        'ARSP': args.arsp_csv,
        'XKF5': args.xkf5_csv,
        'RFND': args.rfnd_csv,
        'BARO': args.baro_csv,
        'TERR': args.terr_csv,
        'BAT': args.bat_csv,
        'PIDP': args.pidp_csv,
        'PIDR': args.pidr_csv,
        'MODE': args.mode_csv,    # New
        'MSG': args.msg_csv,    # Added MSG argument
        'OF': args.of_csv,
    }
    # Filter out None values before passing to function
    csv_files_provided = {k: v for k, v in csv_files.items() if v is not None}


    # --- Determine Log Identifier ---
    att_basename = os.path.basename(args.att_csv)
    log_identifier = att_basename.split('.')[0] if '.' in att_basename else att_basename

    # --- Load and Merge Data using the imported function ---
    print("Loading and merging data...")
    df_merged, loaded_opts = load_and_merge_data(csv_files_provided)

    if df_merged is None or df_merged.empty:
        print("Failed to load or merge sufficient data. Cannot start Dash app.")
        # Optionally create an empty placeholder figure or just exit
        # For now, we exit as the app is useless without data.
        sys.exit(1)

    # --- Serialize data for storage ---
    # Convert timestamp index back to a column and then to ISO format string
    df_merged_reset = df_merged.reset_index()
    df_merged_reset['timestamp'] = df_merged_reset['timestamp'].apply(lambda ts: ts.isoformat())
    stored_data = df_merged_reset.to_dict(orient='split') # Store with timestamp as column
    stored_loaded_opts = json.dumps(loaded_opts) # Simple list, JSON is fine

    # --- Create Notes ---
    # Create notes section once, as it depends only on initially loaded types
    notes_section = create_notes_section(loaded_opts)

    # --- Initialize Dash App ---
    app = dash.Dash(__name__)
    app.title = f"Flight Analysis: {log_identifier}" # Browser tab title

    # --- Define App Layout ---
    app.layout = html.Div([
        # Data Storage
        dcc.Store(id='flight-data-store', data=stored_data),
        dcc.Store(id='loaded-opts-store', data=stored_loaded_opts),
        dcc.Store(id='log-identifier-store', data=log_identifier),
        dcc.Download(id="download-graph-html"), # Add the Download component

        # Header
        html.H1(f"Flight Analysis: {log_identifier}", style={'textAlign': 'center'}),

        # Control Panel
        html.Div([
            # Plot Checklist
            html.Div([
                html.Label("Select Plots:", style={'fontWeight': 'bold'}),
                dcc.Checklist(
                    id='plot-checklist',
                    options=[{'label': name, 'value': key} for key, name in PLOT_DEFINITIONS.items()],
                    value=DEFAULT_PLOTS, # Initially select all
                    inline=True, # Display horizontally
                    style={'margin': '10px'}
                ),
            ], style={'display': 'block', 'marginBottom': '15px'}),

            # Sliders and Inputs Row
            html.Div([
                # Graph Height Slider
                html.Div([
                     html.Label("Graph Height:", style={'fontWeight': 'bold'}),
                     dcc.Slider(
                        id='height-slider',
                        min=400,
                        max=2400,
                        step=100,
                        value=800, # Initial height
                        marks={i: str(i) for i in range(400, 2401, 200)},
                        tooltip={"placement": "bottom", "always_visible": True}
                    ),
                ], style={'display': 'inline-block', 'width': '400px', 'verticalAlign': 'middle', 'marginRight': '40px'}),

                # Stall Speed Input
                html.Div([
                    html.Label("Stall Speed (m/s):", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Input(
                        id='stall-speed-input',
                        type='number',
                        value=13.89, # Default stall speed
                        min=0,
                        step=0.1,
                        style={'width': '80px'}
                    ),
                ], style={'display': 'inline-block', 'verticalAlign': 'middle', 'marginRight': '40px'}), # Added margin

                # Export Button
                html.Div([
                    html.Button("Export Plot to HTML", id="export-button", n_clicks=0)
                ], style={'display': 'inline-block', 'verticalAlign': 'middle'}) # New div for export button

            ], style={'display': 'block'}) # Container for sliders/inputs/button

        ], style={'textAlign': 'center', 'marginBottom': '20px', 'padding': '15px', 'border': '1px solid #ddd', 'borderRadius': '5px'}),

        # Graph Area
        dcc.Loading( # Add loading indicator while graph updates
            id="loading-graph",
            type="circle", # or "default" or "cube" or "dot"
            children=[
                dcc.Graph(
                    id='flight-graph',
                    # Figure is now generated by callback
                    # Initial height set via style in callback
                )
            ]
        ),

        # Messages Table Section
        html.Div([
            html.H3("Flight Log Messages", style={'textAlign': 'center', 'marginTop': '30px'}),
            html.Div(id='messages-table-container')
        ]),

        # Notes Section
        notes_section # Add the notes below the graph
    ])

    # --- Define Callbacks ---
    @callback(
        Output('flight-graph', 'figure'),
        Output('flight-graph', 'style'), # Output to update style (height)
        Input('plot-checklist', 'value'),
        Input('height-slider', 'value'),
        Input('stall-speed-input', 'value'), # Add stall speed input
        State('flight-data-store', 'data'),
        State('loaded-opts-store', 'data'),
        State('log-identifier-store', 'data')
    )
    def update_graph(selected_plots, graph_height, stall_speed, stored_data, stored_loaded_opts, log_id): # Added stall_speed parameter
        if stored_data is None:
            # Handle case where data hasn't loaded or is empty
            return go.Figure(), {'height': f'{graph_height}px'} # Return empty figure

        # Deserialize data
        # Recreate DataFrame from dict (orient='split')
        df = pd.DataFrame(stored_data['data'], columns=stored_data['columns'])
        # Convert timestamp back to datetime objects and set as index
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True) # Ensure sorted index

        loaded_opts_list = json.loads(stored_loaded_opts)

        print(f"Updating graph. Selected plots: {selected_plots}, Height: {graph_height}, Stall Speed: {stall_speed}") # Debug print

        # Create the figure using the selected plots, data, and stall speed
        fig = create_flight_figure(df, loaded_opts_list, selected_plots, log_id, stall_speed) # Pass stall_speed

        # Define the style dictionary including the dynamic height
        graph_style = {'height': f'{graph_height}px'}

        return fig, graph_style

    # --- New Callback for Exporting ---
    @callback(
        Output('download-graph-html', 'data'),
        Input('export-button', 'n_clicks'),
        State('flight-graph', 'relayoutData'),  # <-- now a State again
        State('plot-checklist', 'value'),
        State('height-slider', 'value'),
        State('stall-speed-input', 'value'),
        State('flight-data-store', 'data'),
        State('loaded-opts-store', 'data'),
        State('log-identifier-store', 'data'),
        prevent_initial_call=True # Don't run this callback when the app starts
    )
    def export_graph_html(n_clicks, relayout_data, selected_plots, graph_height, stall_speed, stored_data, stored_loaded_opts, log_id):
        if stored_data is None:
            return no_update # Or potentially send a notification if you add a notification component

        print(f"Export button clicked ({n_clicks} times). Generating HTML...")

        # Deserialize data (same as update_graph)
        df = pd.DataFrame(stored_data['data'], columns=stored_data['columns'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True) # Ensure sorted index
        loaded_opts_list = json.loads(stored_loaded_opts)

        # --- Filter by x-axis range if set in relayoutData ---
        if relayout_data is not None:
            x_range = None
            # Plotly sometimes uses 'xaxis.range' or 'xaxis.range[0]'/'xaxis.range[1]'
            if 'xaxis.range' in relayout_data:
                x_range = relayout_data['xaxis.range']
            elif 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                x_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
            if x_range:
                # Convert to pandas Timestamp for filtering
                start, end = pd.to_datetime(x_range[0]), pd.to_datetime(x_range[1])
                df = df[(df.index >= start) & (df.index <= end)]

        # Create the figure using the current settings
        fig = create_flight_figure(df, loaded_opts_list, selected_plots, log_id, stall_speed)

        # --- Crucial: Set the height in the figure's layout for export ---
        # The height applied via 'style' to dcc.Graph doesn't affect to_html()
        fig.update_layout(height=graph_height)

        # Generate HTML content
        # full_html=True creates a standalone file
        # include_plotlyjs='cdn' links to Plotly.js online, keeping file size smaller
        html_content = fig.to_html(full_html=True, include_plotlyjs='cdn')

        # Define filename
        filename = f"{log_id}_flight_analysis_export.html"

        print(f"Sending file '{filename}' for download.")
        # Return data for dcc.Download
        return dict(content=html_content, filename=filename)

    # --- Add Callback for Messages Table ---
    @callback(
        Output('messages-table-container', 'children'),
        Input('flight-data-store', 'data')
    )
    def update_messages_table(stored_data):
        if stored_data is None:
            return html.Div("No data available")
        
        # Deserialize data
        df = pd.DataFrame(stored_data['data'], columns=stored_data['columns'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        return create_messages_table(df)

    # --- Run Dash Server ---
    print("\n" + "="*50)
    print(f" Starting Dash server on http://{args.host}:{args.port}")
    print(" Press CTRL+C to stop the server")
    print("="*50 + "\n")
    try:
        # Setting debug=False is recommended for production/sharing
        # Setting debug=True enables hot-reloading and error messages in browser
        app.run(debug=False, host=args.host, port=args.port)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\nError: Port {args.port} is already in use.")
            print("Please stop the existing process using that port or specify a different port using --port <number>.")
        else:
            print(f"\nAn OS error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred while trying to start the server: {e}")
        sys.exit(1) 