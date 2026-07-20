# mmhumans

[generate_calibration_files.py](generate_calibration_files.py) reformats a [dome calibration](../../documentation/calibration_file.md) into mmhuman format. 

# mmhumans tips

On the first screen before loading the video sequence:
- To import a config file it's best to use drag and drop
- When using masked Images, "Use Masks" needs to be turned off and "Use Backgrounds" should be turned off as well
- "Color Correction" and "Remove Ground" work as advertised
- Every setting here can be changed via config file

After loading video sequence: 
- (if needed) First adjust Scene reference frame. For better control TAB can be used to input exact numbers on EVERY slider
- (if needed) Next the Reconstruction Volume needs to be adjusted. 
    - Voxel size has a massive impact on memory usage, quality and artifacts. In my experiments 2mm was by far the best value
    - Try to be as close as possible to the scaling in the real world. Science scale (in Scene reference frame) can help with the dimensions

- For all sliders smaller and larger values than the slider min/max can be entered via pressing TAB
- Remove distortion didn't work for me and needed to be turned off ALWAYS. 
- Image level of detail, selected camera etc. are only used visualisation (same with Display Mode, ...)
- I left all the thresholds in Segmentation on their default value, all changes I tried made the result worse
- Most important parameters are in HyperParameters. Their description can be found under "Differential Rendering"->"Regularizations"
- After starting the reconstruction "P" can be pressed to show a plane (horizontal/vertical) of the volume, this can also show tSDF or similar. 
- The mesh shown in the visualisation is offset by a bit. This offset gets smaller for the later stages. As far as I know this is only in visualisation while the reconstruction should work without offset. Be careful around the edges of the reconstruction volume
- Under "Reconstruction Volume" is a setting about removing voxels outside FOV. This removes pixels outside ANY camera FOV and only leaves the pixels that are seen by all cameras
- results when enabling Unreliable visual hull mode are really bad
- Overflows of Total vertices can be prevented by increasing the max vertices in "Reconstruction Volume" (use TAB to increase beyond 20kk)
