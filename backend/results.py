import csv
import io
import json
import os
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from simulation import jobs, RESULTS_DIR

router = APIRouter()


def _get_job(job_id: str):
    from database import get_job
    db_job = get_job(job_id)
    if db_job:
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
    total     = 0.0
    miss_keys = {"miss", "dodge", "parry", "glancing"}
    for key in ("direct_results", "tick_results"):
        r = ab.get(key)
        if not isinstance(r, dict):
            continue
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
    ne       = ab.get("num_executes")
    executes = 0
    if isinstance(ne, dict):
        executes = int(safe_float(ne.get("mean", 0)))
    elif isinstance(ne, (int, float)):
        executes = int(ne)

    if executes > 0:
        return executes, False

    child_counts = [ability_count(c) for c in ab.get("children", []) if isinstance(c, dict)]
    child_sum    = sum(c[0] for c in child_counts)
    if child_sum > 0:
        return child_sum, all(c[1] for c in child_counts)

    hc = _hit_count_from_results(ab)
    return int(hc), True


def spell_display_name(ab: dict) -> str:
    spell_name = ab.get("spell_name", "").strip()
    if spell_name:
        return spell_name
    return ab.get("name", "?").replace("_", " ").title()


def spell_icon_slug(ab: dict) -> str:
    icon = ab.get("spell_icon", "") or ab.get("icon", "")
    if icon:
        return icon.lower().replace(" ", "_")
    raw = ab.get("name", "") or ab.get("spell_name", "")
    slug = re.sub(r"[^a-z0-9_]", "_", raw.lower()).strip("_")
    return slug or "inv_misc_questionmark"


def _buff_spell_id(b: dict) -> int:
    return int(b.get("spell") or b.get("id") or 0)


def _buff_entry(b: dict, kind: str, uptime_override: float | None = None) -> dict | None:
    if not isinstance(b, dict):
        return None
    name = b.get("spell_name") or b.get("name", "?")
    name = name.replace("_", " ").title()
    icon = (b.get("spell_icon") or b.get("icon") or "").lower().replace(" ", "_")
    if not icon:
        icon = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_") or "inv_misc_questionmark"
    spell_id = _buff_spell_id(b)
    if uptime_override is not None:
        uptime = uptime_override
    else:
        raw = safe_float(b.get("uptime", b.get("start_count", -1)))
        if raw <= 0.0 or raw >= 1.0:
            return None
        uptime = round(raw * 100, 1)
    return {"name": name, "uptime": uptime, "icon": icon, "kind": kind, "spell_id": spell_id}


def _parse_buffs(cd: dict) -> list:
    out = []
    for section, kind in (("buffs", "buff"), ("debuffs", "debuff")):
        for b in cd.get(section, []):
            entry = _buff_entry(b, kind)
            if entry:
                out.append(entry)
    out.sort(key=lambda x: x["uptime"], reverse=True)
    return out[:30]


def _parse_buffs_constant(player: dict) -> list:
    out = []
    for b in player.get("buffs_constant", []):
        entry = _buff_entry(b, "constant", uptime_override=100.0)
        if entry:
            out.append(entry)
    return out


