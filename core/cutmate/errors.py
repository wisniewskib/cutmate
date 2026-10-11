class CutmateError(Exception):
    """Base for every user-facing error; the CLI prints it as one line."""


class ConfigError(CutmateError):
    pass


class MediaError(CutmateError):
    pass


class BackendError(CutmateError):
    pass


class EDLError(CutmateError):
    pass
