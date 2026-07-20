from __future__ import annotations

import colour
import cv2
import numpy as np

COLOUR_CORRECTION_METHOD = 0
# colour-science implements three colour correction methods.
COLOUR_CORRECTION_METHOD_NAMES = ["Cheung 2004", "Finlayson 2015", "Vandermonde"]
COLOUR_CORRECTION_METHOD = COLOUR_CORRECTION_METHOD_NAMES[COLOUR_CORRECTION_METHOD]

COLOR_DIM = 3


class ColorCalibrator:

    def __init__(self) -> None:
        # Colour Fitting
        self.REFERENCE_COLOUR_CHECKER = colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
        self.colour_checker_rows = self.REFERENCE_COLOUR_CHECKER.rows
        self.colour_checker_columns = self.REFERENCE_COLOUR_CHECKER.columns

        # reference swatches of the color_checker board.
        # provided in xyY format -> convert to XYZ -> convert to linear RGB
        self.REFERENCE_SWATCHES = colour.XYZ_to_RGB(
            colour.xyY_to_XYZ(list(self.REFERENCE_COLOUR_CHECKER.data.values())),
            "sRGB",
            self.REFERENCE_COLOUR_CHECKER.illuminant,
        )

        self.REFERENCE_SWATCHES_XYZ = colour.xyY_to_XYZ(list(self.REFERENCE_COLOUR_CHECKER.data.values()))

    def detect_aruco_and_color_patches(
        self, image: np.array, padding: float, annotation_info: str = "", marker_ids: None | list[int] = None
    ) -> tuple[list, np.array]:
        if marker_ids is None:
            marker_ids = [0, 1, 2, 3]
        annotation_overlay = np.zeros(image.shape, dtype=np.float32)

        # Detect Aruco markers in grayscale image
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == COLOR_DIM else image
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        corners, ids, _ = detector.detectMarkers((np.array(gray) * 255).astype(np.uint8))
        if ids is None:  # could not find markers
            cv2.putText(
                annotation_overlay,
                f"{annotation_info} No Color Checker Found",
                (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                3,
                (0.8, 0.8, 0.8),
                5,
            )
            return None, annotation_overlay

        # Draw detected markers on the image
        annotation_overlay = cv2.aruco.drawDetectedMarkers(annotation_overlay, corners, ids)
        cv2.putText(
            annotation_overlay, f"{annotation_info}", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 3, (0.8, 0.8, 0.8), 5
        )

        # Ensure all desired markers are detected
        ids = ids.flatten()
        if not all(marker_id in ids for marker_id in marker_ids):
            return None, annotation_overlay

        # Get the corners of the detected markers
        detected_corners = dict(zip(ids, corners))

        patch_rows = 4
        patch_cols = 6
        patch_size = 40  # mm

        # Define board corners in the canonical (flattened) view
        canonical_corners = np.array(
            [
                [0, 0],  # Top-left
                [patch_cols * patch_size, 0],  # Top-right
                [patch_cols * patch_size, patch_rows * patch_size],  # Bottom-right
                [0, patch_rows * patch_size],  # Bottom-left
            ],
            dtype=np.float32,
        )

        # Get the detected corners of the markers
        marker_corners = []
        for marker_id, reference_corner in zip(marker_ids, [1, 0, 3, 2]):
            # reference corner determines which corner of the marker defines the bounding box of the color checker grid
            marker_corners.append(detected_corners[marker_id][0][reference_corner])  # Get corner of each marker
        marker_corners = np.array(marker_corners).astype(np.float32)

        # Estimate homography
        homography, _ = cv2.findHomography(marker_corners, canonical_corners)

        pad = patch_size * padding

        # Draw the color patch grid

        sampled_colors = []
        patch_positions = []
        for row in range(patch_rows):
            for col in range(patch_cols):
                x_start = col * patch_size + pad
                x_end = (col + 1) * patch_size - pad
                y_start = row * patch_size + pad
                y_end = (row + 1) * patch_size - pad

                # Define the padded patch in canonical space
                canonical_patch = np.array(
                    [
                        [x_start, y_start],
                        [x_end, y_start],
                        [x_end, y_end],
                        [x_start, y_end],
                    ],
                    dtype=np.float32,
                )

                patch_corners_original = cv2.perspectiveTransform(
                    canonical_patch[None, :, :], np.linalg.inv(homography)
                )[0]

                # Extract the bounding box of the patch
                x_min, y_min = np.min(patch_corners_original, axis=0).astype(int)
                x_max, y_max = np.max(patch_corners_original, axis=0).astype(int)

                # Extract and sample color in the patch region
                patch = image[y_min:y_max, x_min:x_max]
                if patch.size == 0:  # Skip empty regions
                    sampled_colors.append((0, 0, 0))
                    continue

                avg_color = patch.mean(axis=(0, 1))
                sampled_colors.append(avg_color)

                patch_positions.append(patch_corners_original)
                # Fill the patch with the average color
                c = float(avg_color) if np.isscalar(avg_color) else tuple(map(float, avg_color))
                cv2.fillPoly(annotation_overlay, [patch_corners_original.astype(int)], color=c)
                cv2.polylines(
                    annotation_overlay,
                    [patch_corners_original.astype(int)],
                    isClosed=True,
                    color=(0, 1, 0),
                    thickness=1,
                )
                cv2.putText(
                    annotation_overlay,
                    f"{len(sampled_colors) - 1}",
                    (x_min, y_min),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.3,
                    (0.8, 0.8, 0.8),
                    1,
                )

        return sampled_colors, annotation_overlay

    def generate_aruco_markers(
        self,
        output_dir: str = "./aruco_markers",
        marker_size_mm: int = 30,
        dpi: int = 300,
        marker_ids: list[int] | None = None,
    ) -> None:
        # Define the ArUco dictionary
        if marker_ids is None:
            marker_ids = [0, 1, 2, 3]
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

        # Calculate marker size in pixels
        marker_size_inch = marker_size_mm / 25.4  # Convert mm to inches
        marker_size_pixels = int(marker_size_inch * dpi)

        for marker_id in marker_ids:
            # Generate the marker
            marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size_pixels)

            # Create an image with a white border
            border_size = marker_size_pixels // 10  # 10% of marker size
            bordered_img = cv2.copyMakeBorder(
                marker_img,
                border_size,
                border_size,
                border_size,
                border_size,
                cv2.BORDER_CONSTANT,
                value=(255, 255, 255),
            )

            # Save the marker as a PNG file
            output_path = f"{output_dir}/aruco_marker_{marker_id}.png"
            cv2.imwrite(output_path, bordered_img)

    def calcualte_white_balance(self, swatches: np.array) -> np.array:
        # perform white balance with one of the gray swatches
        white_swatch = swatches[18]  # white swatch
        reference_white = self.REFERENCE_SWATCHES[18]
        # get white balance coefficients.
        wb_coefficients = reference_white / white_swatch
        # normalize coefficients, sallest scalar is 1. Image tends to get lightened somewhat
        return wb_coefficients * (1 / wb_coefficients.min())

    def calcualte_color_matrix(self, swatches: np.array, method: str = "Cheung 2004") -> np.array:
        return colour.matrix_colour_correction(swatches, self.REFERENCE_SWATCHES, method)

    def calibrate_color(
        self, image: np.array, padding: float = 0.7, method: str = "Cheung 2004", annotation_info: str = ""
    ) -> tuple[np.array | None, np.array | None, np.array | None, np.array]:
        swatches, annotation_overlay = self.detect_aruco_and_color_patches(image, padding, annotation_info)
        if swatches is None:
            return None, None, None, annotation_overlay
        swatches = np.array(swatches)

        if image.ndim == COLOR_DIM:
            white_balance = self.calcualte_white_balance(swatches)
            correction_matrix = self.calcualte_color_matrix(swatches * white_balance, method)
            return white_balance, correction_matrix, swatches, annotation_overlay
        # for IR images we still want the swatches so we can check the camera brightness
        return None, None, swatches, annotation_overlay
