"""
Cascades OHADA — Droit des affaires
Couvre AUSCGIE, AUDCG, AUVE pour les principaux événements juridiques.
"""
from baobab.engines.event_engine.cascade import CascadeDefinition, CascadeStep
from baobab.verticals.ohada.events import OhadaEventType


CREATION_SARL_CASCADE = CascadeDefinition(
    cascade_id="OHADA.CREATION.SARL.V2014",
    event_type=OhadaEventType.CREATION_SARL,
    corpus="OHADA",
    description="Cascade création SARL — AUSCGIE Art. 309-395",
    steps=[
        CascadeStep(
            name="Rédaction et signature des statuts",
            rule_id="OHADA.AUSCGIE.ART309.V2014",
            deadline_days=0,
        ),
        CascadeStep(
            name="Dépôt du capital social en banque (libération au moins 1/4)",
            rule_id="OHADA.AUSCGIE.ART311.V2014",
            deadline_days=5,
        ),
        CascadeStep(
            name="Enregistrement des statuts (Administration fiscale)",
            rule_id="OHADA.AUDCG.ART27.V2010",
            deadline_days=30,
            sanction="Amende fiscale",
        ),
        CascadeStep(
            name="Immatriculation au RCCM",
            rule_id="OHADA.AUDCG.ART25.V2010",
            deadline_days=45,
            sanction="Absence de personnalité morale",
        ),
        CascadeStep(
            name="Publication dans un Journal d'Annonces Légales",
            rule_id="OHADA.AUSCGIE.ART260.V2014",
            deadline_days=75,
        ),
        CascadeStep(
            name="Déclaration fiscale d'existence",
            rule_id="NATIONAL.CGI.ART69.V2022",
            deadline_days=30,
        ),
        CascadeStep(
            name="Affiliation organismes sociaux",
            rule_id="NATIONAL.CSS.ART10.V2022",
            deadline_days=30,
        ),
    ],
)


CREATION_SA_CASCADE = CascadeDefinition(
    cascade_id="OHADA.CREATION.SA.V2014",
    event_type=OhadaEventType.CREATION_SA,
    corpus="OHADA",
    description="Cascade création SA — AUSCGIE Art. 385-920",
    steps=[
        CascadeStep(
            name="Rédaction statuts SA",
            rule_id="OHADA.AUSCGIE.ART385.V2014",
            deadline_days=0,
        ),
        CascadeStep(
            name="Constitution et souscription du capital (libération 50% minimum)",
            rule_id="OHADA.AUSCGIE.ART389.V2014",
            deadline_days=30,
            sanction="Nullité de la société",
        ),
        CascadeStep(
            name="Assemblée constitutive des actionnaires",
            rule_id="OHADA.AUSCGIE.ART404.V2014",
            deadline_days=45,
        ),
        CascadeStep(
            name="Enregistrement fiscal des statuts",
            rule_id="OHADA.AUDCG.ART27.V2010",
            deadline_days=60,
        ),
        CascadeStep(
            name="Immatriculation RCCM",
            rule_id="OHADA.AUDCG.ART25.V2010",
            deadline_days=75,
        ),
        CascadeStep(
            name="Publication JAL",
            rule_id="OHADA.AUSCGIE.ART260.V2014",
            deadline_days=90,
        ),
        CascadeStep(
            name="Premier Conseil d'Administration (nomination dirigeants)",
            rule_id="OHADA.AUSCGIE.ART414.V2014",
            deadline_days=105,
        ),
    ],
)


AGO_ANNUELLE_CASCADE = CascadeDefinition(
    cascade_id="OHADA.AGO.ANNUELLE.V2014",
    event_type=OhadaEventType.AGO_ANNUELLE,
    corpus="OHADA",
    description="Cascade AGO annuelle — AUSCGIE Art. 133-156",
    steps=[
        CascadeStep(
            name="Clôture de l'exercice comptable",
            rule_id="OHADA.AUSCGIE.ART138.V2014",
            deadline_days=0,
        ),
        CascadeStep(
            name="Établissement des états financiers annuels",
            rule_id="OHADA.AUSCGIE.ART138.V2014",
            deadline_days=90,
        ),
        CascadeStep(
            name="Rapport du Commissaire aux Comptes",
            rule_id="OHADA.AUSCGIE.ART702.V2014",
            deadline_days=120,
            sanction="Nullité des délibérations",
        ),
        CascadeStep(
            name="Convocation des associés/actionnaires (21j minimum avant AGO)",
            rule_id="OHADA.AUSCGIE.ART133.V2014",
            deadline_days=150,
            sanction="Nullité de l'AGO",
        ),
        CascadeStep(
            name="Tenue de l'AGO (dans les 6 mois suivant clôture)",
            rule_id="OHADA.AUSCGIE.ART140.V2014",
            deadline_days=180,
            sanction="Sanction pénale dirigeants + dissolution judiciaire possible",
        ),
        CascadeStep(
            name="Dépôt des comptes approuvés au RCCM",
            rule_id="OHADA.AUDCG.ART20.V2010",
            deadline_days=210,
            sanction="Amende + injonction tribunal",
        ),
    ],
)


