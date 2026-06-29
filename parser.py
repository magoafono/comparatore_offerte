"""Parsing dei file XML offerte e CSV parametri/prezzi."""

import csv
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

from config import MAPPING, FASCIA_MAP


@dataclass
class IntervalloPrezzo:
    fascia: str
    prezzo: float
    unita_misura: str
    consumo_da: Optional[int] = None
    consumo_a: Optional[int] = None


@dataclass
class ComponenteImpresa:
    nome: str
    descrizione: str
    tipologia: str
    macroarea: str
    prezzi: List[IntervalloPrezzo] = field(default_factory=list)


@dataclass
class CondizioneContrattuale:
    tipologia: str
    descrizione: str
    limitante: bool


@dataclass
class Sconto:
    nome: str
    descrizione: str
    validita: str
    iva_sconto: str
    condizione_applicazione: str
    durata_mesi: int = 0
    prezzi: List[IntervalloPrezzo] = field(default_factory=list)


@dataclass
class Offerta:
    piva_utente: str
    cod_offerta: str
    nome_offerta: str
    descrizione: str
    tipo_cliente: str  # domestico / altri_usi
    tipo_offerta: str  # fisso / variabile
    tipologia_fasce: str  # monoraria / bioraria / trioraria
    durata: str
    garanzie: str
    modalita_attivazione: str
    telefono: str
    url_sito: str
    url_offerta: str
    data_inizio: str
    data_fine: str
    consumo_min: Optional[int]
    consumo_max: Optional[int]
    modalita_pagamento: str
    tipo_dispacciamento: str
    nome_dispacciamento: str
    regioni: List[str] = field(default_factory=list)
    tipologie_att_contr: List[str] = field(default_factory=list)
    componenti: List[ComponenteImpresa] = field(default_factory=list)
    condizioni: List[CondizioneContrattuale] = field(default_factory=list)
    sconti: List[Sconto] = field(default_factory=list)


def _text(elem, tag, default=""):
    child = elem.find(tag)
    return child.text.strip() if child is not None and child.text else default


