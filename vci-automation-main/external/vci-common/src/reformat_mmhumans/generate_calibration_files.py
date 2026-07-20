import os
import json
import argparse
import numpy as np
import xml.etree.ElementTree as ET
from xml.dom import minidom
from PIL import Image

def generate_mapping(input_folder_path, image_fn, mapping_fn):
    """
    Generates a mapping from image base names (e.g., "C0001") to incremental IDs (e.g., "1", "2", ...).
    Only image files found in the specified folder are considered; other camera sources are ignored.

    Parameters:
        input_folder_path (str): Path to the parent folder containing the image folder and the output mapping file.
        image_fn (str): Name of the subfolder that contains the image files (e.g., "images").
        mapping_fn (str): Name of the output JSON file to save the generated mapping (e.g., "mapping.json").

    Returns:
        None: Saves the mapping as a JSON file in the specified location.
    """
    image_folder = os.path.join(input_folder_path, image_fn)
    mapping_file_path = os.path.join(input_folder_path, mapping_fn)
    
    # List and sort image files with .png or .jpg extensions
    files = sorted([f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg'))])
    
    # Create a mapping from image filename (without extension) to an index-based string
    mapping = {os.path.splitext(f)[0]: str(i + 1) for i, f in enumerate(files)}
    
    # Save mapping to a JSON file
    with open(mapping_file_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4)
    
    print(f"Mapping file saved to {mapping_file_path}")
    

def apply_mask(input_folder_path, image_fn, mask_fn, output_fn, mask_prefix, mask_suffix, threshold=1):
    """
    Applies a binary or soft mask to RGB images. For each image, the corresponding mask is used to retain
    foreground pixels and make the background transparent.

    Parameters:
        input_folder_path (str): The base folder containing image and mask subfolders.
        image_fn (str): The subfolder name containing input images.
        mask_fn (str): The subfolder name containing masks.
        output_fn (str): The subfolder name where masked images will be saved.
        mask_prefix (str): Prefix to identify the corresponding mask file for each image.
        mask_suffix (str): Suffix (including file extension, e.g., ".png") to identify the corresponding mask file.
        threshold (int, optional): Threshold for binarizing the mask (0–255). If negative, no thresholding is applied.
                                   Default is 1.

    Returns:
        None: Masked images are saved in the specified output folder as transparent PNGs.
    """
    image_folder = os.path.join(input_folder_path, image_fn)
    output_folder = os.path.join(input_folder_path, output_fn)
    mask_folder = os.path.join(input_folder_path, mask_fn)
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for file_name in os.listdir(image_folder):
        if file_name.endswith('.jpg') or file_name.endswith('.png'):
            base_name = os.path.splitext(file_name)[0]
            mask_name = f"{mask_prefix}{base_name}{mask_suffix}"
            image_path = os.path.join(image_folder, file_name)
            mask_path = os.path.join(mask_folder, mask_name)

            if os.path.exists(mask_path):
                # Load image and mask
                image = Image.open(image_path).convert('RGBA')
                mask = Image.open(mask_path).convert('L')  # Grayscale mask

                # Binarize mask if threshold is specified
                if threshold >= 0:
                    binary_mask = mask.point(lambda p: 255 if p > threshold else 0)
                else:
                    binary_mask = mask

                # Use the binary mask as an alpha channel to mask the image
                masked_image = Image.composite(image, Image.new('RGBA', image.size, (0, 0, 0, 0)), binary_mask)

                # Save the masked image as PNG to preserve transparency
                output_path = os.path.join(output_folder, f"{base_name}.png")
                masked_image.save(output_path)
                print(f"Saved masked image: {output_path}")
            else:
                print(f"No matching mask found: {mask_path} for image {file_name}")


def extract_calibration_data(json_file_name, folder_path):
    """
    Extracts raw calibration data from a JSON file located in the given folder.

    Parameters:
        json_file_name (str): Name of the JSON file containing calibration data (must include ".json").
        folder_path (str): Path to the folder where the JSON file is located.

    Returns:
        dict or None: Raw calibration data as loaded from the file. Returns None if the file does not exist.
    """
    json_file_path = os.path.join(folder_path, json_file_name)
    if not os.path.exists(json_file_path):
        print(f"Error: The JSON file '{json_file_path}' does not exist.")
        return None

    with open(json_file_path, "r") as json_file:
        raw_data = json.load(json_file)

    print(f"Extracted raw calibration data from {json_file_path}.")
    return raw_data


def translate_to_numpy(raw_data, id_mapping, scale_factor_intrinsics):
    """
    Converts raw calibration data into NumPy matrices. Optionally remaps camera IDs
    to a new set using the provided mapping. Intrinsic parameters are scaled by the
    given scale factor.

    Parameters:
        raw_data (dict): Raw calibration data loaded from a JSON file.
        id_mapping (dict or None): Mapping from original camera IDs (e.g., "C0001") to new IDs.
                                   If None, original IDs are used without remapping.
        scale_factor_intrinsics (float): Scale factor to adjust intrinsic parameters (e.g., for resized images).

    Returns:
        dict or None: Dictionary of calibration data indexed by the new camera IDs.
                      Each entry contains NumPy arrays for intrinsics, extrinsics, and other parameters.
                      Returns None if the input data is invalid.
    """
    if raw_data is None or "cameras" not in raw_data:
        print("Error: No valid camera data provided.")
        return None

    numpy_data = {}

    for camera in raw_data["cameras"]:
        old_camera_id = camera.get("camera_id", "Unknown")

        # Determine new camera ID
        if id_mapping is not None:
            if old_camera_id not in id_mapping:
                print(f"Warning: Old camera ID '{old_camera_id}' not found in the provided mapping.")
                continue  # Skip cameras not in the mapping
            new_camera_id = id_mapping[old_camera_id]
        else:
            new_camera_id = old_camera_id

        # Extrinsics
        view_matrix = np.array(camera["extrinsics"]["view_matrix"]).reshape(4, 4)

        # Intrinsics
        camera_matrix = np.array(camera["intrinsics"]["camera_matrix"]).reshape(3, 3)
        camera_matrix[0, 0] *= scale_factor_intrinsics  # fx
        camera_matrix[1, 1] *= scale_factor_intrinsics  # fy
        camera_matrix[0, 2] *= scale_factor_intrinsics  # cx
        camera_matrix[1, 2] *= scale_factor_intrinsics  # cy

        # Additional intrinsics
        color_correction_matrix = np.array(camera["intrinsics"]["color_correction_matrix"]).reshape(3, 3)
        distortion_coefficients = np.array(camera["intrinsics"]["distortion_coefficients"])
        white_balance_coefficients = np.array(camera["intrinsics"]["white_balance_coefficients"])
        resolution = np.array(camera["intrinsics"]["resolution"]) * scale_factor_intrinsics

        # Store all processed parameters
        numpy_data[new_camera_id] = {
            "view_matrix": view_matrix,
            "camera_matrix": camera_matrix,
            "color_correction_matrix": color_correction_matrix,
            "distortion_coefficients": distortion_coefficients,
            "white_balance_coefficients": white_balance_coefficients,
            "resolution": resolution
        }

    print("Translated calibration data to NumPy matrices and remapped camera IDs.")
    return numpy_data


def format_calibration_data_to_xml(numpy_data, output_file_name, folder_path, nb_cameras):
    """
    Converts calibration data in NumPy format into an XML structure compatible with the millimetric humans code.
    The XML contains projection, intrinsic, extrinsic, and distortion parameters for each camera.

    Distortion coefficients K1, K2, K3 (radial) and P1, P2 (tangential) are explicitly set to zero
    in the output, even if values are present in the input data.

    Parameters:
        numpy_data (dict): Calibration data for each camera, where values are NumPy matrices or arrays.
        output_file_name (str): Desired name of the output XML file (should include ".xml").
        folder_path (str): Path to the folder where the XML file will be saved.
        nb_cameras (int): Total number of cameras to include in the XML metadata.

    Returns:
        None: The function writes the resulting XML file to disk.
    """
    if numpy_data is None:
        print("Error: No NumPy data provided for formatting.")
        return None

    root = ET.Element("CalibrationResult")

    # Add general information about the number of cameras
    info = ET.SubElement(root, "Information")
    info.set("nbCamera", str(nb_cameras))

    for camera_id, data in numpy_data.items():
        # Create a Camera element with ID and resolution
        camera = ET.SubElement(root, "Camera", id=str(camera_id),
                               width=str(int(data["resolution"][0])),
                               height=str(int(data["resolution"][1])))

        # Extract camera parameters
        K = data["camera_matrix"]
        R = data["view_matrix"][:3, :3]
        T = data["view_matrix"][:3, 3].reshape(3, 1)

        # Compute the projection matrix P = K [R | T]
        RT = np.hstack((R, T))
        P = K @ RT
        ET.SubElement(camera, "P").text = " ".join(map(str, P.flatten()))

        # Add intrinsic matrix K
        ET.SubElement(camera, "K").text = " ".join(map(str, K.flatten()))

        # Add rotation matrix R
        ET.SubElement(camera, "R").text = " ".join(map(str, R.flatten()))

        # Add translation vector T
        ET.SubElement(camera, "T").text = " ".join(map(str, T.flatten()))

        # Extract principal point (Cx, Cy) from K
        Cx, Cy = K[0, 2], K[1, 2]

        # Force distortion parameters to zero regardless of input values
        distortion = data["distortion_coefficients"]
        K1, K2, K3, P1, P2 = distortion[:5]
        K1, K2, K3 = 0.0, 0.0, 0.0  # Radial distortion
        P1, P2 = 0.0, 0.0          # Tangential distortion

        # Add Distortion parameters
        distortion_elem = ET.SubElement(camera, "Distortion")
        distortion_elem.set("K1", str(K1))
        distortion_elem.set("K2", str(K2))
        distortion_elem.set("K3", str(K3))
        distortion_elem.set("P1", str(P1))
        distortion_elem.set("P2", str(P2))
        distortion_elem.set("Cx", str(Cx))
        distortion_elem.set("Cy", str(Cy))

    # Generate pretty-printed XML
    output_file_path = os.path.join(folder_path, output_file_name)
    tree = ET.ElementTree(root)
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

    # Write to file
    with open(output_file_path, "w") as f:
        f.write(xml_str)

    print(f"Calibration data saved in XML format at: {output_file_path}")


def generate_sequence_xml(input_folder_path, image_folder_fn, output_file_name, id_mapping, nb_cameras, jpg=True):
    """
    Generates a sequence XML file for camera image mapping. The generated XML contains
    information about the cameras and the images captured by each camera, based on
    the provided ID mapping. This is used in the context of the mmHumans project
    to track which images correspond to which cameras.

    Parameters:
        input_folder_path (str): Path to the folder containing the images.
        image_folder_fn (str): The folder name containing the images (images are filtered by camera IDs).
        output_file_name (str): Name of the output XML file.
        id_mapping (dict): A mapping from old camera IDs (e.g., "C0001") to new camera IDs (e.g., 1, 2, ...).
        nb_cameras (int): The number of cameras in the setup.
        jpg (bool): Whether to look for .jpg files (default is True). If False, looks for .png files.

    Returns:
        None: The function writes the XML data to a file in the specified folder.
    """
    root = ET.Element("Video")

    # Add general information about the video sequence
    info = ET.SubElement(root, "Information")
    info.set("nbCamera", str(nb_cameras))
    info.set("fps", "30")  # Frame rate set to 30fps by default
    info.set("beginId", "0")  # Default begin ID
    info.set("endId", "0")  # Default end ID

    # Get the list of all image files in the specified image folder
    image_files = os.listdir(os.path.join(input_folder_path, image_folder_fn))

    # Process each camera ID mapping
    for old_id, new_id in id_mapping.items():
        # Filter files that contain the old camera ID in their name
        filtered_files = [f for f in image_files if str(old_id) in f]

        if not filtered_files:
            print(f"Warning: No images found for Camera ID {old_id}")
            continue  # Skip cameras without matching images

        # Create the Camera element for each mapped camera
        camera_elem = ET.SubElement(root, "Camera", id=str(new_id))
        camera_elem.set("path", image_folder_fn)  # Path to the folder with images
        camera_elem.set("fileNameFormat", filtered_files[0])  # Set filename format (e.g., first matching image)

    # Construct the full path for the output XML file
    output_file_path = os.path.join(input_folder_path, output_file_name)

    # Convert the ElementTree to a string and pretty-print it
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

    # Write the pretty-printed XML to the output file
    with open(output_file_path, "w") as f:
        f.write(xml_str)

    print(f"Sequence XML saved as {output_file_path}")

def generate_calibration_and_sequence_files(
        input_folder_path, calibration_input, mapping, scale_factor, 
        calibration_output_fn, sequence_nomask_fn, sequence_masked_fn, 
        image_nomask_fn, image_masked_fn, onlymasks):
    """
    Generates calibration and sequence XML files by extracting, translating, and formatting data.
    It processes camera calibration data, applies scaling, and creates sequence files for both masked
    and unmasked images based on the provided mapping.

    Parameters:
        input_folder_path (str): Path to the folder containing input and output files.
        calibration_input (str): Name of the input calibration JSON file.
        mapping (str): Name of the camera mapping file (JSON) containing old-to-new camera ID mapping.
        scale_factor (float): Scaling factor to apply to the camera calibration data (affects resolution and intrinsics).
        calibration_output_fn (str): Name of the output XML file for storing the formatted calibration data.
        sequence_nomask_fn (str): Name of the output sequence XML file for unmasked images.
        sequence_masked_fn (str): Name of the output sequence XML file for masked images.
        image_nomask_fn (str): Folder name containing unmasked image files.
        image_masked_fn (str): Folder name containing masked image files.
        onlymasks (bool): If True, only generates the sequence for masked images, skipping the unmasked sequence.

    Returns:
        None: The function saves the generated XML files to the specified output path.
    """

    # Load the existing camera mapping from the specified mapping file
    mapping_path = os.path.join(input_folder_path, mapping)
    nb_cameras = 0
    if os.path.exists(mapping_path):    
        with open(mapping_path, 'r') as f:
            id_mapping = json.load(f)  # Load the camera ID mapping from the JSON file.
            nb_cameras = len(id_mapping)  # Get the number of cameras based on the mapping.
            print(f"{nb_cameras} cameras found in mapping file.")
    else:
        print(f"Mapping file not found under {mapping_path}")
        return None  # Return if the mapping file is missing

    # Extract raw calibration data from the input JSON file
    raw_data = extract_calibration_data(calibration_input, input_folder_path)

    # Convert raw calibration data to NumPy matrices, adjusting for camera IDs and applying scaling
    numpy_data = translate_to_numpy(raw_data, id_mapping, scale_factor)

    if numpy_data is None:
        print("Error: Calibration data could not be processed.")
        return  # Exit if calibration data could not be generated

    # Format and save the calibration data as an XML file
    format_calibration_data_to_xml(numpy_data, calibration_output_fn, input_folder_path, nb_cameras)
    
    # Generate sequence XML files for both masked and unmasked images
    if not onlymasks:
        # Generate sequence XML for unmasked images
        generate_sequence_xml(input_folder_path, image_nomask_fn, sequence_nomask_fn, id_mapping, nb_cameras)
    
    # Always generate sequence XML for masked images (even if onlymasks is True)
    generate_sequence_xml(input_folder_path, image_masked_fn, sequence_masked_fn, id_mapping, nb_cameras, jpg=False)


def generate_schedule_file(folder_path, schedule_file_name, masked):
    """
    Creates a schedule file in JSON format with default values for LOD (Levels of Detail) settings.
    The function includes configuration options for learning rates, regularization weights, and more
    for each LOD level. Additionally, if `masked` is True, it adjusts the "MaskCarvingReg" in the 
    LOD4 configuration.

    Parameters:
        folder_path (str): Path to the folder where the schedule file will be saved.
        schedule_file_name (str): Name of the output schedule JSON file.
        masked (bool): Whether the schedule should include an adjusted "MaskCarvingReg" for LOD4. 

    Returns:
        None: The function saves the schedule data to the specified file.
    """
    
    # Create a dictionary with default schedule values for each LOD (Level of Detail)
    schedule_data = {
        "num_lods": 5,
        "LOD4": {
            "LearningRate": 0.01,
            "Beta1": 0.9,
            "Beta2": 0.995,
            "MLPLearningRate": 0.01,
            "MLPbeta1": 0.9,
            "MLPbeta2": 0.995,
            "PhotometricLossWeight": 4.0,
            "EikonalReg": 0.01,
            "TSDFSmoothingReg": 0.005,
            "FeaturesLaplacianReg": 0.005,
            "ColorSmoothingReg": 0.005,
            "SmoothNormalReg": 0.005,
            "ColorCorrectSmoothnessReg": 10.0,
            "MaskReg": 0.0,
            "MaskCarvingReg": 0.0,
            "NonStickReg": 0.0,
            "BinarizationReg2D": 0.0,
            "BinarizationReg3D": 0.0,
            "batch_size": 2,
            "iterations": 2000,
            "density": 15.0,
            "GaussianSigma": 0.8,
            "TSDFInverseSlope": 4.0,
            "MinStepSize": 0.1,
            "MaxStepSize": 0.5,
            "TransmittanceStep": 0.1,
            "AllocationLimit": 1.75,
            "OutsideMaskLossWeight": 1.0
        },
        "LOD3": {
            "LearningRate": 0.01,
            "MLPLearningRate": 0.01,
            "iterations": 3000,
            "density": [7.5, 15.0],
            "TSDFSmoothingReg": 0.005,
            "EikonalReg": 0.01,
            "SmoothNormalReg": 0.005,
            "FeaturesLaplacianReg": 0.005,
            "ColorSmoothingReg": 0.005,
            "ColorCorrectSmoothnessReg": 4.0
        },
        "LOD2": {
            "LearningRate": 0.01,
            "MLPLearningRate": 0.01,
            "iterations": 3000,
            "density": [10.0, 20.0],
            "TSDFSmoothingReg": 0.005,
            "EikonalReg": 0.01,
            "SmoothNormalReg": 0.005,
            "FeaturesLaplacianReg": 0.005,
            "ColorSmoothingReg": 0.005
        },
        "LOD1": {
            "LearningRate": 0.01,
            "MLPLearningRate": 0.01,
            "iterations": 3000,
            "density": [10.0, 20.0],
            "TSDFSmoothingReg": 0.08,
            "EikonalReg": 0.16,
            "SmoothNormalReg": 0.08,
            "FeaturesLaplacianReg": 0.08,
            "ColorSmoothingReg": 0.08
        },
        "LOD0": {
            "LearningRate": [0.01, 0.001],
            "MLPLearningRate": [0.01, 0.001],
            "iterations": 1000,
            "density": [15.0, 30.0],
            "TSDFSmoothingReg": 0.08,
            "EikonalReg": 0.16,
            "SmoothNormalReg": 0.08,
            "FeaturesLaplacianReg": 0.08,
            "ColorSmoothingReg": 0.08,
            "batch_size": 4
        }
    }

    # If masked is True, adjust the MaskCarvingReg for LOD4
    if masked:
        schedule_data["LOD4"]["MaskCarvingReg"] = 0.0025

    # Construct the full path for the schedule file to be saved
    schedule_file_path = os.path.join(folder_path, schedule_file_name)

    # Write the default schedule data to a JSON file
    with open(schedule_file_path, 'w') as json_file:
        json.dump(schedule_data, json_file, indent=4)

    print(f"Created default schedule file: {schedule_file_name}")


def generate_scene_config_txt(input_folder_path, scene_config_file_name, calibration_output_fn, schedule_file_name, sequence_file_name, backgrounds_fn, masked):
    """
    Generates the scene_config_undistorted.txt file with dynamic values based on the provided arguments.
    
    Parameters:
        input_folder_path (str): The folder containing the images (path).
        output_file_name (str): Calibration file name.
        schedule_file_name (str): Schedule file name.
        sequence_file_name (str): Sequence file name.
        scene_config_file_name (str): Name of the scene config file to generate.
    
    Returns:
        None: The function saves the scene configuration to the specified file.
    """
    
    # Construct the export directory path
    export_dir = os.path.abspath(os.path.join(input_folder_path, "results"))
    
    # Define the full path for the scene config file to be generated
    scene_config_path = os.path.join(input_folder_path, scene_config_file_name)
    
    # Open and write to the scene config file
    with open(scene_config_path, "w") as f:
        f.write(f"DifferentialRendering#OptimizeColorCorrection bool 1\n")
        f.write(f"DifferentialRendering#OptimizeWithinLightSpots bool 1\n")
        
        # Camera settings (assuming 4 cameras here for example) (to be honest, I dont know what it does)
        f.write(f"DifferentialRendering#activeCameras{0} ivec4 -1 -1 15 0\n")
        f.write(f"DifferentialRendering#testCameras{0} ivec4 -1 -1 15 0\n")
        
        for i in range(1,4):  
            f.write(f"DifferentialRendering#activeCameras{i} ivec4 0 0 0 0\n")
            f.write(f"DifferentialRendering#testCameras{i} ivec4 0 0 0 0\n")
        
        # Reconstruction volume settings
        # Note: Reconstruction volume needs to be adjusted if the object to be reconstructed changes.
        f.write(f"ReconstructionVolume#GroundHeight float 0.035\n")
        f.write(f"ReconstructionVolume#RemoveGround bool 1\n")
        f.write(f"ReconstructionVolume#VolumeExtent vec3 5.0 2.0 5.0\n")
        f.write(f"ReconstructionVolume#VolumeMinCorner vec3 -2.0 0.0 -2.0\n")
        f.write(f"ReconstructionVolume#VoxelSize float 2.0\n")
        
        # Scene reference frame settings
        # Note: The scene scale, translation, and rotation are subject to change 
        # if the camera configuration changes (e.g., number or placement of cameras).
        f.write(f"SceneReferenceFrame#FrustumsLength float 1\n")
        f.write(f"SceneReferenceFrame#ScaleMatrixRow0 vec4 1.0 0.0 0.0 0.0\n")
        f.write(f"SceneReferenceFrame#ScaleMatrixRow1 vec4 0.0 1.0 0.0 0.0\n")
        f.write(f"SceneReferenceFrame#ScaleMatrixRow2 vec4 0.0 0.0 1.0 0.0\n")
        f.write(f"SceneReferenceFrame#ScaleMatrixRow3 vec4 0.0 0.0 0.0 1.0\n")
        f.write(f"SceneReferenceFrame#SceneRotation vec3 0.0 0.0 90.0\n")
        f.write(f"SceneReferenceFrame#SceneScale float 0.5\n")
        f.write(f"SceneReferenceFrame#SceneTranslation vec3 0.5 0.15 2.4\n")
        
        # Window settings
        f.write(f"Window#BackgroundColor vec4 0.0 0.0 0.0 1.0\n")
        f.write(f"Window#BackgroundsDir string {backgrounds_fn}\n")
        
        # Calibration file name (dynamic)
        f.write(f"Window#CalibrationFile string {calibration_output_fn}\n")
        
        # Export directory path (dynamic)
        f.write(f"Window#ExportDir string {export_dir}\n")
        
        f.write(f"Window#ExportMeshes bool 1\n")
        f.write(f"Window#ExportRenders bool 1\n")
        f.write(f"Window#ExportVolumetricData bool 1\n")
        f.write(f"Window#MLP_FEATURES int 8\n")
        f.write(f"Window#RawImages bool 0\n")
        
        # Schedule file name (dynamic)
        f.write(f"Window#ScheduleFile string {schedule_file_name}\n")
        
        # Sequence file name (dynamic)
        f.write(f"Window#SequenceFile string {sequence_file_name}\n")
        
        f.write(f"Window#SkipVisualHull bool 0\n")
        f.write(f"Window#USE_REFLECTED_VEC bool 1\n")
        f.write(f"Window#UseBackgrounds bool {int(not masked)}\n") # Only use Backgrounds in non-masked environment
        f.write(f"Window#UseMasks bool 0\n")
        f.write(f"Window#imagePyramidLevels int 5\n")
        f.write(f"Window#segmentationPyramidLevel int 1\n")
    
    print(f"Scene configuration saved as {scene_config_path}")


def get_input_with_default(prompt, default_value, valid_check=None):
    """
    Prompt the user for input and return the value. If the user presses enter without providing input,
    return the default_value. Optionally validate the input using valid_check.
    """
    while True:
        user_input = input(f"{prompt} (default: {default_value}): ")
        user_input = user_input if user_input else default_value
        if valid_check and not valid_check(user_input):
            print("Invalid input, please try again.")
            continue
        return user_input

def valid_folder(path):
    """Check if the path is a valid folder."""
    return os.path.isdir(path)

def valid_json(path):
    """Check if the path is a valid file."""
    return path.endswith(".json")

def valid_bool_input(input_str):
    """Check if the input is either 'yes' or 'no' (case insensitive)."""
    return input_str.lower() in ['true', 'false', 't', 'f']

import readline

#!/usr/bin/python

import pathlib


def complete_path(text, state):
    incomplete_path = pathlib.Path(text)
    if incomplete_path.is_dir():
        completions = [p.as_posix() for p in incomplete_path.iterdir()]
    elif incomplete_path.exists():
        completions = [incomplete_path]
    else:
        exists_parts = pathlib.Path('.')
        for part in incomplete_path.parts:
            test_next_part = exists_parts / part
            if test_next_part.exists():
                exists_parts = test_next_part

        completions = []
        for p in exists_parts.iterdir():
            p_str = p.as_posix()
            if p_str.startswith(text):
                completions.append(p_str)
    return completions[state]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate calibration, schedule, and scene configuration files for a given input folder.")
    
    # Optional input arguments
    parser.add_argument("--input_folder", type=str, help="Path to the folder containing Images, Masks, the calibration file and where output files will be saved.")
    parser.add_argument("--calibration", type=str, help="Name of the JSON file containing calibration data.")
    parser.add_argument("--rgb", type=str, help="Name of the folder containing rgb Images")
    parser.add_argument("--backgrounds", type=str, help="Name of the folder containing background Images")
    parser.add_argument("--masks", type=str, help="Name of the folder containing image masks")
    parser.add_argument("--masked_images", type=str, help="Name of the folder where the masked_images should be generated")
    parser.add_argument("--onlymasks", type=str, help="If True, only calibration files for Masked Images will be generated.")
    parser.add_argument("--alreadymasked", type=str, help="If True, assumes images are already masked.")
    parser.add_argument("--mask_prefix", type=str, help="The prefix of the masks")
    parser.add_argument("--mask_suffix", type=str, help="The suffix of the masks")
    parser.add_argument("--mask_threshold", type=int, default=1, help="The threshold for mask binarization (default: 1).")
    parser.add_argument("--scale_factor", type=float, default=1, help="Factor for scaling intrinsic parameters of calibration file (default: 1).")
    
    # Parse arguments
    args = parser.parse_args()


    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete_path)

    # 1. Get 'input_folder' argument with validation
    input_folder_path = args.input_folder if args.input_folder else get_input_with_default("Enter the path to the input folder containing the calibration file. This is also used as the output folder for all created files.", "./", valid_check=valid_folder)

    # 2. Get 'calibration' argument with validation
    calibration_input_fn = args.calibration if args.calibration else get_input_with_default("Enter the calibration file name", "calibration_dome.json", valid_check=valid_json)

    # 3. Get subfolder names (no validation needed for subfolders)

    # 4. Get 'onlymasks' and 'alreadymasked' arguments with validation
    if(args.onlymasks is not None):
        onlymasks = args.onlymasks
        background_fn = args.backgrounds if args.backgrounds else get_input_with_default("Enter the subfolder name for background images", "backgrounds")
    else:
        onlymasks = get_input_with_default("Generate calibration for masked images only? (True/False)", "False", valid_check=valid_bool_input).lower() in ['true', 't']
        background_fn = None

    if(args.alreadymasked is not None):
        alreadymasked = args.onlymasks
        image_masked_fn = args.masked_images if args.masked_images else get_input_with_default("Enter the subfolder name where the masked images should be generated", "MaskedImages")
        masks_fn = args.masks if args.masks else get_input_with_default("Enter the subfolder name for mask images", "mask")
    else:
        alreadymasked = get_input_with_default("Are the images already masked? (True/False)", "False", valid_check=valid_bool_input).lower() in ['true', 't']
        image_masked_fn = args.masked_images if args.masked_images else get_input_with_default("Enter the subfolder name where the masked images are located in", "MaskedImages")
    

    if(not onlymasks or not alreadymasked):    
        image_nomask_fn = args.rgb if args.rgb else get_input_with_default("Enter the subfolder name for RGB images", "rgb")        
    else:
        image_nomask_fn = image_masked_fn


    # Define input folder path and subfolder names
    

    # Define file names
    mapping_fn = "mapping.json"
    calibration_output_fn = "calibration_undistorted.xml"
    sequence_nomask_fn = "sequence.xml"
    sequence_masked_fn = "sequence_masked.xml"
    schedule_nomask_fn = "schedule.json"
    schedule_masked_fn = "schedule_masked.json"
    scene_config_nomask_fn = "scene_config.txt"
    scene_config_masked_fn = "scene_config_masked.txt"

    # Pre and Suffix for mask naming convention
    mask_prefix = args.mask_prefix
    mask_suffix = args.mask_suffix

    # Other parameters
    scale_factor_intrinsics = args.scale_factor
    mask_th = args.mask_threshold

    # Step 1: Generate the mapping from old camera_ids to 1, 2, 3, ..., n
    generate_mapping(input_folder_path, image_nomask_fn, mapping_fn)

    # Step 2: Apply mask to images if they are not already masked
    if not alreadymasked:
        apply_mask(input_folder_path, image_nomask_fn, masks_fn, image_masked_fn, mask_prefix, mask_suffix, mask_th)

    # Step 3: Generate calibration and sequence XML files (outputs)
    generate_calibration_and_sequence_files(
        input_folder_path=input_folder_path, 
        calibration_input=calibration_input_fn, 
        mapping=mapping_fn,
        scale_factor=scale_factor_intrinsics,
        calibration_output_fn=calibration_output_fn,
        sequence_nomask_fn=sequence_nomask_fn,
        sequence_masked_fn=sequence_masked_fn,
        image_nomask_fn=image_nomask_fn,
        image_masked_fn=image_masked_fn, 
        onlymasks=onlymasks
    )
    
    # Step 4: Generate schedule JSON files (output)
    if not args.onlymasks:
        generate_schedule_file(
            folder_path=input_folder_path,
            schedule_file_name=schedule_nomask_fn,
            masked=False
        )
    
    generate_schedule_file(
        folder_path=input_folder_path,
        schedule_file_name=schedule_masked_fn,
        masked=True
    )

    # Step 5: Generate scene configuration text file (output)
    if not onlymasks:
        generate_scene_config_txt(
            input_folder_path=input_folder_path,
            scene_config_file_name=scene_config_nomask_fn,
            calibration_output_fn=calibration_output_fn,
            schedule_file_name=schedule_nomask_fn,
            sequence_file_name=sequence_nomask_fn,
            backgrounds_fn=background_fn,
            masked=False
        )

    # Always generate masked scene configuration text file (even if onlymasks is True)
    generate_scene_config_txt(
        input_folder_path=input_folder_path,
        scene_config_file_name=scene_config_masked_fn,
        calibration_output_fn=calibration_output_fn,
        schedule_file_name=schedule_masked_fn,
        sequence_file_name=sequence_masked_fn,
        backgrounds_fn=None,  # No backgrounds for masked configuration
        masked=True
    )




