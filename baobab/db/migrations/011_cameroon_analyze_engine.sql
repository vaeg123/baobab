-- BAOBAB 0.5 — Moteur d'analyse juridique camerounais + JURICAF + corpus bootstrap

-- ── Juridictions CM additionnelles ───────────────────────────────────────────

INSERT INTO legal_jurisdictions
    (code, name, kind, country_code, parent_code, legal_system, default_language, pack)
VALUES
    ('CM.APPEAL',  'Cours d''appel du Cameroun',                          'COURT',    'CM',   'CM',   'MIXED_CIVIL_COMMON_LAW', 'fr', 'cameroun'),
    ('CM.LABOUR',  'Juridictions du travail du Cameroun',                  'COURT',    'CM',   'CM',   'MIXED_CIVIL_COMMON_LAW', 'fr', 'cameroun'),
    ('CM.TRIBUNAL','Tribunaux de grande instance du Cameroun',             'COURT',    'CM',   'CM',   'MIXED_CIVIL_COMMON_LAW', 'fr', 'cameroun'),
    ('CEMAC',      'Communauté Économique et Monétaire d''Afrique Centrale','REGIONAL', NULL,   NULL,   'COMMUNITY_LAW',           'fr', 'cameroun'),
    ('COBAC',      'Commission Bancaire de l''Afrique Centrale',           'COURT',    NULL,   'CEMAC','COMMUNITY_LAW',           'fr', 'cameroun')
ON CONFLICT (code) DO NOTHING;

-- ── Source JURICAF (collecte active) ─────────────────────────────────────────

INSERT INTO legal_sources
    (code, name, jurisdiction_code, source_type, base_url, access_mode, license_review_required)
VALUES
    ('CM.JURICAF.SEARCH',
     'JURICAF — jurisprudence camerounaise (recherche)',
     'CM.SUPREME',
     'CASE_LAW',
     'https://juricaf.org/recherche/pays:cameroun',
     'INSTITUTIONAL_AGGREGATOR',
     TRUE)
ON CONFLICT (code) DO UPDATE
    SET name        = EXCLUDED.name,
        base_url    = EXCLUDED.base_url,
        access_mode = EXCLUDED.access_mode,
        enabled     = TRUE;

-- Active les sources précédemment insérées sans collecteur
UPDATE legal_sources
   SET enabled = TRUE
 WHERE code IN ('CM.JURICAF', 'CM.NATLEX');

-- ── Table de log des analyses IA camerounaises ────────────────────────────────