def _int_text(elem, tag, default=None):
    val = _text(elem, tag, "")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def parse_xml_offerte(xml_path: Path) -> List[Offerta]:
    """Parsa il file XML delle offerte usando iterparse per gestire file grandi."""
    offerte = []
    ns = {"ns": "http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01"}

    context = ET.iterparse(str(xml_path), events=("start", "end"))
    context = iter(context)
    event, root = next(context)

    current_offerta = None
    current_componente = None
    current_condizione = None
    current_sconto = None

    for event, elem in context:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if event == "start":
            if tag == "offerta":
                current_offerta = {
                    "componenti": [],
                    "condizioni": [],
                    "sconti": [],
                    "regioni": [],
                    "tipologie_att_contr": [],
                }
            elif tag == "ComponenteImpresa":
                current_componente = {
                    "prezzi": [],
                }
            elif tag == "CondizioniContrattuali":
                current_condizione = {}
            elif tag == "Sconto":
                current_sconto = {
                    "prezzi": [],
                    "durata_mesi": 0,
                }

        elif event == "end":
            if tag == "offerta":
                offerte.append(Offerta(
                    piva_utente=current_offerta.get("piva_utente", ""),
                    cod_offerta=current_offerta.get("cod_offerta", ""),
                    nome_offerta=current_offerta.get("nome_offerta", ""),
                    descrizione=current_offerta.get("descrizione", ""),
                    tipo_cliente=current_offerta.get("tipo_cliente", ""),
                    tipo_offerta=current_offerta.get("tipo_offerta", ""),
                    tipologia_fasce=current_offerta.get("tipologia_fasce", ""),
                    durata=current_offerta.get("durata", ""),
                    garanzie=current_offerta.get("garanzie", ""),
                    modalita_attivazione=current_offerta.get("modalita_attivazione", ""),
                    telefono=current_offerta.get("telefono", ""),
                    url_sito=current_offerta.get("url_sito", ""),
                    url_offerta=current_offerta.get("url_offerta", ""),
                    data_inizio=current_offerta.get("data_inizio", ""),
                    data_fine=current_offerta.get("data_fine", ""),
                    consumo_min=current_offerta.get("consumo_min"),
                    consumo_max=current_offerta.get("consumo_max"),
                    modalita_pagamento=current_offerta.get("modalita_pagamento", ""),
                    tipo_dispacciamento=current_offerta.get("tipo_dispacciamento", ""),
                    nome_dispacciamento=current_offerta.get("nome_dispacciamento", ""),
                    componenti=current_offerta.get("componenti", []),
                    condizioni=current_offerta.get("condizioni", []),
                    sconti=current_offerta.get("sconti", []),
                    regioni=current_offerta.get("regioni", []),
                    tipologie_att_contr=current_offerta.get("tipologie_att_contr", []),
                ))
                elem.clear()
                root.clear()
                current_offerta = None

            elif tag == "ComponenteImpresa":
                if current_offerta is not None and current_componente is not None:
                    current_offerta["componenti"].append(ComponenteImpresa(
                        nome=current_componente.get("nome", ""),
                        descrizione=current_componente.get("descrizione", ""),
                        tipologia=current_componente.get("tipologia", ""),
                        macroarea=current_componente.get("macroarea", ""),
                        prezzi=current_componente.get("prezzi", []),
                    ))
                current_componente = None

            elif tag == "CondizioniContrattuali":
                if current_offerta is not None and current_condizione is not None:
                    limitante_raw = current_condizione.get("limitante", "02")
                    current_offerta["condizioni"].append(CondizioneContrattuale(
                        tipologia=current_condizione.get("tipologia", ""),
                        descrizione=current_condizione.get("descrizione", ""),
                        limitante=MAPPING["limitante"].get(limitante_raw, False),
                    ))
                current_condizione = None

            elif tag == "Sconto":
                if current_offerta is not None and current_sconto is not None:
                    current_offerta["sconti"].append(Sconto(
                        nome=current_sconto.get("nome", ""),
                        descrizione=current_sconto.get("descrizione", ""),
                        validita=current_sconto.get("validita", ""),
                        iva_sconto=current_sconto.get("iva_sconto", ""),
                        condizione_applicazione=current_sconto.get("condizione_applicazione", ""),
                        durata_mesi=current_sconto.get("durata_mesi", 0),
                        prezzi=current_sconto.get("prezzi", []),
                    ))
                current_sconto = None

            # Estrazione campi Sconto
            elif current_sconto is not None:
                if tag == "NOME":
                    current_sconto["nome"] = elem.text.strip() if elem.text else ""
                elif tag == "DESCRIZIONE":
                    current_sconto["descrizione"] = elem.text.strip() if elem.text else ""
                elif tag == "VALIDITA":
                    current_sconto["validita"] = elem.text.strip() if elem.text else ""
                elif tag == "DURATA" and current_sconto is not None:
                    current_sconto["durata_mesi"] = int(elem.text.strip()) if elem.text and elem.text.strip().isdigit() else 0
                elif tag == "IVA_SCONTO":
                    current_sconto["iva_sconto"] = elem.text.strip() if elem.text else ""
                elif tag == "CONDIZIONE_APPLICAZIONE":
                    current_sconto["condizione_applicazione"] = elem.text.strip() if elem.text else ""
                elif tag == "PREZZO":
                    current_sconto["prezzo"] = elem.text.strip() if elem.text else "0"
                elif tag == "UNITA_MISURA":
                    current_sconto["unita_misura"] = MAPPING["unita_misura"].get(elem.text.strip(), "")
                elif tag == "PrezziSconto":
                    if "prezzo" in current_sconto and "unita_misura" in current_sconto:
                        try:
                            prezzo_val = float(current_sconto["prezzo"].replace(",", "."))
                        except ValueError:
                            prezzo_val = 0.0
                        current_sconto["prezzi"].append(IntervalloPrezzo(
                            fascia="unica",
                            prezzo=prezzo_val,
                            unita_misura=current_sconto["unita_misura"],
                        ))
                    for k in ("prezzo", "unita_misura"):
                        current_sconto.pop(k, None)

            # Estrazione campi offerta
            elif current_offerta is not None and current_componente is None and current_condizione is None and current_sconto is None:
                if tag == "PIVA_UTENTE":
                    current_offerta["piva_utente"] = elem.text.strip() if elem.text else ""
                elif tag == "COD_OFFERTA":
                    current_offerta["cod_offerta"] = elem.text.strip() if elem.text else ""
                elif tag == "NOME_OFFERTA":
                    current_offerta["nome_offerta"] = elem.text.strip() if elem.text else ""
                elif tag == "DESCRIZIONE" and "descrizione" not in current_offerta:
                    current_offerta["descrizione"] = elem.text.strip() if elem.text else ""
                elif tag == "TIPO_CLIENTE":
                    current_offerta["tipo_cliente"] = MAPPING["tipo_cliente"].get(elem.text.strip(), "")
                elif tag == "TIPO_OFFERTA":
                    current_offerta["tipo_offerta"] = MAPPING["tipo_offerta"].get(elem.text.strip(), "")
                elif tag == "TIPOLOGIA_FASCE":
                    current_offerta["tipologia_fasce"] = MAPPING["tipologia_fasce"].get(elem.text.strip(), "")
                elif tag == "DURATA":
                    current_offerta["durata"] = elem.text.strip() if elem.text else ""
                elif tag == "GARANZIE":
                    current_offerta["garanzie"] = elem.text.strip() if elem.text else ""
                elif tag == "MODALITA":
                    current_offerta["modalita_attivazione"] = elem.text.strip() if elem.text else ""
                elif tag == "TELEFONO":
                    current_offerta["telefono"] = elem.text.strip() if elem.text else ""
                elif tag == "URL_SITO_VENDITORE":
                    current_offerta["url_sito"] = elem.text.strip() if elem.text else ""
                elif tag == "URL_OFFERTA":
                    current_offerta["url_offerta"] = elem.text.strip() if elem.text else ""
                elif tag == "DATA_INIZIO":
                    current_offerta["data_inizio"] = elem.text.strip() if elem.text else ""
                elif tag == "DATA_FINE":
                    current_offerta["data_fine"] = elem.text.strip() if elem.text else ""
                elif tag == "CONSUMO_MIN":
                    current_offerta["consumo_min"] = _int_text(elem, "CONSUMO_MIN")
                elif tag == "CONSUMO_MAX":
                    current_offerta["consumo_max"] = _int_text(elem, "CONSUMO_MAX")
                elif tag == "MODALITA_PAGAMENTO":
                    current_offerta["modalita_pagamento"] = elem.text.strip() if elem.text else ""
                elif tag == "TIPO_DISPACCIAMENTO":
                    current_offerta["tipo_dispacciamento"] = elem.text.strip() if elem.text else ""
                elif tag == "TIPOLOGIA_ATT_CONTR":
                    codice = elem.text.strip() if elem.text else ""
                    decoded = MAPPING["tipologia_att_contr"].get(codice, "")
                    if decoded:
                        current_offerta["tipologie_att_contr"].append(decoded)
                elif tag == "NOME" and current_componente is None:
                    current_offerta["nome_dispacciamento"] = elem.text.strip() if elem.text else ""
                elif tag == "REGIONE":
                    codice = elem.text.strip() if elem.text else ""
                    if codice:
                        current_offerta["regioni"].append(codice)
                elif tag == "PROVINCIA":
                    codice = elem.text.strip() if elem.text else ""
                    if codice:
                        # Segna con prefisso P_ per distinguerle dalle regioni
                        current_offerta["regioni"].append(f"P_{codice}")

            # Estrazione campi ComponenteImpresa
            elif current_componente is not None:
                if tag == "NOME":
                    current_componente["nome"] = elem.text.strip() if elem.text else ""
                elif tag == "DESCRIZIONE":
                    current_componente["descrizione"] = elem.text.strip() if elem.text else ""
                elif tag == "TIPOLOGIA":
                    current_componente["tipologia"] = elem.text.strip() if elem.text else ""
                elif tag == "MACROAREA":
                    current_componente["macroarea"] = elem.text.strip() if elem.text else ""
                elif tag == "FASCIA_COMPONENTE":
                    current_componente["fascia"] = elem.text.strip() if elem.text else ""
                elif tag == "PREZZO":
                    current_componente["prezzo"] = elem.text.strip() if elem.text else "0"
                elif tag == "UNITA_MISURA":
                    current_componente["unita_misura"] = MAPPING["unita_misura"].get(elem.text.strip(), "")
                elif tag == "CONSUMO_DA":
                    try:
                        current_componente["consumo_da"] = int(elem.text.strip())
                    except (ValueError, TypeError):
                        pass
                elif tag == "CONSUMO_A":
                    try:
                        current_componente["consumo_a"] = int(elem.text.strip())
                    except (ValueError, TypeError):
                        pass
                elif tag == "IntervalloPrezzi":
                    fascia = current_componente.get("fascia", "unica")
                    if "prezzo" in current_componente and "unita_misura" in current_componente:
                        try:
                            prezzo_val = float(current_componente["prezzo"].replace(",", "."))
                        except ValueError:
                            prezzo_val = 0.0
                        current_componente["prezzi"].append(IntervalloPrezzo(
                            fascia=FASCIA_MAP.get(fascia, fascia),
                            prezzo=prezzo_val,
                            unita_misura=current_componente["unita_misura"],
                            consumo_da=current_componente.get("consumo_da"),
                            consumo_a=current_componente.get("consumo_a"),
                        ))
                    for k in ("fascia", "prezzo", "unita_misura", "consumo_da", "consumo_a"):
                        current_componente.pop(k, None)

            # Estrazione campi CondizioniContrattuali
            elif current_condizione is not None:
                if tag == "TIPOLOGIA_CONDIZIONE":
                    current_condizione["tipologia"] = elem.text.strip() if elem.text else ""
                elif tag == "DESCRIZIONE":
                    current_condizione["descrizione"] = elem.text.strip() if elem.text else ""
                elif tag == "LIMITANTE":
                    current_condizione["limitante"] = elem.text.strip() if elem.text else "02"

            elem.clear()

    return offerte


