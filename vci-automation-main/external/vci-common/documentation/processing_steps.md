# Processing Steps

The cameras capture raw bayer images. Each pixel on the sensor captures only one channel: either red, green or blue. (Our cameras pattern is BGGR.)

In order to get a color image with each pixel having three channels, the image needs to be debayered.
You can choose from these debayer methods:

| debayer methods     |                                                                                                                                     |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| debayer_subsample   | Each packet of four captured pixels BGGR is combined into one output pixel. This results in half resolution images.                 |
| debayer_interpolate | The missing pixel values are interpolated from the 4 nearest neighbors of the correct color. This results in full resolution images |
| debayer_malvar      | Uses the Malvar-He-Cutler Linear Image Demosaiking algorithm. Results in full resolution images.                                    |


<br>

Additional processing:

| Processing         |                                                                                                                                                                                                                                                    |
|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| white_balance      | Compensates for the color temperature of the lights. Without correction images have a strong green tint in our setup                                                                                                                               |
| color_correction   | Ensures consistent colors across different cameras and restores the natural contrast and saturation.                                                                                                                                               |
| undistort*         | Compensates for lense distortions                                                                                                                                                                                                                  |
| non_linear*        | Transforms the image from linear space to sRGB. In linear space the brightness values match real light intensity. In sRGB the brightness values are perceptually encoded. sRGB is the standard for displays and most image formats (e.g. png, jpg) |
| superkernel*       | Combines white_balance, color_correction, undistort and non_linear into one, increasing computation speed.                                                                                                                                         |

 ( * can be applied to mono (IR) images.)


### Example combinations:

| Combination                                                |                                                                                                                                    |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| debayer_malvar, superkernel                                | Fully processed image                                                                                                              |
| debayer_subsample, superkernel                             | Fully processed half resolution image                                                                                              |
| debayer_malvar, white_balance, color_correction, undistort | Processed linear image (e.g. for exr format)                                                                                       |
|                                                            | Raw (bayer) image with no processing                                                                                               |
| white_balance, non_linear                                  | Bayer image with corrected color temperature in sRGB space <br/>(white_balance and non_linear are applied before the debayer step) |



# Image Formats

| color / mono   | extra properties                      |
|----------------|---------------------------------------|
| jpg            | quality - determines encoding quality |
| torch:float32  |                                       |
| png            |                                       |
| exr            |                                       |

| matte          | extra properties                                 |
|----------------|--------------------------------------------------|
| jpg            | threshold - binarization threshold (default=0.5) |
| png            |                                                  |