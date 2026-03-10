import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
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
    pa = ab.get("portionaps")
    if isinstance(pa, dict):
        v = safe_float(pa.get("mean"))
        if v > 0:
            return v

    children = ab.get("children", [])
    if children:
        total = sum(ability_dps(c) for c in children)
        if total > 0:
            return total

    if isinstance(ab.get("dps"), (int, float)):
        return safe_float(ab["dps"])
    return 0.0


def ability_crit(ab: dict) -> float:
    def _crit_from_results(results: dict):
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

    for key in ("directresults", "tickresults"):
        result = _crit_from_results(ab.get(key, {}))
        if result is not None:
            return result

    children = ab.get("children", [])
    if children:
        crits = [ability_crit(c) for c in children]
        crits = [c for c in crits if c > 0]
        if crits:
            return round(sum(crits) / len(crits), 2)

    if isinstance(ab.get("crit_pct"), (int, float)):
        v = safe_float(ab["crit_pct"])
        return v * 100 if v <= 1 else v
    return 0.0


def _get_abilities(player: dict) -> list:
    raw = player.get("stats", [])
    if isinstance(raw, list):
        if raw and isinstance(raw[0], dict):
            if "spell_name" in raw[0] or "portionaps" in raw[0] or "children" in raw[0]:
                return raw
        elif not raw:
            return []
    if isinstance(raw, dict):
        for key in ("stats", "abilities", "actions"):
            sub = raw.get(key, [])
            if isinstance(sub, list) and sub:
                return sub
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

        dps_data = cd.get("dps", {})
        dps_mean = safe_float(dps_data.get("mean"))
        dps_std = safe_float(dps_data.get("mean_std_dev"))

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


@router.get("/api/result/{job_id}/debug")
async def get_result_debug(job_id: str):
    """
    Debug endpoint - zwraca surowa strukture JSON2 z kluczowymi polami.
    Uzyj do diagnostyki gdy spelle pokazuja 0 DPS.
    """
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")

    try:
        with open(job["json_path"]) as f:
            raw = json.load(f)

        sim = raw.get("sim", {})
        players = sim.get("players", [])
        if not players:
            return {"error": "no players"}

        player = players[0]
        stats_raw = player.get("stats", [])

        # Pierwsze 3 ability z pelna struktura (bez danych timeseries)
        def strip_timeseries(obj, depth=0):
            if depth > 4:
                return "..."
            if isinstance(obj, dict):
                return {
                    k: strip_timeseries(v, depth + 1)
                    for k, v in obj.items()
                    if k not in ("data", "timeline", "distribution")
                }
            if isinstance(obj, list):
                if len(obj) > 3:
                    return [strip_timeseries(i, depth + 1) for i in obj[:3]] + [f"...+{len(obj)-3} more"]
                return [strip_timeseries(i, depth + 1) for i in obj]
            return obj

        return {
            "player_name": player.get("name"),
            "player_keys": list(player.keys()),
            "stats_type": type(stats_raw).__name__,
            "stats_len": len(stats_raw) if isinstance(stats_raw, (list, dict)) else None,
            "first_3_abilities": strip_timeseries(stats_raw[:3] if isinstance(stats_raw, list) else stats_raw),
            "collected_data_keys": list(player.get("collected_data", {}).keys()),
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}
