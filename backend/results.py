import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from simulation import jobs

router = APIRouter()


def _get_job(job_id: str):
    from database import get_job
    db_job = get_job(job_id)
    if db_job:
        # get_job() zwraca dict od czasu poprawki DetachedInstanceError
        return {"status": db_job["status"], "json_path": db_job["json_path"], "error": db_job["error"]}
    return jobs.get(job_id)


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _get_count(block: dict) -> float:
    c = block.get("count", 0)
    if isinstance(c, dict):
        return safe_float(c.get("sum", c.get("mean", 0)))
    return safe_float(c)


def ability_dps(ab: dict) -> float:
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


def ability_total_dmg(ab: dict) -> float:
    v = safe_float(ab.get("compound_amount", 0))
    if v > 0:
        return v
    children = ab.get("children", [])
    if isinstance(children, list) and children:
        total = sum(ability_total_dmg(c) for c in children if isinstance(c, dict))
        if total > 0:
            return total
    return 0.0


def ability_hps(ab: dict) -> float:
    """Heal per second z portion_aps (heal spelle) lub children."""
    pa = ab.get("portion_aps")
    if isinstance(pa, dict):
        v = safe_float(pa.get("mean"))
        if v > 0:
            return v
    children = ab.get("children", [])
    if isinstance(children, list) and children:
        total = sum(ability_hps(c) for c in children if isinstance(c, dict))
        if total > 0:
            return total
    return 0.0


def ability_total_heal(ab: dict) -> float:
    """Total healing z compound_amount lub heal_results."""
    v = safe_float(ab.get("compound_amount", 0))
    if v > 0:
        return v
    hr = ab.get("heal_results") or ab.get("direct_results", {})
    if isinstance(hr, dict):
        for key, block in hr.items():
            if isinstance(block, dict):
                aa = block.get("actual_amount", {})
                cnt = _get_count(block)
                mean = safe_float(aa.get("mean", 0)) if isinstance(aa, dict) else 0.0
                if mean > 0 and cnt > 0:
                    return mean * cnt
    children = ab.get("children", [])
    if isinstance(children, list) and children:
        total = sum(ability_total_heal(c) for c in children if isinstance(c, dict))
        if total > 0:
            return total
    return 0.0


def _stats_from_results(results: dict):
    if not isinstance(results, dict) or not results:
        return None

    crit_count = 0.0
    hit_count  = 0.0
    miss_count = 0.0
    total_val  = 0.0
    total_cnt  = 0.0
    miss_keys  = {"miss", "dodge", "parry", "glancing"}

    for key, block in results.items():
        if not isinstance(block, dict):
            continue
        cnt = _get_count(block)
        if key == "crit":
            crit_count += cnt
        if key in miss_keys:
            miss_count += cnt
        else:
            aa = block.get("actual_amount")
            if isinstance(aa, dict):
                mean = safe_float(aa.get("mean", 0))
                if mean > 0 and cnt > 0:
                    total_val += mean * cnt
                    total_cnt += cnt
            hit_count += cnt

    all_count = hit_count + miss_count
    crit_pct  = round((crit_count / hit_count * 100), 2) if hit_count > 0 else 0.0
    miss_pct  = round((miss_count / all_count * 100), 1) if all_count > 0 else 0.0
    avg_hit   = round(total_val / total_cnt) if total_cnt > 0 else 0

    return crit_pct, hit_count, miss_pct, avg_hit


def _collect_stats(ab: dict):
    results_list = []
    for key in ("direct_results", "tick_results"):
        r = ab.get(key)
        if r:
            s = _stats_from_results(r)
            if s:
                results_list.append(s)
    for child in ab.get("children", []):
        if isinstance(child, dict):
            results_list.extend(_collect_stats(child))
    return results_list


def _weighted_stats(ab: dict):
    parts = _collect_stats(ab)
    if not parts:
        return 0.0, 0.0, 0
    total_w = sum(p[1] for p in parts)
    if total_w == 0:
        return 0.0, 0.0, 0
    crit_pct = sum(p[0] * p[1] for p in parts) / total_w
    miss_pct = sum(p[2] * p[1] for p in parts) / total_w
    avg_hit  = int(sum(p[3] * p[1] for p in parts) / total_w)
    return round(crit_pct, 2), round(miss_pct, 1), avg_hit


