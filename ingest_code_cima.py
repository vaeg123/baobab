#!/usr/bin/env python3
"""
Insère les textes fondamentaux du Code CIMA dans le corpus BAOBAB.

Sections couvertes :
  - Titre I  : Agrément (art. 1-10)
  - Titre VI : Contrôle de l'État / CRCA (art. 308-330)
  - Titre VII: Provisions techniques et solvabilité (art. 334-340)
  - Traité CIMA 1992 (résumé)

Usage:
    DATABASE_URL=... python ingest_code_cima.py
"""
import asyncio, asyncpg, os, sys
from datetime import date as ddate

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = os.environ["DATABASE_URL"]

DOCS = [
    # ── Traité CIMA ──────────────────────────────────────────────────────────
    {
        "ref": "Traite-CIMA-1992",
        "titre": "Traité instituant la Conférence Interafricaine des Marchés d'Assurances (CIMA) — 10 juillet 1992",
        "type": "traite",
        "corpus": "cima",
        "juridiction": "CIMA",
        "domaine": "Droit CIMA — Fondements institutionnels",
        "pays": "Zone CIMA (14 États)",
        "date": ddate(1992, 7, 10),
        "source_url": "https://www.cima.int",
        "resume": (
            "Le Traité CIMA du 10 juillet 1992 institue la Conférence Interafricaine des Marchés "
            "d'Assurances. Il crée un espace commun d'assurance entre les 14 États membres "
            "(Bénin, Burkina Faso, Cameroun, Centrafrique, Comores, Congo, Côte d'Ivoire, Gabon, "
            "Guinée Bissau, Guinée Équatoriale, Mali, Niger, Sénégal, Tchad, Togo). "
            "Il institue le Code CIMA comme droit commun de l'assurance dans l'espace membre, "
            "avec primauté sur les législations nationales. "
            "Il crée la Commission Régionale de Contrôle des Assurances (CRCA) comme organe "
            "de supervision et de sanction des sociétés d'assurance."
        ),
        "texte_integral": (
            "TRAITÉ INSTITUANT LA CONFÉRENCE INTERAFRICAINE DES MARCHÉS D'ASSURANCES (CIMA)\n"
            "Signé à Yaoundé le 10 juillet 1992\n\n"
            "PRÉAMBULE\n"
            "Les Chefs d'État et de Gouvernement des États membres de la Zone Franc en Afrique,\n"
            "Désireux de renforcer leur coopération dans le domaine des assurances,\n"
            "Conscients de la nécessité d'harmoniser les législations nationales sur les assurances,\n\n"
            "TITRE I — CRÉATION ET MISSIONS\n\n"
            "Article 1 : Il est institué entre les États signataires une Conférence Interafricaine "
            "des Marchés d'Assurances, dénommée CIMA. Les États membres sont : Bénin, Burkina Faso, "
            "Cameroun, République Centrafricaine, Comores, Congo, Côte d'Ivoire, Gabon, Guinée-Bissau, "
            "Guinée Équatoriale, Mali, Niger, Sénégal, Tchad, Togo.\n\n"
            "Article 2 : La CIMA a pour mission de gérer le Code des assurances des États membres, "
            "d'assurer le contrôle des entreprises d'assurance opérant sur le territoire des États "
            "membres et de favoriser le développement du marché des assurances dans ces États.\n\n"
            "Article 3 : Le Code des assurances commun aux États membres de la CIMA, ci-après "
            "dénommé 'Code CIMA', constitue la législation en matière d'assurance dans les États "
            "membres. Il se substitue à toute législation nationale contraire.\n\n"
            "TITRE II — ORGANES DE LA CIMA\n\n"
            "Article 6 : La CIMA comprend :\n"
            "- Le Conseil des Ministres (organe délibérant suprême)\n"
            "- La Commission Régionale de Contrôle des Assurances (CRCA)\n"
            "- Le Secrétariat Général\n\n"
            "Article 7 : La Commission Régionale de Contrôle des Assurances (CRCA) est l'organe "
            "de contrôle et de sanction des entreprises d'assurance. Elle dispose de pouvoirs "
            "d'enquête, de mise en demeure, d'injonction et de sanction disciplinaire.\n\n"
            "Article 8 : Les décisions de la CRCA sont obligatoires pour tous les États membres "
            "et s'imposent aux entreprises d'assurance agréées dans l'espace CIMA.\n\n"
            "TITRE III — PRIMAUTÉ DU DROIT CIMA\n\n"
            "Article 12 : Les dispositions du présent Traité et du Code CIMA priment sur les "
            "législations nationales des États membres en matière d'assurance. Toute disposition "
            "nationale contraire est réputée sans effet dans le domaine couvert par le Code CIMA.\n"
        ),
    },

    # ── Code CIMA — Titre I : Agrément ───────────────────────────────────────
    {
        "ref": "Code-CIMA-Art-1-10-Agrement",
        "titre": "Code CIMA — Titre I : Conditions d'exercice — Agrément (Art. 1 à 10)",
        "type": "code",
        "corpus": "cima",
        "juridiction": "CIMA",
        "domaine": "Agrément des sociétés d'assurance",
        "pays": "Zone CIMA (14 États)",
        "date": ddate(1992, 7, 10),
        "source_url": "https://www.cima.int",
        "resume": (
            "Articles 1 à 10 du Code CIMA relatifs aux conditions d'agrément des entreprises "
            "d'assurance et de réassurance. L'agrément est accordé par arrêté du Ministre en "
            "charge des assurances de l'État membre, après avis de la CRCA. Il est délivré "
            "branche par branche. Le capital social minimum est fixé par le Code."
        ),
        "texte_integral": (
            "CODE CIMA — LIVRE I : LE CONTRAT D'ASSURANCE\n"
            "TITRE I — CONDITIONS D'EXERCICE DES OPÉRATIONS D'ASSURANCE\n\n"
            "Article 1 : Toute entreprise qui se livre à des opérations d'assurance ou de "
            "capitalisation doit, pour exercer son activité, être agréée par le Ministre chargé "
            "des assurances de l'État membre sur le territoire duquel elle entend exercer.\n\n"
            "Article 2 : L'agrément est accordé branche par branche selon la nomenclature fixée "
            "à l'annexe du présent Code. Les branches principales sont :\n"
            "- Branche 1 : Accidents\n- Branche 2 : Maladie\n- Branche 3 : Corps de véhicules terrestres\n"
            "- Branche 6 : Corps de véhicules maritimes\n- Branche 10 : Responsabilité civile véhicules\n"
            "- Branche 13 : Responsabilité civile générale\n- Branche 20 : Vie-décès\n"
            "- Branche 21 : Nuptialité-natalité\n- Branche 22 : Assurances liées à des fonds d'investissement\n"
            "- Branche 26 : Capitalisation\n\n"
            "Article 3 : L'agrément ne peut être accordé qu'à des entreprises constituées sous "
            "forme de société anonyme ou de société d'assurance mutuelle dont le siège social "
            "est situé sur le territoire d'un État membre.\n\n"
            "Article 6 : Le capital social minimum est fixé à :\n"
            "- 1 milliard FCFA pour les sociétés pratiquant des opérations d'assurance vie\n"
            "- 1 milliard FCFA pour les sociétés pratiquant des opérations d'assurance non-vie\n"
            "- 2,4 milliards FCFA pour les sociétés pratiquant les deux types d'opérations\n\n"
            "Article 8 : L'agrément peut être retiré par le Ministre chargé des assurances, "
            "sur proposition de la CRCA, dans les cas prévus aux articles 325 et suivants du présent Code.\n\n"
            "Article 10 : Toute entreprise non agréée qui se livre à des opérations d'assurance "
            "est passible des sanctions pénales prévues par les législations nationales, "
            "sans préjudice de la nullité des contrats conclus.\n"
        ),
    },

    # ── Code CIMA — Titre VI : Contrôle CRCA (Art. 308–330) ─────────────────
    {
        "ref": "Code-CIMA-Art-308-330-CRCA-Controle-Sanctions",
        "titre": "Code CIMA — Titre VI : Contrôle de l'État — Pouvoirs et sanctions de la CRCA (Art. 308 à 330)",
        "type": "code",
        "corpus": "cima",
        "juridiction": "CRCA",
        "domaine": "Contrôle et sanctions CRCA — Droit prudentiel CIMA",
        "pays": "Zone CIMA (14 États)",
        "date": ddate(1992, 7, 10),
        "source_url": "https://www.cima.int",
        "resume": (
            "Articles 308 à 330 du Code CIMA relatifs au contrôle des entreprises d'assurance "
            "par la CRCA et aux sanctions disciplinaires. Gradation des sanctions : "
            "avertissement, blâme, interdiction d'opérations, administration provisoire (art. 323), "
            "retrait d'agrément (art. 325-326), liquidation judiciaire (art. 328). "
            "En cas d'insolvabilité ou de non-exécution d'injonctions réitérées, la CRCA peut "
            "prononcer le retrait de la totalité des agréments."
        ),
        "texte_integral": (
            "CODE CIMA — TITRE VI : CONTRÔLE DE L'ÉTAT\n\n"
            "Article 308 : La Commission Régionale de Contrôle des Assurances (CRCA) est chargée "
            "de veiller au respect, par les entreprises d'assurance, des dispositions législatives "
            "et réglementaires relatives à l'assurance. Elle exerce un contrôle permanent sur "
            "les conditions d'exploitation des entreprises d'assurance et de réassurance, "
            "sur leur solvabilité ainsi que sur le respect des engagements contractuels envers "
            "les assurés.\n\n"
            "Article 309 : La CRCA peut demander à toute entreprise d'assurance la communication "
            "de tous documents, livres, registres et pièces justificatives nécessaires à l'exercice "
            "de sa mission de contrôle. Elle peut procéder à des contrôles sur place.\n\n"
            "Article 310 : Lorsqu'une entreprise d'assurance ne respecte pas les prescriptions du "
            "présent Code ou des textes pris pour son application, ou lorsque son état financier "
            "est de nature à compromettre les intérêts des assurés, la CRCA peut :\n"
            "1° Adresser à ladite entreprise une mise en demeure de se conformer aux prescriptions "
            "légales dans un délai qu'elle fixe ;\n"
            "2° Exiger la communication d'un plan de redressement ;\n"
            "3° Exiger l'adoption d'un plan de financement à court terme ;\n"
            "4° Restreindre ou interdire la libre disposition de tout ou partie des actifs.\n\n"
            "Article 312 : La CRCA peut prononcer à l'encontre des dirigeants d'une entreprise "
            "d'assurance les sanctions disciplinaires suivantes, par ordre croissant de gravité :\n"
            "1° L'avertissement ;\n"
            "2° Le blâme ;\n"
            "3° L'interdiction d'effectuer certaines opérations ;\n"
            "4° La suspension ou l'interdiction de l'exercice de tout ou partie des opérations "
            "assurées par l'agrément ;\n"
            "5° Le retrait de l'agrément pour une ou plusieurs branches.\n\n"
            "Article 313 : Avant de prononcer une sanction disciplinaire, la CRCA doit mettre "
            "l'entreprise en mesure de présenter ses observations dans un délai raisonnable. "
            "Le contradictoire est obligatoire.\n\n"
            "Article 314 : Les sanctions prononcées par la CRCA sont notifiées à l'entreprise "
            "concernée et publiées au Journal officiel de chacun des États membres.\n\n"
            "Article 315 : En cas de manquements graves ou répétés aux dispositions du Code CIMA, "
            "la CRCA peut prononcer, sans mise en demeure préalable, les sanctions prévues "
            "à l'article 312.\n\n"
            "Article 316 : La CRCA peut, dans tous les cas, exiger le remplacement des dirigeants "
            "responsables des manquements constatés.\n\n"
            "Article 323 : Lorsque la situation financière d'une entreprise d'assurance est telle "
            "que les intérêts des assurés, souscripteurs ou bénéficiaires de contrats sont "
            "compromis ou susceptibles de l'être, la CRCA peut nommer un administrateur provisoire. "
            "L'administrateur provisoire se substitue aux organes dirigeants de la société. "
            "Il dispose des pouvoirs les plus étendus pour gérer la société. "
            "Sa nomination suspend les fonctions des organes d'administration, de direction "
            "et de surveillance de la société.\n\n"
            "Article 324 : L'administrateur provisoire établit un rapport sur la situation "
            "financière de l'entreprise dans un délai de trois mois. Il peut proposer à la CRCA "
            "soit un plan de redressement, soit le retrait d'agrément.\n\n"
            "Article 325 : La CRCA prononce le retrait de l'agrément dans les cas suivants :\n"
            "1° L'entreprise ne remplit plus les conditions requises pour l'obtention de l'agrément ;\n"
            "2° L'entreprise n'a pas commencé ses opérations dans un délai d'un an à compter "
            "de la date d'octroi de l'agrément ;\n"
            "3° L'entreprise a cessé ses opérations depuis plus de six mois ;\n"
            "4° L'entreprise ne respecte pas les mesures imposées par la CRCA ;\n"
            "5° L'entreprise présente une situation d'insolvabilité irrémédiable ;\n"
            "6° Les dirigeants de l'entreprise ont fait l'objet de condamnations pénales "
            "incompatibles avec l'exercice de leurs fonctions.\n\n"
            "Article 326 : Le retrait d'agrément est prononcé par la CRCA. Il entraîne :\n"
            "1° La cessation immédiate de la souscription de nouveaux contrats ;\n"
            "2° Le maintien des contrats en cours jusqu'à leur terme normal, dans la limite "
            "maximale de trois mois suivant la date de retrait ;\n"
            "3° L'obligation pour l'entreprise de transférer son portefeuille de contrats "
            "à une autre entreprise agréée, ou à défaut, la résiliation des contrats.\n\n"
            "Article 327 : Après retrait d'agrément, si l'entreprise n'est pas en mesure "
            "d'honorer ses engagements envers les assurés, la CRCA saisit la juridiction "
            "compétente aux fins de liquidation judiciaire.\n\n"
            "Article 328 : La liquidation judiciaire d'une entreprise d'assurance est soumise "
            "aux règles du Code CIMA, qui dérogent au droit commun des procédures collectives. "
            "Les créanciers assurés, souscripteurs et bénéficiaires de contrats bénéficient "
            "d'un privilège spécial sur les actifs représentatifs des provisions techniques, "
            "qui leur sont réservés par préférence à tout autre créancier.\n\n"
            "Article 329 : Le liquidateur est désigné par la juridiction compétente. "
            "Il établit l'état du passif et de l'actif, propose un plan de répartition "
            "et procède à la clôture de la liquidation.\n\n"
            "Article 330 : Les décisions de la CRCA peuvent faire l'objet d'un recours "
            "devant la juridiction administrative compétente dans un délai de deux mois "
            "suivant la notification de la décision.\n"
        ),
    },

    # ── Code CIMA — Solvabilité (Art. 334–340) ───────────────────────────────
    {
        "ref": "Code-CIMA-Art-334-340-Solvabilite-Provisions",
        "titre": "Code CIMA — Provisions techniques et marge de solvabilité (Art. 334 à 340)",
        "type": "code",
        "corpus": "cima",
        "juridiction": "CRCA",
        "domaine": "Solvabilité — Provisions techniques — Actifs représentatifs",
        "pays": "Zone CIMA (14 États)",
        "date": ddate(1992, 7, 10),
        "source_url": "https://www.cima.int",
        "resume": (
            "Articles 334 à 340 du Code CIMA relatifs aux obligations prudentielles des "
            "entreprises d'assurance. Obligation de constituer des provisions techniques "
            "suffisantes (art. 334), de les représenter par des actifs admis (art. 335-336), "
            "et de justifier d'une marge de solvabilité permanente (art. 337-1). "
            "Le défaut de couverture des engagements réglementés constitue un signal "
            "d'insolvabilité justifiant l'intervention de la CRCA."
        ),
        "texte_integral": (
            "CODE CIMA — PROVISIONS TECHNIQUES ET SOLVABILITÉ\n\n"
            "Article 334 : Les entreprises d'assurance sont tenues de constituer et de "
            "maintenir en permanence des provisions techniques suffisantes pour le règlement "
            "intégral de leurs engagements vis-à-vis des assurés et bénéficiaires de contrats. "
            "Ces provisions comprennent notamment :\n"
            "- La provision pour primes non acquises (PPNA)\n"
            "- La provision pour risques en cours (PRC)\n"
            "- La provision pour sinistres à payer (PSAP)\n"
            "- La provision mathématique (pour l'assurance vie)\n"
            "- La provision pour égalisation\n"
            "- La provision pour risques croissants\n\n"
            "Article 335 : Les entreprises d'assurance sont tenues de représenter à tout "
            "moment les provisions techniques par des actifs équivalents. Les actifs admis "
            "en représentation des provisions techniques sont limitativement énumérés par "
            "les règlements de la CIMA (obligations d'État, obligations de sociétés cotées, "
            "actions de sociétés cotées, immeubles, prêts hypothécaires, dépôts bancaires).\n\n"
            "Article 336 : La valeur des actifs représentatifs est calculée conformément "
            "aux règles comptables fixées par le Code CIMA et les instructions de la CRCA. "
            "Toute insuffisance de représentation doit être comblée dans un délai de trente "
            "jours sous peine des sanctions prévues à l'article 312.\n\n"
            "Article 337 : Les entreprises d'assurance doivent justifier, à tout moment, "
            "de l'existence d'une marge de solvabilité suffisante. La marge de solvabilité "
            "est l'excédent des actifs admis sur les passifs exigibles (provisions techniques "
            "et autres dettes). Elle constitue un matelas de sécurité destiné à absorber "
            "les pertes imprévues.\n\n"
            "Article 337-1 : La marge de solvabilité minimale est calculée selon deux méthodes "
            "et la plus élevée est retenue :\n"
            "- En assurance non-vie : 20% des primes émises nettes de cessions en réassurance, "
            "dans la limite de la valeur plancher fixée par règlement CIMA\n"
            "- En assurance vie : 4% des provisions mathématiques brutes de réassurance\n"
            "En tout état de cause, la marge de solvabilité ne peut être inférieure "
            "au fonds de garantie minimum.\n\n"
            "Article 337-2 : Le fonds de garantie minimum représente le tiers de la marge "
            "de solvabilité requise, sans pouvoir être inférieur aux montants minima fixés "
            "par règlement de la CIMA. Lorsque la marge de solvabilité effective tombe "
            "en deçà du fonds de garantie, la CRCA est immédiatement saisie.\n\n"
            "Article 337-3 : Lorsque la marge de solvabilité d'une entreprise devient "
            "inférieure au minimum requis, celle-ci doit soumettre à la CRCA, dans un "
            "délai de trente jours, un plan de redressement exposant les mesures prises "
            "pour rétablir la situation.\n\n"
            "Article 337-4 : Lorsque la marge de solvabilité tombe en deçà du fonds de "
            "garantie, l'entreprise doit soumettre à la CRCA un plan de financement à "
            "court terme (moins de trois mois). La CRCA peut restreindre la libre "
            "disposition des actifs de l'entreprise jusqu'au rétablissement de la situation.\n\n"
            "Article 338 : La CRCA publie annuellement un rapport sur la situation "
            "prudentielle des entreprises d'assurance de la zone CIMA. Ce rapport comprend "
            "notamment les ratios de couverture des provisions techniques et les marges "
            "de solvabilité agrégées du marché.\n\n"
            "Article 339 : Les entreprises d'assurance transmettent trimestriellement "
            "à la CRCA un état de couverture des engagements réglementés et une situation "
            "de leur marge de solvabilité. Tout défaut de transmission est passible "
            "des sanctions prévues à l'article 312.\n\n"
            "Article 340 : La CRCA peut, à tout moment, diligenter un contrôle sur place "
            "pour vérifier la réalité des actifs représentatifs déclarés et la sincérité "
            "des provisions techniques constituées.\n"
        ),
    },

    # ── Code CIMA — Gouvernance et dirigeants (Art. 320–322) ─────────────────
    {
        "ref": "Code-CIMA-Art-320-322-Gouvernance-Dirigeants",
        "titre": "Code CIMA — Gouvernance des sociétés d'assurance — Conditions d'honorabilité des dirigeants (Art. 320 à 322)",
        "type": "code",
        "corpus": "cima",
        "juridiction": "CRCA",
        "domaine": "Gouvernance — Dirigeants — Honorabilité",
        "pays": "Zone CIMA (14 États)",
        "date": ddate(1992, 7, 10),
        "source_url": "https://www.cima.int",
        "resume": (
            "Articles 320 à 322 du Code CIMA relatifs aux conditions d'honorabilité, "
            "de compétence et d'expérience exigées des dirigeants de sociétés d'assurance. "
            "La CRCA peut s'opposer à la nomination d'un dirigeant et exiger son remplacement "
            "en cas de faute de gestion ou de manquement grave. "
            "Ces articles fondent les décisions CRCA de blâme et retrait contre les dirigeants."
        ),
        "texte_integral": (
            "CODE CIMA — GOUVERNANCE DES SOCIÉTÉS D'ASSURANCE\n\n"
            "Article 320 : Les personnes physiques qui dirigent, administrent, gèrent ou "
            "contrôlent à titre habituel une entreprise d'assurance doivent posséder "
            "l'honorabilité et les qualifications ou l'expérience professionnelle nécessaires "
            "à l'exercice de leurs fonctions.\n\n"
            "Article 320-1 : Ne peuvent être administrateurs, membres du conseil de surveillance, "
            "directeurs généraux ou dirigeants d'une entreprise d'assurance :\n"
            "1° Les personnes ayant fait l'objet d'une condamnation pénale pour crimes ou délits "
            "contre les biens ;\n"
            "2° Les personnes ayant fait l'objet d'une mesure de faillite personnelle ;\n"
            "3° Les personnes frappées d'une mesure d'interdiction de gérer par une juridiction ;\n"
            "4° Les personnes dont l'honorabilité ou la compétence n'est pas établie.\n\n"
            "Article 321 : Toute nomination d'un dirigeant doit être notifiée à la CRCA "
            "dans un délai de huit jours. La CRCA peut s'opposer à cette nomination dans "
            "un délai de deux mois si le dirigeant ne remplit pas les conditions prévues "
            "à l'article 320. En l'absence de réponse dans ce délai, la nomination est réputée approuvée.\n\n"
            "Article 322 : La CRCA peut exiger, à tout moment, le remplacement de tout "
            "dirigeant dont le comportement ou la gestion compromet les intérêts des assurés "
            "ou la solidité financière de l'entreprise. En cas de refus, la CRCA peut "
            "prononcer les sanctions prévues à l'article 312, y compris le retrait d'agrément.\n\n"
            "Article 322-1 : Les personnes qui violent les dispositions des articles 320 à 322 "
            "sont personnellement responsables des préjudices causés aux assurés et à "
            "l'entreprise. Leur responsabilité civile peut être engagée par l'administrateur "
            "provisoire ou le liquidateur.\n"
        ),
    },

    # ── Code CIMA — Branche caution (Art. 100–107) ───────────────────────────
    {
        "ref": "Code-CIMA-Art-100-107-Caution",
        "titre": "Code CIMA — Branche caution — Assurance-caution (Art. 100 à 107)",
        "type": "code",
        "corpus": "cima",
        "juridiction": "CIMA",
        "domaine": "Assurance-caution — Garanties — Sûretés",
        "pays": "Zone CIMA (14 États)",
        "date": ddate(1992, 7, 10),
        "source_url": "https://www.cima.int",
        "resume": (
            "Articles 100 à 107 du Code CIMA relatifs à l'assurance-caution. "
            "L'assurance-caution est un mécanisme par lequel un assureur garantit "
            "l'exécution d'une obligation par un débiteur (le souscripteur) au profit "
            "d'un créancier (le bénéficiaire). Elle se distingue du cautionnement civil "
            "par sa nature indemnitaire. Le bénéficiaire ne peut appeler la garantie "
            "que sur présentation de pièces justificatives. "
            "Articulation avec l'AUS OHADA (sûretés)."
        ),
        "texte_integral": (
            "CODE CIMA — BRANCHE CAUTION (ASSURANCE-CAUTION)\n\n"
            "Article 100 : L'assurance-caution est l'opération par laquelle un assureur "
            "s'engage, en contrepartie du paiement d'une prime, à payer au bénéficiaire "
            "une indemnité au cas où le souscripteur n'exécuterait pas ses obligations.\n\n"
            "Article 101 : L'assurance-caution se distingue du cautionnement de droit commun "
            "en ce qu'elle est de nature indemnitaire et non de nature fidéjussoire. "
            "L'assureur ne peut opposer au bénéficiaire les exceptions que le débiteur "
            "principal aurait pu opposer au créancier.\n\n"
            "Article 102 : Le contrat d'assurance-caution doit préciser :\n"
            "1° L'identité du souscripteur (débiteur garanti) et du bénéficiaire (créancier) ;\n"
            "2° La nature et le montant de l'obligation garantie ;\n"
            "3° Les conditions de mise en jeu de la garantie ;\n"
            "4° Le montant maximum de l'engagement de l'assureur ;\n"
            "5° La durée de la garantie.\n\n"
            "Article 103 : La mise en jeu de la garantie est subordonnée à la présentation "
            "par le bénéficiaire :\n"
            "1° D'une demande d'indemnisation précisant la nature et le montant du sinistre ;\n"
            "2° De justificatifs établissant la défaillance du débiteur.\n\n"
            "Article 104 : L'assureur dispose d'un délai de trente jours pour statuer "
            "sur la demande d'indemnisation. Passé ce délai, le silence vaut refus.\n\n"
            "Article 105 : L'assureur subrogé dans les droits du bénéficiaire peut exercer "
            "un recours contre le souscripteur à hauteur des indemnités versées. "
            "Ce recours est fondé sur la subrogation légale.\n\n"
            "Article 106 : Les primes afférentes aux contrats d'assurance-caution entrent "
            "dans l'assiette du calcul de la marge de solvabilité de la branche non-vie.\n\n"
            "Article 107 : La CRCA peut fixer des règles de concentration limitant le montant "
            "maximum d'engagement en assurance-caution pour un même bénéficiaire ou "
            "un même secteur économique.\n"
        ),
    },

    # ── Code CIMA — Sinistres et indemnisation ────────────────────────────────
    {
        "ref": "Code-CIMA-Sinistres-Indemnisation",
        "titre": "Code CIMA — Gestion des sinistres et délais d'indemnisation",
        "type": "code",
        "corpus": "cima",
        "juridiction": "CIMA",
        "domaine": "Sinistres — Indemnisation — Délais légaux",
        "pays": "Zone CIMA (14 États)",
        "date": ddate(1992, 7, 10),
        "source_url": "https://www.cima.int",
        "resume": (
            "Dispositions du Code CIMA relatives à la gestion des sinistres. "
            "Obligation de déclarer le sinistre dans les délais contractuels. "
            "Délai légal d'instruction et de règlement par l'assureur : 3 mois maximum "
            "à compter de la réception de toutes pièces justificatives. "
            "Intérêts de retard en cas de dépassement du délai. "
            "CRCA compétente pour sanctionner les manquements aux délais d'indemnisation."
        ),
        "texte_integral": (
            "CODE CIMA — SINISTRES ET INDEMNISATION\n\n"
            "DÉCLARATION DU SINISTRE\n"
            "L'assuré est tenu de déclarer tout sinistre à son assureur dans les délais prévus "
            "au contrat. Ces délais, qui ne peuvent être inférieurs à cinq jours ouvrés pour "
            "les sinistres de droit commun et à deux jours ouvrés pour le vol, courent à "
            "compter de la date à laquelle l'assuré a eu connaissance du sinistre.\n\n"
            "La tardiveté de la déclaration n'est opposable à l'assuré que si l'assureur "
            "établit que ce retard lui a causé un préjudice.\n\n"
            "INSTRUCTION DU SINISTRE\n"
            "L'assureur dispose d'un délai de trois mois à compter de la réception de "
            "l'ensemble des pièces justificatives pour régler le sinistre ou notifier "
            "son refus de garantie avec motivation.\n\n"
            "Ce délai est suspendu pendant les périodes d'expertise diligentée à la demande "
            "de l'une ou l'autre des parties.\n\n"
            "INTÉRÊTS DE RETARD\n"
            "Passé le délai de trois mois, les sommes dues par l'assureur produisent "
            "de plein droit des intérêts de retard au taux légal majoré de moitié, "
            "sans mise en demeure préalable.\n\n"
            "RECOURS DE L'ASSURÉ\n"
            "En cas de litige sur le montant de l'indemnité, l'assuré peut :\n"
            "1° Saisir la CRCA d'une réclamation ;\n"
            "2° Recourir à l'expertise contradictoire prévue au contrat ;\n"
            "3° Saisir la juridiction compétente (Tribunal de Commerce).\n\n"
            "SANCTIONS DES RETARDS D'INDEMNISATION\n"
            "La CRCA peut sanctionner les entreprises d'assurance qui présentent "
            "un taux anormalement élevé de dossiers sinistres en suspens ou qui "
            "ne respectent pas systématiquement les délais légaux d'indemnisation. "
            "Les sanctions applicables sont celles prévues à l'article 312 du Code CIMA.\n"
        ),
    },
]


