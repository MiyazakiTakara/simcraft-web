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
    SimC JSON2 uzywa snake_case: portion_aps.mean
    Jesli brak na rodzicu, sumuj z children rekurencyjnie.
    """
    pa = ab.get("portion_aps")
    if isinstance(pa, dict):
        v = safe_float(pa.get("mean"))
        if v > 0:
            return v

    children = ab.get("children", [])
    if isinstance(children, list) and children:
        total = sum(ability_dps(c) for c in children if isinstance(c, dict))
        if total > 0:
            return total

    return 0.0


def ability_crit(ab: dict) -> float:
    """
    SimC JSON2 snake_case: direct_results.crit / direct_results.hit
    """
    def _crit_from_results(results: dict):
        if not isinstance(results, dict):
            return None
        crit_block = results.get("crit", {})
        hit_block  = results.get("hit", {})
        crit_count = safe_float(crit_block.get("count") if isinstance(crit_block, dict) else 0)
        hit_count  = safe_float(hit_block.get("count") if isinstance(hit_block, dict) else 0)
        # countsum lub count
        if crit_count == 0:
            crit_count = safe_float(crit_block.get("count_sum", 0) if isinstance(crit_block, dict) else 0)
        if hit_count == 0:
            hit_count = safe_float(hit_block.get("count_sum", 0) if isinstance(hit_block, dict) else 0)
        total = crit_count + hit_count
        if total > 0:
            return round((crit_count / total) * 100, 2)
        return None

    for key in ("direct_results", "tick_results"):
        result = _crit_from_results(ab.get(key, {}))
        if result is not None:
            return result

    # Agreguj z children
    children = ab.get("children", [])
    if isinstance(children, list) and children:
        crits = [ability_crit(c) for c in children if isinstance(c, dict)]
        crits = [c for c in crits if c and c > 0]
        if crits:
            return round(sum(crits) / len(crits), 2)

    return 0.0


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
        dps_std  = safe_float(dps_data.get("mean_std_dev"))

        # -------------------------
        # STATS
        # -------------------------
        bs        = cd.get("buffed_stats", {})
        attr      = bs.get("attribute", {})
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
        # ABILITIES — player["stats"] to lista ability w JSON2
        # -------------------------
        abilities = player.get("stats", [])
        if not isinstance(abilities, list):
            abilities = []

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
                "name":     name,
                "dps":      round(dps, 2),
                "crit_pct": round(crit, 2),
                "executes": executes,
            })
            total_spell_dps += dps

        # Fallback: brak abilities z DPS
        if not spells:
            action_seq = cd.get("action_sequence", [])
            spell_counts: dict = {}
            for action in action_seq:
                sname = action.get("spell_name") or action.get("name", "?")
                spell_counts[sname] = spell_counts.get(sname, 0) + 1
            for sname, count in spell_counts.items():
                spells.append({
                    "name": sname, "dps": 0.0,
                    "crit_pct": 0.0, "executes": count, "percent": 0.0,
                })

        spells = sorted(spells, key=lambda x: x["dps"], reverse=True)

        if total_spell_dps > 0:
            for s in spells:
                s["percent"] = round((s["dps"] / total_spell_dps) * 100, 2)
            top_spells = spells[:25]
            other_dps = sum(s["dps"] for s in spells[25:])
            if other_dps > 0:
                top_spells.append({
                    "name": "Other", "dps": round(other_dps, 2),
                    "crit_pct": 0, "executes": 0,
                    "percent": round((other_dps / total_spell_dps) * 100, 2),
                })
        else:
            top_spells = spells

        return {
            "name":    player.get("name", "?"),
            "dps":     round(dps_mean, 1),
            "dps_std": round(dps_std, 1),
            "stats":   stats,
            "spells":  top_spells,
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
    """Debug endpoint - surowa struktura JSON2."""
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
