from cutmate.captions import to_srt


def test_srt_blocks():
    pages = [{"start": 0.06, "end": 0.9, "words": [["Mówić", 0.06, ""], ["krótko,", 0.41, ""]]},
             {"start": 2.06, "end": 3.0, "words": [["Claude'a", 2.06, "key"]]}]
    assert to_srt(pages) == ("1\n00:00:00,060 --> 00:00:00,900\nMówić krótko,\n\n"
                             "2\n00:00:02,060 --> 00:00:03,000\nClaude'a\n")


def test_srt_hours():
    pages = [{"start": 3723.5, "end": 3724.25, "words": [["x", 3723.5, ""]]}]
    assert "01:02:03,500 --> 01:02:04,250" in to_srt(pages)
