from .errors import CutmateError

FORMATS = {"9:16": (1080, 1920), "16:9": (1920, 1080)}


def size_of(fmt: str) -> tuple[int, int]:
    try:
        return FORMATS[fmt]
    except KeyError:
        raise CutmateError(f"unknown format {fmt!r}; use 9:16 or 16:9") from None
