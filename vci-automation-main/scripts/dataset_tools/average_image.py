# ruff: noqa: T201, INP001
import os

import cv2
import numpy as np


def average_images(input_folder):
    # Check if the input folder exists
    if not os.path.exists(input_folder):
        print("Input folder not found.")
        return

    # Get list of image files in the input folder
    image_files = [
        file for file in os.listdir(input_folder) if file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))
    ]

    if not image_files:
        print("No image files found in the input folder.")
        return

    # Read the first image to get dimensions
    first_image_path = os.path.join(input_folder, image_files[0])
    first_image = cv2.imread(first_image_path)
    height, width, channels = first_image.shape

    # Initialize a numpy array to store the sum of all images
    sum_image = np.zeros((height, width, channels), dtype=np.float32)

    # Loop through each image and add it to the sum
    for indx, image_file in enumerate(image_files):
        print(f"{indx}/{len(image_files)}")
        image_path = os.path.join(input_folder, image_file)
        image = cv2.imread(image_path).astype(np.float32)
        sum_image += image

    # Calculate the average image
    num_images = len(image_files)
    average_image = (sum_image / num_images).astype(np.uint8)

    # Save the average image
    output_path = os.path.join(input_folder, "average_image.jpg")
    cv2.imwrite(output_path, average_image)
    print(f"Average image saved at: {output_path}")

    # Display or save the average image
    cv2.imshow("Average Image", average_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    input_folder = input("Enter the path to the folder containing images: ")
    average_images(input_folder)
