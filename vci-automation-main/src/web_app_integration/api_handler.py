import interceptor

from controller.logging_config import logger

from .script_runner import ScriptRegistry, ScriptRunner
from .user_interface import InterceptorConnectionInterface


def get_info(message: interceptor.MessageIn, *, required: bool = False) -> dict:
    info = {}
    if len(message.payload) > 0:
        info = interceptor.Payload.ToDict(message.payload[0])
    elif required:
        msg = f"Message {message.path} requries a payload"
        raise interceptor.WrongPayloadError(msg)
    return info


def require_parameter(info: dict, parameter: str) -> str | int | float | list:
    value = info.get(parameter)
    if value is None:
        msg = f"Missing required parameter {parameter}"
        raise interceptor.WrongPayloadError(msg)
    return value


class APIHandler(interceptor.MessageHandler):
    """
    Expose the scripts in the registry via interceptor endpoints,
    so that the web-app can execute them
    """

    def __init__(self, server: interceptor.Server | None = None) -> None:
        interceptor.MessageHandler.__init__(self)
        self.script_registry: ScriptRegistry = ScriptRegistry()
        self.running_scripts: dict[str, ScriptRunner] = {}  # runner_id -> ScriptRunner instance

    def OnConnect(self, connection: interceptor.Connection) -> None:  # noqa: N802
        logger.info("BaseHandler::OnConnect")

    def OnDisconnect(  # noqa: N802
        self, connection: interceptor.Connection, graceful: bool  # noqa: ARG002, FBT001
    ) -> None:
        logger.info("BaseHandler::OnDisconnect")
        for script in self.running_scripts.values():
            ui = script.ui
            if isinstance(ui, InterceptorConnectionInterface):
                ui.remove_connection(connection)

    @staticmethod
    def send_dict_response(message: interceptor.MessageIn, dict_response: dict) -> None:
        pl = interceptor.Payload.FromDict(dict_response)
        message.Acknowledge([pl])

    def get_availabele_scripts(self) -> list[str]:
        return list(self.script_registry.get_all())

    def get_script_schema(self, script_name: str) -> dict:
        script_cls = self.script_registry.get_script(script_name)
        if script_cls is None:
            raise ValueError(f"Script {script_name} not found in registry")

        instance: ScriptRunner = script_cls(ui=InterceptorConnectionInterface())
        return instance.get_args_form_schema()

    def run_script(self, script_name: str, connection, runner_id: str, arguments: dict) -> None:
        logger.info(f"API - Run Script {script_name}")
        script_cls = self.script_registry.get_script(script_name)

        if script_cls is None:
            raise ValueError(f"Script {script_name} not found in registry")
            return

        interface = InterceptorConnectionInterface()
        interface.add_connection(connection)
        instance: ScriptRunner = script_cls(ui=interface)

        existent_script: ScriptRunner = self.running_scripts.get(runner_id)
        if existent_script is not None and existent_script.running:
            raise ValueError(f"Runner ID {runner_id} is already in use by another running script.")

        interface.set_runner_id(runner_id)
        self.running_scripts[runner_id] = instance

        try:
            # either use default args or those from the user
            if arguments is None:
                # throw error
                raise ValueError("No arguments provided for script execution.")
            # validate and convert the arguments using the pydantic model
            args = instance.validate_args(arguments)
        except Exception as e:
            instance.ui.error(f"Error validating arguments: {e!s}")
            # del self.running_scripts[runner_id]
            return

        instance.ui.log(f'Script "{instance.display_name}" started.')
        instance.start(args)

    @interceptor.path_handler("SCRIPT_OVERVIEW")
    def _path_script_overview(self, message: interceptor.MessageIn) -> None:
        # return the names of callable scripts, and maybe their descriptons.
        # -> web-app can dynamically create a menu bar with the avaiable scripts
        script_classes = self.get_availabele_scripts()
        # also get the display names of the scripts
        scripts = []
        for script_id in script_classes:
            script_cls = self.script_registry.get_script(script_id)
            if script_cls is None:
                continue
            # todo make method classmethod?
            display_name = script_cls(ui=InterceptorConnectionInterface()).display_name
            scripts.append({"id": script_id, "name": display_name})

        self.send_dict_response(
            message,
            {"scripts": scripts},
        )

    @interceptor.path_handler("GET_SCRIPT_SCHEMA")
    def _path_get_script_schema(self, message: interceptor.MessageIn) -> None:
        # returns the CLI Schema of the requested script.
        # includes:
        # script name, descripton,
        # the fields and flags of the command line arguments
        # IO fields:
        # * text box to show command line print
        # * Yes/No Button for boolean input, or test input.
        # * image field to show display-image
        # -> wep-app dynamically creates a page to display the fields.
        info = get_info(message)
        script_name = require_parameter(info, "script_name")

        # get schema:
        schema = self.get_script_schema(script_name)

        message.Acknowledge([interceptor.Payload.FromDict(schema)])

    @interceptor.path_handler("RUN_SCRIPT")
    def _path_run_script(self, message: interceptor.MessageIn) -> None:
        # pass the name and arguments of the script, similar to how we coud call in via command line.
        # we start the script run.
        # probably keep a referecne to the running script and its arugments in some dataclass

        info = get_info(message)
        script_name = require_parameter(info, "script_name")
        runner_id = require_parameter(info, "runner_id")
        args = info.get("arguments", None)  # dict with arguments
        self.run_script(script_name, message.connection(), runner_id=runner_id, arguments=args)
        message.Acknowledge()

    @interceptor.path_handler("SCRIPT_EVENT_RESPONSE")
    def _path_script_event_response(self, message: interceptor.MessageIn) -> None:
        """
        this is called when the web-app sends a response to an event that a script triggered, e.g. a user input.
        we need to forward this response to the correct script execution that is waiting for it.
        we can identify the correct script execution via the runner_id
        that we set in the InterceptorConnectionInterface when we triggered the event.
        """
        info = get_info(message)
        runner_id = require_parameter(info, "runner_id")
        event_id = require_parameter(info, "event_id")
        event_response = require_parameter(info, "event_response")

        logger.info(
            f"Received event response for runner_id: {runner_id}, event_id: {event_id}, response: {event_response}"
        )

        script = self.running_scripts.get(runner_id)
        if script is None:
            message.Acknowledge(
                [interceptor.Payload.FromDict({"error": f"No running script with runner_id {runner_id}"})]
            )
            return

        script.ui.receive_event_response(event_id, event_response)

        message.Acknowledge()

    @interceptor.path_handler("STOP_SCRIPT")
    def _path_stop_script(self, message: interceptor.MessageIn) -> None:
        # stops/interrupts the script.
        # -> if the user switches the web-app view or something idk.
        info = get_info(message)
        runner_id = require_parameter(info, "runner_id")
        script = self.running_scripts.get(runner_id)
        if script is None:
            message.Acknowledge(
                [interceptor.Payload.FromDict({"error": f"No running script with runner_id {runner_id}"})]
            )
            return

        script.ui.log("Stop requested.")
        script.stop()
        message.Acknowledge([interceptor.Payload.FromDict({"stopping": True})])

    @interceptor.path_handler("SUBSCRIBE_TO_SCRIPT")
    def _path_subscribe_to_script(self, message: interceptor.MessageIn) -> None:
        info = get_info(message)
        runner_id = require_parameter(info, "runner_id")
        script = self.running_scripts.get(runner_id)
        if script is None:
            message.Acknowledge(
                [interceptor.Payload.FromDict({"error": f"No running script with runner_id {runner_id}"})]
            )
            return
        ui: InterceptorConnectionInterface = script.ui
        ui.add_connection(message.connection())
        ui.trigger_output_update()
        message.Acknowledge()
