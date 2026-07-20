from pydantic import BaseModel

from .util import CLI_GROUP_CONNECTION, CliArg, ScriptArgumentField


def server_list_arg(
    default: list[int] | None = None,
    *,
    group: str = CLI_GROUP_CONNECTION,
):
    description = "Specify the server IDs to connect to. Use -1 for all servers (default)."

    class ServerListArgMixin(BaseModel):
        server: list[int] | None = ScriptArgumentField(
            default=default,
            description=description,
            cli=CliArg(
                option_strings=["--server", "-s"],
                group=group,
                nargs="+",
                metavar="SERVER_ID",
            ),
        )

    return ServerListArgMixin
