"""Gestione database SQLite per le offerte."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import sqlite3
from contextlib import contextmanager

from parser import (
    Offerta,
    ComponenteImpresa,
    CondizioneContrattuale,
    Sconto,
    IntervalloPrezzo,
)


# Booleani estratti con LLM e conservati nella tabella principale per filtri veloci.
FEATURES_BOOLEAN = [
    "has_vincoli_limitanti",
    "has_penali_recesso",
    "has_morosita",
    "has_deposito_cauzionale",
    "has_fotovoltaico",
    "has_soci_coop",
    "has_obbligo_requisito",
    "is_geolimitata",
    "is_promozionale",
    "has_sconto_sdd",
    "has_sconto_digitale",
    "has_sconto_benvenuto",
    "has_sconto_fedelta",
    "has_sconto_green",
    "has_sconto_dualfuel",
    "has_sconto_cessione_credito",
    "has_sconto_una_tantum",
    "has_sconto_come_back",
]


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """Crea lo schema del DB se non esiste."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def _offerta_id(conn: sqlite3.Connection, piva: str, cod_offerta: str) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM offerte WHERE piva_utente = ? AND cod_offerta = ?",
        (piva, cod_offerta),
    ).fetchone()
    return row["id"] if row else None


def _insert_offerta(conn: sqlite3.Connection, offerta: Offerta, features: Dict[str, bool]) -> int:
    """Inserisce o sostituisce un'offerta e restituisce il suo id."""
    cols = [
        "piva_utente",
        "cod_offerta",
        "nome_offerta",
        "descrizione",
        "tipo_cliente",
        "tipo_offerta",
        "tipologia_fasce",
        "durata",
        "garanzie",
        "modalita_attivazione",
        "telefono",
        "url_sito",
        "url_offerta",
        "data_inizio",
        "data_fine",
        "consumo_min",
        "consumo_max",
        "modalita_pagamento",
        "tipo_dispacciamento",
        "nome_dispacciamento",
        "estratto",
        "data_ultimo_aggiornamento",
    ] + FEATURES_BOOLEAN

    values = [
        offerta.piva_utente,
        offerta.cod_offerta,
        offerta.nome_offerta,
        offerta.descrizione,
        offerta.tipo_cliente,
        offerta.tipo_offerta,
        offerta.tipologia_fasce,
        offerta.durata,
        offerta.garanzie,
        offerta.modalita_attivazione,
        offerta.telefono,
        offerta.url_sito,
        offerta.url_offerta,
        offerta.data_inizio,
        offerta.data_fine,
        offerta.consumo_min,
        offerta.consumo_max,
        offerta.modalita_pagamento,
        offerta.tipo_dispacciamento,
        offerta.nome_dispacciamento,
        0,  # estratto
        None,  # data_ultimo_aggiornamento verrà impostata dal trigger
    ]
    values += [int(features.get(f, False)) for f in FEATURES_BOOLEAN]

    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    updates = ", ".join([f"{c}=excluded.{c}" for c in cols])

    sql = f"""
        INSERT INTO offerte ({col_names})
        VALUES ({placeholders})
        ON CONFLICT(piva_utente, cod_offerta) DO UPDATE SET
            {updates}
        RETURNING id
    """
    row = conn.execute(sql, values).fetchone()
    return row["id"]


