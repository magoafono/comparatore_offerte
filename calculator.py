"""Calcolo della spesa annua stimata per ogni offerta."""

from typing import Dict, List, Optional
from parser import Offerta, IntervalloPrezzo, Sconto
from config import PROFILO_CONSUMO

SCONTI_PROMO_KEYWORDS = [
    "primo anno", "primi 12", "primi mesi",
    "nei primi", "una tantum", "benvenuto",
    "adesione", "attivazione",
]


def _is_sconto_promozionale(sc: Sconto) -> bool:
    if sc.validita == "02":
        return True
    if sc.validita == "01":
        testo = f"{sc.nome} {sc.descrizione}".lower()
        for kw in SCONTI_PROMO_KEYWORDS:
            if kw in testo:
                return True
    return False


def _calcola_confidenza(offerta) -> str:
    for sc in offerta.sconti:
        if sc.validita == "01" and sc.durata_mesi == 0:
            testo = f"{sc.nome} {sc.descrizione}".lower()
            if any(kw in testo for kw in SCONTI_PROMO_KEYWORDS):
                return "red"
    for sc in offerta.sconti:
        if sc.validita == "01" and sc.durata_mesi == 0:
            return "yellow"
    return "green"


def calcola_spesa_annua(
    offerta: Offerta,
    parametri: Dict[str, float],
    consumo_annuo: int,
    potenza: float,
    pun: float,
    residente: bool,
    confronto_portale: bool = False,
    ignora_sconti_promo: bool = False,
) -> Dict[str, float]:
    """
    Calcola la spesa annua stimata per un'offerta.
    Ritorna un dizionario con i dettagli del calcolo.
    """
    profilo_fasce = PROFILO_CONSUMO.get(offerta.tipologia_fasce, PROFILO_CONSUMO["monoraria"])

    # --- 1. Componenti venditore ---
    costo_fisso_venditore = 0.0
    costo_potenza_venditore = 0.0
    costo_energia_venditore = 0.0

    for comp in offerta.componenti:
        has_scaglioni = any(
            intervallo.consumo_da is not None
            for intervallo in comp.prezzi
        )

        if has_scaglioni:
            fasce = {}
            for intervallo in comp.prezzi:
                if intervallo.consumo_da is None:
                    continue
                fascia = intervallo.fascia
                if fascia not in fasce:
                    fasce[fascia] = []
                fasce[fascia].append(intervallo)
            for fascia in fasce:
                fasce[fascia].sort(key=lambda x: x.consumo_da or 0)

            for fascia, entries in fasce.items():
                if fascia in profilo_fasce:
                    kwh_fascia = consumo_annuo * profilo_fasce[fascia]
                elif fascia == "unica" or not fascia:
                    kwh_fascia = consumo_annuo
                else:
                    kwh_fascia = consumo_annuo

                for e in entries:
                    da = e.consumo_da or 0
                    a = e.consumo_a

                    if e.unita_misura == "euro_kwh":
                        if kwh_fascia <= da:
                            continue
                        if a is not None:
                            kwh_tier = min(kwh_fascia, a) - da
                        else:
                            kwh_tier = kwh_fascia - da
                        costo_energia_venditore += e.prezzo * kwh_tier
                    elif e.unita_misura == "euro_anno":
                        if consumo_annuo >= da and (a is None or consumo_annuo <= a):
                            costo_fisso_venditore += e.prezzo
                    elif e.unita_misura == "euro_kw_anno":
                        if consumo_annuo >= da and (a is None or consumo_annuo <= a):
                            costo_potenza_venditore += e.prezzo * potenza
        else:
            for intervallo in comp.prezzi:
                if intervallo.unita_misura == "euro_anno":
                    costo_fisso_venditore += intervallo.prezzo
                elif intervallo.unita_misura == "euro_kw_anno":
                    costo_potenza_venditore += intervallo.prezzo * potenza
                elif intervallo.unita_misura == "euro_kwh":
                    fascia = intervallo.fascia
                    if fascia in profilo_fasce:
                        kwh_fascia = consumo_annuo * profilo_fasce[fascia]
                    elif fascia == "unica" or not fascia:
                        kwh_fascia = consumo_annuo
                    else:
                        kwh_fascia = consumo_annuo
                    costo_energia_venditore += intervallo.prezzo * kwh_fascia

    # --- 2. PUN (solo per offerte a prezzo variabile) ---
    costo_pun = 0.0
    if offerta.tipo_offerta == "variabile":
        # Il PUN si applica all'intero consumo (tutte le fasce)
        costo_pun = pun * consumo_annuo

    spesa_venditore = costo_fisso_venditore + costo_potenza_venditore + costo_energia_venditore + costo_pun

    # --- 2b. Sconti automatici (senza condizioni speciali) ---
    sconti_totali = 0.0
    for sc in offerta.sconti:
        if sc.condizione_applicazione != "00":
            continue
        if ignora_sconti_promo and _is_sconto_promozionale(sc):
            continue
        for p in sc.prezzi:
            if p.unita_misura == "euro_anno":
                sconti_totali += p.prezzo
            elif p.unita_misura == "euro_kwh":
                sconti_totali += p.prezzo * consumo_annuo
    spesa_venditore = max(0.0, spesa_venditore - sconti_totali)

    confidenza = _calcola_confidenza(offerta)

    # --- 3. Oneri di sistema ---
    oneri_fissi, oneri_kwh = _calcola_oneri_sistema(parametri, potenza, residente, confronto_portale=confronto_portale)
    costo_oneri_fissi = oneri_fissi
    costo_oneri_energia = oneri_kwh * consumo_annuo

    spesa_totale = spesa_venditore + costo_oneri_fissi + costo_oneri_energia

    return {
        "spesa_totale": round(spesa_totale, 2),
        "spesa_venditore": round(spesa_venditore, 2),
        "costo_fisso_venditore": round(costo_fisso_venditore, 2),
        "costo_potenza_venditore": round(costo_potenza_venditore, 2),
        "costo_energia_venditore": round(costo_energia_venditore, 2),
        "costo_pun": round(costo_pun, 2),
        "oneri_fissi_sistema": round(costo_oneri_fissi, 2),
        "oneri_energia_sistema": round(costo_oneri_energia, 2),
        "pun_usato": round(pun, 5),
        "confidenza": confidenza,
    }


