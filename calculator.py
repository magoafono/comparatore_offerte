"""Calcolo della spesa annua stimata per ogni offerta."""

import re
from typing import Dict, List, Optional
from parser import Offerta, IntervalloPrezzo, Sconto
from config import PROFILO_CONSUMO

SCONTI_PROMO_KEYWORDS = [
    "primo anno", "primi 12", "primi mesi",
    "nei primi", "una tantum", "benvenuto",
    "adesione", "attivazione",
]

# Sconti condizionati applicabili con --sconti-condizionati: solo condizioni di
# pagamento/fatturazione facilmente verificabili, non condizioni di orario,
# consumo, appartenenza o fedeltà.
SCONTI_CONDIZIONATI_KEYWORDS = [
    "domiciliazione", "sdd", "addebito diretto", "sepa",
    "fattura elettronica", "fattura digitale", "dematerializzazione",
    "paperless", "bolletta elettronica", "convergenza",
]


def _sconto_condizionato_ammesso(sc: Sconto) -> bool:
    testo = f"{sc.nome} {sc.descrizione}".lower()
    return any(k in testo for k in SCONTI_CONDIZIONATI_KEYWORDS)


def _is_sconto_promozionale(sc: Sconto) -> bool:
    # "Sconto 12/24 mesi" è uno sconto strutturale legato alla durata dell'offerta,
    # non una promozione temporanea: non va rimosso da --ignora-sconti-promo.
    if re.fullmatch(r"sconto \d+ mesi", sc.nome.strip().lower()):
        return False
    if sc.validita in ("02", "03"):
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
    perdite_rete: Optional[float] = None,
    sconti_condizionati: bool = False,
    commodity: str = "elettrico",
    ambito_gas: str = "a3",
    uso_domestico: bool = True,
) -> Dict[str, float]:
    """
    Calcola la spesa annua stimata per un'offerta.
    Ritorna un dizionario con i dettagli del calcolo.

    perdite_rete: fattore λ applicato al PUN delle offerte variabili. Se None,
    usa il parametro ``lambda`` del CSV ARERA (0.10). La propria offerta può
    sovrascriverlo con il valore di ``my_offer.json``.
    """
    if offerta.tipologia_fasce in PROFILO_CONSUMO:
        profilo_fasce = PROFILO_CONSUMO[offerta.tipologia_fasce]
    else:
        # tipologia_fasce vuota o sconosciuta: inferisce dal componente energia
        fasce_energia = set()
        for comp in offerta.componenti:
            for p in comp.prezzi:
                if p.unita_misura in ("euro_kwh", "euro_smc") and p.prezzo > 0:
                    fasce_energia.add(p.fascia)
        if {"F1", "F2"} <= fasce_energia and "F3" not in fasce_energia:
            profilo_fasce = PROFILO_CONSUMO["bioraria"]
        elif {"F1", "F2", "F3"} <= fasce_energia:
            profilo_fasce = PROFILO_CONSUMO["trioraria"]
        else:
            profilo_fasce = PROFILO_CONSUMO["monoraria"]

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

                    if e.unita_misura in ("euro_kwh", "euro_smc"):
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
                elif intervallo.unita_misura in ("euro_kwh", "euro_smc"):
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
    perdite_applicate = 0.0
    if offerta.tipo_offerta == "variabile":
        # Le CTE prevedono PUN GME maggiorato delle perdite di rete + spread.
        perdite_applicate = (
            parametri.get("lambda", 0.0) if perdite_rete is None else perdite_rete
        )
        # Il PUN si applica all'intero consumo (tutte le fasce)
        costo_pun = pun * (1 + perdite_applicate) * consumo_annuo

    spesa_venditore = costo_fisso_venditore + costo_potenza_venditore + costo_energia_venditore + costo_pun

    # --- 2b. Sconti automatici (senza condizioni speciali) ---
    sconti_totali = 0.0
    sconti_percentuali_visti = set()
    for sc in offerta.sconti:
        if sc.condizione_applicazione != "00":
            if not (sconti_condizionati and _sconto_condizionato_ammesso(sc)):
                continue
        if ignora_sconti_promo and _is_sconto_promozionale(sc):
            continue

        prezzi_kwh = [p for p in sc.prezzi if p.unita_misura in ("euro_kwh", "euro_smc")]
        # L'XML a volte ripete il prezzo per fascia senza valorizzare FASCIA_COMPONENTE:
        # sommare ogni voce sull'intero consumo triplicherebbe lo sconto.
        if len(prezzi_kwh) > 1 and all(p.fascia in ("", "unica") for p in prezzi_kwh):
            fasce = list(profilo_fasce)
            if len(prezzi_kwh) == len(fasce) and len(fasce) > 1:
                for p, fascia in zip(prezzi_kwh, fasce):
                    sconti_totali += p.prezzo * consumo_annuo * profilo_fasce[fascia]
            else:
                media = sum(p.prezzo for p in prezzi_kwh) / len(prezzi_kwh)
                sconti_totali += media * consumo_annuo
        else:
            for p in prezzi_kwh:
                if p.fascia in profilo_fasce:
                    sconti_totali += p.prezzo * consumo_annuo * profilo_fasce[p.fascia]
                else:
                    sconti_totali += p.prezzo * consumo_annuo

        testo_sconto = f"{sc.nome} {sc.descrizione}".lower()
        base_percentuale = costo_energia_venditore
        base_key = "energia"
        if any(k in testo_sconto for k in ("quota fissa", "commercializzazione", "corrispettivo fisso")):
            base_percentuale = costo_fisso_venditore + costo_potenza_venditore
            base_key = "fissa"
        elif any(k in testo_sconto for k in ("totale", "intera fornitura", "corrispettivo totale")):
            base_percentuale = costo_fisso_venditore + costo_potenza_venditore + costo_energia_venditore + costo_pun
            base_key = "totale"

        def _applica_percentuale(prezzo_pct: float) -> None:
            nonlocal sconti_totali
            nome_norm = re.sub(r"[0-9°]", " ", sc.nome.lower())
            nome_norm = re.sub(r"\b(anno|mesi|mese)\b", " ", nome_norm)
            nome_norm = re.sub(r"\s+", " ", nome_norm).strip()
            chiave = (base_key, nome_norm)
            if chiave in sconti_percentuali_visti:
                return
            sconti_percentuali_visti.add(chiave)
            sconti_totali += base_percentuale * prezzo_pct / 100

        for p in sc.prezzi:
            if p.unita_misura in ("euro_anno", "euro_una_tantum"):
                sconti_totali += p.prezzo
            elif p.unita_misura == "percentuale":
                _applica_percentuale(p.prezzo)
            elif p.unita_misura == "":
                if "%" in testo_sconto:
                    _applica_percentuale(p.prezzo)
                    continue
                # um mancante nell'XML: euristica sul nome
                nome = sc.nome.lower().strip()
                if nome.startswith("sconto f") and len(nome) == 9 and nome[-1] in "123":
                    fascia = f"F{nome[-1]}"
                    kwh_fascia = consumo_annuo * profilo_fasce.get(fascia, 1.0)
                    sconti_totali += p.prezzo * kwh_fascia
                else:
                    # default: importo fisso annuo
                    sconti_totali += p.prezzo
    spesa_venditore = max(0.0, spesa_venditore - sconti_totali)

    confidenza = _calcola_confidenza(offerta)

    # --- 3. Oneri di sistema ---
    if commodity == "gas":
        oneri_fissi, oneri_kwh = _calcola_oneri_sistema_gas(parametri, consumo_annuo, ambito_gas)
    else:
        oneri_fissi, oneri_kwh = _calcola_oneri_sistema(parametri, potenza, residente, confronto_portale=confronto_portale)
    costo_oneri_fissi = oneri_fissi
    costo_oneri_energia = oneri_kwh * consumo_annuo
    accise = _calcola_accise_gas(consumo_annuo, domestico=uso_domestico) if commodity == "gas" else 0.0

    spesa_totale = spesa_venditore + costo_oneri_fissi + costo_oneri_energia + accise

    return {
        "spesa_totale": round(spesa_totale, 2),
        "spesa_venditore": round(spesa_venditore, 2),
        "costo_fisso_venditore": round(costo_fisso_venditore, 2),
        "costo_potenza_venditore": round(costo_potenza_venditore, 2),
        "costo_energia_venditore": round(costo_energia_venditore, 2),
        "costo_pun": round(costo_pun, 2),
        "oneri_fissi_sistema": round(costo_oneri_fissi, 2),
        "oneri_energia_sistema": round(costo_oneri_energia, 2),
        "accise": round(accise, 2),
        "pun_usato": round(pun, 5),
        "perdite_rete": round(perdite_applicate, 5),
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

    # --- CSED, RST ---
    for k in ["csed", "rst", "rstg"]:
        oneri_kwh += parametri.get(k, 0.0)

    # --- Dispacciamento e Capacity Market ---
    # cdispd è già la somma della quota Capacity Market (media di cpty_mrkt_1/2/3)
    # e delle voci Terna (msd, terna, interr, uniess, modeol). Sommare anche i
    # singoli parametri li conterebbe due volte. cpty_mrkt_mt non è dentro cdispd
    # e non va aggiunto (è una quotazione di mercato, non un onere aggiuntivo).
    if "cdispd" in parametri:
        oneri_kwh += parametri["cdispd"]
    else:
        for k in ["msd", "terna", "interr", "uniess", "modeol", "capprod"]:
            oneri_kwh += parametri.get(k, 0.0)
        cpty = [parametri.get(k, 0.0) for k in ("cpty_mrkt_1", "cpty_mrkt_2", "cpty_mrkt_3")]
        oneri_kwh += sum(cpty) / len(cpty)

    # --- Qualità UC6 ---
    oneri_fissi += parametri.get(profilo_uc6s, 0.0)
    oneri_kwh += parametri.get(profilo_uc6p, 0.0)

    # --- Gamma (saldo perequazione?) ---
    # gamma è un valore negativo (-73.16). Non so se va incluso. Per sicurezza lo saltiamo.

    # --- IVA ---
    # L'IVA è applicata sul totale. Per ora calcoliamo senza IVA e aggiungiamo una nota.

    return oneri_fissi, oneri_kwh


SCAGLIONI_GAS = [
    (0, 120, "f1"),
    (120, 480, "f2"),
    (480, 1560, "f3"),
    (1560, 5000, "f4"),
    (5000, 80000, "f5"),
    (80000, None, "f6"),
]

ACCISE_GAS_DOMESTICO = [
    (0, 120, 0.044),
    (120, 480, 0.175),
    (480, 1560, 0.175),
    (1560, 5000, 0.175),
    (5000, None, 0.20),
]


def _quantita_scaglione(consumo: float, da: float, a: Optional[float]) -> float:
    if consumo <= da:
        return 0.0
    return (min(consumo, a) if a is not None else consumo) - da


def _calcola_oneri_sistema_gas(parametri: Dict[str, float], consumo_annuo: float, ambito: str = "a3"):
    """
    Oneri di sistema gas per uso domestico (contatore classe <G6, es. G4/G6).
    Ritorna (oneri_fissi_annuali, oneri_variabili_per_Smc_equivalente).

    Sono esclusi QVD e UG2 (quota vendita al dettaglio/compensazioni), che
    nella lettura del portale non si sommano al prezzo del venditore.
    """
    fissi = parametri.get(f"tau1_cc1_{ambito}", 0.0)
    rate = sum(
        parametri.get(k, 0.0)
        for k in ("qt", "re", "gs", "rs", "ug1", "ug3", f"st_{ambito}", f"vr_{ambito}", "cpr", "grad")
    )
    variabile = rate * consumo_annuo
    for da, a, codice in SCAGLIONI_GAS:
        q = _quantita_scaglione(consumo_annuo, da, a)
        if q:
            variabile += parametri.get(f"tau3_{codice}_{ambito}", 0.0) * q
    rate_eff = variabile / consumo_annuo if consumo_annuo else 0.0
    return fissi, rate_eff


def _calcola_accise_gas(consumo_annuo: float, domestico: bool = True) -> float:
    """Accise gas uso domestico (le accise non sono nel CSV ARERA)."""
    if not domestico:
        return 0.0
    totale = 0.0
    for da, a, rate in ACCISE_GAS_DOMESTICO:
        totale += _quantita_scaglione(consumo_annuo, da, a) * rate
    return totale


def calcola_mia_offerta(
    mia_offerta: dict,
    parametri: Dict[str, float],
    consumo_annuo: int,
    potenza: float,
    pun: float,
    residente: bool,
    confronto_portale: bool = False,
    ignora_sconti_promo: bool = False,
    commodity: str = "elettrico",
    ambito_gas: str = "a3",
    uso_domestico: bool = True,
) -> Dict[str, float]:
    """Calcola la spesa annua per la mia offerta attuale (da my_offer.json).

    Riutilizza la stessa logica del calcolatore: componenti venditore + PUN + oneri sistema + IVA.
    """
    import copy
    from dataclasses import dataclass
    from typing import List

    off_type = mia_offerta["tipo"]
    perdite_rete = mia_offerta.get("perdite_rete")
    unita_energia = "euro_smc" if commodity == "gas" else "euro_kwh"

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
        nome: str = ""
        descrizione: str = ""

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
    altri_costi = mia_offerta.get("altri_costi", 0.0)
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
    if altri_costi > 0:
        componenti.append(ComponenteFake(prezzi=[
            IntervalloFake(fascia="unica", prezzo=altri_costi, unita_misura="euro_anno"),
        ]))
    scaglioni_energia = mia_offerta.get("scaglioni_energia", None)
    if scaglioni_energia:
        prezzi = []
        for s in scaglioni_energia:
            prezzi.append(IntervalloFake(
                fascia="unica",
                prezzo=s["prezzo"],
                unita_misura=unita_energia,
                consumo_da=s["da"],
                consumo_a=s.get("a"),
            ))
        componenti.append(ComponenteFake(prezzi=prezzi))
    elif mia_offerta["prezzo_energia"] > 0:
        componenti.append(ComponenteFake(prezzi=[
            IntervalloFake(fascia="unica", prezzo=mia_offerta["prezzo_energia"], unita_misura=unita_energia),
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

    risultato = calcola_spesa_annua(
        offerta_fake, parametri, consumo_annuo, potenza, pun, residente,
        confronto_portale=confronto_portale,
        ignora_sconti_promo=ignora_sconti_promo,
        perdite_rete=perdite_rete,
        commodity=commodity,
        ambito_gas=ambito_gas,
        uso_domestico=uso_domestico,
    )
    return risultato


def applica_iva(spesa: float, residente: bool) -> float:
    """Applica IVA al totale (elettrico)."""
    iva = 0.10 if residente else 0.22
    return spesa * (1 + iva)


def applica_iva_gas(spesa: float, consumo_annuo: float, domestico: bool = True, prima_casa: bool = True) -> float:
    """IVA gas: 10% fino a 480 Smc/anno per uso domestico in prima casa, 22% oltre.

    Per seconde case/non domestico si applica il 22%.
    """
    if not domestico or not prima_casa:
        return spesa * 1.22
    if consumo_annuo <= 0:
        return spesa * 1.10
    quota_10 = min(consumo_annuo, 480) / consumo_annuo
    iva = spesa * (quota_10 * 0.10 + (1 - quota_10) * 0.22)
    return spesa + iva
