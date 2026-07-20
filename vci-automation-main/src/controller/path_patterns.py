from .controller import Controller


def vci_course_path_pattern(c: Controller):
    """
    Images are grouped by camera-id and the image name contains both image_id and frame number

    Example:
    - rgb images: output_path / C0001 / rgb / C0001_F00001.jpg

    - masks: output_path / C0001 / mask / C0001_F00001.jpg
    """
    # custom path patterns for vci-course
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.image] = "<output_path>/<cam_id>/rgb/<cam_id>_F<frame>"
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.matte] = "<output_path>/<cam_id>/mask/<cam_id>_F<frame>"


def old_path_patterns(c: Controller):
    # custom path patterns for vci-course
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.image] = (
        "<output_path>/frame_<frame>/rgb/<cam_id><suffix>"
    )
    c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.background] = "<output_path>/background/<cam_id><suffix>"


def joint_preview_folder(c: Controller, preview_name, folder_name="_previews"):
    """
    Sets a custom name for the next preview and saves it in specified sub folder

    Example:
    - preview: output_path / _previews / Capture_00001.mp4
    """

    if folder_name is None:
        c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.preview] = f"<output_path>/{preview_name}"
    else:
        c.path_structure.path_patterns[c.path_structure.IMAGE_TYPE.preview] = (
            f"<output_path>/{folder_name}/{preview_name}"
        )
