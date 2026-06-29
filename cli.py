"""Interfaccia a riga di comando con argparse e fallback interattivo."""

import argparse
import sys
from typing import Dict, Any

from config import BLACKLIST_CONDIZIONI_DEFAULT

# Mappature shortcut per le scelte interattive
SHORTCUTS_TIPO_TARIFFA = {
    "0": "tutte", "a": "tutte", "all": "tutte", "tut": "tutte",
    "1": "monoraria", "m": "monoraria", "mono": "monoraria",
    "2": "bioraria", "b": "bioraria", "bio": "bioraria",
    "3": "trioraria", "t": "trioraria", "tri": "trioraria",
}
SHORTCUTS_TIPO_OFFERTA = {
    "0": "tutte", "a": "tutte", "all": "tutte",
    "1": "fisso", "f": "fisso",
    "2": "variabile", "v": "variabile", "var": "variabile",
}
SHORTCUTS_TIPO_CLIENTE = {
    "1": "domestico", "d": "domestico", "dom": "domestico",
    "2": "altri_usi", "a": "altri_usi", "alt": "altri_usi", "au": "altri_usi",
}
SHORTCUTS_COMMODITY = {
    "1": "elettrico", "e": "elettrico", "ele": "elettrico", "el": "elettrico",
    "2": "gas", "g": "gas", "ga": "gas",
}
SHORTCUTS_OUTPUT = {
    "1": "terminal", "t": "terminal", "term": "terminal",
    "2": "csv", "c": "csv",
    "3": "both", "b": "both",
}


def _input_int(prompt: str, default: int = None) -> int:
    while True:
        val = input(f"{prompt}").strip()
        if not val and default is not None:
            return default
        try:
            return int(val)
        except ValueError:
            print("  Inserisci un numero intero valido.")


def _input_float(prompt: str, default: float = None) -> float:
    while True:
        val = input(f"{prompt}").strip().replace(",", ".")
        if not val and default is not None:
            return default
        try:
            return float(val)
        except ValueError:
            print("  Inserisci un numero valido.")


def _input_choice(prompt: str, choices: list, shortcut_map: dict = None, default: str = None) -> str:
    """Richiede una scelta testuale, accettando anche shortcut.
    
    I valori validi sono mostrati automaticamente nel prompt.
    """
    scelta = None
    while scelta is None:
        val = input(f"{prompt}").strip().lower()
        if not val and default is not None:
            return default
        if val in [c.lower() for c in choices]:
            scelta = val
        elif shortcut_map and val in shortcut_map:
            scelta = shortcut_map[val].lower()
        else:
            accettati = ", ".join(sorted(set(choices) | set(shortcut_map.keys() if shortcut_map else [])))
            print(f"  Scelta non valida. Valori accettati: {accettati}")
    return scelta


