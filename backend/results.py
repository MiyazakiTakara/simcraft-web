import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from simulation import jobs

router = APIRouter()


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


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


def ability_crit(ab: dict) -> float:
    def _crit_from_results(results: dict):
        if not isinstance(results, dict):
            return None
        crit_block = results.get("crit", {})
        hit_block  = results.get("hit", {})
        crit_count = safe_float(crit_block.get("count") if isinstance(crit_block, dict) else 0)
        hit_count  = safe_float(hit_block.get("count") if isinstance(hit_block, dict) else 0)
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

    children = ab.get("children", [])
    if isinstance(children, list) and children:
        crits = [ability_crit(c) for c in children if isinstance(c, dict)]
        crits = [c for c in crits if c and c > 0]
        if crits:
            return round(sum(crits) / len(crits), 2)
    return 0.0


def ability_miss_pct(ab: dict) -> float:
    """Procent miss+dodge+parry+glance ze wszystkich prób."""
    def _from_results(results: dict):
        if not isinstance(results, dict):
            return 0.0, 0.0
        miss_keys = ("miss", "dodge", "parry", "glancing")
        total_hits = 0.0
        total_miss = 0.0
        for key, block in results.items():
            if not isinstance(block, dict):
                continue
            cnt = safe_float(block.get("count") or block.get("count_sum", 0))
            if key in miss_keys:
                total_miss += cnt
            total_hits += cnt
        return total_miss, total_hits

    miss_total, hit_total = 0.0, 0.0
    for key in ("direct_results", "tick_results"):
        m, h = _from_results(ab.get(key, {}))
        miss_total += m
        hit_total  += h

    children = ab.get("children", [])
    if isinstance(children, list):
        for c in children:
            if isinstance(c, dict):
                for key in ("direct_results", "tick_results"):
                    m, h = _from_results(c.get(key, {}))
                    miss_total += m
                    hit_total  += h

    if hit_total > 0:
        return round((miss_total / hit_total) * 100, 1)
    return 0.0


def ability_avg_hit(ab: dict, total_dmg: float, count: int) -> float:
    """Średni hit = total_dmg / count (hits that landed)."""
    # Spróbuj wziąć avg bezpośrednio z hit/crit block
    def _avg_from_results(results: dict):
        if not isinstance(results, dict):
            return None
        total_val = 0.0
        total_cnt = 0.0
        for key, block in results.items():
            if key in ("miss", "dodge", "parry", "glancing"):
                continue
            if not isinstance(block, dict):
                continue
            mean = safe_float(block.get("actual_amount", {}).get("mean", 0) if isinstance(block.get("actual_amount"), dict) else 0)
            cnt  = safe_float(block.get("count") or block.get("count_sum", 0))
            if mean > 0 and cnt > 0:
                total_val += mean * cnt
                total_cnt += cnt
        if total_cnt > 0:
            return round(total_val / total_cnt)
        return None

    for key in ("direct_results", "tick_results"):
        v = _avg_from_results(ab.get(key, {}))
        if v is not None:
            return v

    # Fallback: total_dmg / count
    if count and count > 0 and total_dmg > 0:
        return round(total_dmg / count)
    return 0