def _parse_buffs_from_timeline(action_sequence: list, fight_length: float) -> list:
    if not action_sequence or fight_length <= 0:
        return []

    buff_ids: dict[int, dict] = {}
    for ev in action_sequence:
        for b in (ev.get("buffs") or []):
            if not isinstance(b, dict):
                continue
            bid = int(b.get("id", 0))
            if bid and bid not in buff_ids:
                raw_name = b.get("spell_name") or b.get("name", "?")
                name = raw_name.replace("_", " ").title()
                icon = (b.get("spell_icon") or b.get("icon") or "").lower().replace(" ", "_")
                if not icon:
                    icon = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_") or "inv_misc_questionmark"
                buff_ids[bid] = {"name": name, "icon": icon, "spell_id": bid}

    if not buff_ids:
        return []

    active_time: dict[int, float] = {bid: 0.0 for bid in buff_ids}

    events = [(safe_float(ev.get("time", 0)), set(
        int(b["id"]) for b in (ev.get("buffs") or []) if isinstance(b, dict) and b.get("id")
    )) for ev in action_sequence if isinstance(ev, dict)]

    for i in range(len(events) - 1):
        t_start, active_set = events[i]
        t_end = events[i + 1][0]
        window = t_end - t_start
        if window <= 0:
            continue
        for bid in active_set:
            if bid in active_time:
                active_time[bid] += window

    if events:
        t_last, active_set = events[-1]
        window = fight_length - t_last
        if window > 0:
            for bid in active_set:
                if bid in active_time:
                    active_time[bid] += window

    out = []
    for bid, info in buff_ids.items():
        uptime_pct = round(active_time[bid] / fight_length * 100, 1)
        if uptime_pct <= 0.0:
            continue
        out.append({
            "name":     info["name"],
            "uptime":   uptime_pct,
            "icon":     info["icon"],
            "kind":     "buff",
            "spell_id": info["spell_id"],
        })

    out.sort(key=lambda x: x["uptime"], reverse=True)
    return out[:30]


def _parse_timeline(cd: dict, fight_length: float) -> list:
    seq = cd.get("action_sequence", [])
    if not isinstance(seq, list) or not seq:
        return []
    out = []
    for ev in seq[:200]:
        if not isinstance(ev, dict):
            continue
        time     = safe_float(ev.get("time", 0))
        name     = ev.get("spell_name") or ev.get("name", "?")
        name     = name.replace("_", " ").title()
        icon     = (ev.get("spell_icon") or ev.get("icon") or "").lower()
        if not icon:
            icon = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_") or "inv_misc_questionmark"
        etype    = ev.get("type", "cast").lower()
        spell_id = int(ev.get("id", 0))
        out.append({
            "time":     round(time, 2),
            "name":     name,
            "icon":     icon,
            "type":     etype,
            "spell_id": spell_id,
        })
    return out


_SLOT_ORDER = [
    "head", "neck", "shoulder", "shoulders", "back", "chest",
    "wrist", "wrists", "hands", "waist", "legs", "feet",
    "finger1", "finger2", "trinket1", "trinket2",
    "main_hand", "off_hand",
]

_SLOT_LABELS = {
    "head": "Head", "neck": "Neck",
    "shoulder": "Shoulders", "shoulders": "Shoulders",
    "back": "Back", "chest": "Chest",
    "wrist": "Wrist", "wrists": "Wrist",
    "hands": "Hands", "waist": "Waist", "legs": "Legs", "feet": "Feet",
    "finger1": "Ring 1", "finger2": "Ring 2",
    "trinket1": "Trinket 1", "trinket2": "Trinket 2",
    "main_hand": "Main Hand", "off_hand": "Off Hand",
}


