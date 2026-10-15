"""Chapters → lines for the YouTube description ("00:00 Intro"). The first chapter is always 00:00."""


def _stamp(t: float, long: bool) -> str:
    t = int(t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if long else f"{m:02d}:{s:02d}"


def chapters_txt(chapters: list[dict], end: float) -> str:
    if not chapters:
        return ""
    long = end >= 3600
    return "".join(f"{_stamp(0 if i == 0 else c['start'], long)} {c['title']}\n" for i, c in enumerate(chapters))