def spell_display_name(ab: dict) -> str:
    spell_name = ab.get("spell_name", "").strip()
    if spell_name:
        return spell_name
    raw = ab.get("name", "?")
    return raw.replace("_", " ").title()


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

        spells = []
        for ab in abilities:
            if not isinstance(ab, dict):
                continue
            dps     = ability_dps(ab)
            tot_dmg = ability_total_dmg(ab)
            if dps <= 0 and tot_dmg <= 0:
                continue

            name     = spell_display_name(ab)
            crit     = ability_crit(ab)
            miss_pct = ability_miss_pct(ab)

            executes = 0
            ne = ab.get("num_executes")
            if isinstance(ne, dict):
                executes = int(safe_float(ne.get("mean", ne.get("sum", 0))))
            elif isinstance(ne, (int, float)):
                executes = int(ne)

            avg_hit = ability_avg_hit(ab, tot_dmg, executes)

            spells.append({
                "name":      name,
                "dps":       round(dps, 2),
                "total_dmg": round(tot_dmg),
                "crit_pct":  round(crit, 2),
                "executes":  executes,
                "count":     executes,
                "avg_hit":   avg_hit,
                "miss_pct":  miss_pct,
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
                    "dps_pct": 0.0, "dmg_pct": 0.0,
                })

        total_spell_dps = sum(s["dps"] for s in spells)
        total_spell_dmg = sum(s["total_dmg"] for s in spells)

        for s in spells:
            s["dps_pct"] = round((s["dps"] / total_spell_dps * 100), 1) if total_spell_dps > 0 else 0.0
            s["dmg_pct"] = round((s["total_dmg"] / total_spell_dmg * 100), 1) if total_spell_dmg > 0 else 0.0

        spells = sorted(spells, key=lambda x: x["total_dmg"], reverse=True)

        top_spells = spells[:25]
        other_dps  = sum(s["dps"] for s in spells[25:])
        other_dmg  = sum(s["total_dmg"] for s in spells[25:])
        if other_dps > 0 or other_dmg > 0:
            top_spells.append({
                "name": "Other", "dps": round(other_dps, 2), "total_dmg": round(other_dmg),
                "crit_pct": 0, "executes": 0, "count": 0, "avg_hit": 0, "miss_pct": 0.0,
                "dps_pct": round(other_dps / total_spell_dps * 100, 1) if total_spell_dps > 0 else 0.0,
                "dmg_pct": round(other_dmg / total_spell_dmg * 100, 1) if total_spell_dmg > 0 else 0.0,
            })

        return {
            "name":         player.get("name", "?"),
            "dps":          round(dps_mean, 1),
            "dps_std":      round(dps_std, 1),
            "fight_length": round(fight_length, 1),
            "stats":        stats,
            "spells":       top_spells,
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


def generate_dps_chart(json_path: str) -> str:
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

        real_dps = safe_float(cd.get("dps", {}).get("mean", 0))
        real_dmg = safe_float(cd.get("compound_dmg", {}).get("mean", 0))

        TOP_N  = 12
        COLORS = [
            "#f0027f", "#386cb0", "#fdc086", "#7fc97f", "#beaed4",
            "#bf5b17", "#999999", "#1b9e77", "#d95f02", "#7570b3",
            "#e7298a", "#66a61e", "#aaaaaa",
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
            df = pd.DataFrame(rows).sort_values("value", ascending=False).reset_index(drop=True)
            if len(df) > TOP_N:
                other = df.iloc[TOP_N:]["value"].sum()
                df = pd.concat(
                    [df.head(TOP_N), pd.DataFrame([{"name": "Other", "value": other}])],
                    ignore_index=True
                )
            return df["name"].tolist(), df["value"].tolist()

        dmg_names, dmg_vals = build_data(ability_total_dmg)
        dps_names, dps_vals = build_data(ability_dps)

        if not dmg_vals and not dps_vals:
            return None

        player_name = player.get("name", "?")

        def fmt_dmg(v):
            if v >= 1_000_000:
                return f"{v / 1_000_000:.1f}M"
            if v >= 1_000:
                return f"{v / 1_000:.0f}k"
            return str(int(v))

        def fmt_dps(v):
            if v >= 1_000_000:
                return f"{v / 1_000_000:.2f}M"
            if v >= 1_000:
                return f"{v / 1_000:.1f}k"
            return str(int(v))

        dmg_title = f"Total DMG  ({fmt_dmg(real_dmg)})" if real_dmg > 0 else "Total DMG"
        dps_title = f"DPS  ({fmt_dps(real_dps)})"       if real_dps > 0 else "DPS"

        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "pie"}, {"type": "pie"}]],
            subplot_titles=[dmg_title, dps_title],
        )

        fig.add_trace(go.Pie(
            labels=dmg_names,
            values=dmg_vals,
            hole=0.38,
            textinfo="percent",
            textfont_size=11,
            marker=dict(colors=COLORS[:len(dmg_names)], line=dict(color="#0d0d1a", width=1.5)),
            name="Total DMG",
            showlegend=True,
        ), row=1, col=1)

        fig.add_trace(go.Pie(
            labels=dps_names,
            values=dps_vals,
            hole=0.38,
            textinfo="percent",
            textfont_size=11,
            marker=dict(colors=COLORS[:len(dps_names)], line=dict(color="#0d0d1a", width=1.5)),
            name="DPS",
            showlegend=False,
        ), row=1, col=2)

        fig.update_layout(
            title=dict(
                text=f"{player_name} \u2014 Damage Breakdown",
                font=dict(size=17, color="#ffffff"),
                x=0.5, xanchor="center",
            ),
            legend=dict(
                orientation="v",
                yanchor="middle", y=0.5,
                xanchor="left",   x=1.01,
                font=dict(size=11, color="#cccccc"),
                bgcolor="rgba(0,0,0,0)",
            ),
            paper_bgcolor="#12121f",
            plot_bgcolor="#12121f",
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
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")
    return parse_results(job["json_path"])


@router.get("/api/result/{job_id}/dps-chart.png")
async def get_dps_chart(job_id: str):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")
    png = generate_dps_chart(job["json_path"])
    if not png or not os.path.exists(png):
        raise HTTPException(500, "Chart generation failed")
    return FileResponse(png, media_type="image/png")


@router.get("/api/result/{job_id}/debug")
async def get_result_debug(job_id: str):
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
                return {k: strip_timeseries(v, depth + 1) for k, v in obj.items() if k not in ("data", "timeline", "distribution")}
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
