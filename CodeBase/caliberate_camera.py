#!/usr/bin/env python3
"""
calibrate_camera_charuco.py

Runs OpenCV camera calibration on a folder of ChArUco board images and writes 
camera_matrix + distortion_coefficients to a YAML file that the C++ MAVROS 
precision-landing node loads via cv::FileStorage (~camera_calib_file param).

Default spec (A4 Printable Board):
    7x9 squares, 25mm square size (0.025m), 18mm marker size (0.018m), DICT_5X5_50

Usage:
    python3 calibrate_camera.py --images-dir calib_images --squares-x 7 \
        --squares-y 9 --square-size 0.025 --marker-size 0.018 \
        --dictionary DICT_5X5_50 --out camera_calibration.yaml
"""

import argparse
import glob
import os

import cv2
import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--images-dir", default="calib_images")
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
    p.add_argument("--out", default="camera_calibration.yaml")
    p.add_argument("--visualize", action="store_true",
                    help="Show detected ChArUco corners on each image before solving")
    return p.parse_args()


def get_aruco_dictionary(dict_name):
    # Retrieve the correct dictionary mapping from OpenCV
    attr = getattr(cv2.aruco, dict_name, None)
    if attr is None:
        raise ValueError(f"Invalid ArUco dictionary name: {dict_name}")
    return cv2.aruco.getPredefinedDictionary(attr)


def main():
    args = parse_args()

    # Define board parameters
    try:
        dictionary = get_aruco_dictionary(args.dictionary)
    except ValueError as e:
        print(e)
        return

    # Create the ChArUco Board physical layout in memory
    board = cv2.aruco.CharucoBoard(
        (args.squares_x, args.squares_y),
        args.square_size,
        args.marker_size,
        dictionary
    )
    
    # Create Detector Parameters
    # Using CHARUCO detection requires a detector setup in modern OpenCV 4.x+
    detector_params = cv2.aruco.DetectorParameters()
    charuco_params = cv2.aruco.CharucoParameters()
    
    # Group detector together
    detector = cv2.aruco.CharucoDetector(board, charuco_params, detector_params)

    # Containers for global 3D/2D correspondences
    all_charuco_corners = []
    all_charuco_ids = []

    image_files = sorted(glob.glob(os.path.join(args.images_dir, "*.png")) +
                          glob.glob(os.path.join(args.images_dir, "*.jpg")))
    if len(image_files) < 10:
        raise RuntimeError(
            f"Only found {len(image_files)} images in {args.images_dir}. "
            "Need at least ~15-20 for a reliable calibration."
        )

    img_size = None
    used = 0

    for fname in image_files:
        img = cv2.imread(fname)
        if img is None:
            print(f"Skipping unreadable file: {fname}")
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if img_size is None:
            img_size = gray.shape[::-1]  # (width, height)
        elif gray.shape[::-1] != img_size:
            print(f"Skipping {fname}: resolution mismatch with earlier images "
                  f"({gray.shape[::-1]} vs {img_size}). Calibrate one "
                  "resolution at a time.")
            continue

        # Detect ChArUco corners
        # This modern API automatically detects markers, interpolates corners,
        # and filters out weak detections
        charuco_corners, charuco_ids, marker_corners, marker_ids = detector.detectBoard(gray)

        # We need at least 4 successfully interpolated corners to use this view
        if charuco_corners is not None and len(charuco_corners) >= 4:
            all_charuco_corners.append(charuco_corners)
            all_charuco_ids.append(charuco_ids)
            used += 1

            if args.visualize:
                vis = img.copy()
                cv2.aruco.drawDetectedCornersCharuco(vis, charuco_corners, charuco_ids)
                cv2.imshow("ChArUco Corners", vis)
                cv2.waitKey(200)
        else:
            print(f"Not enough ChArUco corners detected in {fname}, skipping.")

    if args.visualize:
        cv2.destroyAllWindows()

    print(f"Using {used}/{len(image_files)} images for calibration.")
    if used < 10:
        raise RuntimeError("Too few successful detections to calibrate reliably. "
                           "Try capturing cleaner, sharper images closer to the lens.")

    # Rational distortion model (8 coeffs) handles wide-FOV FPV lenses better
    # than the default 5-coefficient model.
    flags = cv2.CALIB_RATIONAL_MODEL

    # Calibrate using ChArUco-specific geometry solver
    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
        charucoCorners=all_charuco_corners,
        charucoIds=all_charuco_ids,
        board=board,
        imageSize=img_size,
        cameraMatrix=None,
        distCoeffs=None,
        flags=flags
    )

    print("\n=== Calibration Results ===")
    print(f"RMS reprojection error: {rms:.4f} px "
          f"({'GOOD' if rms < 0.5 else 'ACCEPTABLE' if rms < 1.0 else 'POOR -- recapture images'})")
    print("Camera matrix:\n", camera_matrix)
    print("Distortion coefficients:\n", dist_coeffs.ravel())

    # Write in OpenCV FileStorage format so the C++ node can parse it directly
    fs = cv2.FileStorage(args.out, cv2.FILE_STORAGE_WRITE)
    fs.write("image_width", img_size[0])
    fs.write("image_height", img_size[1])
    fs.write("camera_matrix", camera_matrix)
    fs.write("distortion_coefficients", dist_coeffs)
    fs.write("rms_reprojection_error", rms)
    fs.release()
    print(f"\nSaved calibration to {args.out}")
    print("Point the MAVROS node's ~camera_calib_file param at this file.")


if __name__ == "__main__":
    main()
