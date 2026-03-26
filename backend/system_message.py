# system_message.py — endpointy komunikatu systemowego (#59)
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_config, set_config, add_log

router = APIRouter()

VALID_TYPES = {"info", "warning", "danger"}


class SystemMessageUpdate(BaseModel):
    message: str
    type: str = "info"


# ---------- admin endpoints ----------

def _require_admin_from_admin_module(request: Request):
    """Importuje _require_admin z admin.py żeby nie duplikować logiki."""
    from admin import _require_admin
    return _require_admin(request)


@router.get("/admin/api/system-message")
async def admin_get_system_message(request: Request):
    _require_admin_from_admin_module(request)
    return {
        "message": get_config("system_message", ""),
        "type":    get_config("system_message_type", "info"),
    }


@router.post("/admin/api/system-message")
async def admin_set_system_message(request: Request, data: SystemMessageUpdate):
    _require_admin_from_admin_module(request)
    if data.type not in VALID_TYPES:
        raise HTTPException(400, f"type must be one of: {', '.join(VALID_TYPES)}")
    msg = data.message.strip()
    if len(msg) > 500:
        raise HTTPException(400, "message too long (max 500 chars)")
    set_config("system_message", msg)
    set_config("system_message_type", data.type)
    add_log(
        level="INFO",
        message="[system-message] set by admin",
        context=f"type: {data.type}\nmessage: {msg!r}",
    )
    return {"ok": True, "message": msg, "type": data.type}


@router.delete("/admin/api/system-message")
async def admin_clear_system_message(request: Request):
    _require_admin_from_admin_module(request)
    set_config("system_message", "")
    set_config("system_message_type", "info")
    add_log(level="INFO", message="[system-message] cleared by admin")
    return {"ok": True}


# ---------- publiczny endpoint ----------

@router.get("/api/system-message")
async def public_system_message():
    """Publiczny — używany przez frontend do wyświetlenia bannera."""
    msg = get_config("system_message", "")
    if not msg:
        return {"message": None, "type": "info"}
    return {
        "message": msg,
        "type":    get_config("system_message_type", "info"),
    }