def _insert_componenti(conn: sqlite3.Connection, offerta_id: int, componenti: List[ComponenteImpresa]) -> None:
    for comp in componenti:
        cur = conn.execute(
            """
            INSERT INTO componenti (offerta_id, nome, descrizione, tipologia, macroarea)
            VALUES (?, ?, ?, ?, ?)
            """,
            (offerta_id, comp.nome, comp.descrizione, comp.tipologia, comp.macroarea),
        )
        componente_id = cur.lastrowid
        for p in comp.prezzi:
            conn.execute(
                """
                INSERT INTO prezzi_componenti
                    (componente_id, fascia, prezzo, unita_misura, consumo_da, consumo_a)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    componente_id,
                    p.fascia,
                    p.prezzo,
                    p.unita_misura,
                    p.consumo_da,
                    p.consumo_a,
                ),
            )


def _insert_condizioni(conn: sqlite3.Connection, offerta_id: int, condizioni: List[CondizioneContrattuale]) -> None:
    for c in condizioni:
        conn.execute(
            """
            INSERT INTO condizioni (offerta_id, tipologia, descrizione, limitante)
            VALUES (?, ?, ?, ?)
            """,
            (offerta_id, c.tipologia, c.descrizione, int(c.limitante)),
        )


def _insert_sconti(conn: sqlite3.Connection, offerta_id: int, sconti: List[Sconto]) -> None:
    for sc in sconti:
        cur = conn.execute(
            """
            INSERT INTO sconti
                (offerta_id, nome, descrizione, validita, iva_sconto,
                 condizione_applicazione, durata_mesi)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offerta_id,
                sc.nome,
                sc.descrizione,
                sc.validita,
                sc.iva_sconto,
                sc.condizione_applicazione,
                sc.durata_mesi,
            ),
        )
        sconto_id = cur.lastrowid
        for p in sc.prezzi:
            conn.execute(
                """
                INSERT INTO prezzi_sconti (sconto_id, fascia, prezzo, unita_misura)
                VALUES (?, ?, ?, ?)
                """,
                (sconto_id, p.fascia, p.prezzo, p.unita_misura),
            )


def _insert_regioni(conn: sqlite3.Connection, offerta_id: int, regioni: List[str]) -> None:
    for r in regioni:
        conn.execute(
            "INSERT INTO regioni (offerta_id, codice) VALUES (?, ?)",
            (offerta_id, r),
        )


def _insert_tipologie_attivazione(conn: sqlite3.Connection, offerta_id: int, tipologie: List[str]) -> None:
    for t in tipologie:
        conn.execute(
            "INSERT INTO tipologie_attivazione (offerta_id, tipo) VALUES (?, ?)",
            (offerta_id, t),
        )


