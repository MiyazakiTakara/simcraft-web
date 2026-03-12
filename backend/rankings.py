from fastapi import APIRouter, Query
from database import SessionLocal
from sqlalchemy import text

router = APIRouter()

WOW_CLASSES = [
    "Death Knight", "Demon Hunter", "Druid", "Evoker", "Hunter",
    "Mage", "Monk", "Paladin", "Priest", "Rogue",
    "Shaman", "Warlock", "Warrior"
]

FIGHT_STYLES = ["Patchwerk", "HecticAddCleave", "LightMovement", "HeavyMovement"]

_PRIVACY_JOIN = """
    LEFT JOIN users u ON u.bnet_id = h.user_id
"""
_PRIVACY_FILTER = "(u.profile_private IS NULL OR u.profile_private = FALSE OR h.is_guest = TRUE)"
# Exclude private character entries
_PRIVACY_FILTER += " AND h.is_private = FALSE"
# Exclude simulations submitted via WoW addon without a session (source = 'addon')
_SOURCE_FILTER  = "(h.source IS NULL OR h.source != 'addon')"


@router.get("/api/rankings")
def get_rankings(
    fight_style: str = Query(default="Patchwerk"),
    character_class: str = Query(default=""),
    character_spec: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=100),
):
    filters = [
        "h.dps IS NOT NULL", "h.dps > 0", "h.character_name IS NOT NULL",
        _PRIVACY_FILTER,
        _SOURCE_FILTER,
    ]
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

    sql = text(f"""
        SELECT DISTINCT ON (LOWER(h.character_name), LOWER(COALESCE(h.character_realm_slug, '')))
            h.job_id,
            h.character_name,
            h.character_realm_slug AS character_realm,
            h.character_class,
            h.character_spec,
            h.fight_style,
            h.dps,
            h.created_at
        FROM history h
        {_PRIVACY_JOIN}
        WHERE {where}
        ORDER BY
            LOWER(h.character_name),
            LOWER(COALESCE(h.character_realm_slug, '')),
            h.dps DESC
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, params).fetchall()

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


@router.get("/api/rankings/top3")
def get_top3(fight_style: str = Query(default="Patchwerk")):
    sql = text(f"""
        SELECT DISTINCT ON (LOWER(h.character_name), LOWER(COALESCE(h.character_realm_slug, '')))
            h.job_id,
            h.character_name,
            h.character_realm_slug AS character_realm,
            h.character_class,
            h.character_spec,
            h.dps,
            h.created_at
        FROM history h
        {_PRIVACY_JOIN}
        WHERE h.dps IS NOT NULL
          AND h.dps > 0
          AND h.character_name IS NOT NULL
          AND LOWER(h.fight_style) = LOWER(:fight_style)
          AND {_PRIVACY_FILTER}
          AND {_SOURCE_FILTER}
        ORDER BY
            LOWER(h.character_name),
            LOWER(COALESCE(h.character_realm_slug, '')),
            h.dps DESC
    """)

    with SessionLocal() as db:
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


@router.get("/api/rankings/meta")
def get_rankings_meta():
    specs_sql = text("""
        SELECT DISTINCT h.character_class, h.character_spec
        FROM history h
        LEFT JOIN users u ON u.bnet_id = h.user_id
        WHERE h.character_class IS NOT NULL AND h.character_spec IS NOT NULL
          AND (u.profile_private IS NULL OR u.profile_private = FALSE OR h.is_guest = TRUE)
          AND (h.source IS NULL OR h.source != 'addon')
        ORDER BY h.character_class, h.character_spec
    """)

    with SessionLocal() as db:
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
