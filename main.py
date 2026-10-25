"""Entry point del comparatore offerte."""

import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Fallback manuale se python-dotenv non è installato (es. python di sistema)
    _env_path = Path(".env")
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _value = _line.partition("=")
            _key = _key.strip()
            if _key and _key not in os.environ:
                os.environ[_key] = _value.strip().strip('"').strip("'")

from config import (
    DATA_DIR, PROFILO_CONSUMO, REGIONI_AMBITO_GAS, REGIONI_MAP, carica_mia_offerta,
)
from downloader import ottieni_file_open_data
from parser import parse_xml_offerte, parse_csv_parametri, parse_csv_prezzi, ultimo_mese_prezzi
from filters import FiltroOfferte
from parser import has_penale_recesso, has_penale_recesso_limitante
from calculator import calcola_spesa_annua, calcola_mia_offerta, applica_iva, applica_iva_gas
from formatter import stampa_tabella, esporta_csv
from cli import parse_args
from venditori import build_vendor_map, get_vendor_name
from verifica import verifica_offerte, warn_cache_stale
from popola_db import popola, default_db_path
from database import load_offerte, load_parametri, load_prezzi
from penali import filtra_penali

from collections import defaultdict


def _campi_offerta(off):
    qf = sum(p.prezzo for comp in off.componenti for p in comp.prezzi if p.unita_misura == "euro_anno")
    spread = next((p.prezzo for comp in off.componenti for p in comp.prezzi if p.unita_misura == "euro_kwh" and p.prezzo > 0), 0)
    sconti = tuple((s.nome, round(p.prezzo, 2)) for s in off.sconti for p in s.prezzi if s.condizione_applicazione == "00" and p.unita_misura == "euro_anno")
    return (off.tipologia_fasce, qf, spread, sconti)


def _formatta_suffisso(off):
    parti = []
    if off.tipologia_fasce:
        parti.append(off.tipologia_fasce)
    qf = sum(p.prezzo for comp in off.componenti for p in comp.prezzi if p.unita_misura == "euro_anno")
    if qf > 0:
        parti.append(f"QF {qf:.0f}€")
    spread = next((p.prezzo for comp in off.componenti for p in comp.prezzi if p.unita_misura == "euro_kwh" and p.prezzo > 0), 0)
    if spread > 0:
        parti.append(f"spread {spread:.4f}")
    for s in off.sconti:
        for p in s.prezzi:
            if p.unita_misura == "euro_anno" and s.condizione_applicazione == "00":
                parti.append(f"{s.nome} {p.prezzo:.0f}€")
    return ", ".join(parti)


def disambigua_offerte(offerte):
    gruppi = defaultdict(list)
    for i, off in enumerate(offerte):
        gruppi[(off.piva_utente, off.nome_offerta)].append(i)

    for (piva, nome), indices in gruppi.items():
        if len(indices) <= 1:
            continue
        group_offers = [offerte[i] for i in indices]
        campi = [_campi_offerta(off) for off in group_offers]
        if len(set(campi)) <= 1:
            for j, idx in enumerate(indices, 1):
                offerte[idx].nome_offerta = f"{nome} ({j})"
            continue
        campi_unici = set()
        for off in group_offers:
            suffisso = _formatta_suffisso(off)
            campi_unici.add(suffisso)
        if len(campi_unici) == len(indices):
            for off, suffisso in zip(group_offers, [_formatta_suffisso(off) for off in group_offers]):
                off.nome_offerta = f"{nome} ({suffisso})"
        else:
            for j, idx in enumerate(indices, 1):
                offerte[idx].nome_offerta = f"{nome} ({j})"


