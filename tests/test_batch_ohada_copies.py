from pathlib import Path
import json

from baobab.pipeline.batch_store_ohada_copies import identity_from_filename, source_url_index


def test_extracts_case_identity_from_acquired_filename():
    assert identity_from_filename(Path("arret-ccja-CCJA-063-2013.pdf")) == (
        "arret_ccja", "63", "2013"
    )
    assert identity_from_filename(Path("ordonnance-ccja-CCJA-001-2016-CCJA.pdf")) == (
        "ordonnance_ccja", "1", "2016"
    )


def test_rejects_non_case_file():
    assert identity_from_filename(Path("code-ohada-2025.pdf")) is None


def test_source_url_index_uses_download_manifest(tmp_path):
    input_dir = tmp_path / "ohada_arrets"
    input_dir.mkdir()
    (tmp_path / "ohada_arrets.json").write_text(json.dumps([{
        "local_pdf": "data/raw/ohada_arrets/arret-ccja-CCJA-016-2013.pdf",
        "source_url": "https://biblio.ohada.org/index.php?lvl=notice_display&id=4783",
    }]), encoding="utf-8")

    assert source_url_index(input_dir) == {
        "arret-ccja-CCJA-016-2013.pdf":
        "https://biblio.ohada.org/index.php?lvl=notice_display&id=4783",
    }
