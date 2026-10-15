from cutmate.chapters import chapters_txt


def test_chapters_txt_first_is_zero():
    chs = [{"start": 0.1, "title": "Intro", "num": 1}, {"start": 75.4, "title": "Jak „to” działa", "num": 2}]
    assert chapters_txt(chs, 600.0) == "00:00 Intro\n01:15 Jak „to” działa\n"


def test_chapters_txt_long_video():
    chs = [{"start": 0.0, "title": "A", "num": 1}, {"start": 3725.0, "title": "B", "num": 2}]
    assert chapters_txt(chs, 4000.0) == "0:00:00 A\n1:02:05 B\n"


def test_chapters_txt_empty():
    assert chapters_txt([], 10.0) == ""
