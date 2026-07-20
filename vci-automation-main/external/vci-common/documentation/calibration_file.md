# Calibration file

The calibration json file contains the extrinsic `view_matrix` (camera pose) and intrinsic `camera_matrix`, `distortion_coefficients` and `resolution` for each camera.
Color cameras also have `white_balance_coefficients` and a `color_correction_matrix`.

Color cameras have a `camera_id` starting with C while mono cameras (with an infrared filter) start with M.

The calibration infos are used by the vci-capture servers to [process](processing_steps.md) the images.

## Coordinate system

The extrinsic `view_matrix` is a 4x4 matrix compose of rotation and translation that describes the pose of the camera in the world. 
```
  view_matrix = |rot 3x3 ,  t 3x1|
                | 0      ,  1    |
```
* The 3x3 **rotation matrix** describes how the camera is oriented relative to the world. 
* The **translation vector** describes the position of the camera, expressed in the camera's coordiante frame. Because of this the translation vector does not directly express the world position of the camera. 

Here is a python example for calculating the world camera positions:

```python
  import json
  from pyquaternion import Quaternion
  import numpy as np
  
  input_path = "some/path/to/calibration_dome.json"
  
  with open(input_path) as f:
      calibration_json = json.load(f)
  calibration_cameras = calibration_json["cameras"]

  for calib in calibration_cameras:
      extrinsic_matrix = np.array(calib["extrinsics"]["view_matrix"]).reshape((4, 4))
      rot = extrinsic_matrix[:3, :3]
      t = extrinsic_matrix[:, -1][:-1]

      # positon:
      world_position = -rot.T @ t

      # rotation:
      q = Quaternion(matrix=rot)
      q = Quaternion(-q.w, q.x, q.y, q.z)
```

There are lots of coordinate systems that each interpret the axis differently.
The [OpenCV coordinate system](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html) looks like this:
  
       z (forward into the scene, away from viewer)
      /
     /______ x (right)
     |
     |
     | y (down)

Depending on how the stage was calibrated, either one of the cameras will be the origin of the coordinate system, 
or the center of the stage will be the origin.

You can [reformat](../src/reformat_camorph/reformat) the calibration file into a few common formats with ``src/camorph_reformat/reformat.py``.
This script can also [visualize the camera poses](../src/reformat_camorph/reformat.md#visualize-camera-positions).

## Intrinsic camera_matrix

The ``camera_matrix`` encodes how 3D points in the camera coordinate system are projected onto the 2D image plane.

The 3x3 matrix is composed of the focal lengths fx and fy and the principal point (cx, cy). Both are expressed in pixel units.

```
  camera_matrix = |fx,  0, cx|
                  | 0, fy, cy|
                  | 0,  0,  1|
```

(Undistorted images still keep this camera_matrix.)

## Resolution and Crop

The resolution is formated as [w, h]. E.g: "resolution": [ 5328,4608 ].
We always calibrate in full resolution, when you are working with half resolution images, you need to halve the ``resolution`` and the ``camera_matrix``.
When you crop your images you need adjust the camera_matrix and resolution to match. [auto_crop](../src/auto_crop/auto_crop.md) can crop images and camera_matrices to the *foreground region*.
Alternatively, if you want to crop all camera_matrices to the *same crop_region* you can use [reformat_camorph](../src/reformat_camorph/reformat.md#crop-images).

## Example calibration file:

```json
{
  "meta": "Extrinsics use OpenCV coordinate system (x right, y down, z forward into the scene)",
  "timestamp": "2025.04.16 17:11",
  "cameras": [
    {
      "camera_id": "C0000",
      "extrinsics": {
        "view_matrix": [
          0.014268333005231695,
          -0.936269490984733,
          -0.35099267075601587,
          1.1347066543282522,
          0.9991369931596014,
          -0.00034438397341915716,
          0.0415349286705688,
          0.04209244478498064,
          -0.03900876277507643,
          -0.351282395873844,
          0.9354565702243421,
          3.0663792873532434,
          0.0,
          0.0,
          0.0,
          1.0
        ]
      },
      "intrinsics": {
        "camera_matrix": [
          4568.130666239859,
          0.0,
          2654.71143516446,
          0.0,
          4567.693506686942,
          2268.390557937662,
          0.0,
          0.0,
          1.0
        ],
        "color_correction_matrix": [
          1.5431115095062167,
          -0.38989381648627014,
          -0.2547371825840727,
          -0.5409460032593453,
          1.9282328143473744,
          -0.45575775547096326,
          0.06084527197081402,
          -0.6347260378786151,
          1.544129885638444
        ],
        "distortion_coefficients": [
          -0.13481387594943003,
          0.13788313386998072,
          8.00603804349891e-05,
          -0.00020106846476988774,
          -0.029572708531640863
        ],
        "resolution": [
          5328,
          4608
        ],
        "white_balance_coefficients": [
          2.106836865185809,
          1.0,
          1.957982496441579
        ]
      }
    },
    {
      "camera_id": "C0001",
      [...]
    }
    [...]
}
```