async def main():
    conn = await asyncpg.connect(DB)
    inserted = 0
    updated = 0
    try:
        for doc in DOCS:
            texte = (doc.get("texte_integral") or "")[:80_000]
            existing = await conn.fetchval(
                "SELECT id FROM legal_corpus WHERE ref = $1", doc["ref"]
            )
            if existing:
                await conn.execute(
                    """UPDATE legal_corpus SET
                        titre=$1, type=$2, corpus=$3, juridiction=$4,
                        domaine=$5, pays=$6, date_decision=$7, source_url=$8,
                        resume=$9, texte_integral=$10
                       WHERE ref=$11""",
                    doc["titre"], doc["type"], doc["corpus"], doc.get("juridiction"),
                    doc.get("domaine"), doc.get("pays"), doc.get("date"),
                    doc.get("source_url"), doc.get("resume"), texte, doc["ref"],
                )
                print(f"  ✓ UPDATED  {doc['ref']}")
                updated += 1
            else:
                await conn.execute(
                    """INSERT INTO legal_corpus
                        (ref, titre, type, corpus, juridiction, domaine, pays,
                         date_decision, source_url, resume, texte_integral)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                    doc["ref"], doc["titre"], doc["type"], doc["corpus"],
                    doc.get("juridiction"), doc.get("domaine"), doc.get("pays"),
                    doc.get("date"), doc.get("source_url"), doc.get("resume"), texte,
                )
                print(f"  ✓ INSERTED {doc['ref']}")
                inserted += 1
    finally:
        await conn.close()

    print(f"\n{inserted} insérés, {updated} mis à jour — {len(DOCS)} documents Code CIMA traités.")


if __name__ == "__main__":
    asyncio.run(main())
