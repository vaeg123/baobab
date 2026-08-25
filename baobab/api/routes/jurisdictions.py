"""Public discovery endpoints for BAOBAB legal packs and source provenance."""

from fastapi import APIRouter, HTTPException

from baobab.core.jurisdictions import (
    JURISDICTION_BY_CODE,
    SOURCE_BY_CODE,
    jurisdiction_payload,
    source_payload,
)

router = APIRouter(tags=["jurisdictions"])


@router.get("/legal/jurisdictions")
async def list_jurisdictions(pack: str | None = None, kind: str | None = None):
    items = jurisdiction_payload()
    if pack:
        items = [item for item in items if item["pack"] == pack.lower()]
    if kind:
        items = [item for item in items if item["kind"] == kind.upper()]
    return {"total": len(items), "results": items}


@router.get("/legal/jurisdictions/{code}")
async def get_jurisdiction(code: str):
    item = JURISDICTION_BY_CODE.get(code.upper())
    if not item:
        raise HTTPException(404, "Juridiction inconnue.")
    return next(row for row in jurisdiction_payload() if row["code"] == item.code)


@router.get("/legal/sources")
async def list_sources(jurisdiction: str | None = None):
    items = source_payload()
    if jurisdiction:
        code = jurisdiction.upper()
        items = [item for item in items if item["jurisdiction_code"] == code]
    return {"total": len(items), "results": items}


@router.get("/legal/sources/{code}")
async def get_source(code: str):
    item = SOURCE_BY_CODE.get(code.upper())
    if not item:
        raise HTTPException(404, "Source juridique inconnue.")
    return next(row for row in source_payload() if row["code"] == item.code)
