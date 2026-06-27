"""Mappatura PIVA venditore → nome commerciale."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter

from config import DATA_DIR
from parser import Offerta


DOMAIN_TO_VENDOR = {
    "a2a": "A2A", "enel": "Enel Energia", "e-on": "E.ON", "eon": "E.ON",
    "dolomitienergia": "Dolomiti Energia", "dolomiti": "Dolomiti Energia",
    "cvaenergie": "CVA", "cva": "CVA",
    "irenenergia": "Iren", "iren": "Iren",
    "heracomm": "Hera Comm", "hera": "Hera",
    "acsmaenergia": "Acsma Energia", "acsma": "Acsma Energia",
    "estraspa": "Estra", "novaenergia": "Nova Energia",
    "nova": "Nova Energia", "selexia": "Selexia",
    "wekiwi": "Wekiwi", "sorgenia": "Sorgenia",
    "engie": "Engie", "edisonenergia": "Edison Energia", "edison": "Edison",
    "neonovaenergia": "NeoNova", "next": "Next Energy",
    "exergia": "Exergia", "martelius": "Martelius",
    "colsamenergie": "Colsam Energie", "coop": "Coop",
    "italiangas": "Italian Gas", "italgas": "Italgas",
    "metanonord": "Metano Nord", "sgrservizi": "SGR Servizi",
    "actonenergia": "Acton Energia", "apienergia": "Api Energia", "api": "Api Energia",
    "iberdrola": "Iberdrola", "3zinnen": "3 Zinnen Energy",
    "lorolucegas": "Loro LuceGas", "passuellofratelli": "Passuello F.lli",
    "greenplanner": "Green Planner", "tes": "TES",
    "omega": "Omega", "primilucegas": "Primiluce Gas",
    "energieoltre": "Energie Oltre", "lumenergia": "LumEnergia", "lumsa": "Lumsa",
    "con-plast": "ConPlast", "europaenergia": "Europa Energia",
    "segnali": "Segnali", "ardian": "Ardian", "eco-forn": "EcoForn",
    "senec": "Senec", "magigas": "MagiGas",
    "synergas": "Synergas", "trentino": "Trentino Energia",
    "primoris": "Primoris", "lucegas": "Luce Gas",
    "ceo": "CEO Energy", "inex": "Inex",
    "semplice": "Semplice", "europaenergie": "Europa Energie",
    "sen.ec": "Sen.ec", "negozio": "Negozio Energetico",
    "gsa": "GSA", "genfit": "Genfit",
    "axpo": "Axpo Italia", "axpoitalia": "Axpo Italia",
    "etruria": "Etruria Energia", "e-distribuzione": "E-Distribuzione",
    "publiconnessioni": "Publi Connessioni", "sistemi": "Sistemi Energetici",
    "revit": "Revit", "terranuova": "Terra Nuova",
    "savio": "Savio", "win": "Win Energia",
    "telos": "Telos", "quantum": "Quantum",
    "nexum": "Nexum", "spigas": "SPI Gas",
    "energit": "Energit", "sel": "SEL",
    "novasol": "Novasol", "energia-total": "Energia Total",
    "totalenergies": "TotalEnergies", "total": "TotalEnergies",
    "rnergia": "Rnergia", "octopus": "Octopus Energy",
    "illumia": "Illumia", "axopower": "Axopower",
    "enna": "Ena Energia", "tialtri": "Tialtri",
    "egea": "Egea Group", "vazzoler": "Vazzoler",
}


def _domain_to_vendor_name(url: str):
    if not url:
        return None
    try:
        if not url.startswith("http"):
            url = f"http://{url}"
        parsed = urlparse(url)
        domain = (parsed.netloc or parsed.path).lower()
        domain = re.sub(r"^www\.", "", domain)
        main_part = domain.split(".")[0]
        full_domain = f"{main_part}.{domain.split('.')[1]}" if len(domain.split(".")) > 1 else main_part
        for key, name in DOMAIN_TO_VENDOR.items():
            if key in domain or key in main_part:
                return name
        name = main_part.replace("-", " ").replace("_", " ").strip()
        if name and len(name) > 2 and not name.isdigit():
            return " ".join(w.capitalize() for w in name.split())
    except Exception:
        pass
    return None


def _offer_name_to_vendor_name(offer_names: list):
    if not offer_names:
        return None
    first_words = []
    for name in offer_names:
        words = name.strip().split()
        if words:
            first_words.append(words[0].upper())
    if first_words:
        most_common = Counter(first_words).most_common(1)[0][0]
        name = most_common.capitalize()
        if 3 <= len(name) <= 20:
            return name
    return None


def build_vendor_map(offerte: list):
    """Costruisce mappa PIVA → nome commerciale, con cache su JSON."""
    cache_path = DATA_DIR / "venditori.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    vend_data = {}
    for o in offerte:
        p = o.piva_utente
        if p not in vend_data:
            vend_data[p] = {"urls": set(), "nomi": []}
        if o.url_sito:
            vend_data[p]["urls"].add(o.url_sito)
        vend_data[p]["nomi"].append(o.nome_offerta)

    vendor_map = {}
    for piva, data in vend_data.items():
        name = None
        for url in sorted(data["urls"]):
            name = _domain_to_vendor_name(url)
            if name:
                break
        if not name:
            name = _offer_name_to_vendor_name(data["nomi"])
        if name and len(name) >= 2:
            vendor_map[piva] = name
        else:
            vendor_map[piva] = piva

    try:
        cache_path.write_text(
            json.dumps(vendor_map, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass

    return vendor_map


def get_vendor_name(piva: str, vendor_map: dict) -> str:
    return vendor_map.get(piva, piva)
