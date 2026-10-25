"""Stima e filtro delle penali di recesso dalle condizioni XML.

L'XML ARERA spesso riporta solo "Oneri di Recesso Anticipato" senza importo.
La stima usa il testo disponibile e, se presente, il file locale
`data/penali_manuali.json` per integrare i dati letti dalla CTE.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from config import DATA_DIR
from parser import Offerta

OVERRIDES_PATH = DATA_DIR / "penali_manuali.json"

_AMT = re.compile(r"(\d+(?:[.,]\d+)?)\s*€(?!\s*(?:/|per)\s*kwh)", re.I)
_NOPEN = re.compile(
    r"non applica alcun onere|non ne prevede|non sono previsti oneri|"
    r"nessuna penale|senza oneri|non prevede alcun onere",
    re.I,
)
_MONETARY = re.compile(
    r"corrispettivo|indennizzo|penale|onere|addebit|riserva di|perdita economica",
    re.I,
)
_PER_MESE = re.compile(
    r"per ogni mese|per nr\.? di mesi|per ciascun mese|mensilità residue|€\s*per\s*mese",
    re.I,
)
_MASSIMO = re.compile(r"massimo|non potrà superare|fino a|cap", re.I)
_DUR_MESI = re.compile(r"(\d+)\s*mesi", re.I)
_DUR_ANNI = re.compile(r"(\d+)\s*anni", re.I)
_DUR_NOME = re.compile(r"\b(12|24|36|48|60|72|84|96|108|120)\b")
_OVERRIDES_CACHE: Optional[dict] = None


@dataclass
class PenaleInfo:
    tipo: str  # "nessuna", "cap", "mensile", "sconosciuta"
    importo: Optional[float] = None  # cap in € oppure rate in €/mese
    durata_mesi: Optional[int] = None
    descrizione: str = ""
    fonte: str = "xml"  # xml / override


def _durata_mesi(off: Offerta) -> Optional[int]:
    if off.durata:
        try:
            durata = int(off.durata)
        except ValueError:
            durata = 0
        if durata > 0:
            return durata

    testo = f"{off.nome_offerta} {off.descrizione}"
    m = _DUR_MESI.search(testo)
    if m:
        return int(m.group(1))
    m = _DUR_ANNI.search(testo)
    if m:
        return int(m.group(1)) * 12
    if "dieci anni" in testo.lower():
        return 120
    m = _DUR_NOME.search(off.nome_offerta)
    if m:
        return int(m.group(1))
    return None


def _carica_overrides() -> dict:
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None:
        return _OVERRIDES_CACHE
    if not OVERRIDES_PATH.exists():
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE
    try:
        data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE
    if not isinstance(data, dict):
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE
    _OVERRIDES_CACHE = {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}
    return _OVERRIDES_CACHE


def _da_override(off: Offerta, overrides: dict) -> Optional[PenaleInfo]:
    entry = overrides.get(off.cod_offerta) or overrides.get(off.nome_offerta)
    if not entry:
        return None
    tipo = entry.get("tipo", "sconosciuta")
    if tipo == "nessuna":
        return PenaleInfo("nessuna", 0.0, _durata_mesi(off), "override manuale", "override")
    if tipo == "cap":
        importo = entry.get("importo")
        if importo is not None:
            return PenaleInfo("cap", float(importo), _durata_mesi(off), "override manuale", "override")
    if tipo == "mensile":
        rate = entry.get("rate")
        if rate is not None:
            durata = entry.get("durata_mesi") or _durata_mesi(off)
            return PenaleInfo("mensile", float(rate), durata, "override manuale", "override")
    return None


def stima_penale(off: Offerta) -> PenaleInfo:
    """Stima la penale di recesso di un'offerta."""
    overrides = _carica_overrides()
    override = _da_override(off, overrides)
    if override is not None:
        return override

    c05 = [c for c in off.condizioni if c.tipologia == "05"]
    if not c05:
        return PenaleInfo("nessuna", 0.0, _durata_mesi(off), "", "xml")

    testo = " ".join((c.descrizione or "") for c in c05).strip()
    durata = _durata_mesi(off)
    importi = [float(m.group(1).replace(",", ".")) for m in _AMT.finditer(testo)]

    if importi and not _MASSIMO.search(testo) and _PER_MESE.search(testo):
        return PenaleInfo("mensile", max(importi), durata, testo, "xml")
    if importi:
        return PenaleInfo("cap", max(importi), durata, testo, "xml")
    if _NOPEN.search(testo):
        return PenaleInfo("nessuna", 0.0, durata, testo, "xml")
    if _MONETARY.search(testo):
        return PenaleInfo("sconosciuta", None, durata, testo, "xml")
    return PenaleInfo("sconosciuta", None, durata, testo, "xml")


def penale_max_12m(info: PenaleInfo) -> Optional[float]:
    """Penale massima stimata uscendo dopo 12 mesi. None se non quantificabile."""
    if info.tipo == "nessuna":
        return 0.0
    if info.tipo == "cap":
        return info.importo
    if info.tipo == "mensile" and info.importo is not None and info.durata_mesi:
        return info.importo * max(0, info.durata_mesi - 12)
    return None


def filtra_penali(
    offerte: List[Offerta],
    mese_max: Optional[float] = None,
    max_12m: Optional[float] = None,
) -> Tuple[List[Offerta], List[Offerta], List[Offerta]]:
    """
    Filtra le offerte in base alle soglie penale.

    Ritorna (tenute, sopra_soglia, sconosciute).
    - mese_max: soglia €/mese residuo (si applica alle penali mensili)
    - max_12m: soglia penale massima a 12 mesi (cap o mensile × mesi residui)
    Le penali non quantificabili vengono messe in `sconosciute`.
    """
    tenute: List[Offerta] = []
    sopra: List[Offerta] = []
    sconosciute: List[Offerta] = []

    for o in offerte:
        info = stima_penale(o)
        if info.tipo == "sconosciuta":
            sconosciute.append(o)
            continue

        ok = True
        if mese_max is not None and info.tipo == "mensile":
            if info.importo is None or info.importo > mese_max:
                ok = False
        if max_12m is not None:
            massimo = penale_max_12m(info)
            if massimo is None:
                sconosciute.append(o)
                continue
            if massimo > max_12m:
                ok = False

        if ok:
            tenute.append(o)
        else:
            sopra.append(o)

    return tenute, sopra, sconosciute
