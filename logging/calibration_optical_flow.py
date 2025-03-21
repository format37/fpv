import pandas as pd
import os
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse

def plot_optical_flow_and_imu(of_file, imu_file, rfnd_file=None, output_file=None):
    """
    Plot optical flow, IMU, and rangefinder data from CSV files using interactive Plotly
    
    Args:
        of_file: Path to optical flow CSV file
        imu_file: Path to IMU CSV file
        rfnd_file: Path to rangefinder CSV file (optional)
        output_file: Optional path to save the HTML plot
    """
    # Read the CSV files
    of_data = pd.read_csv(of_file)
    imu_data = pd.read_csv(imu_file)
    
    # Read rangefinder data if provided
    has_rfnd = False
    if rfnd_file and os.path.exists(rfnd_file):
        rfnd_data = pd.read_csv(rfnd_file)
        has_rfnd = True

    # Group by TimeUS and calculate mean for the OF data
    of_grouped = of_data.groupby('TimeUS').agg({
        'flowX': 'mean',
        'bodyX': 'mean',
        'flowY': 'mean',
        'bodyY': 'mean'
    }).reset_index()

    # Group by TimeUS and calculate mean for the IMU data
    imu_grouped = imu_data.groupby('TimeUS').agg({
        'GyrX': 'mean',
        'GyrY': 'mean',
        'GyrZ': 'mean'
    }).reset_index()
    
    # Determine number of rows based on available data
    num_rows = 3
    if has_rfnd:
        num_rows += 2  # Add two more rows for Dist and Quality
    
    # Create a subplot figure
    subplot_titles = ['X-axis Data', 'Y-axis Data', 'Z-axis Data']
    if has_rfnd:
        subplot_titles.extend(['Rangefinder Distance', 'Rangefinder Quality'])
    
    fig = make_subplots(rows=num_rows, cols=1, 
                        shared_xaxes=True,
                        subplot_titles=subplot_titles,
                        vertical_spacing=0.1)
    
    # Add X-axis data (Row 1)
    fig.add_trace(go.Scatter(
        x=of_grouped['TimeUS'], 
        y=of_grouped['flowX'],
        mode='lines',
        name='OF.flowX'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=of_grouped['TimeUS'], 
        y=of_grouped['bodyX'],
        mode='lines',
        name='OF.bodyX'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=imu_grouped['TimeUS'], 
        y=imu_grouped['GyrX'],
        mode='lines',
        name='IMU.GyrX'
    ), row=1, col=1)
    
    # Add Y-axis data (Row 2)
    fig.add_trace(go.Scatter(
        x=of_grouped['TimeUS'], 
        y=of_grouped['flowY'],
        mode='lines',
        name='OF.flowY'
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=of_grouped['TimeUS'], 
        y=of_grouped['bodyY'],
        mode='lines',
        name='OF.bodyY'
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=imu_grouped['TimeUS'], 
        y=imu_grouped['GyrY'],
        mode='lines',
        name='IMU.GyrY'
    ), row=2, col=1)
    
    # Add Z-axis data (Row 3)
    fig.add_trace(go.Scatter(
        x=imu_grouped['TimeUS'], 
        y=imu_grouped['GyrZ'],
        mode='lines',
        name='IMU.GyrZ'
    ), row=3, col=1)
    
    # Add RFND data if available
    if has_rfnd:
        # Add Rangefinder Distance (Row 4)
        fig.add_trace(go.Scatter(
            x=rfnd_data['TimeUS'], 
            y=rfnd_data['Dist'],
            mode='lines',
            name='RFND.Dist'
        ), row=4, col=1)
        
        # Add Rangefinder Quality (Row 5)
        fig.add_trace(go.Scatter(
            x=rfnd_data['TimeUS'], 
            y=rfnd_data['Quality'],
            mode='lines',
            name='RFND.Quality'
        ), row=5, col=1)
    
    # Update layout
    fig.update_layout(
        title='Optical Flow, IMU, and Rangefinder Data Comparison',
        xaxis_title='Time (μs)' if not has_rfnd else None,
        xaxis3_title=None if has_rfnd else 'Time (μs)',
        xaxis5_title='Time (μs)' if has_rfnd else None,
        yaxis_title='Value',
        hovermode='closest',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        width=2000,
        height=2200
    )
    
    # Save the interactive plot as HTML if output file is specified
    if output_file:
        fig.write_html(output_file)
    
    # Display the plot
    fig.show()

if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description='Plot optical flow, IMU, and rangefinder data from CSV files')
    parser.add_argument('--of', type=str, required=True, help='Path to optical flow CSV file')
    parser.add_argument('--imu', type=str, required=True, help='Path to IMU CSV file')
    parser.add_argument('--rfnd', type=str, help='Path to rangefinder CSV file (optional)')
    parser.add_argument('--output', '-o', type=str, help='Path to save the HTML plot (optional)')
    
    args = parser.parse_args()
    
    # Check if files exist
    if not os.path.exists(args.of):
        print(f"Error: {args.of} not found!")
    elif not os.path.exists(args.imu):
        print(f"Error: {args.imu} not found!")
    else:
        plot_optical_flow_and_imu(args.of, args.imu, args.rfnd, args.output)