CREATE TABLE IF NOT EXISTS cm_analyze_log (
    id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID        NOT NULL,
    question     TEXT        NOT NULL,
    query_type   VARCHAR(30) NOT NULL,
    n_docs       INTEGER     NOT NULL DEFAULT 0,
    ai_used      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cm_analyze_log_ws   ON cm_analyze_log(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cm_analyze_log_date ON cm_analyze_log(created_at DESC);

-- ── Index FTS dédié corpus camerounais (plus rapide que le global) ────────────

CREATE INDEX IF NOT EXISTS idx_lc_cm_fts ON legal_corpus
    USING gin(to_tsvector('french', coalesce(titre,'') || ' ' || coalesce(resume,'')))
    WHERE country_code = 'CM';

-- ── Bootstrap corpus CM — textes de référence vérifiés ───────────────────────
-- Les résumés constituent le contexte de raisonnement pour l'analyse IA.
-- Chaque texte n'est inséré que s'il est absent (idempotent).

INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision, pays, domaine, resume,
    mots_cles, source_url, country_code, jurisdiction_code, language_code,
    legal_status, official_citation, publication_date
)
SELECT
    'CM.CONST.1996', 'loi_constitutionnelle', 'cm', 'CM',
    'Constitution du Cameroun — Loi N°96/06 du 18 janvier 1996',
    '1996-01-18', 'Cameroun', 'Droit constitutionnel',
    'La loi N°96/06 du 18 janvier 1996 portant révision de la Constitution du 2 juin 1972 fonde '
    'la République du Cameroun en État unitaire décentralisé, indivisible, laïc, démocratique et social. '
    'Elle consacre le bilinguisme français-anglais comme pilier de l''unité nationale. '
    'Le Président de la République est élu au suffrage universel direct pour un mandat de sept ans renouvelable une fois. '
    'Elle instaure : le Sénat (chambre haute), le Conseil constitutionnel (contrôle de constitutionnalité), '
    'la Cour des comptes (contrôle financier), et affirme l''indépendance du pouvoir judiciaire. '
    'Les libertés fondamentales sont garanties (art. 1 à 26) : liberté d''opinion, d''expression, de presse, '
    'de réunion, d''association, droit à la propriété, inviolabilité du domicile, présomption d''innocence.',
    ARRAY['constitution','droits fondamentaux','État unitaire','décentralisation',
          'bilinguisme','sénat','conseil constitutionnel','suffrage universel','liberté'],
    'https://www.prc.cm/fr/multimedia/documents/4722-constitution-of-cameroon-18-01-1996',
    'CM', 'CM', 'fr', 'IN_FORCE',
    'Loi N°96/06 du 18 janvier 1996 portant révision de la Constitution du 2 juin 1972',
    '1996-01-18'
WHERE NOT EXISTS (
    SELECT 1 FROM legal_corpus WHERE ref = 'CM.CONST.1996' AND corpus = 'cm'
);

INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision, pays, domaine, resume,
    mots_cles, source_url, country_code, jurisdiction_code, language_code,
    legal_status, official_citation, publication_date
)
SELECT
    'CM.CP.2016', 'loi', 'cm', 'CM',
    'Code pénal du Cameroun — Loi N°2016/007 du 12 juillet 2016',
    '2016-07-12', 'Cameroun', 'Droit pénal',
    'La loi N°2016/007 du 12 juillet 2016 portant Code pénal abroge le Code pénal de 1967 et ses modifications. '
    'Il distingue crimes, délits et contraventions. Principales dispositions : '
    'art. 1-30 — principes généraux (légalité des délits et peines, non-rétroactivité, participation criminelle) ; '
    'art. 80-137 — infractions contre la sécurité de l''État ; '
    'art. 161-234 — atteintes aux personnes (meurtre, viol, coups et blessures volontaires) ; '
    'art. 308-1 à 308-7 — infractions informatiques (cybercriminalité, accès non autorisé) ; '
    'art. 134 — corruption active et passive d''agents publics (jusqu''à 15 ans d''emprisonnement) ; '
    'art. 318-326 — infractions économiques et financières (escroquerie, abus de confiance, détournement). '
    'Les mineurs relèvent d''une juridiction spéciale (tribunal pour enfants).',
    ARRAY['code pénal','crime','délit','corruption','cybercriminalité','atteintes aux personnes',
          'sécurité de l''État','mineurs','escroquerie','détournement'],
    'https://www.minjustice.gov.cm',
    'CM', 'CM', 'fr', 'IN_FORCE',
    'Loi N°2016/007 du 12 juillet 2016 portant Code Pénal',
    '2016-07-12'
WHERE NOT EXISTS (
    SELECT 1 FROM legal_corpus WHERE ref = 'CM.CP.2016' AND corpus = 'cm'
);

INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision, pays, domaine, resume,
    mots_cles, source_url, country_code, jurisdiction_code, language_code,
    legal_status, official_citation, publication_date
)
SELECT
    'CM.CPP.2005', 'loi', 'cm', 'CM',
    'Code de procédure pénale du Cameroun — Loi N°2005/007 du 27 juillet 2005',
    '2005-07-27', 'Cameroun', 'Procédure pénale',
    'La loi N°2005/007 du 27 juillet 2005 régit la procédure pénale au Cameroun. '
    'Elle organise trois phases : enquête préliminaire (police judiciaire, 48h renouvelable), '
    'instruction préparatoire (juge d''instruction), jugement (tribunal compétent selon la peine encourue). '
    'Garanties fondamentales : présomption d''innocence (art. 8), droit à un conseil dès la garde à vue (art. 119), '
    'assistance consulaire pour les étrangers. '
    'Détention provisoire : 6 mois maximum en matière correctionnelle, renouvelable une fois ; '
    'jusqu''à 18 mois en matière criminelle. '
    'Voies de recours : appel (délai 10 jours), pourvoi en cassation devant la Cour suprême. '
    'Le ministère public est représenté par le Procureur de la République ou le Procureur général.',
    ARRAY['procédure pénale','garde à vue','détention provisoire','instruction','présomption d''innocence',
          'nullités','cour suprême','appel','cassation','procureur','juge d''instruction'],
    'https://www.minjustice.gov.cm',
    'CM', 'CM', 'fr', 'IN_FORCE',
    'Loi N°2005/007 du 27 juillet 2005 portant Code de procédure pénale',
    '2005-07-27'
