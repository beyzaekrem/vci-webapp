# Image Processing Pipeline

First we retrieve a BufferEntry from a Camera with CaptureNext.
The **BufferEntry** contains the (packed) image bytes in bit depth 8/10/12/14/16 accoring to the camera and its settings.

The BufferEntry is then unpacked into a **GibbsImage**.
The GibbsImage contains the pixels (torch.tensor) as well as some meta info passed from the BufferEntry - camera_id, pixellayout, image_type.
GibbsImages are in float32, having resolved both the byte packing as well as the bit depth.
(the precision of the bit depth stays the same.)

The GibbsImage may be processed with the gibbs.processing kernels. Or the pixels tensor can directly be changed with tensor operations. Generally the GibbsImage is mutated effectivly in-place. Since some image processing operations do allow this.
The operations can change not just the pixels values and pixel-shape but also the pixellayout (e.g. from Bayer BGGR -> RGB).

Lastly, the GibbsImage can be encoded into image formats (jpg, png, avif, etc.)
This returns an **EncodedImage**, leaving the GibbsImage unchanged.
(The encoding can reduce the bit-depth.)

#### Overview

BufferEntry -> GibbsImage -> EncodedImage

* Camera.CaptureNext -> BufferEntry

* BufferEntry -> GibbsImage
    * BufferEntryToDeviceAsnyc(BufferEntry) -> tensor
    * UnpackBuffer(tensor, buffer_info) -> **GibbsImage**
    or
    * BufferEntryToDeviceAnsyc(BufferEntry) -> tensor
    * CombinedKernel_Color(tensor, buffer_info) -> **GibbsImage**

* Processing Kernels (GibbsImage) -> GibbsImage

* Matting (GibbsImage-image, GibbsImage-background) -> GibbsImage-mask

* Encoding (GibbsImage) -> EncodedImage

## saving to ssds (aka. dumps)

The (packed) BufferEntries are directly saved, along with one copy of meta data per camera.
(This assumes that the meta-data will not change mid-caputre. So you cannot change the bit-depth during the caputre. Most Cameras do not allow you to do this anyway.)

When Reading the dump, the BufferEntries are unpacked immediately into a GibbsImage.

* gibbs.io.CacheWriter Write frame (BufferEntry)
* gibbs.io.CacheReader LoadFrame -> GibbsImage


## send with interceptor

To pass the EncodedImages over vci-websocket (aka interceptor) to a client, the python class **ImagePackage** can be used. 

When sending over network, the meta information of the EncodedImages (e.g. camera_ids, image_type, shape, format, ...) is automatically assembled into a dictionary, while the data(torch.tensor) or each EncodedImage gets passed as bytes.