def _calcola_oneri_sistema(parametri: Dict[str, float], potenza: float, residente: bool, confronto_portale: bool = False):
    """
    Calcola gli oneri di sistema in base al profilo.
    Ritorna (oneri_fissi_annuali, oneri_per_kwh).
    Se confronto_portale=True, esclude sigma1 e sigma2 (costi fissi identici per tutti).
    """
    oneri_fissi = 0.0
    oneri_kwh = 0.0

    # Selettore profilo
    if residente:
        profilo_accisa = "acc_c_r_l" if potenza <= 3 else "acc_c_r_h"
        profilo_arim = "arim_dr"
        profilo_asos = "asos_dr"
        profilo_disp = "dispbt_d"
        profilo_pcv = "pcv_c"
        profilo_uc6s = "uc6s_d"
        profilo_uc6p = "uc6p_d"
    else:
        profilo_accisa = "acc_c_nr"
        profilo_arim = "arim_dnr_v"
        profilo_asos = "asos_dnr_v"
        profilo_disp = "dispbt_d"
        profilo_pcv = "pcv_c"
        profilo_uc6s = "uc6s_d"
        profilo_uc6p = "uc6p_d"
        oneri_fissi += parametri.get("asos_dnr_f", 0.0)
        oneri_fissi += parametri.get("arim_dnr_f", 0.0)

    # --- Accisa ---
    oneri_kwh += parametri.get(profilo_accisa, 0.0)

    # --- Trasmissione ---
    oneri_kwh += parametri.get("tras", 0.0)

    # --- ARIM ---
    oneri_kwh += parametri.get(profilo_arim, 0.0)

    # --- ASOS ---
    oneri_kwh += parametri.get(profilo_asos, 0.0)

    # --- Commercializzazione vendita ---
    oneri_fissi += parametri.get(profilo_pcv, 0.0)

    # --- Dispacciamento fisso ---
    oneri_fissi += parametri.get(profilo_disp, 0.0)

    # --- Misura ---
    oneri_fissi += parametri.get("mis", 0.0)

    # --- Sigma1 (distribuzione fissa) ---
    if not confronto_portale:
        oneri_fissi += parametri.get("sigma1", 0.0)

    # --- Sigma2 (trasporto fisso?) ---
    if not confronto_portale:
        oneri_fissi += parametri.get("sigma2", 0.0)

    # --- UC3 (perequazione) ---
    oneri_kwh += parametri.get("uc3", 0.0)

    # --- CSED, CDISPD, MSD, UNIESS, TERNA, INTERR, RST ---
    for k in ["csed", "cdispd", "msd", "uniess", "terna", "interr", "rst", "rstg"]:
        oneri_kwh += parametri.get(k, 0.0)

    # --- Modeol, capprod ---
    for k in ["modeol", "capprod"]:
        oneri_kwh += parametri.get(k, 0.0)

    # --- Qualità UC6 ---
    oneri_fissi += parametri.get(profilo_uc6s, 0.0)
    oneri_kwh += parametri.get(profilo_uc6p, 0.0)

    # --- Capacity Market ---
    for k in ["cpty_mrkt_1", "cpty_mrkt_2", "cpty_mrkt_3", "cpty_mrkt_mt"]:
        oneri_kwh += parametri.get(k, 0.0)

    # --- Gamma (saldo perequazione?) ---
    # gamma è un valore negativo (-73.16). Non so se va incluso. Per sicurezza lo saltiamo.

    # --- IVA ---
    # L'IVA è applicata sul totale. Per ora calcoliamo senza IVA e aggiungiamo una nota.

    return oneri_fissi, oneri_kwh


