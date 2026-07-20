import argparse

from pydantic import BaseModel

from controller.args.argparse_utils import CliArg, ScriptArgumentField
from web_app_integration.api_handler import APIHandler
from web_app_integration.script_runner import ScriptRunner


class _FakeRegistry:
    def __init__(self, script_cls):
        self.script_cls = script_cls

    def get_script(self, script_name: str):
        return self.script_cls


class _SchemaArgs(BaseModel):
    camera: str = ScriptArgumentField(
        default="C0001",
        cli=CliArg(group="Image Configuration"),
    )
    output: str = ScriptArgumentField(
        default="TEST",
        cli=CliArg(group="Output Control"),
    )
    verbose: bool = False


class _SchemaScript(ScriptRunner):
    def _get_args_pydantic_model(self) -> type:
        return _SchemaArgs

    def main(self, args: argparse.Namespace) -> None:
        pass


def test_get_script_schema_returns_json_schema_and_ui_schema(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    handler = APIHandler.__new__(APIHandler)
    handler.script_registry = _FakeRegistry(_SchemaScript)

    response = handler.get_script_schema("scripts.capture.example_script")

    assert set(response) == {"schema", "uiSchema"}
    assert response["schema"]["title"] == "_SchemaArgs"
    assert response["uiSchema"]["ui:groups"] == [
        {"title": "Image Configuration", "fields": ["camera"]},
        {"title": "Output Control", "fields": ["output"]},
    ]
    assert response["uiSchema"]["ui:order"] == ["camera", "output", "verbose"]
    assert "camera" not in response["uiSchema"]
