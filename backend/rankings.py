from fastapi import APIRouter, Query
from database import get_db
from sqlalchemy import text

router = APIRouter()

WOW_CLASSES = [
    "Death Knight", "Demon Hunter", "Druid", "Evoker", "Hunter",
    "Mage", "Monk", "Paladin", "Priest", "Rogue",
    "Shaman", "Warlock", "Warrior"
]

FIGHT_STYLES = ["Patchwerk", "HecticAddCleave", "LightMovement", "HeavyMovement"]


@router.get("/api/rankings")
def get_rankings(
    fight_style: str = Query(default="Patchwerk"),
    character_class: str = Query(default=""),
    character_spec: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=100),
):
    db = get_db()
    try:
        filters = ["h.dps IS NOT NULL", "h.dps > 0", "h.character_name IS NOT NULL"]
        params = {"fight_style": fight_style, "limit": limit}

        if fight_style:
            filters.append("LOWER(h.fight_style) = LOWER(:fight_style)")
        if character_class:
            filters.append("LOWER(h.character_class) = LOWER(:character_class)")
            params["character_class"] = character_class
        if character_spec:
            filters.append("LOWER(h.character_spec) = LOWER(:character_spec)")
            params["character_spec"] = character_spec

        where = " AND ".join(filters)

        # Best result per unique (name, realm) combo — no spam from the same char
        sql = text(f"""
            SELECT DISTINCT ON (LOWER(h.character_name), LOWER(COALESCE(h.character_realm, '')))
                h.job_id,
                h.character_name,
                h.character_realm,
                h.character_class,
                h.character_spec,
                h.fight_style,
                h.dps,
                h.created_at
            FROM history h
            WHERE {where}
            ORDER BY
                LOWER(h.character_name),
                LOWER(COALESCE(h.character_realm, '')),
                h.dps DESC
        """)

        rows = db.execute(sql, params).fetchall()

        # Sort by dps desc and take top N
        results = sorted(
            [
                {
                    "rank": 0,
                    "job_id": r.job_id,
                    "character_name": r.character_name,
                    "character_realm": r.character_realm or "",
                    "character_class": r.character_class or "",
                    "character_spec": r.character_spec or "",
                    "fight_style": r.fight_style or "",
                    "dps": float(r.dps),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            key=lambda x: x["dps"],
            reverse=True,
        )[:limit]

        for i, entry in enumerate(results):
            entry["rank"] = i + 1

        return {"rankings": results, "fight_style": fight_style}
    finally:
        db.close()


@router.get("/api/rankings/top3")
def get_top3(fight_style: str = Query(default="Patchwerk")):
    """Lightweight endpoint for home page podium — always Patchwerk, no class filter."""
    db = get_db()
    try:
        sql = text("""
            SELECT DISTINCT ON (LOWER(h.character_name), LOWER(COALESCE(h.character_realm, '')))
                h.job_id,
                h.character_name,
                h.character_realm,
                h.character_class,
                h.character_spec,
                h.dps,
                h.created_at
            FROM history h
            WHERE h.dps IS NOT NULL
              AND h.dps > 0
              AND h.character_name IS NOT NULL
              AND LOWER(h.fight_style) = LOWER(:fight_style)
            ORDER BY
                LOWER(h.character_name),
                LOWER(COALESCE(h.character_realm, '')),
                h.dps DESC
        """)
        rows = db.execute(sql, {"fight_style": fight_style}).fetchall()
        results = sorted(
            [
                {
                    "job_id": r.job_id,
                    "character_name": r.character_name,
                    "character_realm": r.character_realm or "",
                    "character_class": r.character_class or "",
                    "character_spec": r.character_spec or "",
                    "dps": float(r.dps),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            key=lambda x: x["dps"],
            reverse=True,
        )[:3]
        for i, entry in enumerate(results):
            entry["rank"] = i + 1
        return {"top3": results}
    finally:
        db.close()


@router.get("/api/rankings/meta")
def get_rankings_meta():
    """Returns available classes, specs and fight styles for filter dropdowns."""
    db = get_db()
    try:
        specs_sql = text("""
            SELECT DISTINCT character_class, character_spec
            FROM history
            WHERE character_class IS NOT NULL AND character_spec IS NOT NULL
            ORDER BY character_class, character_spec
        """)
        rows = db.execute(specs_sql).fetchall()
        classes_specs = {}
        for r in rows:
            cls = r.character_class
            if cls not in classes_specs:
                classes_specs[cls] = []
            if r.character_spec and r.character_spec not in classes_specs[cls]:
                classes_specs[cls].append(r.character_spec)
        return {
            "classes": sorted(classes_specs.keys()),
            "classes_specs": classes_specs,
            "fight_styles": FIGHT_STYLES,
        }
    finally:
        db.close()
