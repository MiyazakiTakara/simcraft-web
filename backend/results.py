import json
from fastapi import APIRouter, HTTPException
from simulation import jobs

router = APIRouter()


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def pct(val):
    """Normalize a ratio/percent value to 0-100 scale."""
    v = safe_float(val)
    return round(v * 100 if v <= 1 else v, 2)


def ability_dps(ab: dict) -> float:
    """
    Extract DPS from a SimC ability entry.
    SimC JSON2: portionaps.mean = DPS contribution of this ability.
    If portionaps is missing (parent entry without direct damage),
    recursively sum children portionaps.
    compoundamount.mean is total damage dealt (NOT DPS) — avoid for DPS.
    """
    pa = ab.get("portionaps")
    if isinstance(pa, dict):
        v = safe_float(pa.get("mean"))
        if v > 0:
            return v

    # Parent entry with no portionaps: sum children recursively
    children = ab.get("children", [])
    if children:
        total = sum(ability_dps(c) for c in children)
        if total > 0:
            return total

    # Last resort flat fields (older SimC formats)
    if isinstance(ab.get("dps"), (int, float)):
        return safe_float(ab["dps"])
    return 0.0


def ability_crit(ab: dict) -> float:
    """
    Extract crit % from ability.
    Looks inside directresults and tickresults for crit/hit counts.
    Falls back to children aggregate if parent has no results.
    """
    def _crit_from_results(results: dict) -> float | None:
        if not isinstance(results, dict):
            return None
        crit_block = results.get("crit", {})
        hit_block = results.get("hit", {})
        crit_count = safe_float(crit_block.get("countsum") if isinstance(crit_block, dict) else 0)
        hit_count = safe_float(hit_block.get("countsum") if isinstance(hit_block, dict) else 0)
        total = crit_count + hit_count
        if total > 0:
            return round((crit_count / total) * 100, 2)
        return None

    # Try directresults first, then tickresults
    for key in ("directresults", "tickresults"):
        result = _crit_from_results(ab.get(key, {}))
        if result is not None:
            return result

    # Try aggregating from children
    children = ab.get("children", [])
    if children:
        crits = [ability_crit(c) for c in children]
        crits = [c for c in crits if c > 0]
        if crits:
            return round(sum(crits) / len(crits), 2)

    # Flat fallback
    if isinstance(ab.get("crit_pct"), (int, float)):
        v = safe_float(ab["crit_pct"])
        return v * 100 if v <= 1 else v
    return 0.0


def _get_abilities(player: dict) -> list:
    """
    Safely extract ability list from player dict.
    In SimC JSON2 abilities live in player["stats"] as a list of dicts.
    Guard against player["stats"] being a dict (buffed_stats confusion).
    """
    raw = player.get("stats", [])
    if isinstance(raw, list):
        # Verify first element looks like an ability (has spell_name or portionaps)
        if raw and isinstance(raw[0], dict):
            if "spell_name" in raw[0] or "portionaps" in raw[0] or "children" in raw[0]:
                return raw
        elif not raw:
            return []
    if isinstance(raw, dict):
        # Some SimC versions nest abilities under a sub-key
        for key in ("stats", "abilities", "actions"):
            sub = raw.get(key, [])
            if isinstance(sub, list) and sub:
                return sub
    # Fallback: try collected_data action_sequence (no DPS info, just counts)
    return []


def parse_results(json_path: str):
    try:
        with open(json_path) as f:
            raw = json.load(f)

        sim = raw.get("sim", {})
        players = sim.get("players", [])

        if not players:
            return {"error": "No player data"}

        player = players[0]
        cd = player.get("collected_data", {})

        # -------------------------
        # DPS
        # -------------------------
        dps_data = cd.get("dps", {})
        dps_mean = safe_float(dps_data.get("mean"))
        dps_std = safe_float(dps_data.get("mean_std_dev"))

        # -------------------------
        # STATS
        # SimC JSON2: buffed_stats.attribute = primary stats
        #             buffed_stats.stats = secondary stats
        # Fallback: try reading secondaries directly from buffed_stats root.
        # -------------------------
        bs = cd.get("buffed_stats", {})
        attr = bs.get("attribute", {})
        stats_data = bs.get("stats", {})

        if not stats_data:
            stats_data = bs

        stats = {
            "strength":        safe_float(attr.get("strength")),
            "agility":         safe_float(attr.get("agility")),
            "stamina":         safe_float(attr.get("stamina")),
            "intellect":       safe_float(attr.get("intellect")),
            "crit_pct":        pct(stats_data.get("spell_crit",
                                   stats_data.get("crit_pct",
                                   stats_data.get("attack_crit", 0)))),
            "haste_pct":       pct(stats_data.get("spell_haste",
                                   stats_data.get("haste_pct",
                                   stats_data.get("attack_haste", 0)))),
            "mastery_pct":     pct(stats_data.get("mastery_value",
                                   stats_data.get("mastery_pct", 0))),
            "versatility_pct": pct(stats_data.get("damage_versatility",
                                   stats_data.get("versatility_pct", 0))),
        }

        # -------------------------
        # SPELLS / ABILITIES
        # -------------------------
        abilities = _get_abilities(player)

        spells = []
        total_spell_dps = 0.0

        for ab in abilities:
            if not isinstance(ab, dict):
                continue

            dps = ability_dps(ab)
            if dps <= 0:
                continue

            name = ab.get("spell_name") or ab.get("name", "?")
            crit = ability_crit(ab)

            executes = 0
            ne = ab.get("num_executes")
            if isinstance(ne, dict):
                executes = int(safe_float(ne.get("mean", ne.get("sum", 0))))
            elif isinstance(ne, (int, float)):
                executes = int(ne)

            spells.append({
                "name": name,
                "dps": round(dps, 2),
                "crit_pct": round(crit, 2),
                "executes": executes,
            })
            total_spell_dps += dps

        # Fallback: no abilities with DPS found — use action_sequence for counts only
        if not spells:
            action_seq = cd.get("action_sequence", [])
            spell_counts: dict = {}
            for action in action_seq:
                spell_name = action.get("spell_name") or action.get("name", "?")
                spell_counts[spell_name] = spell_counts.get(spell_name, 0) + 1
            for spell_name, count in spell_counts.items():
                spells.append({
                    "name": spell_name,
                    "dps": 0.0,
                    "crit_pct": 0.0,
                    "executes": count,
                    "percent": 0.0,
                })

        spells = sorted(spells, key=lambda x: x["dps"], reverse=True)

        if total_spell_dps > 0:
            for s in spells:
                s["percent"] = round((s["dps"] / total_spell_dps) * 100, 2)

            top_spells = spells[:25]
            other_dps = sum(s["dps"] for s in spells[25:])
            if other_dps > 0:
                top_spells.append({
                    "name": "Other",
                    "dps": round(other_dps, 2),
                    "crit_pct": 0,
                    "executes": 0,
                    "percent": round((other_dps / total_spell_dps) * 100, 2),
                })
        else:
            top_spells = spells

        return {
            "name": player.get("name", "?"),
            "dps": round(dps_mean, 1),
            "dps_std": round(dps_std, 1),
            "stats": stats,
            "spells": top_spells,
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


@router.get("/api/result/{job_id}/json")
async def get_result_json(job_id: str):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")
    return parse_results(job["json_path"])
