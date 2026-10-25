"""Verifica presenza offerte sul sito venditore via Serper.dev (Google Search API)."""

import json
import os
import http.client
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from config import DATA_DIR

CACHE_PATH = DATA_DIR / "verifica_cache.json"
URLS_CACHE_PATH = DATA_DIR / "verifica_urls.json"
ENV_KEY = "SERPER_API_KEY"

VERIFIED = "✓"
NOT_FOUND = "✗"
ERROR = "!"
NO_CHECK = "-"


def _carica_cache() -> Dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    cache: Dict[str, dict] = {}
    for key, val in raw.items():
        if isinstance(val, str):
            stato = val if val != "ND" else NOT_FOUND
            cache[key] = {"cod": stato, "nome": None, "ts": "unknown"}
        elif isinstance(val, dict):
            if val.get("cod") == "ND":
                val["cod"] = NOT_FOUND
            if val.get("nome") == "ND":
                val["nome"] = NOT_FOUND
            cache[key] = val
        else:
            cache[key] = {"cod": None, "nome": None, "ts": "unknown"}
    return cache


def _salva_cache(cache: Dict[str, dict]):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _carica_urls_cache() -> Dict[str, dict]:
    if not URLS_CACHE_PATH.exists():
        return {}
    try:
        with open(URLS_CACHE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _salva_urls_cache(cache: Dict[str, dict]):
    URLS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(URLS_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _cerca_query_serper(termine: str, dominio: str, api_key: str, exact: bool = True) -> Tuple[str, Optional[str]]:
    if exact:
        query = f'"{termine}" site:{dominio}'
    else:
        parole = " ".join(f'+{p}' for p in termine.split())
        query = f'{parole} site:{dominio}'
    payload = json.dumps({"q": query, "gl": "it", "hl": "it"})
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    try:
        conn = http.client.HTTPSConnection("google.serper.dev", timeout=15)
        conn.request("POST", "/search", payload, headers)
        res = conn.getresponse()
        data = res.read().decode()
        conn.close()
    except Exception:
        return ERROR, None

    try:
        results = json.loads(data)
    except json.JSONDecodeError:
        return ERROR, None

    for item in results.get("organic", []):
        link = item.get("link", "")
        if dominio not in link:
            continue
        if termine in link or termine in item.get("title", "") or termine in item.get("snippet", ""):
            return VERIFIED, link
    return NOT_FOUND, None


def _cerca_serper(cod_offerta: str, nome_offerta: str, dominio: str, api_key: str) -> Tuple[str, Optional[str], str, Optional[str], int]:
    stato_cod, url_cod = _cerca_query_serper(cod_offerta, dominio, api_key, exact=True)
    if nome_offerta:
        stato_nome, url_nome = _cerca_query_serper(nome_offerta, dominio, api_key, exact=False)
        return stato_cod, url_cod, stato_nome, url_nome, 2
    return stato_cod, url_cod, NO_CHECK, None, 1


def _estrai_dominio(url_offerta: str) -> Optional[str]:
    if not url_offerta:
        return None
    try:
        parsed = urlparse(url_offerta)
        host = parsed.hostname
        if host:
            host = host.removeprefix("www.")
            return host
    except Exception:
        return None
    return None


def warn_cache_stale(giorni: int = 14):
    if not CACHE_PATH.exists():
        return
    cache = _carica_cache()
    now = datetime.now(timezone.utc)
    soglia = now - timedelta(days=giorni)
    stantie = 0
    for entry in cache.values():
        ts_str = entry.get("ts", "unknown")
        if ts_str == "unknown":
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts < soglia:
                stantie += 1
        except (ValueError, TypeError):
            continue
    if stantie > 0:
        totale = len(cache)
        print(f"\n💾 Cache verifica: {stantie}/{totale} entry più vecchie di {giorni} giorni.")
        print(f"   Per aggiornarle cancella: {CACHE_PATH}")


def verifica_offerte(
    offerte: list,
    limite: int = 50,
    max_workers: int = 3,
    offset: int = 0,
) -> Tuple[Dict[str, str], int]:
    api_key = os.environ.get(ENV_KEY)
    if not api_key:
        print(f"   ❌ {ENV_KEY} non trovata. Puoi impostarla con:")
        print(f"      export {ENV_KEY}='tua_chiave'")
        print(f"   oppure aggiungila al file .env:")
        print(f"      {ENV_KEY}=tua_chiave")
        return {}, 0

    cache = _carica_cache()
    urls_cache = _carica_urls_cache()
    da_verificare = []
    offerta_info = {}
    risultati = {}
    now_ts = datetime.now(timezone.utc).isoformat()
    skippati = 0

    for r in offerte:
        if skippati < offset:
            skippati += 1
            continue
        if r.get("_mia"):
            continue
        cod = r.get("cod_offerta", "")
        if not cod:
            continue
        if len(risultati) + len(da_verificare) >= limite:
            break

        entry = cache.get(cod)
        if entry is not None and entry.get("cod") is not None and entry.get("nome") is not None:
            risultati[cod] = f"{entry['cod']} {entry['nome']}"
            continue

        url = r.get("url_offerta", "")
        dominio = _estrai_dominio(url)
        if not dominio:
            risultati[cod] = f"{NO_CHECK} {NO_CHECK}"
            continue

        nome = r.get("nome_offerta", "")
        offerta_info[cod] = r
        if entry is not None and entry.get("cod") is not None and entry.get("nome") is None:
            da_verificare.append((cod, nome, dominio, True))
        else:
            da_verificare.append((cod, nome, dominio, False))

    if not da_verificare:
        _salva_urls_cache(urls_cache)
        return risultati, 0

    aggiornati = 0
    credito_speso = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuri = {}
        for cod, nome, dominio, solo_nome in da_verificare:
            if solo_nome:
                futuri[executor.submit(_cerca_query_serper, nome, dominio, api_key, exact=False)] = (cod, "nome_only")
            else:
                futuri[executor.submit(_cerca_serper, cod, nome, dominio, api_key)] = (cod, "both")

        for futuro in as_completed(futuri):
            cod, mode = futuri[futuro]
            r = offerta_info[cod]
            if mode == "nome_only":
                stato_nome, url_nome = futuro.result()
                entry = cache.get(cod, {})
                stato_cod = entry.get("cod", NO_CHECK)
                url_cod = entry.get("url_cod")
                risultati[cod] = f"{stato_cod} {stato_nome}"
                cache[cod] = {"cod": stato_cod, "url_cod": url_cod, "nome": stato_nome, "url_nome": url_nome, "ts": now_ts}
                credito_speso += 1
            else:
                stato_cod, url_cod, stato_nome, url_nome, chiamate = futuro.result()
                risultati[cod] = f"{stato_cod} {stato_nome}"
                cache[cod] = {"cod": stato_cod, "url_cod": url_cod, "nome": stato_nome, "url_nome": url_nome, "ts": now_ts}
                credito_speso += chiamate

            urls_cache[cod] = {
                "cod": stato_cod,
                "url_cod": url_cod,
                "nome": stato_nome,
                "url_nome": url_nome,
                "nome_offerta": r.get("nome_offerta", ""),
                "venditore": r.get("nome_venditore") or r.get("venditore", ""),
                "ts": now_ts,
            }
            aggiornati += 1
            if aggiornati % 10 == 0:
                _salva_cache(cache)
                _salva_urls_cache(urls_cache)

    _salva_cache(cache)
    _salva_urls_cache(urls_cache)
    return risultati, credito_speso
