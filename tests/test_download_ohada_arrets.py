from baobab.pipeline.scrapers.download_ohada_arrets import extract_notice_ids, parse_notice


SHELF_HTML = """
<a href="index.php?lvl=notice_display&id=2500">Arrêt 007/2015</a>
<a href="index.php?id=2501&lvl=notice_display">Arrêt 013/2015</a>
<a href="index.php?lvl=notice_display&id=2500">doublon</a>
<a href="index.php?lvl=notice_display&id=1881">Journal officiel OHADA</a>
"""

NOTICE_HTML = """
<div>Titre :\n Arrêt 007/2015 - Affaire : A c/ B</div>
<div>Date d'audience :\n 26/02/2015</div>
<div>Auteurs :\n CCJA</div>
<div>Affaire :\n A c/ B</div>
<a href="./doc_num.php?explnum_id=3155">PDF</a>
"""


def test_extract_notice_ids_preserves_order_and_removes_duplicates():
    assert extract_notice_ids(SHELF_HTML) == [2500, 2501]


def test_extract_notice_ids_supports_other_jurisprudence_types():
    html = '<a href="index.php?lvl=notice_display&id=42">Ordonnance 001/2020</a>'
    assert extract_notice_ids(html, "Ordonnance") == [42]


def test_parse_notice_keeps_official_provenance():
    record = parse_notice(NOTICE_HTML, 2500)
    assert record["ref"] == "CCJA-007/2015"
    assert record["date_str"] == "2015-02-26"
    assert record["source_pdf_url"].endswith("doc_num.php?explnum_id=3155")
    assert record["metadata"]["notice_id"] == 2500