def calcola_mia_offerta(
    mia_offerta: dict,
    parametri: Dict[str, float],
    consumo_annuo: int,
    potenza: float,
    pun: float,
    residente: bool,
    confronto_portale: bool = False,
    ignora_sconti_promo: bool = False,
) -> Dict[str, float]:
    """Calcola la spesa annua per la mia offerta attuale (da my_offer.json).

    Riutilizza la stessa logica del calcolatore: componenti venditore + PUN + oneri sistema + IVA.
    """
    import copy
    from dataclasses import dataclass
    from typing import List

    off_type = mia_offerta["tipo"]
    perdite_rete = mia_offerta.get("perdite_rete", 0.0)

    # Crea un'offerta fake per riusare calcola_spesa_annua
    @dataclass
    class IntervalloFake:
        fascia: str
        prezzo: float
        unita_misura: str
        consumo_da: Optional[int] = None
        consumo_a: Optional[int] = None

    @dataclass
    class ComponenteFake:
        prezzi: list

    @dataclass
    class ScontoFake:
        condizione_applicazione: str
        prezzi: list
        validita: str = ""
        durata_mesi: int = 0

    @dataclass
    class CondizioneFake:
        limitante: bool
        descrizione: str = ""

    @dataclass
    class OffertaFake:
        tipologia_fasce: str
        tipo_offerta: str
        componenti: list
        sconti: list
        condizioni: list
        cod_offerta: str = "MIA_OFFERTA"
        piva_utente: str = ""
        nome_offerta: str = ""
        url_offerta: str = ""

    tariffa = mia_offerta["tariffa"]
    quota_potenza = mia_offerta.get("quota_potenza", 0.0)
    sconti = mia_offerta.get("sconti", 0.0)

    componenti = []
    if mia_offerta["quota_fissa"] > 0:
        componenti.append(ComponenteFake(prezzi=[
            IntervalloFake(fascia="unica", prezzo=mia_offerta["quota_fissa"], unita_misura="euro_anno"),
        ]))
    if quota_potenza > 0:
        componenti.append(ComponenteFake(prezzi=[
            IntervalloFake(fascia="unica", prezzo=quota_potenza, unita_misura="euro_kw_anno"),
        ]))
    scaglioni_energia = mia_offerta.get("scaglioni_energia", None)
    if scaglioni_energia:
        prezzi = []
        for s in scaglioni_energia:
            prezzi.append(IntervalloFake(
                fascia="unica",
                prezzo=s["prezzo"],
                unita_misura="euro_kwh",
                consumo_da=s["da"],
                consumo_a=s.get("a"),
            ))
        componenti.append(ComponenteFake(prezzi=prezzi))
    elif mia_offerta["prezzo_energia"] > 0:
        componenti.append(ComponenteFake(prezzi=[
            IntervalloFake(fascia="unica", prezzo=mia_offerta["prezzo_energia"], unita_misura="euro_kwh"),
        ]))

    # Sconti
    sconti_list = []
    if sconti < 0:
        sconti_list.append(ScontoFake(condizione_applicazione="00", prezzi=[
            IntervalloFake(fascia="unica", prezzo=abs(sconti), unita_misura="euro_anno"),
        ]))

    offerta_fake = OffertaFake(
        tipologia_fasce=tariffa,
        tipo_offerta=off_type,
        componenti=componenti,
        sconti=sconti_list,
        condizioni=[],
    )

    pun_effettivo = pun * (1 + perdite_rete)
    risultato = calcola_spesa_annua(
        offerta_fake, parametri, consumo_annuo, potenza, pun_effettivo, residente,
        confronto_portale=confronto_portale,
        ignora_sconti_promo=ignora_sconti_promo,
    )
    return risultato


def applica_iva(spesa: float, residente: bool) -> float:
    """Applica IVA al totale."""
    iva = 0.10 if residente else 0.22
    return spesa * (1 + iva)
