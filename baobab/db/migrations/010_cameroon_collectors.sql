-- Sources opérationnelles distinctes pour le moteur de collecte camerounais.
INSERT INTO legal_sources
    (code,name,jurisdiction_code,source_type,base_url,access_mode,license_review_required)
VALUES
    ('CM.PRC.LOIS','Présidence du Cameroun — Lois','CM','LEGISLATION',
     'https://www.prc.cm/fr/actualites/actes/lois','OFFICIAL_HTML_PDF',TRUE),
    ('CM.PRC.ORDONNANCES','Présidence du Cameroun — Ordonnances','CM','LEGISLATION',
     'https://www.prc.cm/fr/actualites/actes/ordonnances','OFFICIAL_HTML_PDF',TRUE),
    ('CM.PRC.DECRETS','Présidence du Cameroun — Décrets','CM','LEGISLATION',
     'https://www.prc.cm/fr/actualites/actes/decrets','OFFICIAL_HTML_PDF',TRUE)
ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name,base_url=EXCLUDED.base_url,
    access_mode=EXCLUDED.access_mode,enabled=TRUE;
