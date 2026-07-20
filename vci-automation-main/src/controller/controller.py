import contextlib
import sys

from web_app_integration.user_interface import CLIInterface, UserInterface

from .components import (
    CalibrationModule,
    CaptureModule,
    ConnectionManager,
    ModeControllModule,
    OutputWritersModule,
    ParametersModule,
    StatusModule,
)
from .logging_config import logger, set_global_verbosity
from .output_writers import (
    CalibrationWriter,
    FolderMode,
    ImageWriter,
    PathStructure,
    PreviewWriter,
    WriterContext,
)
from .system_layout_reader import SystemLayoutReader

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Controller(
    CaptureModule,
    CalibrationModule,
    OutputWritersModule,
    ParametersModule,
    ModeControllModule,
    StatusModule,
):
    FOLDER_MODE = FolderMode

    def __init__(
        self,
        server_list: list[str] | None = None,
        log_level: str = "INFO",
        *,
        mode: str | None = None,
        system_layout_filepath: str = "config/system_layout.json",
        user_interface : UserInterface = CLIInterface()
    ) -> None:
        """
        Establishes active connections to vci-capture servers. The ip adresses are defined in the system_layout file.

        The servers manage physical hardware and persist in specific operational modes
        (e.g. "record" for disk capture, "calibration" for calibration tasks). Each mode has different capabilities,
        some functions (aka. wrapped API endpoints) are only available in certain modes or give a different response
        to the same call.

        **Operational Modes**
        - **Standard Modes ("single", "record", "replay", "ring_buffer", "calibration")**: The Controller takes *active
         owership* of the hardware and switches the servers to the given operation mode. If a mode was already running
         on the server, ControlTakenError is raised. When the Controller is closed, server actions and hardware
         triggers are stopped.
        - **"observer" Mode:** The Controller connects passively, not interrupting ongoing modes, actions or triggers.
        - **None:** Initializes an active owership connection, without setting the mode immediately. This allows for
            conditional logic before calling `switch_mode()` later.


        **Recommended Usage:**
        Use Controller as a **context manager** (`with Controller() as c: ...`) to ensure that image/video transfers are
        properly completed before the session termiantes.

        **Saving Data and Images:**
        The Controller includes built-in media writers. Once a destination is set
        via `set_image_path()`, the Controller automatically routes and saves
        incoming data, managing the underlying I/O asynchronously.

        Args:
            server_list (list[str] | None, optional): Specifies which servers to connect to. Defaults to None.
                    - If **None**: Connects to ALL servers defined in the system layout.
                    - If **list[int]**: Connects only to specified servers by their index in the layout file (e.g(`[0,2]`))
            log_level (str, optional): Logging verbosity(e.g. "DEBUG", "INFO"). Defaults to "INFO".
            mode (str, optional): The intended mode ("single", "record", "replay", "ring_buffer", "calibration". Special no-interferance mode: "observer")
            system_layout_filepath (str, optional): Path to system_layout json file. Defaults to "config/system_layout.json".
        """

        path_structure = PathStructure()
        set_global_verbosity(log_level)

        self.ui = user_interface
        writer_context: WriterContext = WriterContext(path_structure=path_structure, user_interface=user_interface)
        self.writer_context = writer_context
        self.path_structure = path_structure
        self._connection = ConnectionManager(user_interface)
        self.preview_writer = PreviewWriter(writer_context)
        self.image_writer = ImageWriter(writer_context)
        self.calibration_writer = CalibrationWriter(writer_context)
        self.system_layout = SystemLayoutReader(system_layout_filepath, user_interface)
        self.initial_mode = mode
        # connect
        if server_list is None:
            server_list = self.system_layout.get_server_list()
        self._connection.connect(server_list, self.system_layout)

        # run startup code
        if self.initial_mode == "observer":
            ## observational mode.
            logger.info("connected as observer.")
        else:
            self.stop()
            if self.initial_mode is not None:
                self.switch_mode(self.initial_mode)
            try:
                self.set_software_trigger(False)
            except RuntimeError as e:
                logger.warning(f"Couldn't stop hardware triggers. Error: {e}")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        self.preview_writer.close_writer()
        self.wait_images_transferred()
        if self.initial_mode != "observer":
            self.stop()
            with contextlib.suppress(Exception):
                self.set_software_trigger(False)
        else:
            logger.info("Observer disconnecting. Leaving hardware states untouched.")
        self._connection.disconnect()

    def set_verbosity(self, log_level: str) -> None:
        set_global_verbosity(log_level)