def _hit_count_from_results(ab: dict) -> float:
    total = 0.0
    for key in ("direct_results", "tick_results"):
        r = ab.get(key)
        if not isinstance(r, dict):
            continue
        miss_keys = {"miss", "dodge", "parry", "glancing"}
        for bkey, block in r.items():
            if isinstance(block, dict) and bkey not in miss_keys:
                total += _get_count(block)
    for child in ab.get("children", []):
        if isinstance(child, dict):
            total += _hit_count_from_results(child)
    return total


def _has_only_ticks(ab: dict) -> bool:
    if ab.get("direct_results"):
        return False
    for child in ab.get("children", []):
        if isinstance(child, dict) and not _has_only_ticks(child):
            return False
    if ab.get("tick_results"):
        return True
    for child in ab.get("children", []):
        if isinstance(child, dict) and child.get("tick_results"):
            return True
    return False


def ability_count(ab: dict) -> tuple[int, bool]:
    ne = ab.get("num_executes")
    executes = 0
    if isinstance(ne, dict):
        executes = int(safe_float(ne.get("mean", 0)))
    elif isinstance(ne, (int, float)):
        executes = int(ne)

    if executes > 0:
        return executes, False

    child_counts = [
        ability_count(c) for c in ab.get("children", []) if isinstance(c, dict)
    ]
    child_sum = sum(c[0] for c in child_counts)
    if child_sum > 0:
        is_ch = all(c[1] for c in child_counts)
        return child_sum, is_ch

    hc = _hit_count_from_results(ab)
    return int(hc), True


def spell_display_name(ab: dict) -> str:
    spell_name = ab.get("spell_name", "").strip()
    if spell_name:
        return spell_name
    raw = ab.get("name", "?")
    return raw.replace("_", " ").title()


