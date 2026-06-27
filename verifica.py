"""Verifica presenza offerte sul sito del venditore via DuckDuckGo."""

import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Optional

from config import DATA_DIR

CACHE_PATH = DATA_DIR / "verifica_cache.json"

VERIFIED = "✓"
NOT_FOUND = "ND"
ERROR = "!"


def _carica_cache() -> Dict[str, str]:
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _salva_cache(cache: Dict[str, str]):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _cerca_su_ddg(cod_offerta: str, dominio: str) -> str:
    query = f'"{cod_offerta}" site:{dominio}'
    data = urllib.parse.urlencode({"q": query}).encode()
    req = urllib.request.Request(
        "https://html.duckduckgo.com/html/",
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode()
        if cod_offerta in html:
            return VERIFIED
        return NOT_FOUND
    except Exception:
        return ERROR


def _estrai_dominio(url_offerta: str) -> Optional[str]:
    if not url_offerta:
        return None
    try:
        parsed = urllib.parse.urlparse(url_offerta)
        host = parsed.hostname
        if host:
            host = host.removeprefix("www.")
            return host
    except Exception:
        return None
    return None


def verifica_offerte(
    offerte: list,
    limite: int = 50,
    max_workers: int = 5,
) -> Dict[str, str]:
    cache = _carica_cache()
    da_verificare = []
    risultati = {}

    for r in offerte:
        if r.get("_mia"):
            continue
        cod = r.get("cod_offerta", "")
        if not cod:
            continue
        if len(risultati) + len(da_verificare) >= limite:
            break
        if cod in cache:
            risultati[cod] = cache[cod]
            continue
        url = r.get("url_offerta", "")
        dominio = _estrai_dominio(url)
        if not dominio:
            risultati[cod] = NOT_FOUND
            continue
        da_verificare.append((cod, dominio))

    if not da_verificare:
        return risultati

    aggiornati = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuri = {
            executor.submit(_cerca_su_ddg, cod, dominio): (cod, dominio)
            for cod, dominio in da_verificare
        }
        for futuro in as_completed(futuri):
            cod, dominio = futuri[futuro]
            try:
                stato = futuro.result()
            except Exception:
                stato = ERROR
            risultati[cod] = stato
            cache[cod] = stato
            aggiornati += 1
            if aggiornati % 10 == 0:
                _salva_cache(cache)
            time.sleep(0.3)

    _salva_cache(cache)
    return risultati
