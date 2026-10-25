"""Popolamento e aggiornamento del database SQLite con le offerte ARERA."""
import re
from pathlib import Path
from typing import List, Optional

from config import DATA_DIR
from database import init_db, save_offerte, save_parametri, save_prezzi
from downloader import ottieni_file_open_data
from parser import Offerta, parse_xml_offerte, parse_csv_parametri, parse_csv_prezzi


def default_db_path(commodity: str = "elettrico") -> Path:
    return DATA_DIR / ("offerte_gas.db" if commodity == "gas" else "offerte.db")


def _data_riferimento_da_path(path: Path) -> str:
    """Estrae la data YYYYMMDD dal nome del file, oppure ritorna lo stem."""
    m = re.search(r"(\d{8})\.(csv|xml)$", path.name)
    return m.group(1) if m else path.stem

def popola(
    db_path: Optional[Path] = None,
    commodity: str = "elettrico",
    forza_download: bool = False,
    no_llm: bool = False,
    batch_size: int = 50,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_base_url: Optional[str] = None,
    no_rule_based: bool = False,
) -> int:
    """
    Scarica i file open data, parsa le offerte, estrae le feature con LLM e salva nel DB.
    Ritorna il numero di offerte inserite/aggiornate.
    """
    db_path = db_path or default_db_path(commodity)
    init_db(db_path)

    print(f"[popola-db] Scaricamento dati {commodity}...")
    xml_path, csv_path, prezzi_path = ottieni_file_open_data(commodity, forza_download=forza_download)
    print(f"[popola-db] XML: {xml_path}")
    print(f"[popola-db] Parametri: {csv_path}")
    print(f"[popola-db] Prezzi: {prezzi_path}")

    print("[popola-db] Parsing XML...")
    offerte: List[Offerta] = parse_xml_offerte(xml_path, commodity=commodity)
    print(f"[popola-db] Offerte trovate: {len(offerte)}")

    print("[popola-db] Parsing parametri di sistema e prezzi storici...")
    parametri = parse_csv_parametri(csv_path)
    prezzi = parse_csv_prezzi(prezzi_path)
    data_rif = _data_riferimento_da_path(csv_path)

    features_map = {}
    tags_map = {}
    if not no_llm:
        # Di default usiamo solo euristiche rule-based (Piano A). L'LLM locale è
        # lasciato come opzione avanzata perché con modelli come Gemma 3 12B Q8_0
        # richiede ~15-20s/offerta, rendendo impraticabile il popolamento di
        # ~3.300 offerte. Per forzare l'LLM usare --no-rule-based.
        use_llm = no_rule_based
        use_rule_based = not no_rule_based
        mode = "LLM" if use_llm else "rule-based"
        print(f"[popola-db] Estrazione feature testuali ({mode})...")
        from extractor import extract_features
        features_map, tags_map = extract_features(
            offerte,
            provider_name=llm_provider,
            model=llm_model,
            base_url=llm_base_url,
            batch_size=batch_size,
            use_rule_based=use_rule_based,
            use_llm=use_llm,
        )
    else:
        print("[popola-db] Estrazione disabilitata: i booleani saranno lasciati a 0.")

    print("[popola-db] Salvataggio nel DB...")
    save_parametri(db_path, data_rif, parametri)
    save_prezzi(db_path, data_rif, prezzi)
    # Salva a chunk per non creare una transazione troppo lunga
    chunk_size = 500
    for i in range(0, len(offerte), chunk_size):
        chunk = offerte[i : i + chunk_size]
        save_offerte(db_path, chunk, features_map, tags_map)
        print(f"[popola-db] Salvate {min(i + chunk_size, len(offerte))}/{len(offerte)} offerte")

    print("[popola-db] Pulizia offerte non più presenti nello XML...")
    from database import prune_offerte
    eliminate = prune_offerte(db_path, [o.cod_offerta for o in offerte])
    print(f"[popola-db] Offerte eliminate: {eliminate}")

    print(f"[popola-db] Completato: {len(offerte)} offerte nel DB.")
    return len(offerte)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Popola il DB offerte ARERA")
    parser.add_argument("--db-path", type=str, default="", help="Percorso DB SQLite")
    parser.add_argument("--commodity", default="elettrico", choices=["elettrico", "gas"])
    parser.add_argument("--forza-download", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--llm-provider", default="auto")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--no-rule-based", action="store_true",
                        help="Forza l'estrazione di tutte le feature con LLM, saltando l'euristica rule-based")
    args = parser.parse_args()

    db = Path(args.db_path) if args.db_path else default_db_path(args.commodity)
    popola(
        db_path=db,
        commodity=args.commodity,
        forza_download=args.forza_download,
        no_llm=args.no_llm,
        batch_size=args.batch_size,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_base_url=args.llm_base_url,
        no_rule_based=args.no_rule_based,
    )
