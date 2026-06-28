"""Configurazione e costanti del comparatore offerte."""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Directory base
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"

# URL base del portale
BASE_URL = "https://www.ilportaleofferte.it/portaleOfferte"

# URL file open data (pattern: anno_mese come YYYY_M)
# Esempio: /resources/opendata/csv/offerteML/2026_6/PO_Offerte_E_MLIBERO_20260626.xml
OPENDATA_URLS = {
    "elettrico": {
        "offerte_xml": BASE_URL + "/resources/opendata/csv/offerteML/{anno}_{mese}/PO_Offerte_E_MLIBERO_{data}.xml",
        "parametri_csv": BASE_URL + "/resources/opendata/csv/parametriML/{anno}_{mese}/PO_Parametri_Mercato_Libero_E_{data}.csv",
    },
    "gas": {
        "offerte_xml": BASE_URL + "/resources/opendata/csv/offerteML/{anno}_{mese}/PO_Offerte_G_MLIBERO_{data}.xml",
        "parametri_csv": BASE_URL + "/resources/opendata/csv/parametriML/{anno}_{mese}/PO_Parametri_Mercato_Libero_G_{data}.csv",
    },
}

# Prezzi storici (PUN, PSV, ecc.)
PREZZI_STORICI_URL = BASE_URL + "/resources/cms/documents/fe9833ce8870cb2e146cce5cafe3e7df.csv"

# Mappatura codici XML
MAPPING = {
    "tipo_cliente": {
        "01": "domestico",
        "02": "altri_usi",
    },
    "tipo_offerta": {
        "01": "fisso",
        "02": "variabile",
    },
    "tipologia_fasce": {
        "01": "monoraria",
        "02": "bioraria",
        "03": "trifaria",
    },
    "limitante": {
        "01": True,   # limitante / trappola
        "02": False,  # non limitante
    },
    "unita_misura": {
        "01": "euro_anno",
        "02": "euro_kw_anno",
        "03": "euro_kwh",
        "04": "percentuale",
    },
    "tipologia_att_contr": {
        "01": "nuova",
        "02": "cambio",
        "03": "voltura",
        "04": "subentro",
        "99": "altro",
    },
}

# Codici ISTAT regioni (da ZoneOfferta/REGIONE nell'XML)
REGIONI_MAP = {
    "01": "piemonte",
    "02": "valle d'aosta",
    "03": "lombardia",
    "04": "trentino-alto adige",
    "05": "veneto",
    "06": "friuli-venezia giulia",
    "07": "liguria",
    "08": "emilia-romagna",
    "09": "toscana",
    "10": "umbria",
    "11": "marche",
    "12": "lazio",
    "13": "abruzzo",
    "14": "molise",
    "15": "campania",
    "16": "puglia",
    "17": "basilicata",
    "18": "calabria",
    "19": "sicilia",
    "20": "sardegna",
}

# Profili di consumo standard (percentuali per fascia)
# "tutte" = nessun filtro, profilo monoraria per il calcolo
PROFILO_CONSUMO = {
    "tutte": {"unica": 1.0},
    "monoraria": {"unica": 1.0},
    "bioraria": {"F1": 0.50, "F2": 0.50},
    "trifaria": {"F1": 0.33, "F2": 0.31, "F3": 0.36},
}

# Mappatura fasce componenti → nomi canonici
FASCIA_MAP = {
    "01": "F1",
    "02": "F2",
    "03": "F3",
}

# Parole chiave default per escludere offerte "trappola" nelle condizioni
BLACKLIST_CONDIZIONI_DEFAULT = [
    "socio",
    "pannello",
    "fotovoltaic*",
    "obbligatorio",
    "sottoscrivere",
    "convenzione",
    "circolo",
    "iscritto",
    "membership",
    "abbonamento",
    "vincolato",
    "vincolo",
    "penale",
    "penali",
    "recesso anticipato",
    "indennizzo",
    "spese di disattivazione",
    "valle d'aosta",
    "alto adige",
    "maggior tutela",
    "polizza rca",
    "smart tv",
    "b-bike",
    "universo casa",
    "tim energia",
    "bozza",
    "gia' sottoscritto",
    "già sottoscritto",
]

# Parametri di sistema per profilo: pattern di ricerca nel CSV parametri
# Chiave: (profilo_regex, tipo_quota_regex) → usiamo match sulla descrizione
# tipo_quota: "quota energia", "quota fissa", "quota potenza"
PROFILI_PARAMETRI = {
    "domestico_residente": {
        "descrizione_match": ["DOMESTICO RESIDENTE", "DOMESTICO"],
        "escludi": ["NON DOMESTICO", "NON RESIDENTE"],
    },
    "domestico_non_residente": {
        "descrizione_match": ["DOMESTICO NON RESIDENTE"],
        "escludi": [],
    },
    "non_domestico": {
        "descrizione_match": ["NON DOMESTICO"],
        "escludi": [],
    },
}

# --- Mia offerta (confronto) ---
MY_OFFER_STUB_PATH = DATA_DIR / "my_offer_stub.json"
MY_OFFER_PATH = DATA_DIR / "my_offer.json"

# Campi obbligatori per my_offer.json
MY_OFFER_REQUIRED = {"venditore", "nome_offerta", "tipo", "tariffa", "prezzo_energia", "quota_fissa"}

def carica_mia_offerta() -> Optional[Dict[str, Any]]:
    """Carica la mia offerta da my_offer.json. Ritorna None se non esiste."""
    if not MY_OFFER_PATH.exists():
        if MY_OFFER_STUB_PATH.exists():
            print(f"⚠️  Crea data/my_offer.json copiando da data/my_offer_stub.json e inserisci i tuoi dati.")
        return None
    try:
        with open(MY_OFFER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Filtra chiavi _note
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        # Verifica campi obbligatori
        mancanti = MY_OFFER_REQUIRED - set(data.keys())
        if mancanti:
            print(f"⚠️  my_offer.json: campi mancanti: {', '.join(sorted(mancanti))}")
            print(f"   Usa data/my_offer_stub.json come modello.")
            return None
        # Default per opzionali
        data.setdefault("quota_potenza", 0.0)
        data.setdefault("sconti", 0.0)
        return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Errore lettura my_offer.json: {e}")
        return None