def parse_csv_parametri(csv_path: Path) -> Dict[str, float]:
    """Parsa il CSV dei parametri di sistema (nome_parametro, valore, descrizione)."""
    parametri = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 2:
                nome = row[0].strip()
                valore_str = row[1].strip().replace(",", ".")
                try:
                    parametri[nome] = float(valore_str)
                except ValueError:
                    continue
    return parametri


def parse_csv_prezzi(prezzi_path: Path) -> Dict[str, float]:
    """
    Parsa il CSV dei prezzi storici.
    Ritorna un dizionario con l'ultimo valore disponibile per ogni indicatore.
    """
    ultimo_pun = None
    # Prova encoding utf-8, fallback su latin-1 (il CSV del portale usa € in cp1252)
    for enc in ("utf-8", "latin-1"):
        try:
            with open(prezzi_path, "r", encoding=enc) as f:
                reader = csv.reader(f, delimiter=";")
                header = next(reader, None)
                if not header:
                    return {}
                for row in reader:
                    if len(row) >= 2:
                        anno_mese = row[0].strip()
                        pun_str = row[1].strip().replace(",", ".")
                        try:
                            ultimo_pun = float(pun_str)
                        except ValueError:
                            continue
            break
        except UnicodeDecodeError:
            continue
    return {"PUN": ultimo_pun} if ultimo_pun is not None else {}
