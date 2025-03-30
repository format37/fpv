# pip install pandas plotly "kaleido>=0.1.0,<0.2.0" imageio imageio-ffmpeg tqdm # Use specific kaleido range for better compatibility initially
python flight_video_generator.py \
        --att-csv CSV_OUTPUT/00000053.ATT.csv \
        --imu-csv CSV_OUTPUT/00000053.IMU.csv \
        --pos-csv CSV_OUTPUT/00000053.POS.csv \
        --arsp-csv CSV_OUTPUT/00000053.ARSP.csv \
        --gps-csv CSV_OUTPUT/00000053.GPS.csv \
        --xkf5-csv CSV_OUTPUT/00000053.XKF5.csv \
        --bat-csv CSV_OUTPUT/00000053.BAT.csv \
        --plots roll_att pitch_att alt_agl speed battery \
        --width 640 \
        --height 1080 \
        --fps 50 \
        --window 20 \
        --stall-speed 13.9 \
        --start-time "2025-03-29 16:21:30.000" \
        --end-time "2025-03-29 16:22:30.000" \
        --output my_flight_video.mp4

# --- Time and Frame Limiting Examples ---
        # Example 1: Generate only the first 50 frames (approx 1 second at 50fps)
        # --start-frame 0 --max-frames 50 \
        # Example 2: Start generation 100 frames in, generate max 50 frames
        # --start-frame 100 --max-frames 50 \
        # Example 3: Generate video between specific timestamps (requires knowing log times)
        # Replace with actual timestamps from your log, e.g., using UTC from ATT.TimeUS
        # --start-time "2023-10-27 10:30:15.000" \
        # --end-time "2023-10-27 10:30:45.500" \
        # Example 4: Use time limits AND frame limits (frames relative to time window)
        # --start-time "2023-10-27 10:30:15.000" \
        # --end-time "2023-10-27 10:30:45.500" \
        # --start-frame 10 --max-frames 100 \ # Start 10 frames into the 30.5s clip, generate max 100 frames
        # --- Current Settings ---