import os
import uuid
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from slowapi import Limiter
from slowapi.util import get_remote_address

from logging_config import setup_logging
from simulation import (
    jobs, _running_lock, _count_running, _get_max_concurrent,
    _get_guest_sims_enabled, _build_simc_input, _run_sim,
    _validate_addon_text, SimRequest,
)
from database import create_job, get_result_data

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
log = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")

# Słownik grupowych jobów vault: group_id -> stan grupy
vault_groups: dict = {}
_vault_lock = threading.Lock()


class VaultItem(BaseModel):
    name: str
    slot: str
    item_id: Optional[int] = 0
    item_level: Optional[int] = 0
    # Opcjonalny override linii simc dla danego itemu (np. z addon exportu)
    simc_line: Optional[str] = None


class VaultRequest(BaseModel):
    session: Optional[str] = None
    addon_text: str
    items: List[VaultItem]
    fight_style: Optional[str] = "Patchwerk"
    iterations: Optional[int] = 1000
    target_error: Optional[float] = 0.5
    one_button_mode: Optional[bool] = False


def _inject_vault_item(addon_text: str, item: VaultItem) -> str:
    """Podmienia/dopisuje item w profilu simc na zadany przedmiot z Vaultu."""
    if item.simc_line:
        # Jeśli mamy gotową linię simc, podmieniamy slot w addon_text
        lines = addon_text.splitlines()
        slot_key = item.slot.lower().replace(" ", "_")
        new_lines = [l for l in lines if not l.strip().lower().startswith(slot_key + "=")]
        new_lines.append(item.simc_line.strip())
        return "\n".join(new_lines)
    elif item.item_id and item.item_id > 0:
        # Minimalny zapis simc: slot=,id=XXXXX,ilevel=YYY
        lines = addon_text.splitlines()
        slot_key = item.slot.lower().replace(" ", "_")
        new_lines = [l for l in lines if not l.strip().lower().startswith(slot_key + "=")]
        ilevel_part = f",ilevel={item.item_level}" if item.item_level else ""
        new_lines.append(f"{slot_key}=,id={item.item_id}{ilevel_part}")
        return "\n".join(new_lines)
    # Brak danych do podmiany — zwróć oryginał (baseline)
    return addon_text


