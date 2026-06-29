"""
Cascades CIMA — MVP Sinistre
Basé sur le Code CIMA Articles 260–300 (délais d'indemnisation)
"""
from baobab.engines.event_engine.cascade import CascadeDefinition, CascadeStep
from baobab.verticals.cima.events import CimaEventType


SINISTRE_INCENDIE_CASCADE = CascadeDefinition(
    cascade_id="CIMA.SINISTRE.INCENDIE.V2022",
    event_type=CimaEventType.SINISTRE_INCENDIE,
    corpus="CIMA",
    description="Cascade sinistre incendie — Art. 12, 260-270 CIMA",
    steps=[
        CascadeStep(
            name="Déclaration sinistre",
            rule_id="CI.CIMA.CODE.ART12.V2022",
            deadline_days=5,
            sanction="Déchéance possible si déclaration hors délai (Art. 12 CIMA)",
        ),
        CascadeStep(
            name="Désignation expert",
            rule_id="CI.CIMA.CODE.ART260.V2022",
            deadline_days=15,
            sanction="Mise en demeure assureur (Art. 260 CIMA)",
        ),
        CascadeStep(
            name="Rapport d'expertise",
            rule_id="CI.CIMA.CODE.ART261.V2022",
            deadline_days=30,
        ),
        CascadeStep(
            name="Offre provisionnelle d'indemnisation",
            rule_id="CI.CIMA.CODE.ART269.V2022",
            deadline_days=45,
            sanction="Intérêts de retard au double du taux légal",
        ),
        CascadeStep(
            name="Offre définitive d'indemnisation",
            rule_id="CI.CIMA.CODE.ART270.V2022",
            deadline_days=90,
            sanction="Intérêts de retard au double du taux légal (Art. 270 CIMA)",
        ),
        CascadeStep(
            name="Paiement indemnité",
            rule_id="CI.CIMA.CODE.ART271.V2022",
            deadline_days=105,
            sanction="Intérêts de retard majorés",
        ),
        CascadeStep(
            name="Archivage dossier",
            rule_id="CI.CIMA.CODE.ART300.V2022",
            deadline_days=None,
        ),
    ],
)


SINISTRE_AUTO_CASCADE = CascadeDefinition(
    cascade_id="CIMA.SINISTRE.AUTO.V2022",
    event_type=CimaEventType.SINISTRE_AUTO,
    corpus="CIMA",
    description="Cascade sinistre automobile — Art. 231-252 CIMA",
    steps=[
        CascadeStep(
            name="Déclaration sinistre auto",
            rule_id="CI.CIMA.CODE.ART231.V2022",
            deadline_days=5,
        ),
        CascadeStep(
            name="Constat amiable ou procès-verbal",
            rule_id="CI.CIMA.CODE.ART232.V2022",
            deadline_days=10,
        ),
        CascadeStep(
            name="Expertise véhicule",
            rule_id="CI.CIMA.CODE.ART240.V2022",
            deadline_days=20,
        ),
        CascadeStep(
            name="Offre d'indemnisation",
            rule_id="CI.CIMA.CODE.ART248.V2022",
            deadline_days=60,
            sanction="Intérêts légaux (Art. 252 CIMA)",
        ),
        CascadeStep(
            name="Paiement",
            rule_id="CI.CIMA.CODE.ART250.V2022",
            deadline_days=75,
        ),
    ],
)