def _input_yesno(prompt: str, default: bool = False) -> bool:
    default_str = "s" if default else "n"
    while True:
        val = input(f"{prompt} (s/n) [{default_str}]: ").strip().lower()
        if not val:
            return default
        if val in ("s", "si", "yes", "y", "1"):
            return True
        if val in ("n", "no", "0"):
            return False
        print("  Rispondi s o n.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Comparatore Offerte Energia Elettrica (Mercato Libero) - Open Data ARERA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python main.py                                    # Modalità interattiva
  python main.py --consumo-annuo 1000 --potenza 3 --tipo-tariffa monoraria
  python main.py --non-residente --consumo-annuo 2000 --pun 0.12 --senza-vincoli --output both
        """,
    )
    parser.add_argument("--commodity", choices=["elettrico", "gas"], default="elettrico",
                        help="Tipo di commodity (default: elettrico)")
    parser.add_argument("--tipo-cliente", choices=["domestico", "altri_usi"], default="domestico",
                        help="Tipologia cliente (default: domestico)")
    parser.add_argument("--residente", action="store_true", help="Residenza principale (prima casa)")
    parser.add_argument("--non-residente", action="store_true", help="Seconda casa / non residente")
    parser.add_argument("--consumo-annuo", type=int, help="Consumo annuo stimato in kWh")
    parser.add_argument("--potenza", type=float, default=3.0, help="Potenza impegnata in kW (default: 3)")
    parser.add_argument("--tipo-tariffa", default="tutte",
                        choices=["tutte", "monoraria", "bioraria", "trioraria"],
                        help="Tipologia tariffa (default: tutte)")
    parser.add_argument("--tipo-offerta", default="tutte",
                        choices=["tutte", "fisso", "variabile"],
                        help="Tipo prezzo (default: tutte)")
    parser.add_argument("--pun", type=float, help="Valore PUN in €/kWh (default: ultimo mensile)")
    parser.add_argument("--escludi-parole", type=str, default="",
                        help="Esclude offerte le cui condizioni contengono queste parole "
                             "(separate da virgola, es: --escludi-parole 'fotovoltaico, pannelli')")
    parser.add_argument("--senza-vincoli", action="store_true",
                        help="Esclude offerte con condizioni limitanti (LIMITANTE=01: "
                             "vincoli, obblighi, requisiti particolari)")
    parser.add_argument("--no-oneri-recesso", action="store_true",
                        help="Escludi offerte con penali/oneri di recesso")
    parser.add_argument("--filtra-venditori", type=str, default="",
                        help="Mostra solo le offerte dei venditori con queste PIVA "
                             "(separate da virgola, es: --filtra-venditori 01877220366,001046)")
    parser.add_argument("--aggiorna-dati", action="store_true",
                        help="Forza il download dei file aggiornati dal portale "
                             "(anziché usare i dati in cache)")
    parser.add_argument("--output", choices=["terminal", "csv", "both"], default="terminal",
                        help="Modalità di output (default: terminal)")
    parser.add_argument("--csv-path", type=str, default="",
                        help="Percorso file CSV di output (default: auto-generato)")
    parser.add_argument("--confronto-portale", action="store_true",
                        help="Esclude costi fissi identici (sigma1/sigma2) per allinearsi al confronto del portale ARERA")
    parser.add_argument("--tipo-attivazione", default="tutte",
                        choices=["tutte", "nuova", "cambio", "voltura", "subentro"],
                        help="Tipo di attivazione (default: tutte)")
    parser.add_argument("--confronto-mia-offerta", action="store_true",
                        help="Confronta con la mia offerta attuale da data/my_offer.json "
                             "(mostra una riga ★ in fondo alla tabella)")
    parser.add_argument("--max", type=int, default=50,
                        help="Numero massimo di offerte da mostrare (default: 50)")
    parser.add_argument("--ignora-sconti-promo", action="store_true",
                        help="Ignora sconti promozionali (validità limitata) nel calcolo annuale")
    parser.add_argument("--regione", type=str, default="",
                        help="Filtra per regione (codice ISTAT a 2 cifre o nome). "
                             "Es: --regione toscana o --regione 09. "
                             "Senza il flag, mostra tutte le offerte incluse quelle geolimitate.")
    parser.add_argument("--verifica", nargs="?", const="normal", default=None,
                        choices=["normal", "strict"],
                        help="Verifica presenza offerte sul sito venditore via Google (Serper.dev). "
                             "'normal' = colonna Check; 'strict' = solo offerte verificate. "
                             "Richiede SERPER_API_KEY.")
    return parser


def parse_args() -> Dict[str, Any]:
    parser = build_parser()
    args = parser.parse_args()

    config = {
        "commodity": args.commodity,
        "tipo_cliente": args.tipo_cliente,
        "residente": args.residente,
        "non_residente": args.non_residente,
        "consumo_annuo": args.consumo_annuo,
        "potenza": args.potenza,
        "tipo_tariffa": args.tipo_tariffa,
        "tipo_offerta": args.tipo_offerta,
        "pun": args.pun,
        "exclude_condizioni": [k.strip() for k in args.escludi_parole.split(",") if k.strip()],
        "solo_semplici": args.senza_vincoli,
        "no_oneri_recesso": args.no_oneri_recesso,
        "venditori": [v.strip() for v in args.filtra_venditori.split(",") if v.strip()],
        "download": args.aggiorna_dati,
        "output": args.output,
        "csv_path": args.csv_path,
        "confronto_portale": args.confronto_portale,
        "tipo_attivazione": args.tipo_attivazione,
        "confronta": args.confronto_mia_offerta,
        "max": args.max,
        "ignora_sconti_promo": args.ignora_sconti_promo,
        "zona": args.regione,
        "verifica": args.verifica,
    }

    # Se mancano dati essenziali, entra in modalità interattiva
    dati_mancanti = (
        config["consumo_annuo"] is None
        or config["tipo_tariffa"] is None
        or (not config["residente"] and not config["non_residente"])
    )
    if dati_mancanti:
        config = _modalita_interattiva(config)

    # Default residente se non specificato e non siamo in interattivo
    if not config["residente"] and not config["non_residente"]:
        config["residente"] = True

    return config


def _modalita_interattiva(config: Dict[str, Any]) -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("  COMPARATORE OFFERTE ENERGIA - Modalità Interattiva")
    print("=" * 60 + "\n")

    if config["commodity"] is None:
        config["commodity"] = _input_choice(
            "Commodity (1=elettrico, 2=gas): ",
            ["elettrico", "gas"],
            shortcut_map=SHORTCUTS_COMMODITY,
            default="elettrico",
        )

    if config["tipo_cliente"] is None:
        config["tipo_cliente"] = _input_choice(
            "Tipo cliente (1=domestico, 2=altri_usi): ",
            ["domestico", "altri_usi"],
            shortcut_map=SHORTCUTS_TIPO_CLIENTE,
            default="domestico",
        )

    if config["consumo_annuo"] is None:
        config["consumo_annuo"] = _input_int("Consumo annuo stimato (kWh): ")

    if config["tipo_tariffa"] is None:
        config["tipo_tariffa"] = _input_choice(
            "Tipologia tariffa (0=tutte, 1=monoraria, 2=bioraria, 3=trioraria): ",
            ["tutte", "monoraria", "bioraria", "trioraria"],
            shortcut_map=SHORTCUTS_TIPO_TARIFFA,
            default="tutte",
        )

    if config["tipo_offerta"] is None:
        config["tipo_offerta"] = _input_choice(
            "Tipo prezzo (0=tutte, 1=fisso, 2=variabile): ",
            ["tutte", "fisso", "variabile"],
            shortcut_map=SHORTCUTS_TIPO_OFFERTA,
            default="tutte",
        )

    if not config["residente"] and not config["non_residente"]:
        config["residente"] = _input_yesno("L'utenza è per la residenza principale (prima casa)?", default=True)
        config["non_residente"] = not config["residente"]

    if config["potenza"] == 3.0:
        val = input(f"Potenza impegnata in kW [3]: ").strip()
        if val:
            try:
                config["potenza"] = float(val.replace(",", "."))
            except ValueError:
                pass

    if config["pun"] is None:
        val = input("Valore PUN in €/kWh (lascia vuoto per ultimo mensile): ").strip()
        if val:
            try:
                config["pun"] = float(val.replace(",", "."))
            except ValueError:
                pass

    if not config["solo_semplici"]:
        config["solo_semplici"] = _input_yesno(
            "Escludere offerte con condizioni limitanti (socio, vincoli, ecc.)?", default=True
        )

    if not config["no_oneri_recesso"]:
        config["no_oneri_recesso"] = _input_yesno(
            "Escludere offerte con penali/oneri di recesso?", default=True
        )

    if config["tipo_attivazione"] == "tutte":
        config["tipo_attivazione"] = _input_choice(
            "Tipo attivazione (0=tutte, 1=nuova, 2=cambio, 3=voltura, 4=subentro): ",
            ["tutte", "nuova", "cambio", "voltura", "subentro"],
            shortcut_map={
                "0": "tutte", "a": "tutte",
                "1": "nuova", "n": "nuova",
                "2": "cambio", "c": "cambio",
                "3": "voltura", "v": "voltura",
                "4": "subentro", "s": "subentro",
            },
            default="tutte",
        )

    if config["output"] is None:
        config["output"] = _input_choice(
            "Output (1=terminal, 2=csv, 3=both): ",
            ["terminal", "csv", "both"],
            shortcut_map=SHORTCUTS_OUTPUT,
            default="terminal",
        )

    print("\n" + "=" * 60)
    return config
