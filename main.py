"""Entry point del comparatore offerte."""

import sys
from datetime import datetime
from pathlib import Path

from config import DATA_DIR, PROFILO_CONSUMO
from downloader import ottieni_file_open_data
from parser import parse_xml_offerte, parse_csv_parametri, parse_csv_prezzi
from filters import FiltroOfferte
from calculator import calcola_spesa_annua, applica_iva
from formatter import stampa_tabella, esporta_csv
from cli import parse_args
from venditori import build_vendor_map, get_vendor_name


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
    exclude_keywords = config["exclude_condizioni"]
    solo_semplici = config["solo_semplici"]
    no_oneri_recesso = config["no_oneri_recesso"]
    venditori = config["venditori"]
    forza_download = config["download"]
    output_mode = config["output"]
    csv_path = config["csv_path"]
    confronto_portale = config["confronto_portale"]
    tipo_attivazione = config["tipo_attivazione"]

    print(f"\n🔍 Comparatore Offerte - Mercato Libero {commodity.title()}")
    print(f"   Consumo: {consumo_annuo} kWh/anno | Potenza: {potenza} kW | Tariffa: {tipo_tariffa}")
    print(f"   Residenza: {'Prima casa' if residente else 'Seconda casa'}")
    print("-" * 60)

    # 1. Download
    try:
        xml_path, csv_param_path, csv_prezzi_path = ottieni_file_open_data(
            commodity, forza_download=forza_download
        )
    except RuntimeError as e:
        print(f"❌ Errore download: {e}")
        sys.exit(1)

    # 2. Parse
    print("📄 Parsing offerte XML...")
    offerte = parse_xml_offerte(xml_path)
    print(f"   Trovate {len(offerte)} offerte totali")

    print("🔖 Mappatura nomi venditori...")
    vendor_map = build_vendor_map(offerte)
    print(f"   Mappati {len(vendor_map)} venditori")

    print("📊 Parsing parametri di sistema...")
    parametri = parse_csv_parametri(csv_param_path)

    print("💶 Parsing prezzi storici...")
    prezzi = parse_csv_prezzi(csv_prezzi_path)
    pun_default = prezzi.get("PUN", 0.0)
    pun = pun_custom if pun_custom is not None else pun_default
    print(f"   PUN usato: {pun:.4f} €/kWh")

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

    offerte_filtrate = filtro.get()
    print(f"   {len(offerte_filtrate)} offerte dopo i filtri")

    if not offerte_filtrate:
        print("\n⚠️ Nessuna offerta corrisponde ai criteri. Prova a allentare i filtri.")
        sys.exit(0)

    # 4. Calcolo spesa
    print("🧮 Calcolo spesa annua stimata...")
    risultati = []
    for offerta in offerte_filtrate:
        dettagli = calcola_spesa_annua(
            offerta, parametri, consumo_annuo, potenza, pun, residente,
            confronto_portale=confronto_portale
        )
        spesa_totale_iva = applica_iva(dettagli["spesa_totale"], residente)

        condizioni_limitanti = any(c.limitante for c in offerta.condizioni)
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
            "pun_usato": dettagli["pun_usato"],
            "url_offerta": offerta.url_offerta,
            "condizioni_limitanti": condizioni_limitanti,
            "descrizione_condizioni": descrizione_condizioni,
        })

    # Ordina per spesa totale crescente
    risultati.sort(key=lambda x: x["spesa_totale"])

    # 5. Output
    if output_mode in ("terminal", "both"):
        stampa_tabella(risultati)

    if output_mode in ("csv", "both"):
        if not csv_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = DATA_DIR / f"risultati_{commodity}_{ts}.csv"
        else:
            csv_path = Path(csv_path)
        esporta_csv(risultati, csv_path)

    print("\n✅ Completato!")


if __name__ == "__main__":
    main()