DISSOLUTION_CASCADE = CascadeDefinition(
    cascade_id="OHADA.DISSOLUTION.V2014",
    event_type=OhadaEventType.DISSOLUTION,
    corpus="OHADA",
    description="Cascade dissolution — AUSCGIE Art. 200-234",
    steps=[
        CascadeStep(
            name="Décision de dissolution (AGE ou tribunal)",
            rule_id="OHADA.AUSCGIE.ART200.V2014",
            deadline_days=0,
        ),
        CascadeStep(
            name="Nomination du liquidateur",
            rule_id="OHADA.AUSCGIE.ART204.V2014",
            deadline_days=15,
        ),
        CascadeStep(
            name="Publication dissolution dans JAL",
            rule_id="OHADA.AUSCGIE.ART206.V2014",
            deadline_days=15,
            sanction="Inopposabilité aux tiers",
        ),
        CascadeStep(
            name="Déclaration de cessation aux autorités fiscales et sociales",
            rule_id="NATIONAL.CGI.ART72.V2022",
            deadline_days=30,
        ),
        CascadeStep(
            name="Inventaire des actifs et passifs",
            rule_id="OHADA.AUSCGIE.ART208.V2014",
            deadline_days=60,
        ),
        CascadeStep(
            name="Recouvrement des créances et paiement des dettes",
            rule_id="OHADA.AUSCGIE.ART210.V2014",
            deadline_days=180,
        ),
        CascadeStep(
            name="Partage de l'actif net entre associés",
            rule_id="OHADA.AUSCGIE.ART215.V2014",
            deadline_days=210,
        ),
        CascadeStep(
            name="Radiation du RCCM",
            rule_id="OHADA.AUDCG.ART57.V2010",
            deadline_days=240,
            sanction="Maintien fictif de la personnalité morale",
        ),
    ],
)


CESSION_PARTS_CASCADE = CascadeDefinition(
    cascade_id="OHADA.CESSION.PARTS.V2014",
    event_type=OhadaEventType.CESSION_PARTS,
    corpus="OHADA",
    description="Cascade cession de parts SARL — AUSCGIE Art. 317-328",
    steps=[
        CascadeStep(
            name="Notification aux autres associés (droit de préemption)",
            rule_id="OHADA.AUSCGIE.ART317.V2014",
            deadline_days=0,
        ),
        CascadeStep(
            name="Délai de réponse des associés",
            rule_id="OHADA.AUSCGIE.ART318.V2014",
            deadline_days=30,
            sanction="Réputé avoir renoncé",
        ),
        CascadeStep(
            name="Agrément de la cession (AGO si requis)",
            rule_id="OHADA.AUSCGIE.ART319.V2014",
            deadline_days=45,
        ),
        CascadeStep(
            name="Acte de cession (écrit obligatoire)",
            rule_id="OHADA.AUSCGIE.ART317.V2014",
            deadline_days=60,
        ),
        CascadeStep(
            name="Enregistrement fiscal de l'acte de cession",
            rule_id="NATIONAL.CGI.ART150.V2022",
            deadline_days=75,
            sanction="Droits de mutation + pénalités",
        ),
        CascadeStep(
            name="Mise à jour statuts et registre des associés",
            rule_id="OHADA.AUSCGIE.ART325.V2014",
            deadline_days=90,
        ),
        CascadeStep(
            name="Dépôt modificatif au RCCM",
            rule_id="OHADA.AUDCG.ART35.V2010",
            deadline_days=105,
        ),
    ],
)


