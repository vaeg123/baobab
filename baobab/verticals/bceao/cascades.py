"""
Cascades BCEAO — Banque et Finance UEMOA
Couvre Instruction 008/2021 (LCB/FT), Loi bancaire UMOA 2009, Règlements 15/2002 et 09/2010.
"""
from baobab.engines.event_engine.cascade import CascadeDefinition, CascadeStep
from baobab.verticals.bceao.events import BceaoEventType


DECLARATION_SOUPCON_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.DECLARATION.SOUPCON.V2021",
    event_type=BceaoEventType.DECLARATION_SOUPCON,
    corpus="BCEAO",
    description="Déclaration de soupçon LCB/FT — Instruction BCEAO 008/2021",
    steps=[
        CascadeStep(
            name="Détection et gel interne de l'opération suspecte",
            rule_id="BCEAO.INSTR008.ART23.V2021",
            deadline_days=0,
        ),
        CascadeStep(
            name="Déclaration à la CENTIF (obligatoire sous 24h)",
            rule_id="BCEAO.INSTR008.ART25.V2021",
            deadline_days=1,
            sanction="Amende 5 000 000 à 50 000 000 FCFA + suspension agrément possible",
        ),
        CascadeStep(
            name="Transmission du dossier complet à la CENTIF",
            rule_id="BCEAO.INSTR008.ART26.V2021",
            deadline_days=3,
        ),
        CascadeStep(
            name="Blocage des fonds si instruction CENTIF",
            rule_id="BCEAO.INSTR008.ART30.V2021",
            deadline_days=5,
            sanction="Complicité blanchiment",
        ),
        CascadeStep(
            name="Rapport interne compliance",
            rule_id="BCEAO.INSTR008.ART35.V2021",
            deadline_days=7,
        ),
        CascadeStep(
            name="Archivage dossier (10 ans minimum)",
            rule_id="BCEAO.INSTR008.ART40.V2021",
            deadline_days=None,
            sanction="Sanction pénale",
        ),
    ],
)


CONTROLE_CBF_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.CONTROLE.CBF.V2009",
    event_type=BceaoEventType.CONTROLE_CBF,
    corpus="BCEAO",
    description="Contrôle sur place Commission Bancaire — Loi bancaire UMOA Art. 52-68",
    steps=[
        CascadeStep(
            name="Réception notification de contrôle CBF",
            rule_id="BCEAO.LOI_BANCAIRE.ART52.V2009",
            deadline_days=0,
        ),
        CascadeStep(
            name="Remise des documents demandés (délai 48h)",
            rule_id="BCEAO.LOI_BANCAIRE.ART54.V2009",
            deadline_days=2,
            sanction="Injonction + astreinte journalière",
        ),
        CascadeStep(
            name="Accueil de la mission et mise à disposition locaux",
            rule_id="BCEAO.LOI_BANCAIRE.ART55.V2009",
            deadline_days=3,
        ),
        CascadeStep(
            name="Réponse aux questionnaires de la mission",
            rule_id="BCEAO.LOI_BANCAIRE.ART56.V2009",
            deadline_days=15,
        ),
        CascadeStep(
            name="Rapport préliminaire CBF — réponse de l'établissement sous 15j",
            rule_id="BCEAO.LOI_BANCAIRE.ART60.V2009",
            deadline_days=30,
        ),
        CascadeStep(
            name="Rapport définitif CBF",
            rule_id="BCEAO.LOI_BANCAIRE.ART61.V2009",
            deadline_days=60,
        ),
        CascadeStep(
            name="Plan de redressement si injonction",
            rule_id="BCEAO.LOI_BANCAIRE.ART65.V2009",
            deadline_days=90,
            sanction="Sanctions disciplinaires jusqu'au retrait d'agrément",
        ),
        CascadeStep(
            name="Mise en œuvre mesures correctives",
            rule_id="BCEAO.LOI_BANCAIRE.ART66.V2009",
            deadline_days=180,
        ),
    ],
)


RAPPORT_MENSUEL_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.RAPPORT.MENSUEL.V2018",
    event_type=BceaoEventType.RAPPORT_MENSUEL_BCEAO,
    corpus="BCEAO",
    description="Reporting réglementaire mensuel — Instruction BCEAO 94-01",
    steps=[
        CascadeStep(
            name="Clôture des données comptables du mois",
            rule_id="BCEAO.INSTR9401.ART5.V2018",
            deadline_days=0,
        ),
        CascadeStep(
            name="Réconciliation des comptes et validation interne",
            rule_id="BCEAO.INSTR9401.ART6.V2018",
            deadline_days=10,
        ),
        CascadeStep(
            name="Transmission reporting BCEAO (délai J+15)",
            rule_id="BCEAO.INSTR9401.ART7.V2018",
            deadline_days=15,
            sanction="Amende 500 000 FCFA/jour de retard",
        ),
        CascadeStep(
            name="Transmission reporting CBF (délai J+20)",
            rule_id="BCEAO.LOI_BANCAIRE.ART48.V2009",
            deadline_days=20,
            sanction="Injonction CBF",
        ),
        CascadeStep(
            name="Archivage états transmis",
            rule_id="BCEAO.INSTR9401.ART10.V2018",
            deadline_days=30,
        ),
    ],
)


