# Camorph Reformat 

[Camorph](https://github.com/Fraunhofer-IIS/camorph) is a camera parameter conversion library that supports 
several common formats including fbx, colmap, nerf and unity.
[``reformat.py``](reformat.py) extends the library with the  [``dome`` format](../../documentation/calibration_file.md).
(In theory Meshroom is supported as well but that outputs an outdated file version.)

## Setup
Install camorph with:
```sh
pip install git+https://github.com/Fraunhofer-IIS/camorph
```
Tested with camorph version 0.3.5

## Usage

In [``reformat.py``](reformat.py) you can rewrite the ``main()`` function to suit your needs.
Here are a few use cases:

### Visualize camera positions:

```python
def main():
    cams = camorph.read_cameras("dome", "path/to/calibration_dome.json")
    visualize(cams)
```

### Convert to colmap:

```python
def main():
    cams = camorph.read_cameras("dome", "path/to/calibration_dome.json",
                                imdir="path/to/capture/frame_00001/rgb/",
                                images_half_resolution=False)
    # convert to colmap
    camorph.write_cameras("colmap", "reformat_output/manual_sparse_model", cams)
```

See [keyword arguments](#key-word-arugments).

The colmap conversion creates two files in the output folder: cameras.txt and images.txt.
You can [reconstruct a model from the known camera poses.](https://colmap.github.io/faq.html#reconstruct-sparse-dense-model-from-known-camera-poses)

When using **masks in colmap**, you need to rename them according to [colmaps mask naming convention](https://colmap.github.io/faq.html#mask-image-regions).
Otherwise, your masks may be silently ignored.
The mask filename must be equal to the image name with the added extension ``.png``.
If the image is called ``C0004.jpg``, then the corresponding mask needs to be called ``C0004.jpg.png``

In ubuntu, you can use the ``rename`` command to do this. Navigate into the mask folder in the command line and call 
```sh
rename 's/^mask_(.*)\..+$/$1.jpg.png/' mask_*.*
``` 
(This is adding the ending .jpg.png. adjust to match your input images)
.You may need to install rename 
```sh
sudo apt install rename
```

### Convert to and from fbx:

```python
def main():
    cams = camorph.read_cameras("dome", "path/to/calibration_dome.json")
    # convert to fbx
    camorph.write_cameras("fbx", "reformat_output/calibration.fbx", cams)
```
You can import the .fbx file into Blender to view the camera positions.
You can add cameras in Blender and convert back to dome format, in order to create virtual cameras.

```python
def main():
    # read back fbx and convert to dome format
    cameras_fbx = camorph.read_cameras("fbx", "reformat_output/calibration.fbx")
    camorph.write_cameras("dome", "reformat_output/back_to_dome.json", cameras_fbx)

    # intrinsic view_matrix is incorrect when importing from fbx
    # You also loose the attributes "color_correction_matrix", "white_balance_coefficients" 
    # and "distortion_coefficients"
```

### Crop images

If you crop your images the camera intrinsic camera_matrix need to be adjusted to match.
If you want to apply the same crop region to all images you can use Camorph's ``write_cameras`` for this.
Specify your crop region as `crop = [[x1,y1],[x2,y2]]`, 
describing the pixel locations of the top-left and bottom-right corners.

```python
def main():
    cams = camorph.read_cameras("dome", "path/to/calibration_dome.json", 
                                images_half_resolution=False)
    camorph.write_cameras("dome", "reformat_output/cropped_calibration.json", cams,
                          crop=[[1000, 1000], [2000, 1500]])
    # You can read from dome and write as dome again to adjust resolution or crop 
    # without loosing any of the camera attributes.
    # If you do this, make sure not to confuse the two files! 
    # You wouldn't want to crop twice
```

The crop region will be applied to all cameras and only effects the intrinsic camera_matrix.
This does not modify the images.

[Auto Crop](../auto_crop/auto_crop.md) can automatically crop both images and camera matrices to the foreground region.

## Keyword arguments of dome

These are the keyword arguments supported by ``camorph.read_cameras("dome", input_path)``

``imdir`` expects a path to an image directory where each image name contains the camera name. For example 
valid image names for camera C0004 would be: ``C0004.jpg``, ``C0004.png``, or ``any_text_C0004_some_more_text.png``.
If you do not provide an imdir, each camera gets a default image name of ``<camera_name>.jpg`` (e.g. ``C0004.jpg``).
Cameras with no corresponding image in imdir are removed from the calibration.  

``absolute_path`` determines whether the entire path of the image_directory should be output.

``images_half_resolution`` determines whether to adjust the intrinsic camera_matrix for half resolution. 
The calibration file describes the camera's full resolution. However, when capturing images you have the option to get 
half resolution images instead. When you are working with half resolution set ``image_half_resolution=True``

``sensor_size_mm`` camera sensor size in mm. Default is ``sensor_size_mm = [14, 12]`` (Ximea camera sensor size)