def _insert_tag_estratti(
    conn: sqlite3.Connection, offerta_id: int, tags: List[Dict[str, Any]]
) -> None:
    for tag in tags:
        conn.execute(
            """
            INSERT INTO tag_estratti
                (offerta_id, tag, valore, tipo, confidenza, source, modello, ts_estrazione)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offerta_id,
                tag["tag"],
                tag.get("valore"),
                tag.get("tipo", "text"),
                tag.get("confidenza"),
                tag.get("source"),
                tag.get("modello"),
                tag.get("ts_estrazione"),
            ),
        )


def save_offerta(
    db_path: Path,
    offerta: Offerta,
    features: Optional[Dict[str, bool]] = None,
    tags: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Upsert di una singola offerta con le relative feature e tag."""
    with _connect(db_path) as conn:
        _save_offerta_in_transaction(conn, offerta, features or {}, tags or [])
        conn.commit()


def save_offerte(
    db_path: Path,
    offerte: List[Offerta],
    features_map: Optional[Dict[str, Dict[str, bool]]] = None,
    tags_map: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    """Upsert di una lista di offerte. features_map e tags_map sono indicizzati per cod_offerta."""
    features_map = features_map or {}
    tags_map = tags_map or {}
    with _connect(db_path) as conn:
        for offerta in offerte:
            features = features_map.get(offerta.cod_offerta, {})
            tags = tags_map.get(offerta.cod_offerta, [])
            _save_offerta_in_transaction(conn, offerta, features, tags)
        conn.commit()


def _save_offerta_in_transaction(
    conn: sqlite3.Connection,
    offerta: Offerta,
    features: Dict[str, bool],
    tags: List[Dict[str, Any]],
) -> None:
    offerta_id = _insert_offerta(conn, offerta, features)

    # elimina i figli precedenti (full refresh per l'offerta)
    for tbl in ("componenti", "condizioni", "sconti", "regioni", "tipologie_attivazione", "tag_estratti"):
        conn.execute(f"DELETE FROM {tbl} WHERE offerta_id = ?", (offerta_id,))

    _insert_componenti(conn, offerta_id, offerta.componenti)
    _insert_condizioni(conn, offerta_id, offerta.condizioni)
    _insert_sconti(conn, offerta_id, offerta.sconti)
    _insert_regioni(conn, offerta_id, offerta.regioni)
    _insert_tipologie_attivazione(conn, offerta_id, offerta.tipologie_att_contr)
    _insert_tag_estratti(conn, offerta_id, tags)

    conn.execute(
        "UPDATE offerte SET estratto = 1, data_ultimo_aggiornamento = CURRENT_TIMESTAMP WHERE id = ?",
        (offerta_id,),
    )


def load_offerte(db_path: Path) -> List[Offerta]:
    """Carica tutte le offerte dal DB ricostruendo gli oggetti Python."""
    with _connect(db_path) as conn:
        # 1. Offerte
        rows = conn.execute("SELECT * FROM offerte").fetchall()

        # 2. Componenti
        componenti_by_id: Dict[int, ComponenteImpresa] = {}
        componenti_by_offerta: Dict[int, List[ComponenteImpresa]] = {}
        for comp_row in conn.execute("SELECT * FROM componenti"):
            comp = ComponenteImpresa(
                nome=comp_row["nome"],
                descrizione=comp_row["descrizione"],
                tipologia=comp_row["tipologia"],
                macroarea=comp_row["macroarea"],
                prezzi=[],
            )
            componenti_by_id[comp_row["id"]] = comp
            componenti_by_offerta.setdefault(comp_row["offerta_id"], []).append(comp)

        # 3. Prezzi componenti
        for p in conn.execute("SELECT * FROM prezzi_componenti"):
            comp = componenti_by_id.get(p["componente_id"])
            if comp is None:
                continue
            comp.prezzi.append(
                IntervalloPrezzo(
                    fascia=p["fascia"],
                    prezzo=p["prezzo"],
                    unita_misura=p["unita_misura"],
                    consumo_da=p["consumo_da"],
                    consumo_a=p["consumo_a"],
                )
            )

        # 4. Condizioni
        condizioni_by_offerta: Dict[int, List[CondizioneContrattuale]] = {}
        for c in conn.execute("SELECT * FROM condizioni"):
            cond = CondizioneContrattuale(
                tipologia=c["tipologia"],
                descrizione=c["descrizione"],
                limitante=bool(c["limitante"]),
            )
            condizioni_by_offerta.setdefault(c["offerta_id"], []).append(cond)

        # 5. Sconti
        sconti_by_id: Dict[int, Sconto] = {}
        sconti_by_offerta: Dict[int, List[Sconto]] = {}
        for sc_row in conn.execute("SELECT * FROM sconti"):
            sc = Sconto(
                nome=sc_row["nome"],
                descrizione=sc_row["descrizione"],
                validita=sc_row["validita"],
                iva_sconto=sc_row["iva_sconto"],
                condizione_applicazione=sc_row["condizione_applicazione"],
                durata_mesi=sc_row["durata_mesi"],
                prezzi=[],
            )
            sconti_by_id[sc_row["id"]] = sc
            sconti_by_offerta.setdefault(sc_row["offerta_id"], []).append(sc)

        # 6. Prezzi sconti
        for p in conn.execute("SELECT * FROM prezzi_sconti"):
            sc = sconti_by_id.get(p["sconto_id"])
            if sc is None:
                continue
            sc.prezzi.append(
                IntervalloPrezzo(
                    fascia=p["fascia"],
                    prezzo=p["prezzo"],
                    unita_misura=p["unita_misura"],
                )
            )

        # 7. Regioni
        regioni_by_offerta: Dict[int, List[str]] = {}
        for r in conn.execute("SELECT * FROM regioni"):
            regioni_by_offerta.setdefault(r["offerta_id"], []).append(r["codice"])

        # 8. Tipologie attivazione
        tipologie_by_offerta: Dict[int, List[str]] = {}
        for t in conn.execute("SELECT * FROM tipologie_attivazione"):
            tipologie_by_offerta.setdefault(t["offerta_id"], []).append(t["tipo"])

        # 9. Assemblaggio
        offerte = []
        for row in rows:
            offerta_id = row["id"]
            offerte.append(
                Offerta(
                    piva_utente=row["piva_utente"],
                    cod_offerta=row["cod_offerta"],
                    nome_offerta=row["nome_offerta"],
                    descrizione=row["descrizione"],
                    tipo_cliente=row["tipo_cliente"],
                    tipo_offerta=row["tipo_offerta"],
                    tipologia_fasce=row["tipologia_fasce"],
                    durata=row["durata"],
                    garanzie=row["garanzie"],
                    modalita_attivazione=row["modalita_attivazione"],
                    telefono=row["telefono"],
                    url_sito=row["url_sito"],
                    url_offerta=row["url_offerta"],
                    data_inizio=row["data_inizio"],
                    data_fine=row["data_fine"],
                    consumo_min=row["consumo_min"],
                    consumo_max=row["consumo_max"],
                    modalita_pagamento=row["modalita_pagamento"],
                    tipo_dispacciamento=row["tipo_dispacciamento"],
                    nome_dispacciamento=row["nome_dispacciamento"],
                    regioni=regioni_by_offerta.get(offerta_id, []),
                    tipologie_att_contr=tipologie_by_offerta.get(offerta_id, []),
                    componenti=componenti_by_offerta.get(offerta_id, []),
                    condizioni=condizioni_by_offerta.get(offerta_id, []),
                    sconti=sconti_by_offerta.get(offerta_id, []),
                )
            )
        return offerte


def save_parametri(
    db_path: Path, data_riferimento: str, parametri: Dict[str, float]
) -> None:
    """Salva i parametri di sistema per una data di riferimento."""
    with _connect(db_path) as conn:
        for nome, valore in parametri.items():
            conn.execute(
                """
                INSERT INTO parametri_sistema (data_riferimento, nome, valore)
                VALUES (?, ?, ?)
                ON CONFLICT(data_riferimento, nome) DO UPDATE SET valore=excluded.valore
                """,
                (data_riferimento, nome, valore),
            )
        conn.commit()


def save_prezzi(
    db_path: Path, data_riferimento: str, prezzi: Dict[str, float]
) -> None:
    """Salva i prezzi storici per una data di riferimento."""
    with _connect(db_path) as conn:
        for indicatore, valore in prezzi.items():
            if valore is None:
                continue
            conn.execute(
                """
                INSERT INTO prezzi_storici (data_riferimento, indicatore, valore)
                VALUES (?, ?, ?)
                ON CONFLICT(data_riferimento, indicatore) DO UPDATE SET valore=excluded.valore
                """,
                (data_riferimento, indicatore, valore),
            )
        conn.commit()


def _latest_data_riferimento(conn: sqlite3.Connection, table: str) -> Optional[str]:
    row = conn.execute(
        f"SELECT MAX(data_riferimento) AS d FROM {table}"
    ).fetchone()
    return row["d"] if row else None


def load_parametri(db_path: Path) -> Dict[str, float]:
    """Carica i parametri di sistema più recenti."""
    with _connect(db_path) as conn:
        data = _latest_data_riferimento(conn, "parametri_sistema")
        if not data:
            return {}
        rows = conn.execute(
            "SELECT nome, valore FROM parametri_sistema WHERE data_riferimento = ?",
            (data,),
        ).fetchall()
        return {r["nome"]: r["valore"] for r in rows}


def load_prezzi(db_path: Path) -> Dict[str, float]:
    """Carica i prezzi storici più recenti."""
    with _connect(db_path) as conn:
        data = _latest_data_riferimento(conn, "prezzi_storici")
        if not data:
            return {}
        rows = conn.execute(
            "SELECT indicatore, valore FROM prezzi_storici WHERE data_riferimento = ?",
            (data,),
        ).fetchall()
        return {r["indicatore"]: r["valore"] for r in rows}


def prune_offerte(db_path: Path, codici_attivi: List[str]) -> int:
    """
    Elimina dal DB le offerte il cui cod_offerta non è presente nella lista.
    Ritorna il numero di offerte eliminate.
    """
    if not codici_attivi:
        return 0
    with _connect(db_path) as conn:
        placeholders = ",".join(["?"] * len(codici_attivi))
        cur = conn.execute(
            f"DELETE FROM offerte WHERE cod_offerta NOT IN ({placeholders})",
            codici_attivi,
        )
        conn.commit()
        return cur.rowcount


_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS offerte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    piva_utente TEXT NOT NULL,
    cod_offerta TEXT NOT NULL,
    nome_offerta TEXT,
    descrizione TEXT,
    tipo_cliente TEXT,
    tipo_offerta TEXT,
    tipologia_fasce TEXT,
    durata TEXT,
    garanzie TEXT,
    modalita_attivazione TEXT,
    telefono TEXT,
    url_sito TEXT,
    url_offerta TEXT,
    data_inizio TEXT,
    data_fine TEXT,
    consumo_min INTEGER,
    consumo_max INTEGER,
    modalita_pagamento TEXT,
    tipo_dispacciamento TEXT,
    nome_dispacciamento TEXT,
    estratto INTEGER DEFAULT 0,
    data_ultimo_aggiornamento TEXT,
    {', '.join([f + ' INTEGER DEFAULT 0' for f in FEATURES_BOOLEAN])},
    UNIQUE(piva_utente, cod_offerta)
);

CREATE TABLE IF NOT EXISTS componenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offerta_id INTEGER NOT NULL REFERENCES offerte(id) ON DELETE CASCADE,
    nome TEXT,
    descrizione TEXT,
    tipologia TEXT,
    macroarea TEXT
);

