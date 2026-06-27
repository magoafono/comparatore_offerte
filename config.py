"""Configurazione e costanti del comparatore offerte."""

import os
from pathlib import Path

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
    "fotovoltaico",
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
