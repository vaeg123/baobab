from baobab.pipeline.sync_ocr_canonical_text import join_ocr_pages, should_replace


def test_ocr_pages_are_ordered_and_labelled():
    text = join_ocr_pages([(2, b"deux"), (1, b"un")])
    assert text == "[Page 1]\nun\n\n[Page 2]\ndeux"


def test_ocr_only_replaces_a_shorter_text_when_substantial():
    substantial = "droit " * 50
    assert should_replace("notice courte", substantial) is True
    assert should_replace("texte plus long " * 100, substantial) is False
    assert should_replace("", "trop court") is False
