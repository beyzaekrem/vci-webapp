class ServersEncounteredError(Exception):
    pass


class TriggerBoxError(Exception):
    pass


class ServerDesyncError(Exception):
    pass


class NoServersRunning(Exception):
    pass


class PowerControlException(Exception):
    pass


class ImageWriteFailure(Exception):
    pass