def _slug_to_title(slug: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[_\-]+", slug) if w)


def _looks_like_slug(name: str) -> bool:
    if not name:
        return False
    if " " in name:
        return False
    if "_" in name or "-" in name:
        return True
    if name == name.lower() and len(name) > 3:
        return True
    return False


def _parse_items(player: dict) -> list:
    gear = player.get("gear")

    if isinstance(gear, dict) and gear:
        raw_items = gear
    elif isinstance(gear, list) and gear:
        raw_items = {g["slot"]: g for g in gear if isinstance(g, dict) and g.get("slot")}
    else:
        raw_items = player.get("items") or {}
        if not isinstance(raw_items, dict):
            raw_items = {}

    out = []
    seen = set()
    ordered_slots = _SLOT_ORDER + [s for s in raw_items if s not in _SLOT_ORDER]
    for slot in ordered_slots:
        item = raw_items.get(slot)
        if not isinstance(item, dict) or slot in seen:
            continue
        seen.add(slot)

        encoded = item.get("encoded_item", "")

        item_id = int(item.get("id", 0))
        if not item_id and encoded:
            m = re.search(r",id=(\d+)", encoded)
            if m:
                item_id = int(m.group(1))

        ilvl = int(safe_float(item.get("item_level", item.get("ilevel", 0))))

        name = item.get("name", "").strip()

        if _looks_like_slug(name):
            name = _slug_to_title(name)
        elif not name and encoded:
            raw_slug = encoded.split(",")[0].strip()
            if raw_slug and not raw_slug.isdigit():
                name = _slug_to_title(raw_slug)

        icon    = (item.get("icon", "") or "").lower().replace(" ", "_")
        quality = int(item.get("quality", 0))

        raw_gems = item.get("gems", [])
        gems = []
        if isinstance(raw_gems, list):
            for g in raw_gems:
                if isinstance(g, dict):
                    gems.append({"id": int(g.get("id", 0)), "name": g.get("name", "")})
                elif isinstance(g, (int, str)) and str(g).isdigit():
                    gems.append({"id": int(g), "name": ""})

        enchant_raw = item.get("enchant", item.get("enchants", None))
        enchant = None
        if isinstance(enchant_raw, dict):
            enchant = {"id": int(enchant_raw.get("id", 0)), "name": enchant_raw.get("name", "")}
        elif isinstance(enchant_raw, (int, str)) and str(enchant_raw).isdigit():
            enchant = {"id": int(enchant_raw), "name": ""}

        if not item_id and not name and not ilvl:
            continue

        out.append({
            "slot":       slot,
            "slot_label": _SLOT_LABELS.get(slot, slot.replace("_", " ").title()),
            "id":         item_id,
            "name":       name,
            "item_level": ilvl,
            "icon":       icon,
            "quality":    quality,
            "gems":       gems,
            "enchant":    enchant,
        })

    return out


def _avg_item_level(items: list) -> int | None:
    ilvls = [i["item_level"] for i in items if i["item_level"] > 0]
    if not ilvls:
        return None
    return round(sum(ilvls) / len(ilvls))


# ---------------------------------------------------------------------------
# Wyciaganie talent string z raw SimC JSON
# SimC moze zapisac talents w roznych miejscach w zaleznosci od wersji i trybu
# (addon paste vs armory fetch). Sprawdzamy wszystkie znane lokalizacje.
# ---------------------------------------------------------------------------
def _extract_talents_from_raw(raw: dict, player: dict) -> str | None:
    # 1. Bezposrednio na playerze (addon paste — SimC wpisuje z inputu)
    for key in ("talents_str", "talents", "talent_string", "talent_code"):
        v = player.get(key)
        if v and isinstance(v, str) and len(v) > 10:
            return v.strip()

    # 2. Profil gracza na poziomie sim (armory fetch — SimC zapisuje po pobraniu)
    sim = raw.get("sim", {})
    for key in ("talents_str", "talents", "talent_string", "talent_code"):
        v = sim.get(key)
        if v and isinstance(v, str) and len(v) > 10:
            return v.strip()

    # 3. sim.players[0].specialization.talent_string (niektore wersje SimC)
    spec = player.get("specialization") or player.get("spec") or {}
    if isinstance(spec, dict):
        for key in ("talent_string", "talents_str", "talents"):
            v = spec.get(key)
            if v and isinstance(v, str) and len(v) > 10:
                return v.strip()

    # 4. sim.players[0].profile (armory — SimC TWW zapisuje profil postaci)
    profile = player.get("profile") or {}
    if isinstance(profile, dict):
        for key in ("talent_string", "talents_str", "talents", "talent_code"):
            v = profile.get(key)
            if v and isinstance(v, str) and len(v) > 10:
                return v.strip()

    # 5. Fallback: szukaj rekurencyjnie w pierwszym playerze do glebokosci 3
    def _deep_search(obj, depth=0):
        if depth > 3 or not isinstance(obj, dict):
            return None
        for key in ("talents_str", "talent_string", "talent_code"):
            v = obj.get(key)
            if v and isinstance(v, str) and len(v) > 10:
                return v.strip()
        for v in obj.values():
            if isinstance(v, dict):
                found = _deep_search(v, depth + 1)
                if found:
                    return found
        return None

    return _deep_search(player)


def parse_results(json_path: str):
    try:
        with open(json_path) as f:
            raw = json.load(f)

        sim     = raw.get("sim", {})
        players = sim.get("players", [])
        if not players:
            return {"error": "No player data"}

        player = players[0]
        cd     = player.get("collected_data", {})

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

        items = _parse_items(player)
        avg_item_level = (
            int(safe_float(player.get("avg_item_level", 0))) or _avg_item_level(items) or None
        )

        abilities = player.get("stats", [])
        if not isinstance(abilities, list):
            abilities = []

        spells = []
        for ab in abilities:
            if not isinstance(ab, dict):
                continue
            dps_v   = ability_dps(ab)
            tot_dmg = ability_total_dmg(ab)
            if dps_v <= 0 and tot_dmg <= 0:
                continue

            name                        = spell_display_name(ab)
            crit_pct, miss_pct, avg_hit = _weighted_stats(ab)
            executes, is_channel        = ability_count(ab)
            icon                        = spell_icon_slug(ab)
            spell_id                    = int(ab.get("id", 0))

            if avg_hit == 0 and executes > 0 and tot_dmg > 0:
                avg_hit = round(tot_dmg / executes)

            spells.append({
                "name":       name,
                "icon":       icon,
                "spell_id":   spell_id,
                "dps":        round(dps_v, 2),
                "total_dmg":  round(tot_dmg),
                "crit_pct":   crit_pct,
                "executes":   executes,
                "count":      executes,
                "avg_hit":    avg_hit,
                "miss_pct":   miss_pct,
                "is_channel": is_channel,
            })

        if not spells:
            action_seq   = cd.get("action_sequence", [])
            spell_counts: dict = {}
            for action in action_seq:
                sname = action.get("spell_name") or action.get("name", "?")
                sname = sname.replace("_", " ").title()
                spell_counts[sname] = spell_counts.get(sname, 0) + 1
            for sname, count in spell_counts.items():
                spells.append({
                    "name": sname, "icon": "inv_misc_questionmark", "spell_id": 0,
                    "dps": 0.0, "total_dmg": 0,
                    "crit_pct": 0.0, "executes": count, "count": count,
                    "avg_hit": 0, "miss_pct": 0.0, "is_channel": False,
                    "dps_pct": 0.0, "dmg_pct": 0.0,
                })

        total_spell_dps = sum(s["dps"]       for s in spells)
        total_spell_dmg = sum(s["total_dmg"] for s in spells)

        for s in spells:
            s["dps_pct"] = round(s["dps"]       / total_spell_dps * 100, 1) if total_spell_dps > 0 else 0.0
            s["dmg_pct"] = round(s["total_dmg"] / total_spell_dmg * 100, 1) if total_spell_dmg > 0 else 0.0

        spells = sorted(spells, key=lambda x: x["total_dmg"], reverse=True)

        top_spells = spells[:25]
        other_dps  = sum(s["dps"]       for s in spells[25:])
        other_dmg  = sum(s["total_dmg"] for s in spells[25:])
        if other_dps > 0 or other_dmg > 0:
            top_spells.append({
                "name": "Other", "icon": "inv_misc_questionmark", "spell_id": 0,
                "dps": round(other_dps, 2), "total_dmg": round(other_dmg),
                "crit_pct": 0, "executes": 0, "count": 0, "avg_hit": 0, "miss_pct": 0.0,
                "is_channel": False,
                "dps_pct": round(other_dps / total_spell_dps * 100, 1) if total_spell_dps > 0 else 0.0,
                "dmg_pct": round(other_dmg / total_spell_dmg * 100, 1) if total_spell_dmg > 0 else 0.0,
            })

        buffs = _parse_buffs(cd)
        if not buffs:
            action_seq = cd.get("action_sequence", [])
            buffs = _parse_buffs_from_timeline(action_seq, fight_length)

        constant_buffs = _parse_buffs_constant(player)
        buffs = buffs + constant_buffs

        timeline = _parse_timeline(cd, fight_length)

        # Wyciagamy talent string ze wszystkich znanych lokalizacji w SimC JSON
        talents_str = _extract_talents_from_raw(raw, player)

        return {
            "name":           player.get("name", "?"),
            "dps":            round(dps_mean, 1),
            "dps_std":        round(dps_std, 1),
            "fight_length":   round(fight_length, 1),
            "avg_item_level": avg_item_level,
            "stats":          stats,
            "items":          items,
            "spells":         top_spells,
            "buffs":          buffs,
            "timeline":       timeline,
            "talents_str":    talents_str,
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


@router.get("/api/result/{job_id}/json")
async def get_result_json(job_id: str):
    from database import get_result_data, get_job

    job = get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")

    data = get_result_data(job_id)
    if data:
        return data

    json_path = job.get("json_path")
    if json_path and os.path.exists(json_path):
        return parse_results(json_path)

    raise HTTPException(404, "Result data not found")


@router.get("/api/result/{job_id}/meta")
async def get_result_meta(job_id: str):
    from database import SessionLocal, HistoryEntryModel, get_result_talents

    talents = get_result_talents(job_id)

    with SessionLocal() as db:
        entry = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.job_id == job_id
        ).first()

    if not entry:
        return {"talents": talents}

    return {
        "character_name":       entry.character_name,
        "character_class":      entry.character_class,
        "character_spec":       entry.character_spec,
        "character_spec_id":    entry.character_spec_id,
        "character_realm_slug": entry.character_realm_slug,
        "fight_style":          entry.fight_style,
        "role":                 entry.role,
        "author_bnet_id":       entry.user_id or None,
        "talents":              talents,
    }


@router.get("/api/result/{job_id}/csv")
async def get_result_csv(job_id: str):
    from database import get_result_data, get_job

    job = get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")

    data = get_result_data(job_id)
    if not data:
        json_path = job.get("json_path")
        if json_path and os.path.exists(json_path):
            data = parse_results(json_path)
        else:
            raise HTTPException(404, "Result data not found")

    if "error" in data:
        raise HTTPException(500, data["error"])

    spells = data.get("spells", [])

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["spell", "spell_id", "dps", "dps_pct", "total_dmg", "dmg_pct", "crit_pct", "avg_hit", "count"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for s in spells:
        writer.writerow({
            "spell":     s.get("name", ""),
            "spell_id":  s.get("spell_id", 0),
            "dps":       s.get("dps", 0),
            "dps_pct":   s.get("dps_pct", 0),
            "total_dmg": s.get("total_dmg", 0),
            "dmg_pct":   s.get("dmg_pct", 0),
            "crit_pct":  s.get("crit_pct", 0),
            "avg_hit":   s.get("avg_hit", 0),
            "count":     s.get("count", 0),
        })

    csv_bytes = buf.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="result_{job_id}.csv"'},
    )


@router.get("/api/result/{job_id}/debug")
async def get_result_debug(job_id: str):
    from database import get_result_data, get_job

    job = get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Result not ready")

    data = get_result_data(job_id)
    if not data:
        raise HTTPException(404, "Result data not in DB (old result or parse failed)")

    return {
        "source":         "db",
        "keys":           list(data.keys()),
        "dps":            data.get("dps"),
        "spells_count":   len(data.get("spells", [])),
        "items_count":    len(data.get("items", [])),
        "buffs_count":    len(data.get("buffs", [])),
        "timeline_count": len(data.get("timeline", [])),
        "has_stats":      bool(data.get("stats")),
        "has_talents":    bool(data.get("talents_str")),
    }
