"""Formattazione output: tabella terminale e CSV."""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict


def _color(text: str, color: str) -> str:
    """Applica colore ANSI al testo."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


TIPO_MAP = {"fisso": "Fix", "variabile": "Var"}
TARIFFA_MAP = {"monoraria": "Mono", "bioraria": "Bi", "trifaria": "Tri"}


def _vislen(s: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def stampa_tabella(risultati: List[Dict], limite: int = 50):
    """Stampa una tabella formattata a terminale."""
    if not risultati:
        print(_color("Nessuna offerta trovata con i filtri specificati.", "yellow"))
        return

    # I risultati arrivano già ordinati da main.py
    mia_offerta = next((r for r in risultati if r.get("_mia")), None)
    pos_mia = next((i for i, r in enumerate(risultati) if r.get("_mia")), None)

    totali = len(risultati)
    mostra = min(limite, totali)
    r0 = risultati[0]
    pun_usato = r0.get("pun_usato", 0)
    on_fissi = r0.get("oneri_fissi_sistema", 0)
    on_en = r0.get("oneri_energia_sistema", 0)
    print(f"\n{_color('RISULTATI', 'bold')} ({totali} offerte trovate, prime {mostra} mostrate)\n")
    print(f"   PUN: {pun_usato:.4f} €/kWh")
    print(f"   Oneri fissi sistema: {on_fissi:.2f} €/anno | Oneri energia: {on_en:.2f} €/anno\n")

    # Header
    fmt_header = "{:<3} {:<17} {:<40} {:<32} {:<5} {:<7} {:<6} {:<5} {:<12} {}"
    header = fmt_header.format(
        "#", "Venditore", "Offerta", "Cod.Offerta", "Tipo", "Tariffa",
        "Check", "Conf", "Spesa Tot.", "Spesa Vend.",
    )
    print(_color(header, "bold"))
    print(_color("-" * len(header), "bold"))

    for i, r in enumerate(risultati[:limite], 1):
        if r.get("_mia"):
            if pos_mia > 0:
                print(_color("-" * len(header), "bold"))
            rank = _color("★", "cyan") + "  "
            nome = r.get("nome_offerta", "")[:38]
        else:
            rank = str(i)
            nome = r.get("nome_offerta", "")[:38]

        venditore = (r.get("nome_venditore", "") or r.get("venditore", ""))[:15]
        codice = r.get("cod_offerta", "")
        tipo = TIPO_MAP.get(r.get("tipo_offerta", ""), r.get("tipo_offerta", ""))[:5]
        tariffa = TARIFFA_MAP.get(r.get("tipologia_fasce", ""), r.get("tipologia_fasce", ""))[:5]
        spesa_tot = f"{r.get('spesa_totale', 0):.2f}"
        spesa_vend = f"{r.get('spesa_venditore', 0):.2f}"

        conf = r.get("confidenza", "green")
        conf_dot = _color("●", conf)
        conf_fmt = " " + conf_dot
        conf_fmt += " " * max(0, 5 - _vislen(conf_fmt))

        check = r.get("check", "")
        if check:
            simboli = check.split(" ")
            colored = []
            for s in simboli:
                if s == "✓":
                    colored.append(_color("✓", "green"))
                elif s in ("✗", "!"):
                    colored.append(_color(s, "red"))
                else:
                    colored.append(s)
            check_fmt = " " + " ".join(colored)
        else:
            check_fmt = " " + _color("?", "yellow") + " " + _color("?", "yellow")
        check_fmt += " " * max(0, 6 - _vislen(check_fmt))
        row = f"{rank:<3} {venditore:<17} {nome:<40} {codice:<32} {tipo:<5} {tariffa:<7} {check_fmt} {conf_fmt} {spesa_tot:<12} {spesa_vend}"
        print(row)

    # Se mia offerta è fuori dalla top N, mostra in fondo
    if mia_offerta and pos_mia is not None and pos_mia >= limite:
        print(_color("-" * len(header), "bold"))
        r = mia_offerta
        venditore = (r.get("venditore", "") or "")[:15]
        nome = r.get("nome_offerta", "")[:38]
        codice = r.get("cod_offerta", "")
        tipo = TIPO_MAP.get(r.get("tipo_offerta", ""), r.get("tipo_offerta", ""))[:5]
        tariffa = TARIFFA_MAP.get(r.get("tipologia_fasce", ""), r.get("tipologia_fasce", ""))[:5]
        spesa_tot = f"{r.get('spesa_totale', 0):.2f}"
        spesa_vend = f"{r.get('spesa_venditore', 0):.2f}"
        check_mia = mia_offerta.get("check", "")
        if check_mia:
            check_fmt = " " + check_mia
            check_fmt += " " * max(0, 6 - _vislen(check_fmt))
        else:
            check_fmt = f" {_color('?', 'yellow')} {_color('?', 'yellow')} "
        row = f"{_color('★', 'cyan')}   {venditore:<17} {nome:<40} {codice:<32} {tipo:<5} {tariffa:<7} {check_fmt} {'':5} {spesa_tot:<12} {spesa_vend}"
        print(row)

    print("\n" + _color("Nota: gli importi sono stimati (IVA inclusa in Spesa Tot.).", "yellow"))
    print(_color("PUN usato: {:.4f} €/kWh. Usa --pun per cambiarlo.".format(
        risultati[0].get("pun_usato", 0) if risultati else 0), "cyan"))


def esporta_csv(risultati: List[Dict], output_path: Path):
    """Esporta i risultati in un file CSV."""
    if not risultati:
        print(_color("Nessun dato da esportare.", "yellow"))
        return

    fieldnames = [
        "rank", "cod_offerta", "venditore", "nome_venditore", "nome_offerta", "tipo_offerta",
        "tipologia_fasce", "check", "confidenza", "spesa_totale", "spesa_venditore",
        "costo_fisso_venditore", "costo_potenza_venditore",
        "costo_energia_venditore", "costo_pun", "oneri_fissi_sistema",
        "oneri_energia_sistema", "iva", "pun_usato", "url_offerta",
        "condizioni_limitanti", "descrizione_condizioni",
    ]

    # Filtra mia offerta dal ranking
    risultati_csv = [r for r in risultati if not r.get("_mia")]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(risultati_csv, 1):
            row = {k: r.get(k, "") for k in fieldnames}
            row["rank"] = i
            writer.writerow(row)

        # Aggiungi riga mia offerta in fondo
        mia = next((r for r in risultati if r.get("_mia")), None)
        if mia:
            row = {k: mia.get(k, "") for k in fieldnames}
            row["rank"] = "★"
            writer.writerow(row)

    print(_color(f"\nCSV esportato: {output_path}", "green"))