INCIDENT_PAIEMENT_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.INCIDENT.PAIEMENT.V2002",
    event_type=BceaoEventType.INCIDENT_PAIEMENT,
    corpus="BCEAO",
    description="Incident de paiement / chèque sans provision — Règlement BCEAO 15/2002",
    steps=[
        CascadeStep(
            name="Constatation incident de paiement",
            rule_id="BCEAO.REGL15.ART8.V2002",
            deadline_days=0,
        ),
        CascadeStep(
            name="Déclaration à la Centrale des Incidents de Paiement (CIP) sous 48h",
            rule_id="BCEAO.REGL15.ART10.V2002",
            deadline_days=2,
            sanction="Amende + responsabilité solidaire",
        ),
        CascadeStep(
            name="Notification écrite au client",
            rule_id="BCEAO.REGL15.ART12.V2002",
            deadline_days=3,
        ),
        CascadeStep(
            name="Mise en demeure de régularisation au client",
            rule_id="BCEAO.REGL15.ART14.V2002",
            deadline_days=10,
        ),
        CascadeStep(
            name="Si non régularisé : déclaration interdiction bancaire",
            rule_id="BCEAO.REGL15.ART16.V2002",
            deadline_days=15,
            sanction="Maintien interdiction jusqu'à régularisation",
        ),
        CascadeStep(
            name="Si régularisation : déclaration levée d'interdiction à CIP",
            rule_id="BCEAO.REGL15.ART18.V2002",
            deadline_days=5,
        ),
    ],
)


AGREMENT_BANQUE_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.AGREMENT.BANQUE.V2009",
    event_type=BceaoEventType.AGREMENT_BANQUE,
    corpus="BCEAO",
    description="Demande d'agrément bancaire — Loi bancaire UMOA Art. 15-35",
    steps=[
        CascadeStep(
            name="Constitution et dépôt du dossier d'agrément CBF",
            rule_id="BCEAO.LOI_BANCAIRE.ART15.V2009",
            deadline_days=0,
        ),
        CascadeStep(
            name="Vérification complétude dossier par CBF",
            rule_id="BCEAO.LOI_BANCAIRE.ART17.V2009",
            deadline_days=30,
            sanction="Dossier incomplet = irrecevabilité",
        ),
        CascadeStep(
            name="Instruction du dossier par CBF",
            rule_id="BCEAO.LOI_BANCAIRE.ART20.V2009",
            deadline_days=90,
        ),
        CascadeStep(
            name="Audition des dirigeants par CBF (si requise)",
            rule_id="BCEAO.LOI_BANCAIRE.ART21.V2009",
            deadline_days=120,
        ),
        CascadeStep(
            name="Décision d'agrément ou refus",
            rule_id="BCEAO.LOI_BANCAIRE.ART22.V2009",
            deadline_days=180,
            sanction="Silence = refus implicite",
        ),
        CascadeStep(
            name="Publication de l'agrément au Journal Officiel",
            rule_id="BCEAO.LOI_BANCAIRE.ART24.V2009",
            deadline_days=210,
        ),
        CascadeStep(
            name="Libération du capital minimum réglementaire",
            rule_id="BCEAO.LOI_BANCAIRE.ART25.V2009",
            deadline_days=240,
            sanction="Retrait agrément",
        ),
        CascadeStep(
            name="Ouverture effective et premier reporting BCEAO",
            rule_id="BCEAO.LOI_BANCAIRE.ART30.V2009",
            deadline_days=270,
        ),
    ],
)