WHERE NOT EXISTS (
    SELECT 1 FROM legal_corpus WHERE ref = 'CM.CPP.2005' AND corpus = 'cm'
);

INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision, pays, domaine, resume,
    mots_cles, source_url, country_code, jurisdiction_code, language_code,
    legal_status, official_citation, publication_date
)
SELECT
    'CM.CT.1992', 'loi', 'cm', 'CM',
    'Code du travail du Cameroun — Loi N°92/007 du 14 août 1992',
    '1992-08-14', 'Cameroun', 'Droit du travail',
    'La loi N°92/007 du 14 août 1992 portant Code du travail régit les relations entre employeurs '
    'et travailleurs dans le secteur privé et parapublic camerounais. '
    'Contrat de travail : CDI (contrat à durée indéterminée, résiliation par préavis) et CDD '
    '(durée maximale 2 ans, renouvelable une fois). '
    'Durée légale du travail : 40 heures par semaine, heures supplémentaires majorées à 20% puis 50%. '
    'Congés : 1,5 jour ouvrable par mois de service, soit 18 jours minimum par an. '
    'Salaire minimum (SMIG) : fixé par décret. '
    'Licenciement : pour faute grave (faute lourde, abandon de poste) ou motif réel et sérieux (économique, '
    'insuffisance professionnelle) — préavis et indemnité de licenciement obligatoires sauf faute lourde. '
    'Inspection du travail : contrôle permanent, médiation des conflits individuels et collectifs.',
    ARRAY['contrat de travail','CDI','CDD','licenciement','SMIG','congé annuel',
          'heures supplémentaires','syndicat','inspection du travail','préavis','indemnité'],
    'https://www.mintss.gov.cm',
    'CM', 'CM', 'fr', 'IN_FORCE',
    'Loi N°92/007 du 14 août 1992 portant Code du Travail',
    '1992-08-14'
WHERE NOT EXISTS (
    SELECT 1 FROM legal_corpus WHERE ref = 'CM.CT.1992' AND corpus = 'cm'
);

INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision, pays, domaine, resume,
    mots_cles, source_url, country_code, jurisdiction_code, language_code,
    legal_status, official_citation, publication_date
)
SELECT
    'CM.CS.STAT.2000', 'loi', 'cm', 'CM',
    'Statut général de la Fonction publique — Loi N°2000/010 du 19 décembre 2000',
    '2000-12-19', 'Cameroun', 'Droit de la fonction publique',
    'La loi N°2000/010 du 19 décembre 2000 fixe les droits et obligations des fonctionnaires camerounais. '
    'Recrutement : par concours (voie normale) ou sur titre pour les cadres spécialisés. '
    'Positions : activité (affectation en poste), détachement (auprès d''un autre organisme, durée 2 ans renouvelable), '
    'disponibilité (suspension temporaire, non rémunérée). '
    'Avancement : à l''ancienneté (automatique, tous les 2 ans) et au choix (mérite, commission d''avancement). '
    'Régime disciplinaire : avertissement, blâme, retenue de salaire, mise à pied, révocation — '
    'conseil de discipline obligatoire pour les sanctions graves. '
    'Retraite : à 60 ans (agents de l''État) ou 55 ans (personnels de la sûreté). '
    'La MINFOPRA assure la gestion administrative centralisée des ressources humaines de l''État.',
    ARRAY['fonction publique','fonctionnaire','recrutement','concours','avancement',
          'retraite','discipline','détachement','disponibilité','MINFOPRA'],
    'https://www.minfopra.gov.cm',
    'CM', 'CM', 'fr', 'IN_FORCE',
    'Loi N°2000/010 du 19 décembre 2000 portant statut général de la Fonction publique de l''État',
    '2000-12-19'
