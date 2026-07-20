from .cameras_argument import add_cameras_argument, resolve_cameras
from .capture_name_arugment import add_capture_name_argument, add_series_flag_arugment
from .capturing_argument import add_fps_argument, add_max_recording_time_argument
from .exposure_gain_setting import (
    DEFAULT_EXPOSURE,
    LOW_LIGHT_EXPOSURE,
    SPEEDY_EXPOSURE,
    SUPER_SPEEDY_EXPOSURE,
    ExposureSettings,
    add_exposure_argument,
)
from .flexi_range_argument import FLEXI_RANGE_FULL, CreateFlexiRange, FlexiRange, add_flexi_range_argument
from .output_paths_argument import (
    add_folder_mode_argument,
    add_output_folder_argument,
    folder_mode_type,
)
from .processing_steps_arugment import add_processing_steps_argument
from .quality_settings_argument import (
    HIGH_QUALITY_JPG,
    HIGH_QUALITY_PNG,
    LOW_QUALITY_JPG,
    ImageQualitySettings,
    add_quality_argument,
)
from .server_list_argument import add_server_list_argument
from .trigger_control_argument import (
    add_auto_trigger_argument,
    add_auto_trigger_delay_argument,
    add_maximal_trigger_count_argument,
)
