from .util import (
    SpaceSeparatedListAction,
    add_additional_arg_names,
    add_additional_arg_names_from_model,
    use_space_separated_list_argument,
)
from .cameras_argument import cameras_arg, resolve_cameras
from .capture_name_arugment import (
    DATE_KEYWORD,
    capture_name_arg,
    get_current_date_string,
    resolve_capture_name,
    series_flag_arg,
)
from .capturing_argument import fps_arg, max_recording_time_arg
from .exposure_gain_setting import (
    DEFAULT_EXPOSURE,
    EXPOSURE_MAP,
    LOW_LIGHT_EXPOSURE,
    SLOW_EXPOSURE,
    SPEEDY_EXPOSURE,
    SUPER_SPEEDY_EXPOSURE,
    VERY_SLOW_EXPOSURE,
    ExposureArg,
    ExposureSettings,
)
from .flexi_range_argument import (
    FlexiRangeArgMixinFrames,
    flexi_range_arg,
    parse_flexi_range,
    validate_flexi_range,
)
from .output_paths_argument import (
    OUTPUT_PRESETS,
    folder_mode_arg,
    folder_mode_type,
    load_output_presets,
    output_folder_arg,
    output_folder_type,
)
from .processing_steps_arugment import processing_steps_arg, processing_steps_type
from .quality_settings_argument import (
    ENC_QUALITY_AVIF,
    HIGH_QUALITY_JPG,
    HIGH_QUALITY_PNG,
    LOSSLESS_QUALITY_AVIF,
    LOW_QUALITY_JPG,
    QUALITY_EXR,
    QUALITY_PRESETS,
    QUALITY_TORCH,
    ImageQualitySettings,
    quality_arg,
)
from .server_list_argument import server_list_arg
from .trigger_control_argument import (
    auto_trigger_arg,
    auto_trigger_delay_arg,
    maximal_trigger_count_arg,
)

from .flag_argument import ScriptFlagField
