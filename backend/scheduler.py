"""
scheduler.py — automatyczny rebuild SimC przy wykryciu nowego WoW retail buildu.

Logika:
  1. Co N godzin (konfigurowane przez admina, domyślnie 6) polling TACT endpoint.
  2. Porównanie z ostatnim zapisanym buildem w tabeli config (klucz: scheduler.last_wow_build).
  3. Jeśli build się zmienił AND rebuild nie leci właśnie — odpal rebuild SSH.
  4. Alerty w panelu admina przy wykryciu nowego buildu i po zakończeniu.

Konfiguracja (przez admin API lub set_config):
  scheduler.enabled            — "true" / "false" (domyślnie "true")
  scheduler.interval_h         — liczba godzin (domyślnie "6")
  scheduler.last_wow_build     — ostatni znany build (ustawiany automatycznie)
  scheduler.last_check_ts      — timestamp ostatniego pollingu (ISO)
  scheduler.last_check_status  — "ok" / "error: ..." (ostatni wynik pollingu)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import get_config, set_config
from database import trigger_alert, add_log

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_JOB_ID = "wow_build_check"
_SESSION_JOB_ID = "session_cleanup"


def _get_interval_h() -> int:
    try:
        return max(1, int(get_config("scheduler.interval_h", "6")))
    except Exception:
        return 6


def _is_enabled() -> bool:
    return get_config("scheduler.enabled", "true").lower() == "true"


async def _cleanup_sessions() -> None:
    """Usuwa wygasłe sesje z bazy co godzinę."""
    from database import SessionLocal, SessionModel

    with SessionLocal() as db:
        deleted = db.query(SessionModel).filter(
            SessionModel.expires_at < time.time()
        ).delete()
        db.commit()

    if deleted:
        logger.info(f"[scheduler] Usunięto {deleted} wygasłych sesji.")


async def _check_and_rebuild() -> None:
    """
    Właściwy job schedulera:
    1. Pobierz aktualny WoW build z TACT.
    2. Porównaj z ostatnim zapisanym.
    3. Jeśli nowy — odpal rebuild (jeśli nie trwa już).
    """
    if not _is_enabled():
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        # Import tutaj żeby uniknąć circular imports
        from admin import get_wow_retail_build, _rebuild_state

        # Wyczyść cache TACT żeby zawsze pytać świeżo
        from admin import _wow_build_cache
        _wow_build_cache["ts"] = 0

        wow_data = await get_wow_retail_build()

        if "error" in wow_data:
            raise ValueError(wow_data["error"])

        current_build = wow_data.get("build")
        if not current_build:
            raise ValueError("No build returned from TACT")

        set_config("scheduler.last_check_ts", now_iso)
        set_config("scheduler.last_check_status", "ok")

        last_known = get_config("scheduler.last_wow_build", "")

        if last_known == current_build:
            # Brak zmian
            logger.debug(f"[scheduler] WoW build bez zmian: {current_build}")
            return

        # Nowy build wykryty!
        logger.info(f"[scheduler] Nowy WoW build: {last_known!r} → {current_build!r}")
        set_config("scheduler.last_wow_build", current_build)

        add_log(
            level="INFO",
            message=f"[scheduler] Wykryto nowy WoW build: {current_build}" +
                    (f" (poprzedni: {last_known})" if last_known else " (pierwsze wykrycie)"),
        )

        trigger_alert(
            "new_wow_build",
            f"Wykryto nowy WoW retail build: {current_build}"
            + (f" (poprzedni: {last_known})" if last_known else ""),
        )

        # Nie odpalaj jeśli rebuild już trwa
        if _rebuild_state.get("status") == "running":
            logger.warning("[scheduler] Rebuild już trwa — pomijam trigger.")
            add_log(
                level="WARNING",
                message=f"[scheduler] Nowy build {current_build} wykryty, ale rebuild już trwa — pominięto.",
            )
            return

        # Odpal rebuild SSH (ta sama logika co przycisk w adminie)
        await _trigger_auto_rebuild(current_build)

    except Exception as e:
        err_msg = str(e)[:200]
        logger.error(f"[scheduler] Błąd podczas sprawdzania WoW build: {err_msg}")
        set_config("scheduler.last_check_ts", now_iso)
        set_config("scheduler.last_check_status", f"error: {err_msg}")
        add_log(
            level="ERROR",
            message=f"[scheduler] Błąd pollingu TACT: {err_msg}",
        )


async def _trigger_auto_rebuild(current_build: str) -> None:
    """Odpala rebuild SSH identycznie jak endpoint POST /admin/api/simc/rebuild."""
    import os
    import re
    import subprocess
    import asyncio as _aio
    import subprocess as _sp
    from datetime import datetime as _dt

    from admin import _rebuild_state, _get_local_simc_version
    from database import SessionLocal, SimcRebuildLogModel, log_audit

    username    = "scheduler"
    simc_path   = os.environ.get("SIMC_PATH", "/app/SimulationCraft/simc")
    simc_before = _get_local_simc_version(simc_path)

    with SessionLocal() as db:
        log_row = SimcRebuildLogModel(
            triggered_by=username,
            status="running",
            wow_build=current_build,
            simc_before=simc_before,
            started_at=_dt.utcnow(),
        )
        db.add(log_row)
        db.commit()
        db.refresh(log_row)
        log_id = log_row.id

    _rebuild_state.update({
        "status":       "running",
        "triggered_by": username,
        "started_at":   _dt.utcnow().isoformat(),
        "finished_at":  None,
        "simc_before":  simc_before,
        "simc_after":   None,
        "error":        None,
        "log_id":       log_id,
    })

    log_audit(username, "simc.rebuild.start", {
        "log_id":      log_id,
        "simc_before": simc_before,
        "trigger":     "scheduler",
        "wow_build":   current_build,
    })
    add_log(
        level="INFO",
        message=f"[scheduler] Auto-rebuild SimC started (log_id={log_id}, wow_build={current_build})",
    )

    async def _do():
        ssh_host   = os.environ.get("REBUILD_SSH_HOST",    "localhost")
        ssh_user   = os.environ.get("REBUILD_SSH_USER",    "deploy")
        ssh_key    = os.environ.get("REBUILD_SSH_KEY_PATH", "/run/secrets/rebuild_ssh_key")
        ssh_script = os.environ.get("REBUILD_SSH_SCRIPT",   "/opt/scripts/rebuild-simc.sh")

        final_status = "error"
        simc_after   = None
        error_msg    = None
        full_log     = ""

        try:
            proc = await _aio.create_subprocess_exec(
                "ssh",
                "-i", ssh_key,
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=10",
                f"{ssh_user}@{ssh_host}",
                ssh_script,
                stdout=_sp.PIPE,
                stderr=_sp.STDOUT,
            )
            out_bytes, _ = await _aio.wait_for(proc.communicate(), timeout=900)
            full_log = out_bytes.decode(errors="replace")[:50000]

            if proc.returncode == 0:
                m = re.search(r"^SIMC_VERSION=(.+)$", full_log, re.MULTILINE)
                simc_after   = m.group(1).strip()[:64] if m else _get_local_simc_version(simc_path)
                final_status = "success"
            else:
                error_msg = f"SSH script exited with code {proc.returncode}"

        except _aio.TimeoutError:
            error_msg = "rebuild timed out (900s)"
        except FileNotFoundError:
            error_msg = "ssh binary not found"
        except Exception as exc:
            error_msg = str(exc)

        finished = _dt.utcnow()

        with SessionLocal() as db:
            row = db.query(SimcRebuildLogModel).filter(SimcRebuildLogModel.id == log_id).first()
            if row:
                row.status      = final_status
                row.simc_after  = simc_after
                row.finished_at = finished
                row.log_output  = (full_log + (f"\n\nERROR: {error_msg}" if error_msg else ""))[:50000]
                db.commit()

        _rebuild_state.update({
            "status":      final_status,
            "finished_at": finished.isoformat(),
            "simc_after":  simc_after,
            "error":       error_msg,
        })

        log_audit(username, f"simc.rebuild.{final_status}", {
            "log_id":      log_id,
            "simc_before": simc_before,
            "simc_after":  simc_after,
            "error":       error_msg,
            "trigger":     "scheduler",
        })
        add_log(
            level="INFO" if final_status == "success" else "ERROR",
            message=(
                f"[scheduler] Auto-rebuild {final_status} "
                f"(log_id={log_id}, simc={simc_after or 'n/a'})"
                + (f", error: {error_msg}" if error_msg else "")
            ),
        )
        # Alert o wyniku rebuildu
        if final_status == "success":
            trigger_alert(
                "auto_rebuild_success",
                f"Auto-rebuild SimC zakończony sukcesem — WoW build {current_build}, simc {simc_after}",
            )
        else:
            trigger_alert(
                "auto_rebuild_error",
                f"Auto-rebuild SimC BŁĄD — WoW build {current_build}: {error_msg}",
            )

    asyncio.create_task(_do())


# ---------- public API ----------

def start_scheduler() -> None:
    """Uruchamia scheduler. Wywoływać z FastAPI startup."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    interval_h = _get_interval_h()

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _check_and_rebuild,
        trigger=IntervalTrigger(hours=interval_h),
        id=_JOB_ID,
        name="WoW build check & auto-rebuild",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _cleanup_sessions,
        trigger=IntervalTrigger(hours=1),
        id=_SESSION_JOB_ID,
        name="Session cleanup",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(f"[scheduler] Uruchomiony — interwał: {interval_h}h")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Zatrzymany.")


def reschedule(interval_h: int) -> None:
    """Zmienia interwał w locie (bez restartu)."""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return
    interval_h = max(1, interval_h)
    set_config("scheduler.interval_h", str(interval_h))
    _scheduler.reschedule_job(
        _JOB_ID,
        trigger=IntervalTrigger(hours=interval_h),
    )
    logger.info(f"[scheduler] Interwał zmieniony na {interval_h}h")


def get_status() -> dict:
    """Zwraca stan schedulera do API."""
    global _scheduler
    running = bool(_scheduler and _scheduler.running)
    next_run = None
    if running:
        job = _scheduler.get_job(_JOB_ID)
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    return {
        "running":       running,
        "enabled":       _is_enabled(),
        "interval_h":    _get_interval_h(),
        "next_run":      next_run,
        "last_check_ts": get_config("scheduler.last_check_ts",     "") or None,
        "last_check_status": get_config("scheduler.last_check_status", "") or None,
        "last_wow_build":    get_config("scheduler.last_wow_build",    "") or None,
    }


async def trigger_now() -> None:
    """Ręczny trigger poza harmonogramem (używany przez admin API)."""
    await _check_and_rebuild()
