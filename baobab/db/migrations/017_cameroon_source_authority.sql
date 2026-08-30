-- Qualification multidimensionnelle des sources camerounaises.

ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS authority_grade CHAR(1) NOT NULL DEFAULT 'F';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS authenticity_status VARCHAR(40) NOT NULL DEFAULT 'UNVERIFIED';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS coverage_status VARCHAR(40) NOT NULL DEFAULT 'UNKNOWN';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS applicability_status VARCHAR(40) NOT NULL DEFAULT 'TO_DETERMINE';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS authority_note TEXT;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS partnership_priority INTEGER NOT NULL DEFAULT 100;

DO $$ BEGIN
    ALTER TABLE legal_sources ADD CONSTRAINT legal_sources_authority_grade CHECK (authority_grade IN ('A','B','C','D','E','F'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE legal_sources ADD CONSTRAINT legal_sources_partnership_priority CHECK (partnership_priority BETWEEN 1 AND 999);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

INSERT INTO legal_sources
    (code,name,jurisdiction_code,source_type,base_url,access_mode,license_review_required,
     institution_name,authority_type,acquisition_channel,agreement_status,
     authority_grade,authenticity_status,coverage_status,applicability_status,
     authority_note,partnership_priority,technical_format,expected_frequency)
VALUES
    ('CM.JO','Journal officiel de la République du Cameroun','CM','OFFICIAL_GAZETTE',
     'https://www.prc.cm','INSTITUTIONAL_TRANSFER_REQUIRED',TRUE,
     'Secrétariat général de la Présidence de la République','OFFICIAL_GAZETTE',
     'PARTNERSHIP_REQUIRED','TO_REVIEW','A','AUTHENTIC','PARTIAL_DIGITAL_ACCESS','DATE_AND_STATUS_TO_VERIFY',
     'Preuve principale de publication. Accès exhaustif et droits de réutilisation à contractualiser.',1,'PDF_OR_INSTITUTIONAL_EXPORT','REGULAR'),
    ('CM.PRC.ACTES','Présidence de la République du Cameroun — Actes','CM','LEGISLATION',
     'https://www.prc.cm/fr/actualites/actes','OFFICIAL_HTML_PDF',TRUE,
     'Présidence de la République du Cameroun','NATIONAL_EXECUTIVE',
     'OFFICIAL_WEB_PORTAL','TO_REVIEW','B','INSTITUTIONAL','NON_EXHAUSTIVE','JO_AND_EFFECTIVE_DATE_TO_VERIFY',
     'Origine institutionnelle élevée; présence en ligne distincte de la preuve de publication au Journal officiel.',2,'HTML_AND_PDF','DAILY'),
    ('CM.SPM.ACTES','Services du Premier ministre — Lois et règlements','CM','LEGISLATION',
     'https://www.spm.gov.cm/site/?q=fr%2Fdocumentation%2Flois-et-r%C3%A8glements','OFFICIAL_HTML_PDF',TRUE,
     'Services du Premier ministre du Cameroun','NATIONAL_EXECUTIVE',
     'OFFICIAL_WEB_PORTAL','TO_REVIEW','B','INSTITUTIONAL','NON_EXHAUSTIVE','JO_AND_EFFECTIVE_DATE_TO_VERIFY',
     'Source officielle utile pour les actes du Premier ministre; rapprochement PRC et Journal officiel requis.',3,'HTML_AND_PDF','DAILY'),
    ('CM.MINJUSTICE.LEGALIS','Ministère de la Justice — LEGALIS','CM','LEGISLATION_DATABASE',
     'https://www.minjustice.gov.cm/index.php/fr/legalis/accueil-legalis','OFFICIAL_DATABASE',TRUE,
     'Ministère de la Justice du Cameroun','MINISTRY',
     'OFFICIAL_WEB_PORTAL','TO_REVIEW','B','INSTITUTIONAL','COVERAGE_UNDISCLOSED','IN_FORCE_STATUS_TO_VERIFY',
     'Base institutionnelle de législation; export, schéma, fréquence et critères de mise à jour à obtenir.',4,'HTML_DOCUMENTS_AND_EXPORT_TO_NEGOTIATE','IRREGULAR'),
    ('CM.MINJUSTICE.CASELAW','MINJUSTICE — Décisions de justice','CM.SUPREME','CASE_LAW',
     'https://www.minjustice.gov.cm/index.php/fr/e-justice/decisions-de-justice','OFFICIAL_DATABASE',TRUE,
     'Ministère de la Justice du Cameroun','MINISTRY',
     'OFFICIAL_WEB_PORTAL','TO_REVIEW','B','INSTITUTIONAL','NON_EXHAUSTIVE','DECISION_AUTHENTICITY_TO_QUALIFY',
     'Collection officielle non exhaustive; distinguer original signé, copie, transcription et résumé.',5,'HTML_AND_PDF','IRREGULAR')
ON CONFLICT (code) DO UPDATE SET
    name=EXCLUDED.name,base_url=EXCLUDED.base_url,access_mode=EXCLUDED.access_mode,
    institution_name=EXCLUDED.institution_name,authority_type=EXCLUDED.authority_type,
    acquisition_channel=EXCLUDED.acquisition_channel,authority_grade=EXCLUDED.authority_grade,
    authenticity_status=EXCLUDED.authenticity_status,coverage_status=EXCLUDED.coverage_status,
    applicability_status=EXCLUDED.applicability_status,authority_note=EXCLUDED.authority_note,
    partnership_priority=EXCLUDED.partnership_priority,technical_format=EXCLUDED.technical_format,
    expected_frequency=EXCLUDED.expected_frequency,updated_at=NOW(),enabled=TRUE;

UPDATE legal_sources SET authority_grade='C',authenticity_status='INSTITUTIONAL',
    applicability_status='REGIONAL_REGIME_TO_DETERMINE',coverage_status='NON_EXHAUSTIVE',updated_at=NOW()
WHERE jurisdiction_code IN ('OHADA','OHADA.CCJA','CIMA','CEMAC','COBAC')
   OR code LIKE 'OHADA.%' OR code LIKE 'CIMA.%';

UPDATE legal_sources SET authority_grade='E',authenticity_status='SECONDARY',
    applicability_status='ORIENTATION_ONLY',updated_at=NOW()
WHERE code IN ('CM.JURICAF','CM.NATLEX','AGG.JURICAF','CM.JURICAF.SEARCH','PUB.OHADALEGIS');
