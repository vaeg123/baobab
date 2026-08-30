-- Aligne les sources concrètes du moteur de veille sur la qualification A–F.

UPDATE legal_sources SET
    authority_grade='B',authenticity_status='INSTITUTIONAL',coverage_status='NON_EXHAUSTIVE',
    applicability_status='JO_AND_EFFECTIVE_DATE_TO_VERIFY',institution_name='Présidence de la République du Cameroun',
    authority_type='NATIONAL_EXECUTIVE',acquisition_channel='OFFICIAL_WEB_PORTAL',
    agreement_status='TO_REVIEW',partnership_priority=2,updated_at=NOW()
WHERE code IN ('CM.PRC.LOIS','CM.PRC.ORDONNANCES','CM.PRC.DECRETS');

UPDATE legal_sources SET
    authority_grade='E',authenticity_status='SECONDARY',coverage_status='NON_EXHAUSTIVE',
    applicability_status='ORIENTATION_ONLY',updated_at=NOW()
WHERE code='CM.JURICAF.SEARCH';

-- Retire rétroactivement toute autoqualification accordée à l'agrégateur.
UPDATE legal_source_artifacts SET state='OBSERVED',validation_score=0,
    validation_reasons='["SOURCE_SECONDAIRE_REVUE_HUMAINE_REQUISE"]'::jsonb,
    auto_validated_at=NULL
WHERE source_code='CM.JURICAF.SEARCH';

UPDATE legal_watch_events SET review_status='PENDING',reviewed_at=NULL,
    auto_validated_at=NULL,validation_score=0,
    validation_reasons='["SOURCE_SECONDAIRE_REVUE_HUMAINE_REQUISE"]'::jsonb
WHERE source_code='CM.JURICAF.SEARCH' AND review_status='AUTO_VALIDATED';

UPDATE legal_corpus SET source_tier='SECONDARY',editorial_status='TO_REVIEW',
    metadata=jsonb_set(COALESCE(metadata,'{}'::jsonb),'{watch_quarantined}','true'::jsonb),
    updated_at=NOW()
WHERE source_code='CM.JURICAF.SEARCH' AND COALESCE(metadata->>'automated_validation','false')='true';