def _run_vault_group(group_id: str, base_addon_text: str, items: List[VaultItem],
                     fight_style: str, iterations: int, target_error: float,
                     one_button_mode: bool, wow_build: str):
    """Odpalanie symulacji sekwencyjnie: baseline + każdy item z Vaultu."""
    group = vault_groups[group_id]

    def _start_single(label: str, addon_text: str) -> str:
        """Tworzy job i odpala symulację. Zwraca job_id."""
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(RESULTS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        out_path = os.path.join(job_dir, "output.json")

        req = SimRequest(
            addon_text=addon_text,
            fight_style=fight_style,
            iterations=iterations,
            target_error=target_error,
            one_button_mode=one_button_mode,
        )
        simc_input = _build_simc_input(req, out_path)

        with _running_lock:
            jobs[job_id] = {
                "status":          "running",
                "json_path":       out_path,
                "error":           None,
                "started_at":      time.time(),
                "counted":         True,
                "source":          "vault",
                "wow_build":       wow_build,
                "one_button_mode": bool(one_button_mode),
            }
        create_job(job_id, out_path)

        t = threading.Thread(target=_run_sim, args=(job_id, simc_input, out_path), daemon=True)
        t.start()
        return job_id

    def _wait_for_job(job_id: str, timeout: int = 420):
        """Polling co 2s aż job skończy się lub timeout."""
        start = time.time()
        while time.time() - start < timeout:
            job = jobs.get(job_id)
            if job and job["status"] in ("done", "error"):
                return job["status"]
            time.sleep(2)
        return "error"

    # 1. Baseline
    with _vault_lock:
        group["current_label"] = "Baseline"
        group["done_count"] = 0

    baseline_job_id = _start_single("Baseline", base_addon_text)
    with _vault_lock:
        group["baseline_job_id"] = baseline_job_id

    status = _wait_for_job(baseline_job_id)
    baseline_dps = 0.0
    if status == "done":
        result = get_result_data(baseline_job_id)
        baseline_dps = result.get("dps", 0.0) if result else 0.0

    with _vault_lock:
        group["baseline_dps"] = baseline_dps
        group["done_count"] = 1

    # 2. Każdy item sekwencyjnie
    for idx, item in enumerate(items):
        with _vault_lock:
            group["current_label"] = f"{item.slot} — {item.name}"

        modified_addon = _inject_vault_item(base_addon_text, item)
        item_job_id = _start_single(item.name, modified_addon)

        item_status = _wait_for_job(item_job_id)
        item_dps = 0.0
        if item_status == "done":
            result = get_result_data(item_job_id)
            item_dps = result.get("dps", 0.0) if result else 0.0

        dps_delta = item_dps - baseline_dps
        dps_delta_pct = round((dps_delta / baseline_dps * 100), 2) if baseline_dps > 0 else 0.0

        with _vault_lock:
            group["results"].append({
                "item_name":     item.name,
                "slot":          item.slot,
                "item_id":       item.item_id,
                "item_level":    item.item_level,
                "dps":           item_dps,
                "dps_delta":     round(dps_delta, 1),
                "dps_delta_pct": dps_delta_pct,
                "job_id":        item_job_id,
                "status":        item_status,
            })
            group["done_count"] += 1

    # Sortuj wyniki po DPS malejąco i nadaj ranki
    with _vault_lock:
        sorted_results = sorted(group["results"], key=lambda x: x["dps"], reverse=True)
        for rank, r in enumerate(sorted_results, start=1):
            r["rank"] = rank
        group["results"] = sorted_results
        group["status"] = "done"
        group["current_label"] = None

    log.info("vault-group-done", group_id=group_id, items=len(items), baseline_dps=baseline_dps)


@router.post("/api/vault/start")
@limiter.limit("3/minute")
async def start_vault(request: Request, req: VaultRequest):
    if not req.addon_text or not req.addon_text.strip():
        raise HTTPException(400, "Wklej addon export!")
    if not req.items:
        raise HTTPException(400, "Podaj przynajmniej jeden item z Vaultu.")
    if len(req.items) > 9:
        raise HTTPException(400, "Maksymalnie 9 itemów (wielkość Great Vaultu).")

    if not req.session and not _get_guest_sims_enabled():
        raise HTTPException(403, "Symulacje dla niezalogowanych użytkowników są wyłączone.")

    max_concurrent = _get_max_concurrent()
    with _running_lock:
        if _count_running() >= max_concurrent:
            raise HTTPException(429, "Serwer zajęty. Spróbuj za chwilę.")

    _validate_addon_text(req.addon_text)

    from admin import get_wow_build_cached
    wow_build = get_wow_build_cached()

    group_id = str(uuid.uuid4())
    total = len(req.items) + 1  # +1 za baseline

    with _vault_lock:
        vault_groups[group_id] = {
            "status":          "running",
            "total":           total,
            "done_count":      0,
            "current_label":   "Baseline",
            "baseline_job_id": None,
            "baseline_dps":    None,
            "results":         [],
            "started_at":      time.time(),
        }

    t = threading.Thread(
        target=_run_vault_group,
        args=(
            group_id,
            req.addon_text.strip(),
            req.items,
            req.fight_style,
            req.iterations,
            req.target_error,
            req.one_button_mode,
            wow_build,
        ),
        daemon=True,
    )
    t.start()

    log.info("vault-group-started", group_id=group_id, items=len(req.items))
    return {"group_id": group_id, "total": total}


@router.get("/api/vault/status/{group_id}")
async def get_vault_status(group_id: str):
    with _vault_lock:
        group = vault_groups.get(group_id)

    if not group:
        raise HTTPException(404, "Vault group not found.")

    return {
        "status":        group["status"],
        "total":         group["total"],
        "done_count":    group["done_count"],
        "current_label": group["current_label"],
        "baseline_dps":  group["baseline_dps"],
        "results":       group["results"],
    }
