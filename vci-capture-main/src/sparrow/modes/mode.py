from __future__ import annotations

from abc import ABCMeta, abstractmethod

from sparrow.gibbs_wrapper import interceptor


class ModeHandler(interceptor.MessageHandler, metaclass=type("Meta", (ABCMeta, type(interceptor.MessageHandler)), {})):

    @classmethod
    @abstractmethod
    def mode_name(cls) -> str:
        pass

    @classmethod
    def mode_protected(cls) -> str:
        return True

    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def on_start(self) -> None:
        pass

    @abstractmethod
    def on_stop(self) -> None:
        pass

    @abstractmethod
    def get_status(self, *, verbose:bool) -> dict:
        return {}