def _extract_hps_dtps(cd: dict) -> tuple[float, float, float]:
    """
    Wyciaga hps, dtps, tmi z collected_data SimC.
    """
    hps_data  = cd.get("hps") or cd.get("hpse") or {}
    dtps_data = cd.get("dtps") or {}
    tmi_data  = cd.get("tmi") or {}

    hps  = safe_float(hps_data.get("mean") if isinstance(hps_data, dict) else hps_data)
    dtps = safe_float(dtps_data.get("mean") if isinstance(dtps_data, dict) else dtps_data)
    tmi  = safe_float(tmi_data.get("mean") if isinstance(tmi_data, dict) else tmi_data)
    return round(hps, 1), round(dtps, 1), round(tmi, 1)


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
        dps_std  = safe_float(dps_data.get("mean_std_dev"))

        hps, dtps, tmi = _extract_hps_dtps(cd)

        hps_std_data = cd.get("hps") or cd.get("hpse") or {}
        hps_std = safe_float(hps_std_data.get("mean_std_dev", 0) if isinstance(hps_std_data, dict) else 0)

        dtps_std_data = cd.get("dtps") or {}
        dtps_std = safe_float(dtps_std_data.get("mean_std_dev", 0) if isinstance(dtps_std_data, dict) else 0)

        fl_data      = cd.get("fight_length", {})
        fight_length = safe_float(fl_data.get("mean", 1)) or 1.0

        bs         = cd.get("buffed_stats", {})
        attr       = bs.get("attribute", {})
        stats_data = bs.get("stats", {})

        stats = {
            "strength":    int(safe_float(attr.get("strength"))),
            "agility":     int(safe_float(attr.get("agility"))),
            "stamina":     int(safe_float(attr.get("stamina"))),
            "intellect":   int(safe_float(attr.get("intellect"))),
            "crit":        int(safe_float(stats_data.get("crit_rating", 0))),
            "haste":       int(safe_float(stats_data.get("haste_rating", 0))),
            "mastery":     int(safe_float(stats_data.get("mastery_rating", 0))),
            "versatility": int(safe_float(stats_data.get("versatility_rating", 0))),
        }

        abilities = player.get("stats", [])
        if not isinstance(abilities, list):
            abilities = []

        main_hps = hps
        if main_hps <= 0:
            for ab in abilities:
                if isinstance(ab, dict):
                    spell_hps = ability_hps(ab)
                    if spell_hps > main_hps:
                        main_hps = spell_hps

        if main_hps > 100:
            role = "healer"
        else:
            role = "dps"

        spells = []
        for ab in abilities:
            if not isinstance(ab, dict):
                continue
            dps       = ability_dps(ab)
            tot_dmg   = ability_total_dmg(ab)
            spell_hps = ability_hps(ab)
            tot_heal  = ability_total_heal(ab)
            if dps <= 0 and tot_dmg <= 0 and spell_hps <= 0 and tot_heal <= 0:
                continue

            name                        = spell_display_name(ab)
            crit_pct, miss_pct, avg_hit = _weighted_stats(ab)
            executes, is_channel        = ability_count(ab)

            if avg_hit == 0 and executes > 0 and tot_dmg > 0:
                avg_hit = round(tot_dmg / executes)

            spells.append({
                "name":       name,
                "dps":        round(dps, 2),
                "total_dmg":  round(tot_dmg),
                "hps":        round(spell_hps, 2),
                "total_heal": round(tot_heal),
                "crit_pct":   crit_pct,
                "executes":   executes,
                "count":      executes,
                "avg_hit":    avg_hit,
                "miss_pct":   miss_pct,
                "is_channel": is_channel,
            })

        if not spells:
            action_seq = cd.get("action_sequence", [])
            spell_counts: dict = {}
            for action in action_seq:
                sname = action.get("spell_name") or action.get("name", "?")
                sname = sname.replace("_", " ").title()
                spell_counts[sname] = spell_counts.get(sname, 0) + 1
            for sname, count in spell_counts.items():
                spells.append({
                    "name": sname, "dps": 0.0, "total_dmg": 0,
                    "crit_pct": 0.0, "executes": count,
                    "count": count, "avg_hit": 0, "miss_pct": 0.0,
                    "is_channel": False,
                    "dps_pct": 0.0, "dmg_pct": 0.0,
                })

        total_spell_dps  = sum(s["dps"] for s in spells)
        total_spell_dmg  = sum(s["total_dmg"] for s in spells)
        total_spell_hps  = sum(s["hps"] for s in spells)
        total_spell_heal = sum(s["total_heal"] for s in spells)

        for s in spells:
            s["dps_pct"]  = round((s["dps"] / total_spell_dps * 100), 1) if total_spell_dps > 0 else 0.0
            s["dmg_pct"]  = round((s["total_dmg"] / total_spell_dmg * 100), 1) if total_spell_dmg > 0 else 0.0
            s["hps_pct"]  = round((s["hps"] / total_spell_hps * 100), 1) if total_spell_hps > 0 else 0.0
            s["heal_pct"] = round((s["total_heal"] / total_spell_heal * 100), 1) if total_spell_heal > 0 else 0.0

        spells = sorted(spells, key=lambda x: x["total_dmg"], reverse=True)

        top_spells = spells[:25]
        other_dps  = sum(s["dps"] for s in spells[25:])
        other_dmg  = sum(s["total_dmg"] for s in spells[25:])
        other_hps  = sum(s["hps"] for s in spells[25:])
        other_heal = sum(s["total_heal"] for s in spells[25:])
        if other_dps > 0 or other_dmg > 0 or other_hps > 0 or other_heal > 0:
            top_spells.append({
                "name": "Other", "dps": round(other_dps, 2), "total_dmg": round(other_dmg),
                "hps": round(other_hps, 2), "total_heal": round(other_heal),
                "crit_pct": 0, "executes": 0, "count": 0, "avg_hit": 0, "miss_pct": 0.0,
                "is_channel": False,
                "dps_pct":  round(other_dps  / total_spell_dps  * 100, 1) if total_spell_dps  > 0 else 0.0,
                "dmg_pct":  round(other_dmg  / total_spell_dmg  * 100, 1) if total_spell_dmg  > 0 else 0.0,
                "hps_pct":  round(other_hps  / total_spell_hps  * 100, 1) if total_spell_hps  > 0 else 0.0,
                "heal_pct": round(other_heal / total_spell_heal * 100, 1) if total_spell_heal > 0 else 0.0,
            })

        return {
            "name":         player.get("name", "?"),
            "dps":          round(dps_mean, 1),
            "dps_std":      round(dps_std, 1),
            "hps":          main_hps,
            "hps_std":      round(hps_std, 1),
            "role":         role,
            "fight_length": round(fight_length, 1),
            "stats":        stats,
            "spells":       top_spells,
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


def generate_dps_chart(json_path: str, role: str = None) -> str:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        import pandas as pd

        with open(json_path) as f:
            raw = json.load(f)

        sim     = raw.get("sim", {})
        players = sim.get("players", [])
        if not players:
            return None

        player    = players[0]
        cd        = player.get("collected_data", {})
        abilities = player.get("stats", [])
        if not isinstance(abilities, list):
            return None

        if role is None:
            hps, dtps, tmi = _extract_hps_dtps(cd)
            if hps > 100:
                role = "healer"
            else:
                role = "dps"

        real_dps = safe_float(cd.get("dps",  {}).get("mean", 0))
        real_dmg = safe_float(cd.get("compound_dmg", {}).get("mean", 0))
        real_hps = safe_float((cd.get("hps") or cd.get("hpse") or {}).get("mean", 0))

        TOP_N  = 12
        COLORS = [
            "#f0027f", "#386cb0", "#fdc086", "#7fc97f", "#beaed4",
            "#bf5b17", "#999999", "#1b9e77", "#d95f02", "#7570b3",
            "#e7298a", "#66a61e", "#aaaaaa",
        ]
        HEAL_COLORS = [
            "#00cc66", "#33cc99", "#66ffcc", "#00aa44", "#88ddaa",
            "#004d22", "#00ff88", "#009933", "#66cc88", "#33ff66",
            "#00cc55", "#88ff99", "#aaaaaa",
        ]

        def build_data(key_fn):
            rows = []
            for ab in abilities:
                if not isinstance(ab, dict):
                    continue
                name = spell_display_name(ab)[:28]
                val  = key_fn(ab)
                if val > 0:
                    rows.append({"name": name, "value": val})
            if not rows:
                return [], []
            import pandas as pd
            df = pd.DataFrame(rows).sort_values("value", ascending=False).reset_index(drop=True)
            if len(df) > TOP_N:
                other = df.iloc[TOP_N:]["value"].sum()
                df = pd.concat(
                    [df.head(TOP_N), pd.DataFrame([{"name": "Other", "value": other}])],
                    ignore_index=True
                )
            return df["name"].tolist(), df["value"].tolist()

        def fmt_dmg(v):
            if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
            if v >= 1_000:     return f"{v/1_000:.0f}k"
            return str(int(v))

        def fmt_dps(v):
            if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
            if v >= 1_000:     return f"{v/1_000:.1f}k"
            return str(int(v))

        player_name = player.get("name", "?")

        if role == "healer":
            heal_names, heal_vals = build_data(ability_total_heal)
            hps_names,  hps_vals  = build_data(ability_hps)
            if not heal_vals and not hps_vals:
                role = "dps"
            else:
                left_title  = f"Total Heal  ({fmt_dmg(real_hps * safe_float(cd.get('fight_length', {}).get('mean', 1)))})" if real_hps > 0 else "Total Heal"
                right_title = f"HPS  ({fmt_dps(real_hps)})" if real_hps > 0 else "HPS"
                chart_title = f"{player_name} \u2014 Healing Breakdown"
                left_names, left_vals   = heal_names, heal_vals
                right_names, right_vals = hps_names,  hps_vals
                colors = HEAL_COLORS

        if role == "dps":
            dmg_names, dmg_vals = build_data(ability_total_dmg)
            dps_names, dps_vals = build_data(ability_dps)
            if not dmg_vals and not dps_vals:
                return None
            left_title  = f"Total DMG  ({fmt_dmg(real_dmg)})" if real_dmg > 0 else "Total DMG"
            right_title = f"DPS  ({fmt_dps(real_dps)})"       if real_dps > 0 else "DPS"
            chart_title = f"{player_name} \u2014 Damage Breakdown"
            left_names, left_vals   = dmg_names, dmg_vals
            right_names, right_vals = dps_names, dps_vals
            colors = COLORS

        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "pie"}, {"type": "pie"}]],
            subplot_titles=[left_title, right_title],
        )

        fig.add_trace(go.Pie(
            labels=left_names, values=left_vals,
            hole=0.38, textinfo="percent", textfont_size=11,
            marker=dict(colors=colors[:len(left_names)], line=dict(color="#0d0d1a", width=1.5)),
            name=left_title, showlegend=True,
        ), row=1, col=1)

        fig.add_trace(go.Pie(
            labels=right_names, values=right_vals,
            hole=0.38, textinfo="percent", textfont_size=11,
            marker=dict(colors=colors[:len(right_names)], line=dict(color="#0d0d1a", width=1.5)),
            name=right_title, showlegend=False,
        ), row=1, col=2)

        fig.update_layout(
            title=dict(text=chart_title, font=dict(size=17, color="#ffffff"), x=0.5, xanchor="center"),
            legend=dict(
                orientation="v", yanchor="middle", y=0.5,
                xanchor="left", x=1.01,
                font=dict(size=11, color="#cccccc"),
                bgcolor="rgba(0,0,0,0)",
            ),
            paper_bgcolor="#12121f", plot_bgcolor="#12121f",
            font=dict(color="#cccccc", size=12),
            width=1100, height=520,
            margin=dict(t=70, b=30, l=20, r=200),
        )
        fig.update_annotations(font=dict(size=13, color="#aaaaaa"))

        png_path = f"/tmp/dps-chart-{os.path.basename(json_path)}.png"
        fig.write_image(png_path, engine="kaleido", scale=2)
        return png_path

    except Exception as e:
        import traceback
        print(f"[chart error] {e}\n{traceback.format_exc()}")
        return None


