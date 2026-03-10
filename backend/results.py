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
        # STATS (SimC JSON format)
        # crit/haste/mastery/vers are under buffed_stats.stats, NOT buffed_stats.attribute
        # -------------------------
        bs = cd.get("buffed_stats", {})
        attr = bs.get("attribute", {})
        stats_data = bs.get("stats", {})

        def pct(val):
            v = safe_float(val)
            return round(v * 100 if v <= 1 else v, 2)

        stats = {
            "strength": safe_float(attr.get("strength")),
            "agility": safe_float(attr.get("agility")),
            "stamina": safe_float(attr.get("stamina")),
            "intellect": safe_float(attr.get("intellect")),
            "crit_pct": pct(stats_data.get("spell_crit", stats_data.get("attack_crit", 0))),
            "haste_pct": pct(stats_data.get("spell_haste", stats_data.get("attack_haste", 0))),
            "mastery_pct": pct(stats_data.get("mastery_value", 0)),
            # damage_versatility only (not the sum of dmg+heal+mitigation)
            "versatility_pct": pct(stats_data.get("damage_versatility", 0)),
        }

        # -------------------------
        # SPELLS
        # player.stats may not exist in newer SimC JSON output.
        # Fall back to aggregating unique spells from action_sequence.
        # -------------------------
        abilities = player.get("stats", [])

        spells = []
        total_spell_dps = 0.0

        if abilities:
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
        else:
            # Fallback: count executes per spell from action_sequence
            action_seq = cd.get("action_sequence", [])
            spell_counts: dict[str, dict] = {}
            for action in action_seq:
                spell_name = action.get("spell_name") or action.get("name", "?")
                if spell_name not in spell_counts:
                    spell_counts[spell_name] = {"executes": 0}
                spell_counts[spell_name]["executes"] += 1

            for spell_name, data in spell_counts.items():
                spells.append({
                    "name": spell_name,
                    "dps": 0.0,
                    "crit_pct": 0.0,
                    "executes": data["executes"],
                    "percent": 0.0,
                })

        # sort spells by DPS (or executes if no DPS data)
        if total_spell_dps > 0:
            spells = sorted(spells, key=lambda x: x["dps"], reverse=True)

            # add percent DPS
            for s in spells:
                s["percent"] = round((s["dps"] / total_spell_dps) * 100, 2)

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
        else:
            # no DPS breakdown available — sort by executes, no top-25 cap
            top_spells = sorted(spells, key=lambda x: x["executes"], reverse=True)

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
