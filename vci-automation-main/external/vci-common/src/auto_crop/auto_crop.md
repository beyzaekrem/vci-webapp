# Auto Crop

[``auto_crop.py``](auto_crop.py) crops the images, masks, and camera_matrices to the *foreground* region,
as defined by the mask. The adjusted camera_matrices are saved in ``cropped_camera_matrix.json`` 
separate from the unchanged [calibration_dome.json](../../documentation/calibration_file.md).


Since this approach crops each image perfectly to the foreground, each image has a unique camera_matrix and resolution 
in cropped_camera_matrix.json.

## Example cropped_camera_matrix:

```json
{
  "meta": "intrinsic camera_matrices of cropped images",
  "timestamp_original_calib": "2025.04.02 18:51",
  "frames": {
    "frame_00001": {
      "C0000": {
        "crop_region": [[862,718],[2193,1121]],
        "camera_matrix": [
          4568.130206896842,
          0.0,
          1792.714848224602,
          0.0,
          4567.692814053368,
          1550.3896364727348,
          0.0,
          0.0,
          1.0
        ],
        "resolution": [
          1331,
          403
        ]
      },
      "C0001": {...}
    },
    "frame_00002": {...},
    [...]
    }
}
```