FUSION_ABSORPTION_CASCADE = CascadeDefinition(
    cascade_id="OHADA.FUSION.ABSORPTION.V2014",
    event_type=OhadaEventType.FUSION_ABSORPTION,
    corpus="OHADA",
    description="Cascade fusion-absorption — AUSCGIE Art. 189-199",
    steps=[
        CascadeStep(
            name="Projet de fusion établi et signé",
            rule_id="OHADA.AUSCGIE.ART191.V2014",
            deadline_days=0,
        ),
        CascadeStep(
            name="Dépôt projet au RCCM (30j avant toute AGE)",
            rule_id="OHADA.AUSCGIE.ART193.V2014",
            deadline_days=5,
            sanction="Nullité de la fusion",
        ),
        CascadeStep(
            name="Rapport commissaire à la fusion",
            rule_id="OHADA.AUSCGIE.ART194.V2014",
            deadline_days=30,
        ),
        CascadeStep(
            name="AGE des sociétés fusionnantes (approbation)",
            rule_id="OHADA.AUSCGIE.ART195.V2014",
            deadline_days=60,
        ),
        CascadeStep(
            name="Publication de la fusion dans JAL",
            rule_id="OHADA.AUSCGIE.ART197.V2014",
            deadline_days=75,
            sanction="Inopposabilité aux créanciers",
        ),
        CascadeStep(
            name="Opposition des créanciers (délai 30j courant)",
            rule_id="OHADA.AUSCGIE.ART198.V2014",
            deadline_days=105,
        ),
        CascadeStep(
            name="Immatriculation société absorbante / RCCM",
            rule_id="OHADA.AUDCG.ART35.V2010",
            deadline_days=120,
        ),
        CascadeStep(
            name="Radiation société absorbée au RCCM",
            rule_id="OHADA.AUDCG.ART57.V2010",
            deadline_days=135,
        ),
    ],
)


INJONCTION_PAYER_CASCADE = CascadeDefinition(
    cascade_id="OHADA.INJONCTION.PAYER.V2010",
    event_type=OhadaEventType.INJONCTION_PAYER,
    corpus="OHADA",
    description="Cascade injonction de payer — AUVE Art. 1-25",
    steps=[
        CascadeStep(
            name="Requête en injonction de payer déposée au Tribunal",
            rule_id="OHADA.AUVE.ART1.V2010",
            deadline_days=0,
        ),
        CascadeStep(
            name="Ordonnance du juge (délai indicatif)",
            rule_id="OHADA.AUVE.ART4.V2010",
            deadline_days=15,
        ),
        CascadeStep(
            name="Signification de l'ordonnance au débiteur",
            rule_id="OHADA.AUVE.ART7.V2010",
            deadline_days=45,
            sanction="Caducité de l'ordonnance",
        ),
        CascadeStep(
            name="Délai d'opposition du débiteur",
            rule_id="OHADA.AUVE.ART9.V2010",
            deadline_days=60,
        ),
        CascadeStep(
            name="Si pas d'opposition : apposition formule exécutoire",
            rule_id="OHADA.AUVE.ART14.V2010",
            deadline_days=75,
        ),
        CascadeStep(
            name="Exécution forcée (saisie-attribution possible)",
            rule_id="OHADA.AUVE.ART28.V2010",
            deadline_days=90,
        ),
    ],
)


IMMATRICULATION_RCCM_CASCADE = CascadeDefinition(
    cascade_id="OHADA.IMMATRICULATION.RCCM.V2010",
    event_type=OhadaEventType.IMMATRICULATION_RCCM,
    corpus="OHADA",
    description="Cascade immatriculation RCCM — AUDCG Art. 25-55",
    steps=[
        CascadeStep(
            name="Constitution du dossier RCCM",
            rule_id="OHADA.AUDCG.ART25.V2010",
            deadline_days=0,
        ),
        CascadeStep(
            name="Dépôt dossier au Greffe du Tribunal de Commerce",
            rule_id="OHADA.AUDCG.ART25.V2010",
            deadline_days=15,
            sanction="Impossibilité d'exercer légalement",
        ),
        CascadeStep(
            name="Vérification et immatriculation par le Greffe",
            rule_id="OHADA.AUDCG.ART29.V2010",
            deadline_days=30,
        ),
        CascadeStep(
            name="Délivrance extrait RCCM",
            rule_id="OHADA.AUDCG.ART31.V2010",
            deadline_days=35,
        ),
        CascadeStep(
            name="Première mise à jour comptable et déclaration TVA",
            rule_id="NATIONAL.CGI.ART69.V2022",
            deadline_days=60,
        ),
    ],
)
