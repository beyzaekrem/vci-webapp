import importlib
import importlib.util
import inspect
import pathlib
import pkgutil
from abc import ABC, abstractmethod

from jsonargparse import ArgumentParser as JSONArgumentParser

from controller.args.util import (
    apply_arg_modes_to_args,
    apply_arg_modes_to_schema,
    apply_argparse_utils_from_model,
)

from .runnable import Runnable
from .user_interface import CLIInterface, UserInterface
from .util.script_args_ui_schema import ScriptArgsUISchema


class ScriptRunner(ABC):
    """python scripts that can be called via webapp or command line.
    The api_handler.py intercetpor-server hosts and runs ScriptRunners.
    """

    ui: UserInterface

    def __init__(self, ui: UserInterface) -> None:
        self.ui = ui
        self._stopped_logged = False
        self.runnable = Runnable(
            target=self.main,
            on_error=self._on_run_error,
            on_finished=self._on_run_finished,
        )

        # Identity: Path-based naming (e.g., 'capture/single_shot.py')
        script_file = pathlib.Path(inspect.getfile(self.__class__))
        # Assumes this is run from the project root containing a /scripts folder
        try:
            self.unique_id = str(script_file.relative_to(pathlib.Path.cwd() / "scripts"))
        except ValueError:
            self.unique_id = script_file.name

    @property
    def display_name(self) -> str:
        """A human-readable name for the script, derived from the class name."""
        classname = self.__class__.__name__  # camel cased
        display_name = ""
        for char in classname:
            if char.isupper() and display_name:
                display_name += " "
            display_name += char
        return display_name

    @abstractmethod
    def _get_args_pydantic_model(self) -> type:
        """Return the pydantic model class that defines the arguments."""

    @abstractmethod
    def main(self, args) -> None:
        """Define the scripts main."""

    @property
    def running(self) -> bool:
        return self.runnable.running

    @property
    def stop_requested(self) -> bool:
        return self.runnable.stop_requested

    def start(self, *args, **kwargs) -> None:
        self.runnable.start(*args, **kwargs)

    def stop(self) -> None:
        self.runnable.stop()
        cancel_pending_inputs = getattr(self.ui, "cancel_pending_inputs", None)
        if cancel_pending_inputs is not None:
            cancel_pending_inputs()

    def _on_run_error(self, error: Exception) -> None:
        if self.stop_requested:
            self.ui.log(f'Script "{self.display_name}" stopped.')
            self._stopped_logged = True
            return
        self.ui.error(f"Error occurred while running script: {error!s}")

    def _on_run_finished(self) -> None:
        if self.stop_requested and not self._stopped_logged:
            self.ui.log(f'Script "{self.display_name}" stopped.')
        elif not self.stop_requested:
            self.ui.log(f'Script "{self.display_name}" finished.')
        self._stopped_logged = False

    def get_args_json_schema(self) -> dict:
        """Get the JSON schema for the arguments, to be used by the web-app for dynamic form generation."""
        args_model = self._get_args_pydantic_model()
        schema = args_model.model_json_schema(
            union_format="primitive_type_array"
        )  # get the json schema from the pydantic model
        schema = apply_arg_modes_to_schema(schema, args_model, self.ui.get_arg_mode())
        return schema

    def get_args_ui_schema(self, schema: dict | None = None) -> dict:
        """Get the RJSF uiSchema for rendering the argument form in the web-app."""
        return ScriptArgsUISchema.from_model(self._get_args_pydantic_model(), schema)

    def get_args_form_schema(self) -> dict:
        """Get the JSON Schema and RJSF uiSchema for the argument form."""
        schema = self.get_args_json_schema()
        return {
            "schema": schema,
            "uiSchema": self.get_args_ui_schema(schema),
        }

    def validate_args(self, args: dict):
        """Validate the arguments using the pydantic model. (called by both network or cli interfaces)"""
        args_model = self._get_args_pydantic_model()
        args = apply_arg_modes_to_args(args, args_model, self.ui.get_arg_mode())
        validated_args = args_model.model_validate(args)
        return validated_args

    def parse_cli_args(self):
        """Parse arguments from CLI using JSONArgumentParser."""
        parser = JSONArgumentParser(prog=self.unique_id)

        # Build ArgumentParser based on the pydantic model of the script arguments
        args_model = self._get_args_pydantic_model()
        parser.add_class_arguments(args_model)

        # allow space separated list arguments and additional argument names based on the pydantic model:
        apply_argparse_utils_from_model(parser, args_model)

        args = parser.parse_args()  # parse args from CLI, e.g. --exposure speedy
        validated_args = self.validate_args(
            args.__dict__
        )  # validate and convert, so we can get properties (e.g. exposure_settings)
        return validated_args

    @classmethod
    def run_in_cli(cls) -> None:
        """Helper method to run the script from CLI."""
        instance = cls(ui=CLIInterface())
        args = instance.parse_cli_args()
        instance.main(args)


class ScriptRegistry:
    def __init__(self) -> None:
        self.registry: dict[str, type[ScriptRunner]] = {}
        self.dynamic_discovery()

    def dynamic_discovery(self) -> None:
        # discovers all concrete implementations of ScriptRunner in the scripts module
        registry: dict[str, type[ScriptRunner]] = {}
        for _, name, ispkg in pkgutil.walk_packages(["./scripts"], "scripts."):
            if ispkg:
                continue

            try:
                module = importlib.import_module(name)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # 1. Must be a class
                    # 2. Must inherit from ScriptRunner
                    # 3. Must NOT be the ScriptRunner base class itself
                    if inspect.isclass(attr) and issubclass(attr, ScriptRunner) and attr is not ScriptRunner:
                        registry[name] = attr
                        print(f"✅ Registered concrete class: {attr.__name__} from {name}")

            except Exception as e:
                print(f"❌ Failed to load {name}: {e}")
        self.registry = registry

    def get_all(self) -> dict[str, type[ScriptRunner]]:
        return self.registry

    def get_script(self, script_id: str) -> type[ScriptRunner] | None:
        return self.registry.get(script_id)
