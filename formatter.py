"""Formattazione output: tabella terminale e CSV."""

import csv
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


def stampa_tabella(risultati: List[Dict], limite: int = 50):
    """Stampa una tabella formattata a terminale."""
    if not risultati:
        print(_color("Nessuna offerta trovata con i filtri specificati.", "yellow"))
        return

    print(f"\n{_color('RISULTATI', 'bold')} ({len(risultati)} offerte trovate, prime {min(limite, len(risultati))} mostrate):\n")

    # Header — stessi formati delle righe dati
    fmt_header = "{:<3} {:<22} {:<35} {:<10} {:<10} {:<20} {:<18} {:<8} {}"
    header = fmt_header.format(
        "#", "Venditore", "Offerta", "Tipo", "Tariffa",
        "Spesa Totale €/anno", "Spesa Venditore", "PUN", "Condizioni",
    )
    print(_color(header, "bold"))
    print(_color("-" * len(header), "bold"))

    for i, r in enumerate(risultati[:limite], 1):
        venditore = (r.get("nome_venditore", "") or r.get("venditore", ""))[:20]
        nome = r.get("nome_offerta", "")[:33]
        tipo = r.get("tipo_offerta", "")[:10]
        tariffa = r.get("tipologia_fasce", "")[:10]
        spesa_tot = f"{r.get('spesa_totale', 0):.2f}"
        spesa_vend = f"{r.get('spesa_venditore', 0):.2f}"
        pun = f"{r.get('pun_usato', 0):.4f}"
        cond = "Sì" if r.get("condizioni_limitanti", False) else "No"

        row = f"{i:<3} {venditore:<22} {nome:<35} {tipo:<10} {tariffa:<10} {spesa_tot:<20} {spesa_vend:<18} {pun:<8} {cond}"
        print(row)

    print("\n" + _color("Nota: gli importi sono stimati (IVA inclusa: 10% residente / 22% non residente).", "yellow"))
    print(_color("Il PUN è parametrico: usa --pun per simulare diversi scenari.", "cyan"))


def esporta_csv(risultati: List[Dict], output_path: Path):
    """Esporta i risultati in un file CSV."""
    if not risultati:
        print(_color("Nessun dato da esportare.", "yellow"))
        return

    fieldnames = [
        "rank", "cod_offerta", "venditore", "nome_venditore", "nome_offerta", "tipo_offerta",
        "tipologia_fasce", "spesa_totale", "spesa_venditore",
        "costo_fisso_venditore", "costo_potenza_venditore",
        "costo_energia_venditore", "costo_pun", "oneri_fissi_sistema",
        "oneri_energia_sistema", "pun_usato", "url_offerta",
        "condizioni_limitanti", "descrizione_condizioni",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(risultati, 1):
            row = {k: r.get(k, "") for k in fieldnames}
            row["rank"] = i
            writer.writerow(row)

    print(_color(f"\nCSV esportato: {output_path}", "green"))
