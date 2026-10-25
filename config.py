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
        "03": "trioraria",
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
        "05": "euro_una_tantum",
        "06": "percentuale",
    },
    "tipologia_att_contr": {
        "01": "nuova",
        "02": "cambio",
        "03": "voltura",
        "04": "subentro",
        "99": "altro",
    },
}

# Mappatura unità di misura specifica per il gas.
# Nel XML gas: 04 = €/Smc (nell'elettrico 04 = percentuale).
MAPPING_GAS = {
    "unita_misura": {
        "01": "euro_anno",
        "04": "euro_smc",
        "05": "euro_una_tantum",
        "06": "percentuale",
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

# Ambiti di distribuzione gas (a1..a6) per regione ISTAT.
# a1 NORD-OCCIDENTALE, a2 NORD-ORIENTALE, a3 CENTRALE,
# a4 SUD-ORIENTALE, a5 SUD-OCCIDENTALE, a6 MERIDIONALE.
REGIONI_AMBITO_GAS = {
    "01": "a1", "02": "a1", "03": "a1", "07": "a1",
    "04": "a2", "05": "a2", "06": "a2", "08": "a2",
    "09": "a3", "10": "a3", "11": "a3", "12": "a3",
    "13": "a4", "14": "a4", "16": "a4", "17": "a4",
    "15": "a5", "18": "a5",
    "19": "a6", "20": "a6",
}

# Profili di consumo standard (percentuali per fascia)
# "tutte" = nessun filtro, profilo monoraria per il calcolo
PROFILO_CONSUMO = {
    "tutte": {"unica": 1.0},
    "monoraria": {"unica": 1.0},
    "bioraria": {"F1": 0.50, "F2": 0.50},
    "trioraria": {"F1": 0.33, "F2": 0.31, "F3": 0.36},
}

# Mappatura fasce componenti → nomi canonici
# 01/02/03 = F1/F2/F3 standard; 07/08 = codici non-standard usati da alcuni
# venditori (sempre coppie 07+08 sul componente energia, 07 > 08 come prezzo):
# inferenza 07→F1 (fascia di punta), 08→F2 (fascia fuori punta).
FASCIA_MAP = {
    "01": "F1",
    "02": "F2",
    "03": "F3",
    "07": "F1",
    "08": "F2",
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
MY_OFFER_GAS_STUB_PATH = DATA_DIR / "my_offer_gas_stub.json"
MY_OFFER_GAS_PATH = DATA_DIR / "my_offer_gas.json"

# Campi obbligatori per my_offer.json
MY_OFFER_REQUIRED = {"venditore", "nome_offerta", "tipo", "tariffa", "prezzo_energia", "quota_fissa"}

def carica_mia_offerta(commodity: str = "elettrico") -> Optional[Dict[str, Any]]:
    """Carica la mia offerta da my_offer.json (o my_offer_gas.json)."""
    if commodity == "gas":
        path, stub = MY_OFFER_GAS_PATH, MY_OFFER_GAS_STUB_PATH
    else:
        path, stub = MY_OFFER_PATH, MY_OFFER_STUB_PATH

    if not path.exists():
        if stub.exists():
            print(f"⚠️  Crea {path.name} copiando da {stub.name} e inserisci i tuoi dati.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Filtra chiavi _note
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        # Verifica campi obbligatori
        mancanti = MY_OFFER_REQUIRED - set(data.keys())
        if mancanti:
            print(f"⚠️  {path.name}: campi mancanti: {', '.join(sorted(mancanti))}")
            print(f"   Usa {stub.name} come modello.")
            return None
        # Default per opzionali
        data.setdefault("quota_potenza", 0.0)
        data.setdefault("altri_costi", 0.0)
        data.setdefault("sconti", 0.0)
        return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Errore lettura {path.name}: {e}")
        return None