def main():
    config = parse_args()

    commodity = config["commodity"]
    tipo_cliente = config["tipo_cliente"]
    residente = config["residente"]
    consumo_annuo = config["consumo_annuo"]
    potenza = config["potenza"]
    tipo_tariffa = config["tipo_tariffa"]
    tipo_offerta = config["tipo_offerta"]
    pun_custom = config["pun"]
    psv_custom = config["psv"]
    exclude_keywords = config["exclude_condizioni"]
    solo_semplici = config["solo_semplici"]
    no_oneri_recesso = config["no_oneri_recesso"]
    penale_mese_max = config["penale_mese_max"]
    penale_12m_max = config["penale_12m_max"]
    venditori = config["venditori"]
    forza_download = config["download"]
    output_mode = config["output"]
    csv_path = config["csv_path"]
    confronto_portale = config["confronto_portale"]
    tipo_attivazione = config["tipo_attivazione"]
    confronta = config["confronta"]
    max_offerte = config["max"]
    ignora_sconti_promo = config["ignora_sconti_promo"]
    sconti_condizionati = config["sconti_condizionati"]
    zona = config["zona"]
    verifica = config["verifica"]
    cerca = 0

    if verifica:
        if not os.environ.get("SERPER_API_KEY"):
            print("\n❌ Errore: SERPER_API_KEY non trovata.", file=sys.stderr)
            print("   Per usare --verifica devi impostare la chiave Serper.dev:", file=sys.stderr)
            print("     export SERPER_API_KEY='tua_chiave'", file=sys.stderr)
            print("   oppure aggiungerla al file .env del progetto:", file=sys.stderr)
            print("     SERPER_API_KEY=tua_chiave\n", file=sys.stderr)
            sys.exit(1)

    db_path = Path(config["db_path"]) if config["db_path"] else default_db_path(commodity)

    if config["popola_db"]:
        popola(
            db_path=db_path,
            commodity=commodity,
            forza_download=forza_download,
            no_llm=config["no_llm"],
            batch_size=config["batch_size"],
            llm_provider=config.get("llm_provider"),
            llm_model=config.get("llm_model"),
            llm_base_url=config.get("llm_base_url"),
            no_rule_based=config.get("no_rule_based", False),
        )
        return

    print(f"\n🔍 Comparatore Offerte - Mercato Libero {commodity.title()}")
    if commodity == "gas":
        if tipo_tariffa != "tutte":
            print("   ⚠️  --tipo-tariffa ignorato per il gas (offerta monoraria)")
            tipo_tariffa = "tutte"
        print(f"   Consumo: {consumo_annuo} Smc/anno | Tariffa: monoraria")
        print(f"   Uso: {tipo_cliente} | {'Prima casa' if residente else 'Seconda casa'} | Regione: {zona or 'non specificata'}")
    else:
        print(f"   Consumo: {consumo_annuo} kWh/anno | Potenza: {potenza} kW | Tariffa: {tipo_tariffa}")
        print(f"   Residenza: {'Prima casa' if residente else 'Seconda casa'}")
    print("-" * 60)

    # 1. Download (parametri e prezzi sono sempre necessari; XML serve solo se manca il DB)
    try:
        xml_path, csv_param_path, csv_prezzi_path = ottieni_file_open_data(
            commodity, forza_download=forza_download
        )
    except RuntimeError as e:
        print(f"❌ Errore download: {e}")
        sys.exit(1)

    # 2. Caricamento offerte (dal DB se esiste, altrimenti dallo XML)
    if db_path.exists():
        print(f"📄 Caricamento offerte dal DB ({db_path})...")
        offerte = load_offerte(db_path)
    else:
        print("📄 DB non trovato, parsing XML...")
        offerte = parse_xml_offerte(xml_path, commodity=commodity)
    scartate = [o for o in offerte if o.tipo_offerta not in ("fisso", "variabile")]
    if scartate:
        print(f"   Saltate {len(scartate)} offerte con tipologia non gestita (TIPO_OFFERTA non mappato)")
        offerte = [o for o in offerte if o.tipo_offerta in ("fisso", "variabile")]
    disambigua_offerte(offerte)
    print(f"   Trovate {len(offerte)} offerte totali")

    print("🔖 Mappatura nomi venditori...")
    vendor_map = build_vendor_map(offerte)
    print(f"   Mappati {len(vendor_map)} venditori")

    print("📊 Parsing parametri di sistema...")
    if db_path.exists():
        parametri = load_parametri(db_path)
    else:
        parametri = parse_csv_parametri(csv_param_path)

    print("💶 Parsing prezzi storici...")
    if db_path.exists():
        prezzi = load_prezzi(db_path)
    else:
        prezzi = parse_csv_prezzi(csv_prezzi_path)
    if commodity == "gas":
        prezzo_custom = psv_custom
        prezzo_default = prezzi.get("PSV", 0.0)
        etichetta_prezzo = "PSV"
        unita_consumo = "Smc"
        flag_prezzo, env_prezzo = "--psv", "PSV_MANUALE"
    else:
        prezzo_custom = pun_custom
        prezzo_default = prezzi.get("PUN", 0.0)
        etichetta_prezzo = "PUN"
        unita_consumo = "kWh"
        flag_prezzo, env_prezzo = "--pun", "PUN_MANUALE"
    prezzo = prezzo_custom if prezzo_custom is not None else prezzo_default
    if prezzo_custom is None:
        mese = ultimo_mese_prezzi(csv_prezzi_path)
        if mese:
            try:
                eta_mesi = (datetime.now().year - int(mese[:4])) * 12 + (datetime.now().month - int(mese[4:6]))
            except ValueError:
                eta_mesi = 0
            if eta_mesi > 2:
                print(f"   ⚠️  {etichetta_prezzo} di default fermo a {mese}: il CSV prezzi storici non è aggiornato.")
                print(f"      Usa {flag_prezzo} <valore> o {env_prezzo} nel .env con l'ultimo valore disponibile.")
    print(f"   {etichetta_prezzo} usato: {prezzo:.4f} €/{unita_consumo}")

    ambito_gas = "a3"
    if commodity == "gas":
        zona_norm = (zona or "").strip().lower()
        codice_regione = zona_norm if zona_norm in REGIONI_MAP else next(
            (k for k, v in REGIONI_MAP.items() if v == zona_norm), None
        )
        if codice_regione:
            ambito_gas = REGIONI_AMBITO_GAS.get(codice_regione, "a3")
        else:
            print("   ⚠️  Regione non specificata: uso l'ambito gas CENTRALE (a3). Usa --regione ...")

    # 3. Filtri
    print("🔎 Applicazione filtri...")
    filtro = FiltroOfferte(offerte)
    filtro.by_tipo_cliente(tipo_cliente)
    filtro.by_tipo_offerta(tipo_offerta)
    filtro.by_tipologia_fasce(tipo_tariffa)
    filtro.by_consumo_range(consumo_annuo)
    filtro.by_venditori(venditori)
    filtro.by_solo_semplici(solo_semplici)
    filtro.by_no_oneri_recesso(no_oneri_recesso)
    filtro.by_esclude_condizioni_keyword(exclude_keywords)
    filtro.by_tipo_attivazione([tipo_attivazione])
    filtro.by_zone_geografiche(zona)

    offerte_filtrate = filtro.get()

    if penale_mese_max is not None or penale_12m_max is not None:
        offerte_filtrate, sopra_soglia, sconosciute = filtra_penali(
            offerte_filtrate, mese_max=penale_mese_max, max_12m=penale_12m_max
        )
        soglie = []
        if penale_mese_max is not None:
            soglie.append(f"≤ {penale_mese_max:g} €/mese")
        if penale_12m_max is not None:
            soglie.append(f"≤ {penale_12m_max:g} € a 12 mesi")
        print(f"   Filtro penali: {' e '.join(soglie)}")
        if sconosciute:
            print(f"   ⚠️  {len(sconosciute)} offerte escluse: penale non dichiarata/quantificabile nell'XML")
            for o in sconosciute[:5]:
                print(f"      - {o.nome_offerta}")
            if len(sconosciute) > 5:
                print(f"      ... e altre {len(sconosciute) - 5}")
            print("      Controlla la CTE o aggiungi un override in data/penali_manuali.json")
        if sopra_soglia:
            print(f"   🚫 {len(sopra_soglia)} offerte escluse: penale oltre le soglie")

    print(f"   {len(offerte_filtrate)} offerte dopo i filtri")

    if not offerte_filtrate:
        print("\n⚠️ Nessuna offerta corrisponde ai criteri. Prova a allentare i filtri.")
        sys.exit(0)

    # 4. Calcolo spesa
    print("🧮 Calcolo spesa annua stimata...")
    risultati = []
    for offerta in offerte_filtrate:
        dettagli = calcola_spesa_annua(
            offerta, parametri, consumo_annuo, potenza, prezzo, residente,
            confronto_portale=confronto_portale,
            ignora_sconti_promo=ignora_sconti_promo,
            sconti_condizionati=sconti_condizionati,
            commodity=commodity,
            ambito_gas=ambito_gas,
            uso_domestico=(tipo_cliente == "domestico"),
        )
        if commodity == "gas":
            spesa_totale_iva = applica_iva_gas(dettagli["spesa_totale"], consumo_annuo, tipo_cliente == "domestico", residente)
        else:
            spesa_totale_iva = applica_iva(dettagli["spesa_totale"], residente)
        iva = round(spesa_totale_iva - dettagli["spesa_totale"], 2)

        condizioni_limitanti = any(c.limitante for c in offerta.condizioni)
        ha_penali = has_penale_recesso(offerta)
        penali_limitante = has_penale_recesso_limitante(offerta)
        descrizione_condizioni = " | ".join(
            c.descrizione for c in offerta.condizioni
        )

        risultati.append({
            "cod_offerta": offerta.cod_offerta,
            "venditore": offerta.piva_utente,
            "nome_venditore": get_vendor_name(offerta.piva_utente, vendor_map),
            "nome_offerta": offerta.nome_offerta,
            "tipo_offerta": offerta.tipo_offerta,
            "tipologia_fasce": offerta.tipologia_fasce,
            "spesa_totale": spesa_totale_iva,
            "spesa_venditore": dettagli["spesa_venditore"],
            "costo_fisso_venditore": dettagli["costo_fisso_venditore"],
            "costo_potenza_venditore": dettagli["costo_potenza_venditore"],
            "costo_energia_venditore": dettagli["costo_energia_venditore"],
            "costo_pun": dettagli["costo_pun"],
            "oneri_fissi_sistema": dettagli["oneri_fissi_sistema"],
            "oneri_energia_sistema": dettagli["oneri_energia_sistema"],
            "accise": dettagli.get("accise", 0.0),
            "iva": iva,
            "pun_usato": dettagli["pun_usato"],
            "perdite_rete": dettagli.get("perdite_rete", 0.0),
            "url_offerta": offerta.url_offerta,
            "condizioni_limitanti": condizioni_limitanti,
            "ha_penali": ha_penali,
            "penali_limitante": penali_limitante,
            "descrizione_condizioni": descrizione_condizioni,
            "confidenza": dettagli["confidenza"],
        })

    # 4b. Confronto con la mia offerta attuale
    if confronta:
        mia = carica_mia_offerta(commodity)
        if mia:
            print("📋 Confronto con la mia offerta attuale...")
            dettagli = calcola_mia_offerta(
                mia, parametri, consumo_annuo, potenza, prezzo, residente,
                confronto_portale=confronto_portale,
                ignora_sconti_promo=ignora_sconti_promo,
                commodity=commodity,
                ambito_gas=ambito_gas,
                uso_domestico=(tipo_cliente == "domestico"),
            )
            risultati.append({
                "_mia": True,
                "cod_offerta": "MIA_OFFERTA",
                "venditore": mia.get("venditore", "Il mio attuale"),
                "nome_venditore": "",
                "nome_offerta": mia.get("nome_offerta", ""),
                "tipo_offerta": mia.get("tipo", ""),
                "tipologia_fasce": mia.get("tariffa", ""),
                "spesa_totale": (
                    applica_iva_gas(dettagli["spesa_totale"], consumo_annuo, tipo_cliente == "domestico", residente)
                    if commodity == "gas"
                    else applica_iva(dettagli["spesa_totale"], residente)
                ),
                "spesa_venditore": dettagli["spesa_venditore"],
                "costo_fisso_venditore": dettagli["costo_fisso_venditore"],
                "costo_potenza_venditore": dettagli["costo_potenza_venditore"],
                "costo_energia_venditore": dettagli["costo_energia_venditore"],
                "costo_pun": dettagli["costo_pun"],
                "oneri_fissi_sistema": dettagli["oneri_fissi_sistema"],
                "oneri_energia_sistema": dettagli["oneri_energia_sistema"],
                "accise": dettagli.get("accise", 0.0),
                "iva": round(
                    (applica_iva_gas(dettagli["spesa_totale"], consumo_annuo, tipo_cliente == "domestico", residente)
                     if commodity == "gas"
                     else applica_iva(dettagli["spesa_totale"], residente)) - dettagli["spesa_totale"], 2
                ),
                "pun_usato": dettagli["pun_usato"],
                "perdite_rete": dettagli.get("perdite_rete", 0.0),
                "url_offerta": "",
                "condizioni_limitanti": False,
                "ha_penali": False,
                "penali_limitante": False,
                "descrizione_condizioni": "",
                "confidenza": dettagli.get("confidenza", "green"),
            })
            spesa_iva = (
                applica_iva_gas(dettagli["spesa_totale"], consumo_annuo, tipo_cliente == "domestico", residente)
                if commodity == "gas"
                else applica_iva(dettagli["spesa_totale"], residente)
            )
            print(f"   {mia['venditore']} - {mia['nome_offerta']}: {spesa_iva:.2f} €/anno")
        else:
            print("   Crea data/my_offer.json copiando da data/my_offer_stub.json e riprova.")

    # Ordina per spesa totale crescente
    risultati.sort(key=lambda x: x["spesa_totale"])

    # 4c. Verifica sito venditore (opzionale)
    if verifica == "normal":
        print("🔍 Verifica offerte su Google (Serper.dev)...")
        stati, _ = verifica_offerte(risultati, limite=max_offerte)
        if not stati:
            verifica = None
        else:
            for r in risultati:
                cod = r.get("cod_offerta", "")
                if cod in stati:
                    r["check"] = stati[cod]
            ok = sum(1 for v in stati.values() if v == "✓")
            print(f"   {ok}/{len(stati)} offerte trovate sul sito venditore")

    elif verifica == "strict":
        mia_entry = next((r for r in risultati if r.get("_mia")), None)
        if mia_entry:
            risultati = [r for r in risultati if not r.get("_mia")]

        val = input(f"   Offerte verificate da cercare [{max_offerte}] (0 = annulla): ").strip()
        if not val:
            cerca = max_offerte
        else:
            try:
                cerca = int(val)
            except ValueError:
                cerca = 0
        if cerca <= 0:
            print("   Verifica saltata.")
            verifica = None
        else:
            stima = cerca * 4
            print(f"\n⚠️  Verifica 'strict': per trovare {cerca} offerte verificate "
                  f"potrebbero servire fino a ~{stima} chiamate a Serper.dev "
                  f"(massimo 2500/mese).")
            print(f"🔍 Verifica 'strict': cerco {cerca} offerte verificate...")
            batch = cerca
            offset = 0
            verificate = []
            chiamate_fatte = 0

            while offset < len(risultati):
                stati, nuove = verifica_offerte(risultati, limite=batch, offset=offset)
                if not stati:
                    break
                chiamate_fatte += nuove
                for r in risultati:
                    cod = r.get("cod_offerta", "")
                    if cod in stati:
                        r["check"] = stati[cod]
                verificate = [r for r in risultati if "✓" in r.get("check", "")]
                if len(verificate) >= cerca:
                    break
                offset += batch
                batch = min(cerca, len(risultati) - offset)

            if verificate:
                trovate = min(len(verificate), cerca)
                print(f"   {trovate} offerte verificate trovate "
                      f"(usate {chiamate_fatte} chiamate)")
                if trovate < cerca:
                    print(f"   ✋ Solo {trovate} offerte verificate su {cerca} "
                          f"(esaurite le offerte da controllare).")
                risultati = verificate[:trovate]
            else:
                print(f"   Nessuna offerta verificata trovata (usate {chiamate_fatte} chiamate).")
                risultati = []

        if mia_entry:
            risultati.append(mia_entry)

    # 5. Output
    output_limite = max_offerte
    if verifica == "strict" and cerca > 0:
        output_limite = cerca
    if output_mode in ("terminal", "both"):
        stampa_tabella(risultati, limite=output_limite, commodity=commodity)

    if output_mode in ("csv", "both"):
        if not csv_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = DATA_DIR / f"risultati_{commodity}_{ts}.csv"
        else:
            csv_path = Path(csv_path)
        esporta_csv(risultati, csv_path)

    print("\n✅ Completato!")

    if verifica:
        warn_cache_stale()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrotto dall'utente.")
        sys.exit(0)
