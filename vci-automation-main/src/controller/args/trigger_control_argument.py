from pydantic import BaseModel

from .util import CLI_GROUP_IMAGE_TRIGGER, CliArg, ScriptArgumentField


def auto_trigger_arg(
    action_description: str = "image capture",
    default: bool = False,
    *,
    group: str = CLI_GROUP_IMAGE_TRIGGER,
):
    help_msg = (
        f"Automatically triggers {action_description}, "
        "otherwise triggered via manual console prompt. "
        "You can enable/disable this later."
    )

    class AutoTriggerArgMixin(BaseModel):
        auto_trigger: bool = ScriptArgumentField(
            default=default,
            description=help_msg,
            cli=CliArg(option_strings=["--auto-trigger", "-a"], group=group),
        )

    return AutoTriggerArgMixin


def auto_trigger_delay_arg(
    default: int | None = None,
    const: int = 5,
    *,
    group: str = CLI_GROUP_IMAGE_TRIGGER,
):
    class AutoTriggerDelayArgMixin(BaseModel):
        auto_trigger_delay: int | None = ScriptArgumentField(
            default=default,
            description=(
                "Enable automatic trigger and set delay between triggers "
                f"(in seconds). e.g: --auto-trigger-delay (default: {const}) "
                "or --auto-trigger-delay 10."
            ),
            cli=CliArg(
                option_strings=["--auto-trigger-delay", "-d"],
                group=group,
                metavar="SECONDS",
                nargs="?",
                const=const,
            ),
        )

    return AutoTriggerDelayArgMixin


def maximal_trigger_count_arg(default: int | None = None, *, group: str = CLI_GROUP_IMAGE_TRIGGER):
    class MaximalTriggerCountArgMixin(BaseModel):
        maxcount: int | None = ScriptArgumentField(
            default=default,
            description=f"Defines the maximal number of triggers (default: {default}).",
            cli=CliArg(option_strings=["--maxcount", "-m"], group=group, metavar="COUNT"),
        )

    return MaximalTriggerCountArgMixin