CREATE TABLE IF NOT EXISTS prezzi_componenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    componente_id INTEGER NOT NULL REFERENCES componenti(id) ON DELETE CASCADE,
    fascia TEXT,
    prezzo REAL,
    unita_misura TEXT,
    consumo_da INTEGER,
    consumo_a INTEGER
);

CREATE TABLE IF NOT EXISTS condizioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offerta_id INTEGER NOT NULL REFERENCES offerte(id) ON DELETE CASCADE,
    tipologia TEXT,
    descrizione TEXT,
    limitante INTEGER
);

CREATE TABLE IF NOT EXISTS sconti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offerta_id INTEGER NOT NULL REFERENCES offerte(id) ON DELETE CASCADE,
    nome TEXT,
    descrizione TEXT,
    validita TEXT,
    iva_sconto TEXT,
    condizione_applicazione TEXT,
    durata_mesi INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prezzi_sconti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sconto_id INTEGER NOT NULL REFERENCES sconti(id) ON DELETE CASCADE,
    fascia TEXT,
    prezzo REAL,
    unita_misura TEXT
);

CREATE TABLE IF NOT EXISTS regioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offerta_id INTEGER NOT NULL REFERENCES offerte(id) ON DELETE CASCADE,
    codice TEXT
);

CREATE TABLE IF NOT EXISTS tipologie_attivazione (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offerta_id INTEGER NOT NULL REFERENCES offerte(id) ON DELETE CASCADE,
    tipo TEXT
);

