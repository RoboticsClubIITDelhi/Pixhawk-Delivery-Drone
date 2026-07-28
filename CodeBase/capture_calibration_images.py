#!/usr/bin/env python3
"""
capture_calibration_images.py

Captures frames from the camera (or capture card device) for later use in
calibrate_camera.py. Shows a live preview with ChArUco-corner overlay
so you can confirm detection before saving each frame.

Usage:
    python3 capture_calibration_images.py --device 0 --squares-x 7 --squares-y 9 \
        --square-size 0.025 --marker-size 0.018 --dictionary DICT_5X5_50 \
        --out-dir calib_images

Controls (with preview window focused):
    SPACE  - save current frame (only if at least 4 ChArUco corners are detected)
    q      - quit
"""

import argparse
import os
import time

import cv2


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="0",
                    help="Camera index (e.g. 0) or video device path/URL")
    p.add_argument("--squares-x", type=int, default=7,
                    help="Number of squares along the width (X axis)")
    p.add_argument("--squares-y", type=int, default=9,
                    help="Number of squares along the height (Y axis)")
    p.add_argument("--square-size", type=float, default=0.025,
                    help="ChArUco board square edge length in meters")
    p.add_argument("--marker-size", type=float, default=0.018,
                    help="ChArUco board inner marker edge length in meters")
    p.add_argument("--dictionary", default="DICT_5X5_50",
                    help="OpenCV ArUco dictionary name")
    p.add_argument("--out-dir", default="calib_images")
    return p.parse_args()


def get_aruco_dictionary(dict_name):
    attr = getattr(cv2.aruco, dict_name, None)
    if attr is None:
        raise ValueError(f"Invalid ArUco dictionary name: {dict_name}")
    return cv2.aruco.getPredefinedDictionary(attr)


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    # Resolve video device index/path
    device = int(args.device) if args.device.isdigit() else args.device
    cap = cv2.VideoCapture(device)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open capture device {device}")

    # Set up the ChArUco Board physical layout in memory
    try:
        dictionary = get_aruco_dictionary(args.dictionary)
    except ValueError as e:
        print(e)
        return

    board = cv2.aruco.CharucoBoard(
        (args.squares_x, args.squares_y),
        args.square_size,
        args.marker_size,
        dictionary
    )

    # Instantiate detector objects using modern OpenCV 4.x+ API
    detector_params = cv2.aruco.DetectorParameters()
    charuco_params = cv2.aruco.CharucoParameters()
    detector = cv2.aruco.CharucoDetector(board, charuco_params, detector_params)

    saved_count = 0
    print("Press SPACE to save a frame (works when ChArUco corners are detected in green).")
    print("Press q to quit.")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame grab failed, retrying...")
            time.sleep(0.1)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect ChArUco board features
        charuco_corners, charuco_ids, _, _ = detector.detectBoard(gray)

        # We need at least 4 successfully interpolated corners to solve calibration math later
        found = charuco_corners is not None and len(charuco_corners) >= 4

        display = frame.copy()
        if found:
            # Draw detected ChArUco corners with their ID annotations
            cv2.aruco.drawDetectedCornersCharuco(display, charuco_corners, charuco_ids)

        # Display helper text overlays
        status_text = f"Saved: {saved_count}  Corners Detected: {len(charuco_corners) if charuco_corners is not None else 0}"
        cv2.putText(display, status_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0) if found else (0, 0, 255), 2)
        cv2.imshow("ChArUco Calibration Capture", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '):
            if found:
                fname = os.path.join(args.out_dir, f"calib_{saved_count:03d}.png")
                cv2.imwrite(fname, frame)
                saved_count += 1
                print(f"Saved {fname} (with {len(charuco_corners)} corners)")
            else:
                print("Insufficient ChArUco corners detected! Need at least 4 corners to capture.")

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. {saved_count} frames saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
