import os
import re
import time
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

BLIZZARD_CLIENT_ID     = os.getenv("BLIZZARD_CLIENT_ID", "")
BLIZZARD_CLIENT_SECRET = os.getenv("BLIZZARD_CLIENT_SECRET", "")

BLIZZARD_TOKEN_URL = "https://oauth.battle.net/token"
BLIZZARD_API_BASE  = "https://eu.api.blizzard.com"

_token_cache: dict = {"token": None, "expires_at": 0.0}
_tree_cache:  dict = {}
TREE_CACHE_TTL = 3600 * 6


async def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            BLIZZARD_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET),
        )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"]      = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 86400)
    return _token_cache["token"]


def _extract_spell_id(href: str) -> int:
    if not href:
        return 0
    m = re.search(r'/spell/(\d+)', href)
    return int(m.group(1)) if m else 0


async def _fetch_spec_tree(spec_id: int) -> list[dict]:
    """Pobiera talent tree dla spec_id. Zwraca liste node dict posortowana po node_id."""
    now = time.time()
    cached = _tree_cache.get(spec_id)
    if cached and now < cached["expires_at"]:
        return cached["nodes"]

    token = await _get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Battlenet-Namespace": "static-eu",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        spec_resp = await client.get(
            f"{BLIZZARD_API_BASE}/data/wow/playable-specialization/{spec_id}",
            params={"locale": "en_US"},
            headers=headers,
        )
        spec_resp.raise_for_status()
        spec_data = spec_resp.json()

        tree_link = (
            spec_data.get("spec_talent_tree", {}).get("key", {}).get("href", "")
            or spec_data.get("talent_tree", {}).get("key", {}).get("href", "")
        )
        if not tree_link:
            raise HTTPException(502, f"No talent tree link for spec {spec_id}")

        tree_resp = await client.get(tree_link, params={"locale": "en_US"}, headers=headers)
        tree_resp.raise_for_status()
        tree_data = tree_resp.json()

    nodes = []
    for section in ("class_talent_nodes", "spec_talent_nodes"):
        for node in tree_data.get(section, []):
            node_id = node.get("id")
            if not node_id:
                continue
            ranks = node.get("ranks", [])
            if not ranks:
                continue

            first_rank    = ranks[0]
            tooltip       = first_rank.get("tooltip", {})
            talent_info   = tooltip.get("talent", {})
            spell_tooltip = tooltip.get("spell_tooltip", {})
            spell_info    = spell_tooltip.get("spell", {})

            name     = talent_info.get("name") or spell_info.get("name") or "?"
            spell_href = spell_info.get("key", {}).get("href", "")
            spell_id   = _extract_spell_id(spell_href) or int(spell_info.get("id", 0)) or int(talent_info.get("id", 0))
            node_type  = node.get("node_type", {}).get("type", "ACTIVE")

            nodes.append({
                "node_id":   node_id,
                "name":      name,
                "spell_id":  spell_id,
                "type":      node_type,
                "row":       node.get("display_row", 0),
                "col":       node.get("display_col", 0),
                "max_ranks": len(ranks),
            })

    # Kluczowe: sortuj po node_id rosnaco — taka sama kolejnosc jak WoW C_Traits.GetTreeNodes()
    nodes.sort(key=lambda n: n["node_id"])

    _tree_cache[spec_id] = {"nodes": nodes, "expires_at": now + TREE_CACHE_TTL}
    logger.info(f"Fetched talent tree for spec {spec_id}: {len(nodes)} nodes")
    return nodes


# ---------------------------------------------------------------------------
# WoW TWW talent string decoder
#
# Format: LSB-first 6-bit stream (kazdy znak base64 = 6 bitow, bit 0 pierwszy)
#
# Header (56 bitow):
#   version   (8 bits)  = 2
#   spec_id   (16 bits) = Blizzard spec ID
#   config_id (32 bits) = tree config hash (ignorowany)
#
# Body — dla kazdego nodu drzewa (w kolejnosci node_id ASC):
#   isSelected       (1 bit)
#   isPartiallyRanked(1 bit)  — tylko gdy isSelected=1
#   ranksPurchased   (2 bits) — tylko gdy isPartiallyRanked=1; wartosc 0-3
#   isChoiceNode     (1 bit)  — tylko gdy isSelected=1
#   choiceIndex      (2 bits) — tylko gdy isChoiceNode=1
#
# Ref: Blizzard_ClassTalentImportExport.lua (BlizzardInterfaceCode)
# ---------------------------------------------------------------------------

