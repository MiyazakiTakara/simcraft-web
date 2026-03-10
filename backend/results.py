import json
from fastapi import APIRouter, HTTPException
from simulation import jobs

router = APIRouter()


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def ability_dps(ab: dict) -> float:
    """Extract DPS from SimulationCraft ability"""
    ca = ab.get("compound_amount")
    if isinstance(ca, dict):
        return safe_float(ca.get("mean"))
    if isinstance(ca, (int, float)):
        return safe_float(ca)
    if isinstance(ab.get("dps"), (int, float)):
        return safe_float(ab["dps"])
    dmg = ab.get("dmg")
    if isinstance(dmg, dict):
        return safe_float(dmg.get("mean"))
    cdmg = ab.get("compound_dmg")
    if isinstance(cdmg, dict):
        return safe_float(cdmg.get("mean"))
    return 0.0


def ability_crit(ab: dict) -> float:
    """Extract crit % from ability"""
    if isinstance(ab.get("crit_pct"), (int, float)):
        return safe_float(ab["crit_pct"]) * 100 if ab["crit_pct"] <= 1 else safe_float(ab["crit_pct"])
    stats = ab.get("stats")
    if isinstance(stats, dict):
        crit = stats.get("crit_pct")
        if isinstance(crit, dict):
            return safe_float(crit.get("mean")) * 100 if safe_float(crit.get("mean")) <= 1 else safe_float(crit.get("mean"))
        if isinstance(crit, (int, float)):
            return crit * 100 if crit <= 1 else crit
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
        dps_std = safe_float(dps_data.get("mean_std_dev"))

        # -------------------------
        # STATS (nowy format SimC)
        # -------------------------
        bs = cd.get("buffed_stats", {})
        attr = bs.get("attribute", {})

        stats = {
            "strength": safe_float(attr.get("strength")),
            "agility": safe_float(attr.get("agility")),
            "stamina": safe_float(attr.get("stamina")),
            "intellect": safe_float(attr.get("intellect")),

            # kryty / haste / mastery / versatility
            "crit_pct": round(
                safe_float(attr.get("crit_pct", bs.get("crit_pct", 0))) * 100
                if safe_float(attr.get("crit_pct", bs.get("crit_pct", 0))) <= 1
                else safe_float(attr.get("crit_pct", bs.get("crit_pct", 0))),
                2
            ),
            "haste_pct": round(
                safe_float(attr.get("haste_pct", bs.get("haste_pct", 0))) * 100
                if safe_float(attr.get("haste_pct", bs.get("haste_pct", 0))) <= 1
                else safe_float(attr.get("haste_pct", bs.get("haste_pct", 0))),
                2
            ),
            "mastery_pct": round(
                safe_float(attr.get("mastery_pct", bs.get("mastery_value", 0))) * 100
                if safe_float(attr.get("mastery_pct", bs.get("mastery_value", 0))) <= 1
                else safe_float(attr.get("mastery_pct", bs.get("mastery_value", 0))),
                2
            ),
            "versatility_pct": round(
                safe_float(
                    attr.get("versatility_pct", 0)
                    + bs.get("damage_versatility", 0)
                    + bs.get("heal_versatility", 0)
                    + bs.get("mitigation_versatility", 0)
                ) * 100
                if safe_float(
                    attr.get("versatility_pct", 0)
                    + bs.get("damage_versatility", 0)
                    + bs.get("heal_versatility", 0)
                    + bs.get("mitigation_versatility", 0)
                ) <= 1
                else safe_float(
                    attr.get("versatility_pct", 0)
                    + bs.get("damage_versatility", 0)
                    + bs.get("heal_versatility", 0)
                    + bs.get("mitigation_versatility", 0)
                ),
                2
            ),
        }

        # -------------------------
        # SPELLS
        # -------------------------
        abilities = player.get("stats", [])

        spells = []
        total_spell_dps = 0.0

        for ab in abilities:
            name = ab.get("name", "?")
            dps = ability_dps(ab)
            if dps <= 0:
                continue
            crit = ability_crit(ab)
            executes = 0
            ne = ab.get("num_executes")
            if isinstance(ne, dict):
                executes = safe_float(ne.get("sum"))

            spells.append({
                "name": name,
                "dps": round(dps, 2),
                "crit_pct": round(crit, 2),
                "executes": int(executes)
            })

            total_spell_dps += dps

        # sort spells by DPS
        spells = sorted(spells, key=lambda x: x["dps"], reverse=True)

        # add percent DPS
        for s in spells:
            s["percent"] = round((s["dps"] / total_spell_dps) * 100, 2) if total_spell_dps > 0 else 0

        # top 25
        top_spells = spells[:25]

        # OTHER bucket
        other_dps = sum(s["dps"] for s in spells[25:])
        if other_dps > 0:
            top_spells.append({
                "name": "Other",
                "dps": round(other_dps, 2),
                "crit_pct": 0,
                "executes": 0,
                "percent": round((other_dps / total_spell_dps) * 100, 2)
            })

        return {
            "name": player.get("name", "?"),
            "dps": round(dps_mean, 1),
            "dps_std": round(dps_std, 1),
            "stats": stats,
            "spells": top_spells
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
