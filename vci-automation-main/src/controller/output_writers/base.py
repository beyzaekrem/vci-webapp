from abc import ABC
from dataclasses import dataclass

from web_app_integration.user_interface import UserInterface

from .path_structure import PathStructure


# shared context
@dataclass
class WriterContext:
    path_structure: PathStructure
    user_interface: UserInterface


class Writer(ABC):
    ui: UserInterface

    def __init__(self, writer_context: WriterContext):
        self.writer_context = writer_context
        self.path_structure: PathStructure = self.writer_context.path_structure

        # for convenience, define ui
        self.ui = self.writer_context.user_interface