@router.get("/api/result/{job_id}/json")
async def get_result_json(job_id: str):
    job = _get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")
    return parse_results(job["json_path"])


@router.get("/api/result/{job_id}/dps-chart.png")
async def get_dps_chart(job_id: str):
    job = _get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")
    png = generate_dps_chart(job["json_path"], role='dps')
    if not png or not os.path.exists(png):
        raise HTTPException(500, "Chart generation failed")
    return FileResponse(png, media_type="image/png")


@router.get("/api/result/{job_id}/debug-spell")
async def get_debug_spell(job_id: str):
    job = _get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")
    try:
        with open(job["json_path"]) as f:
            raw = json.load(f)
        player = raw.get("sim", {}).get("players", [{}])[0]
        abilities = player.get("stats", [])
        if not isinstance(abilities, list):
            return {"error": "no abilities list"}
        out = []
        for ab in abilities[:5]:
            if not isinstance(ab, dict):
                continue
            if ability_total_dmg(ab) <= 0 and ability_dps(ab) <= 0:
                continue
            crit_pct, miss_pct, avg_hit = _weighted_stats(ab)
            cnt, is_ch = ability_count(ab)
            out.append({
                "name":       spell_display_name(ab),
                "count":      cnt,
                "is_channel": is_ch,
                "crit_pct":   crit_pct,
                "miss_pct":   miss_pct,
                "avg_hit":    avg_hit,
            })
            if len(out) >= 3:
                break
        return {"spells": out}
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


@router.get("/api/result/{job_id}/debug")
async def get_result_debug(job_id: str):
    job = _get_job(job_id)
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
                return {k: strip_timeseries(v, depth + 1) for k, v in obj.items() if k not in ("data", "timeline", "distribution")}
            if isinstance(obj, list):
                if len(obj) > 3:
                    return [strip_timeseries(i, depth + 1) for i in obj[:3]] + [f"...+{len(obj)-3} more"]
                return [strip_timeseries(i, depth + 1) for i in obj]
            return obj

        cd = player.get("collected_data", {})
        hps, dtps, tmi = _extract_hps_dtps(cd)

        return {
            "player_name": player.get("name"),
            "player_keys": list(player.keys()),
            "stats_type": type(stats_raw).__name__,
            "stats_len": len(stats_raw) if isinstance(stats_raw, (list, dict)) else None,
            "first_3_abilities": strip_timeseries(stats_raw[:3] if isinstance(stats_raw, list) else stats_raw),
            "collected_data_keys": list(cd.keys()),
            "hps": hps, "dtps": dtps, "tmi": tmi,
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}