def _build_bitstream(talent_str: str) -> tuple[list[int], int | None]:
    """
    Dekoduje talent string do strumienia bitow (LSB-first, 6-bit per znak).
    Zwraca (bits, spec_id_z_headera).
    """
    # Usun prefiks klasy/spec jesli istnieje (SimC czasem dodaje "SpecClass:" prefix)
    if ":" in talent_str:
        talent_str = talent_str.split(":", 1)[-1].strip()

    talent_str = talent_str.strip()
    if not talent_str:
        return [], None

    # Konwertuj kazdy znak base64 na 6-bit value i pakuj LSB-first
    bits: list[int] = []
    for c in talent_str:
        if 'A' <= c <= 'Z':
            v = ord(c) - ord('A')
        elif 'a' <= c <= 'z':
            v = ord(c) - ord('a') + 26
        elif '0' <= c <= '9':
            v = ord(c) - ord('0') + 52
        elif c in ('+', '-'):
            v = 62
        elif c in ('/', '_'):
            v = 63
        else:
            continue  # ignoruj biale znaki i padding '='

        for bit_i in range(6):  # LSB first
            bits.append((v >> bit_i) & 1)

    total = len(bits)
    if total < 56:
        return bits, None

    def read(offset: int, count: int) -> int:
        result = 0
        for i in range(count):
            if offset + i < total:
                result |= bits[offset + i] << i
        return result

    # version(8) + spec_id(16) + config_id(32) = 56 bitow
    spec_id = read(8, 16)
    return bits, spec_id if spec_id > 0 else None


def decode_wow_talents(talent_str: str, tree_nodes: list[dict]) -> list[dict]:
    """
    Dekoduje WoW TWW talent string uzywajac listy nodow drzewa.
    tree_nodes musi byc posortowane po node_id ASC (tak jak zwraca _fetch_spec_tree).
    Zwraca liste wybranych nodow z polami node_id, name, spell_id, rank, choice_idx.
    """
    bits, _ = _build_bitstream(talent_str)
    total   = len(bits)

    if total < 56:
        return []

    def read(offset: int, count: int) -> int:
        result = 0
        for i in range(count):
            if offset + i < total:
                result |= bits[offset + i] << i
        return result

    offset = 56  # poczatek body po headerze
    result = []

    for node in tree_nodes:
        if offset + 1 > total:
            break

        is_selected = read(offset, 1); offset += 1
        if not is_selected:
            continue

        # isPartiallyRanked (1 bit)
        is_partial = read(offset, 1); offset += 1
        if is_partial:
            ranks_purchased = read(offset, 2); offset += 2
        else:
            ranks_purchased = node["max_ranks"]  # na maksie

        # isChoiceNode (1 bit)
        is_choice = read(offset, 1); offset += 1
        choice_idx = None
        if is_choice:
            choice_idx = read(offset, 2); offset += 2

        result.append({
            "node_id":   node["node_id"],
            "name":      node["name"],
            "spell_id":  node["spell_id"],
            "type":      node["type"],
            "row":       node["row"],
            "col":       node["col"],
            "max_ranks": node["max_ranks"],
            "rank":      ranks_purchased,
            "choice_idx": choice_idx,
        })

    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/talents/tree/{spec_id}")
async def get_talent_tree(spec_id: int):
    try:
        nodes = await _fetch_spec_tree(spec_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Blizzard API error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"spec_id": spec_id, "nodes": nodes}


@router.get("/api/talents/decode")
async def decode_talents(talents_str: str, spec_id: Optional[int] = None):
    """
    Dekoduje WoW TWW talent string i zwraca liste wybranych nodow z nazwami.
    Query params:
      - talents_str: WoW talent export string (base64url, TWW format)
      - spec_id: (opcjonalne) nadpisuje spec_id z headera stringa
    """
    bits, spec_id_from_str = _build_bitstream(talents_str)

    if not bits:
        return {"talents": [], "spec_id": spec_id}

    effective_spec_id = spec_id or spec_id_from_str

    if not effective_spec_id:
        logger.warning("decode_talents: no spec_id available")
        return {"talents": [], "spec_id": None}

    try:
        tree_nodes = await _fetch_spec_tree(effective_spec_id)
    except Exception as e:
        logger.warning(f"decode_talents: could not fetch tree for spec {effective_spec_id}: {e}")
        return {"talents": [], "spec_id": effective_spec_id}

    decoded = decode_wow_talents(talents_str, tree_nodes)
    return {"talents": decoded, "spec_id": effective_spec_id}
