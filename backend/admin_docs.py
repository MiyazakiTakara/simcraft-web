import os
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse

from admin import _require_admin

router = APIRouter(prefix="/admin/api/docs")

DOCS_DIR = Path(os.environ.get("DOCS_DIR", "/app/docs"))
ALLOWED_LANGS = {"pl", "en"}
SEARCH_CONTEXT_CHARS = 120


def _lang_dir(lang: str) -> Path:
    if lang not in ALLOWED_LANGS:
        raise HTTPException(400, f"Invalid lang. Allowed: {', '.join(ALLOWED_LANGS)}")
    return DOCS_DIR / lang


def _safe_path(filename: str, lang: str) -> Path:
    """Zwraca bezpieczną ścieżkę pliku. Blokuje path traversal."""
    if not filename or re.search(r'[\\/]|\.\.',  filename):
        raise HTTPException(400, "Invalid filename")
    if not filename.endswith(".md"):
        raise HTTPException(400, "Only .md files are allowed")
    base = _lang_dir(lang).resolve()
    path = (base / filename).resolve()
    if not str(path).startswith(str(base)):
        raise HTTPException(400, "Invalid filename")
    return path


@router.get("/search")
async def search_docs(request: Request, q: str = Query(..., min_length=2), lang: str = Query(default="pl")):
    _require_admin(request)
    d = _lang_dir(lang)
    d.mkdir(parents=True, exist_ok=True)
    q_lower = q.lower()
    results = []
    for f in sorted(d.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        lines = text.splitlines()
        matches = []
        for i, line in enumerate(lines):
            if q_lower in line.lower():
                snippet = line.strip()
                if len(snippet) > SEARCH_CONTEXT_CHARS:
                    idx = snippet.lower().find(q_lower)
                    start = max(0, idx - 40)
                    snippet = ("..." if start > 0 else "") + snippet[start:start + SEARCH_CONTEXT_CHARS] + "..."
                matches.append({"line": i + 1, "text": snippet})
        name_match = q_lower in f.name.lower().replace(".md", "")
        if matches or name_match:
            results.append({
                "file":       f.name,
                "name_match": name_match,
                "matches":    matches,
            })
    return results


@router.get("")
async def list_docs(request: Request, lang: str = Query(default="pl")):
    _require_admin(request)
    d = _lang_dir(lang)
    d.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(d.glob("*.md")):
        stat = f.stat()
        files.append({
            "name":     f.name,
            "path":     f.name,
            "size":     stat.st_size,
            "modified": stat.st_mtime,
        })
    return files


@router.get("/{filename}")
async def get_doc(filename: str, request: Request, lang: str = Query(default="pl")):
    _require_admin(request)
    path = _safe_path(filename, lang)
    if not path.exists():
        raise HTTPException(404, "File not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"))
