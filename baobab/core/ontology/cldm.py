"""
Canonical Legal Data Model (CLDM)
8 objets racines — 15 propriétés universelles — principe d'immuabilité
"""
from enum import Enum


class RootObject(str, Enum):
    LEGAL_ENTITY    = "LegalEntity"
    LEGAL_EVENT     = "LegalEvent"
    LEGAL_RELATION  = "LegalRelation"
    LEGAL_RULE      = "LegalRule"
    LEGAL_RESOURCE  = "LegalResource"
    LEGAL_ACTOR     = "LegalActor"
    LEGAL_PROCESS   = "LegalProcess"
    LEGAL_KNOWLEDGE = "LegalKnowledge"


UNIVERSAL_PROPERTIES = [
    "id",
    "version",
    "created_at",
    "effective_date",
    "abrogation_date",
    "source",
    "territory",
    "language",
    "confidence",
    "status",
    "author",
    "signatory",
    "index_key",
    "trace_id",
    "integrity_hash",
]


RELATION_TYPES = [
    "abrogated_by",
    "modified_by",
    "cites",
    "applies_to",
    "triggers",
    "sanctions",
    "supersedes",
    "implements",
    "restricts",
    "extends",
]


class RelationDirection(str, Enum):
    OUTBOUND      = "outbound"
    INBOUND       = "inbound"
    BIDIRECTIONAL = "bidirectional"