WHERE NOT EXISTS (
    SELECT 1 FROM legal_corpus WHERE ref = 'CM.CS.STAT.2000' AND corpus = 'cm'
);

INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision, pays, domaine, resume,
    mots_cles, source_url, country_code, jurisdiction_code, language_code,
    legal_status, official_citation, publication_date
)
SELECT
    'CM.CEMAC.CHANGE.2000', 'règlement', 'cm', 'CEMAC',
    'Règlement CEMAC N°02/00/CEMAC/UMAC/CM du 29 avril 2000 relatif aux changes',
    '2000-04-29', 'Zone CEMAC', 'Droit des changes — CEMAC',
    'Le règlement CEMAC N°02/00/CEMAC/UMAC/CM du 29 avril 2000 fixe le régime des changes '
    'applicable dans les six États membres de la CEMAC (Cameroun, Congo, Gabon, Guinée équatoriale, RCA, Tchad). '
    'Obligations principales : domiciliation de toutes les opérations en devises auprès d''un établissement bancaire '
    'agréé par la COBAC ; rapatriement des recettes d''exportation dans les délais réglementaires ; '
    'déclaration préalable à la BEAC pour tout investissement direct étranger dépassant 100 millions FCFA. '
    'La COBAC (Commission Bancaire de l''Afrique Centrale) assure le contrôle prudentiel des banques et '
    'établissements financiers de la zone, incluant les ratios de solvabilité, de liquidité et de division des risques. '
    'Les infractions aux règles de change sont sanctionnées par des amendes administratives et pénales.',
    ARRAY['changes','devises','CEMAC','COBAC','BEAC','investissement étranger',
          'rapatriement','domiciliation bancaire','exportation','contrôle prudentiel'],
    'https://www.cemac.int',
    'CM', 'CEMAC', 'fr', 'IN_FORCE',
    'Règlement CEMAC N°02/00/CEMAC/UMAC/CM du 29 avril 2000 relatif aux changes',
    '2000-04-29'
WHERE NOT EXISTS (
    SELECT 1 FROM legal_corpus WHERE ref = 'CM.CEMAC.CHANGE.2000' AND corpus = 'cm'
);

INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision, pays, domaine, resume,
    mots_cles, source_url, country_code, jurisdiction_code, language_code,
    legal_status, official_citation, publication_date
)
SELECT
    'CM.CCO.1981', 'loi', 'cm', 'CM',
    'Code civil applicable au Cameroun — Ordonnance N°81-02 du 29 juin 1981',
    '1981-06-29', 'Cameroun', 'Droit civil — État civil',
    'Au Cameroun, le droit civil applicable résulte d''un empilement normatif : '
    'le Code civil français de 1804 a été maintenu dans les provinces francophones par réception après l''indépendance, '
    'tandis que les régions anglophones (Nord-Ouest et Sud-Ouest) appliquent la Common Law héritée de l''administration britannique. '
    'L''ordonnance N°81-02 du 29 juin 1981 organise l''état civil (naissance, mariage, décès). '
    'Le droit de la famille camerounais est mixte : mariage civil obligatoire (avec ou sans dot selon la coutume), '
    'régimes matrimoniaux (communauté légale ou séparation de biens), filiation (légitime, naturelle, adoptive), '
    'successions (droit commun et droit coutumier selon les options). '
    'La saisine du tribunal civil de première instance est la voie ordinaire pour les litiges civils.',
    ARRAY['code civil','état civil','mariage','succession','filiation','adoption',
          'régime matrimonial','common law','droit coutumier','anglophone','francophone'],
    'https://www.minjustice.gov.cm',
    'CM', 'CM', 'fr', 'IN_FORCE',
    'Ordonnance N°81-02 du 29 juin 1981 organisant l''état civil au Cameroun',
    '1981-06-29'
WHERE NOT EXISTS (
    SELECT 1 FROM legal_corpus WHERE ref = 'CM.CCO.1981' AND corpus = 'cm'
);