CREATE TABLE IF NOT EXISTS tag_estratti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offerta_id INTEGER NOT NULL REFERENCES offerte(id) ON DELETE CASCADE,
    tag TEXT,
    valore TEXT,
    tipo TEXT,
    confidenza REAL,
    source TEXT,
    modello TEXT,
    ts_estrazione TEXT
);

CREATE TABLE IF NOT EXISTS parametri_sistema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_riferimento TEXT NOT NULL,
    nome TEXT NOT NULL,
    valore REAL,
    UNIQUE(data_riferimento, nome)
);

CREATE TABLE IF NOT EXISTS prezzi_storici (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_riferimento TEXT NOT NULL,
    indicatore TEXT NOT NULL,
    valore REAL,
    UNIQUE(data_riferimento, indicatore)
);

CREATE INDEX IF NOT EXISTS idx_offerte_piva_cod ON offerte(piva_utente, cod_offerta);
CREATE INDEX IF NOT EXISTS idx_offerte_tipo ON offerte(tipo_cliente, tipo_offerta, tipologia_fasce);
CREATE INDEX IF NOT EXISTS idx_componenti_offerta ON componenti(offerta_id);
CREATE INDEX IF NOT EXISTS idx_condizioni_offerta ON condizioni(offerta_id);
CREATE INDEX IF NOT EXISTS idx_sconti_offerta ON sconti(offerta_id);
CREATE INDEX IF NOT EXISTS idx_regioni_offerta ON regioni(offerta_id);
CREATE INDEX IF NOT EXISTS idx_tipologie_attivazione_offerta ON tipologie_attivazione(offerta_id);
CREATE INDEX IF NOT EXISTS idx_tag_estratti_offerta ON tag_estratti(offerta_id);
CREATE INDEX IF NOT EXISTS idx_tag_estratti_tag ON tag_estratti(tag);
CREATE INDEX IF NOT EXISTS idx_parametri_data ON parametri_sistema(data_riferimento);
CREATE INDEX IF NOT EXISTS idx_prezzi_data ON prezzi_storici(data_riferimento);
"""
