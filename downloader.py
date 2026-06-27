"""Gestione download condizionato dei file open data."""

import os
import re
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

from config import DATA_DIR, OPENDATA_URLS, PREZZI_STORICI_URL, BASE_URL


def _oggi_str():
    return datetime.now().strftime("%Y%m%d")


def _oggi_anno_mese():
    d = datetime.now()
    return d.year, d.month


def _build_url(pattern, data_str):
    anno, mese = _oggi_anno_mese()
    return pattern.format(anno=anno, mese=mese, data=data_str)


def _file_esiste_e_aggiornato(path: Path, data_str: str):
    """Ritorna True se il file esiste e il nome contiene la data odierna."""
    if not path.exists():
        return False
    return data_str in path.name


def scarica(url: str, dest: Path):
    """Scarica url in dest, con stampa del progresso."""
    print(f"  -> Download: {url}")
    try:
        with urlopen(url) as response:
            total = response.headers.get("content-length")
            data = response.read()
        dest.write_bytes(data)
        size_kb = len(data) / 1024
        print(f"  -> Salvato: {dest} ({size_kb:.1f} KB)")
    except HTTPError as e:
        raise RuntimeError(f"Errore download {url}: {e.code} {e.reason}") from e


def _trova_url_reale(base_pattern, data_str):
    """Prova a costruire l'URL usando il mese corrente, altrimenti quello precedente."""
    urls = []
    anno, mese = _oggi_anno_mese()
    urls.append(base_pattern.format(anno=anno, mese=mese, data=data_str))
    # Prova mese precedente (in caso il file del nuovo mese non sia ancora pubblicato)
    if mese == 1:
        urls.append(base_pattern.format(anno=anno - 1, mese=12, data=data_str))
    else:
        urls.append(base_pattern.format(anno=anno, mese=mese - 1, data=data_str))
    for url in urls:
        try:
            with urlopen(url) as resp:
                if resp.status == 200:
                    return url
        except HTTPError:
            continue
    return urls[0]  # fallback al primo


def ottieni_file_open_data(commodity: str, forza_download: bool = False):
    """
    Ritorna i percorsi locali dei file open data (XML offerte, CSV parametri, CSV prezzi).
    Scarica solo se mancanti o se forza_download=True.
    """
    data_str = _oggi_str()
    DATA_DIR.mkdir(exist_ok=True)

    # File offerte XML
    xml_name = f"offerte_{commodity}_MLIBERO_{data_str}.xml"
    xml_path = DATA_DIR / xml_name
    if forza_download or not _file_esiste_e_aggiornato(xml_path, data_str):
        url = _trova_url_reale(OPENDATA_URLS[commodity]["offerte_xml"], data_str)
        scarica(url, xml_path)

    # File parametri CSV
    csv_name = f"parametri_ML_{commodity}_{data_str}.csv"
    csv_path = DATA_DIR / csv_name
    if forza_download or not _file_esiste_e_aggiornato(csv_path, data_str):
        url = _trova_url_reale(OPENDATA_URLS[commodity]["parametri_csv"], data_str)
        scarica(url, csv_path)

    # File prezzi storici
    prezzi_name = f"prezzi_storici_{data_str}.csv"
    prezzi_path = DATA_DIR / prezzi_name
    if forza_download or not prezzi_path.exists():
        scarica(PREZZI_STORICI_URL, prezzi_path)

    return xml_path, csv_path, prezzi_path
