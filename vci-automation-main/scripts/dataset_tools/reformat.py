# ruff: noqa: T201, INP001
from reformat_camorph.reformat import (  # from vci-common submodule
    camorph,
    visualize,
)

cams = camorph.read_cameras(
    "dome",
    "/media/ximea/Daten/capture/jens_avatar_001/calibration_dome.json",
    images_half_resolution=False,
)
print("cameras", len(cams))
print("camera_ids:", [cam.name for cam in cams])
visualize(cams)

camorph.write_cameras("fbx", "/media/ximea/Daten/capture/jens_avatar_001/cameras.fbx", cams)
#
# camorph.write_cameras("fbx", "reformat_output/calibration.fbx", cams)
#
# camorph.write_cameras("colmap", "reformat_output/manual_sparse_model", cams)