AGREMENT_MONNAIE_ELEC_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.AGREMENT.MONNAIE.ELEC.V2015",
    event_type=BceaoEventType.AGREMENT_MONNAIE_ELEC,
    corpus="BCEAO",
    description="Agrément émetteur monnaie électronique — Instruction BCEAO 008-05-2015",
    steps=[
        CascadeStep(
            name="Dépôt dossier agrément monnaie électronique BCEAO",
            rule_id="BCEAO.INSTR00815.ART5.V2015",
            deadline_days=0,
        ),
        CascadeStep(
            name="Vérification dossier",
            rule_id="BCEAO.INSTR00815.ART7.V2015",
            deadline_days=30,
        ),
        CascadeStep(
            name="Instruction technique et financière",
            rule_id="BCEAO.INSTR00815.ART8.V2015",
            deadline_days=90,
        ),
        CascadeStep(
            name="Décision BCEAO",
            rule_id="BCEAO.INSTR00815.ART10.V2015",
            deadline_days=120,
            sanction="Exercice illégal activité d'émission",
        ),
        CascadeStep(
            name="Libération fonds de garantie (capital minimum)",
            rule_id="BCEAO.INSTR00815.ART15.V2015",
            deadline_days=150,
        ),
        CascadeStep(
            name="Mise en place dispositif LCB/FT",
            rule_id="BCEAO.INSTR008.ART5.V2021",
            deadline_days=180,
            sanction="Suspension agrément",
        ),
        CascadeStep(
            name="Premier rapport mensuel activités monnaie électronique",
            rule_id="BCEAO.INSTR00815.ART20.V2015",
            deadline_days=210,
        ),
    ],
)


RATIO_PRUDENTIEL_BREACH_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.RATIO.PRUDENTIEL.BREACH.V2010",
    event_type=BceaoEventType.RATIO_PRUDENTIEL_BREACH,
    corpus="BCEAO",
    description="Franchissement d'un seuil prudentiel — Règlement BCEAO 09/2010",
    steps=[
        CascadeStep(
            name="Constatation du breach prudentiel (ratio solvabilité, liquidité, concentration)",
            rule_id="BCEAO.REGL09.ART5.V2010",
            deadline_days=0,
        ),
        CascadeStep(
            name="Information immédiate de la Direction Générale",
            rule_id="BCEAO.REGL09.ART8.V2010",
            deadline_days=1,
        ),
        CascadeStep(
            name="Déclaration spontanée à la CBF",
            rule_id="BCEAO.REGL09.ART10.V2010",
            deadline_days=5,
            sanction="Aggravation sanction si dissimulation",
        ),
        CascadeStep(
            name="Plan de retour à la conformité soumis à CBF",
            rule_id="BCEAO.REGL09.ART12.V2010",
            deadline_days=15,
            sanction="Injonction formelle CBF",
        ),
        CascadeStep(
            name="Mise en œuvre plan de redressement",
            rule_id="BCEAO.REGL09.ART13.V2010",
            deadline_days=30,
        ),
        CascadeStep(
            name="Rapport de suivi mensuel à CBF",
            rule_id="BCEAO.REGL09.ART14.V2010",
            deadline_days=60,
        ),
        CascadeStep(
            name="Retour au ratio conforme (ou sanction)",
            rule_id="BCEAO.REGL09.ART15.V2010",
            deadline_days=90,
            sanction="Sanctions disciplinaires progressives jusqu'à retrait agrément",
        ),
    ],
)


OUVERTURE_COMPTE_KYC_CASCADE = CascadeDefinition(
    cascade_id="BCEAO.OUVERTURE.COMPTE.KYC.V2021",
    event_type=BceaoEventType.OUVERTURE_COMPTE_KYC,
    corpus="BCEAO",
    description="Ouverture de compte / KYC — Instruction BCEAO 008/2021 LCB/FT",
    steps=[
        CascadeStep(
            name="Collecte documents KYC client",
            rule_id="BCEAO.INSTR008.ART10.V2021",
            deadline_days=0,
        ),
        CascadeStep(
            name="Vérification identité et authenticité pièces",
            rule_id="BCEAO.INSTR008.ART11.V2021",
            deadline_days=2,
            sanction="Nullité ouverture + responsabilité établissement",
        ),
        CascadeStep(
            name="Screening listes sanctions internationales (ONU, UE, OFAC)",
            rule_id="BCEAO.INSTR008.ART13.V2021",
            deadline_days=2,
            sanction="Blocage immédiat + déclaration CENTIF",
        ),
        CascadeStep(
            name="Classification du risque client (faible / moyen / élevé)",
            rule_id="BCEAO.INSTR008.ART15.V2021",
            deadline_days=3,
        ),
        CascadeStep(
            name="Validation Responsable Conformité",
            rule_id="BCEAO.INSTR008.ART16.V2021",
            deadline_days=5,
        ),
        CascadeStep(
            name="Ouverture compte et mise à jour système",
            rule_id="BCEAO.INSTR008.ART18.V2021",
            deadline_days=7,
        ),
        CascadeStep(
            name="Archivage dossier KYC (10 ans)",
            rule_id="BCEAO.INSTR008.ART40.V2021",
            deadline_days=None,
        ),
    ],
)
