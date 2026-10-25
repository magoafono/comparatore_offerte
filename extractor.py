"""Estrazione di feature dalle offerte tramite LLM e regole.

Supporta tre provider:
- zenmux (API compatibile OpenAI)
- openrouter (API compatibile OpenAI)
- ollama (endpoint /api/chat locale)

Modalità ibrida (default):
1. Estrae le feature deterministiche con regole/keyword.
2. Invia all'LLM solo le offerte che hanno almeno una feature ambigua (None).
3. Merge: regole sovrascrivono l'LLM, l'LLM riempie solo i None.
"""
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import fnmatch
import httpx
from dotenv import load_dotenv

from config import BLACKLIST_CONDIZIONI_DEFAULT
from parser import Offerta, has_penale_recesso

# Carica .env se presente; le variabili d'ambiente hanno la precedenza.
load_dotenv()

# Booleani che vengono normalizzati sulla tabella offerte.
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

# Chiavi corte per l'output LLM: abbastanza parlanti da non confondere i
# modelli piccoli, ma compatte per ridurre i token generati.
COMPACT_KEYS: Dict[str, str] = {
    "has_vincoli_limitanti": "vcl",
    "has_penali_recesso": "pnl",
    "has_morosita": "mrs",
    "has_deposito_cauzionale": "dep",
    "has_fotovoltaico": "fv",
    "has_soci_coop": "soc",
    "has_obbligo_requisito": "obl",
    "is_geolimitata": "geo",
    "is_promozionale": "prm",
    "has_sconto_sdd": "sdd",
    "has_sconto_digitale": "dig",
    "has_sconto_benvenuto": "bnv",
    "has_sconto_fedelta": "fld",
    "has_sconto_green": "grn",
    "has_sconto_dualfuel": "dfl",
    "has_sconto_cessione_credito": "ces",
    "has_sconto_una_tantum": "unt",
    "has_sconto_come_back": "cbk",
}

FULL_KEYS: Dict[str, str] = {v: k for k, v in COMPACT_KEYS.items()}

COMPACT_DESCRIPTIONS: List[Tuple[str, str]] = [
    ("vcl", "vincoli limitanti (trappole, obblighi, requisiti pesanti)"),
    ("pnl", "penali di recesso anticipato"),
    ("mrs", "mora/ritardo pagamento con effetti sull'offerta"),
    ("dep", "deposito cauzionale"),
    ("fv", "pannelli fotovoltaici obbligatori/legati all'offerta"),
    ("soc", "socio/associato/cooperativa"),
    ("obl", "obbligo o requisito particolare"),
    ("geo", "offerta geolimitata a regioni/province"),
    ("prm", "offerta/sconto promozionale a durata limitata"),
    ("sdd", "sconto con addebito diretto/SDD"),
    ("dig", "sconto digitale/fattura online"),
    ("bnv", "sconto benvenuto/nuovo cliente/primo anno"),
    ("fld", "sconto fedelta/fidelizzazione"),
    ("grn", "sconto green/rinnovabili"),
    ("dfl", "sconto dual fuel luce+gas"),
    ("ces", "sconto cessione credito/bonus"),
    ("unt", "sconto una tantum"),
    ("cbk", "sconto come back/rientro"),
]

# Descrizioni di condizioni contrattuali che possono risultare LIMITANTE=01
# ma sono in realtà procedure burocratiche standard, non vincoli/trappole.
BANAL_CONDITIONS = {
    "attivazione fornitura",
    "disattivazione fornitura",
    "attivazione della fornitura",
    "disattivazione della fornitura",
    "attivazione",
    "disattivazione",
    "raccordamento",
    "subentro",
    "voltura",
}

# Keyword per feature estratte da testo libero (nome offerta, descrizione,
# condizioni e sconti).
FEATURE_KEYWORDS: Dict[str, List[str]] = {
    "has_fotovoltaico": [
        "fotovoltaic*",
        "pannello* fotovoltaico*",
        "pannelli fotovoltaici",
        "impianto fotovoltaico",
    ],
    "has_soci_coop": [
        "socio",
        "soci ",
        "cooperativa",
        "associato",
        "associati",
        "membership",
        "abbonamento",
    ],
    "has_obbligo_requisito": [
        "obbligatorio",
        "requisito",
        "sottoscrivere",
        "iscritto",
        "iscrizione",
        "aderire",
        "adesione",
        "titolari di partita iva",
    ],
    "has_morosita": [
        "moroso",
        "morosita",
        "morosità",
        "ritardo pagamento",
    ],
    "has_deposito_cauzionale": [
        "deposito cauzionale",
        "cauzione",
        "garanzia",
    ],
    "has_sconto_sdd": [
        "sdd",
        "addebito diretto",
        "sepa",
        "domiciliazione",
    ],
    "has_sconto_digitale": [
        "digitale",
        "paperless",
        "online",
        "fattura elettronica",
        "fattura web",
        "email",
    ],
    "has_sconto_benvenuto": [
        "benvenuto",
        "bonus benvenuto",
        "primo anno",
        "primi mesi",
        "nei primi",
        "nuovo cliente",
    ],
    "has_sconto_fedelta": [
        "fedelta",
        "fedeltà",
        "fidelizzazione",
        "fidelity",
        "cliente fedele",
        "clienti fedeli",
    ],
    "has_sconto_green": [
        "green",
        "rinnovabile",
        "rinnovabili",
        "ambiente",
        "sostenibile",
    ],
    "has_sconto_dualfuel": [
        "dual fuel",
        "dualfuel",
        "luce e gas",
        "gas e luce",
    ],
    "has_sconto_cessione_credito": [
        "cessione",
        "credito",
        "bonus",
    ],
    "has_sconto_come_back": [
        "come back",
        "come-back",
        "rientro",
        "rientrare",
    ],
}

PROMO_KEYWORDS = [
    "primo anno",
    "primi mesi",
    "nei primi",
    "validita promozionale",
    "validità promozionale",
    "promozione",
]

UNA_TANTUM_KEYWORDS = [
    "una tantum",
    "una-tantum",
    "tantum",
]


# Configurazioni di default per provider.
PROVIDERS = {
    "zenmux": {
        "api_key_env": "ZENMUX_API_KEY",
        "base_url_env": "ZENMUX_BASE_URL",
        "default_base_url": "https://zenmux.ai/api/v1",
        "default_model": "deepseek/deepseek-v4-flash",
    },
    "openrouter": {
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-v4-flash",
    },
    "ollama": {
        "api_key_env": None,
        "base_url_env": "OLLAMA_BASE_URL",
        "default_base_url": "http://localhost:11434",
        "default_model": "phi4",
    },
}


def resolve_provider(provider_name: Optional[str] = None) -> str:
    """Risolve il provider da usare. Se non specificato, prova in ordine: zenmux, openrouter, ollama."""
    if provider_name and provider_name != "auto":
        if provider_name not in PROVIDERS:
            raise ValueError(f"Provider non supportato: {provider_name}")
        return provider_name

    if os.getenv(PROVIDERS["zenmux"]["api_key_env"]):
        return "zenmux"
    if os.getenv(PROVIDERS["openrouter"]["api_key_env"]):
        return "openrouter"
    if os.getenv(PROVIDERS["ollama"]["base_url_env"], PROVIDERS["ollama"]["default_base_url"]):
        return "ollama"

    raise RuntimeError(
        "Nessun provider LLM configurato. Imposta ZENMUX_API_KEY, OPENROUTER_API_KEY "
        "o OLLAMA_BASE_URL/OLLAMA_MODEL in variabile d'ambiente o nel file .env"
    )


def get_provider_config(
    provider_name: str, model: Optional[str] = None, base_url: Optional[str] = None
) -> Dict[str, Any]:
    cfg = PROVIDERS[provider_name].copy()
    cfg["model"] = model or os.getenv(
        f"{provider_name.upper()}_MODEL", cfg["default_model"]
    )
    cfg["base_url"] = (base_url or os.getenv(cfg["base_url_env"], cfg["default_base_url"])).rstrip("/")
    api_key_env = cfg["api_key_env"]
    cfg["api_key"] = os.getenv(api_key_env) if api_key_env else None
    return cfg


def _normalize_text(text: str) -> str:
    """Normalizza testo per confronti: minuscolo, spazi singoli, no accenti comuni."""
    text = text.lower()
    text = text.replace("'", " ")
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    # normalizza alcune varianti ortografiche
    text = text.replace("validità", "validita")
    text = text.replace("fedeltà", "fedelta")
    text = text.replace("morosità", "morosita")
    return text


def _text_matches(texts: List[str], patterns: List[str]) -> bool:
    """Restituisce True se almeno un pattern matcha almeno uno dei testi."""
    for raw_text in texts:
        text = _normalize_text(raw_text)
        if not text:
            continue
        for pattern in patterns:
            p = _normalize_text(pattern)
            if "*" in p or "?" in p:
                if fnmatch.fnmatch(text, f"*{p}*"):
                    return True
            else:
                if p in text:
                    return True
    return False


def _match_blacklist(texts: List[str], blacklist: List[str]) -> bool:
    """Restituisce True se almeno una voce della blacklist matcha un testo."""
    return _text_matches(texts, blacklist)


def _is_banal_condition(descrizione: str) -> bool:
    """True se la descrizione è una procedura burocratica standard."""
    desc = _normalize_text(descrizione or "")
    return desc in BANAL_CONDITIONS


def _collect_texts(off: Offerta) -> List[str]:
    """Raccoglie tutti i testi rilevanti di un'offerta."""
    texts = [
        off.nome_offerta,
        off.descrizione,
    ]
    for c in off.condizioni:
        texts.append(c.descrizione)
    for comp in off.componenti:
        texts.extend([comp.nome, comp.descrizione])
    return [t for t in texts if t]


def _collect_sconti_texts(off: Offerta) -> List[str]:
    """Raccoglie testi degli sconti."""
    texts = []
    for s in off.sconti:
        t = s.nome or ""
        if s.descrizione:
            t += " " + s.descrizione
        texts.append(t)
    return [t for t in texts if t]


def extract_rule_based_features(off: Offerta) -> Dict[str, Optional[bool]]:
    """
    Estrae feature con regole deterministiche.
    Restituisce dict {feature: True/False/None}. None = ambiguo, da chiedere all'LLM.
    """
    features: Dict[str, Optional[bool]] = {}
    all_texts = _collect_texts(off)
    sconti_texts = _collect_sconti_texts(off)
    has_sconti = len(off.sconti) > 0

    # Deterministici dall'XML
    features["has_penali_recesso"] = has_penale_recesso(off)
    features["is_geolimitata"] = len(off.regioni) > 0

    # Vincoli limitanti: distinguiamo condizioni burocratiche standard da vincoli reali.
    has_blacklist = _match_blacklist(all_texts, BLACKLIST_CONDIZIONI_DEFAULT)
    has_real_limitante = False
    has_banal_limitante = False
    for c in off.condizioni:
        if c.limitante:
            if _is_banal_condition(c.descrizione):
                has_banal_limitante = True
            else:
                has_real_limitante = True

    if has_blacklist or has_real_limitante:
        features["has_vincoli_limitanti"] = True
    elif has_banal_limitante:
        # Procedura standard: non è una trappola.
        features["has_vincoli_limitanti"] = False
    else:
        features["has_vincoli_limitanti"] = False

    # Keyword-based: se non c'è match, consideriamo False. L'LLM interviene solo
    # quando le euristiche sono incerte.
    keyword_texts = all_texts + sconti_texts
    for feature, patterns in FEATURE_KEYWORDS.items():
        features[feature] = _text_matches(keyword_texts, patterns)

    # Promozionale: VALIDITA=02 è promozionale esplicita; keyword promozionali
    # suggeriscono promozione. Se non ci sono sconti siamo sicuri che non lo sia.
    if not has_sconti:
        features["is_promozionale"] = False
    elif any(s.validita == "02" for s in off.sconti):
        features["is_promozionale"] = True
    elif _text_matches(sconti_texts, PROMO_KEYWORDS):
        features["is_promozionale"] = True
    else:
        # Ci sono sconti ma non sappiamo se sono promozionali.
        features["is_promozionale"] = None

    # Una tantum: raramente esplicita. Se non ci sono sconti, sicuramente falso.
    if not has_sconti:
        features["has_sconto_una_tantum"] = False
    elif _text_matches(sconti_texts, UNA_TANTUM_KEYWORDS):
        features["has_sconto_una_tantum"] = True
    else:
        # Ci sono sconti ma non sappiamo se sono una tantum.
        features["has_sconto_una_tantum"] = None

    return features


def _build_prompt(batch: List[Offerta], compact: bool = True) -> str:
    items = []
    for o in batch:
        condizioni = [c.descrizione for c in o.condizioni if c.descrizione]
        sconti = []
        for s in o.sconti:
            text = s.nome
            if s.descrizione:
                text += f" - {s.descrizione}"
            sconti.append(text)
        items.append(
            {
                "cod": o.cod_offerta,
                "nome": o.nome_offerta,
                "descrizione": o.descrizione,
                "condizioni": condizioni,
                "sconti": sconti,
            }
        )

    if compact:
        key_lines = "\n".join([f"{k} = {d}" for k, d in COMPACT_DESCRIPTIONS])
        bool_keys = ", ".join(COMPACT_KEYS.values())
        return f"""Sei un assistente specializzato nell'analisi di offerte di energia elettrica.
Per ogni offerta nell'elenco, estrai informazioni salienti dai testi (nome, descrizione, condizioni contrattuali, sconti) e restituisci un JSON con un array "offerte".
Ogni elemento deve contenere "cod" e i seguenti campi booleani (1 = vero, 0 = falso):
{key_lines}

Rispondi SOLO con il JSON, senza altro testo.

Offerte:
{json.dumps(items, ensure_ascii=False, separators=(',', ':'))}
"""

    # Fallback formato esteso (se il modello si confonde con le chiavi corte)
    feature_list = "\n".join([f'- {f}' for f in FEATURES_BOOLEAN])
    return f"""Sei un assistente specializzato nell'analisi di offerte di energia elettrica.
Per ogni offerta nell'elenco, estrai informazioni salienti dai testi (nome, descrizione, condizioni contrattuali, sconti) e restituisci un JSON con un array "offerte".
Ogni elemento deve contenere "cod_offerta" e i seguenti campi booleani (1 = vero, 0 = falso):
{feature_list}

Inoltre, se trovi altre informazioni utili, inseriscile in "tags" come array di oggetti
{{"tag": "nome_feature", "valore": ..., "tipo": "boolean|number|text"}}.
Esempi di tag utili: durata_promozione_mesi, riassunto_offerta, note.

Rispondi SOLO con il JSON, senza altro testo.

Offerte:
{json.dumps(items, ensure_ascii=False, separators=(',', ':'))}
"""


def _compact_to_full(item: Dict[str, Any]) -> Dict[str, Any]:
    """Converte chiavi corte in nomi lunghi e 'cod' in 'cod_offerta'."""
    normalized: Dict[str, Any] = {}
    for k, v in item.items():
        if k in FULL_KEYS:
            normalized[FULL_KEYS[k]] = v
        elif k == "cod":
            normalized["cod_offerta"] = v
        else:
            normalized[k] = v
    return normalized


def _parse_response(text: str) -> Optional[List[Dict[str, Any]]]:
    # Prova a parsare il testo grezzo
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Prova a estrarre JSON da blocco markdown
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        else:
            return None

    if isinstance(data, dict) and "offerte" in data:
        items = data["offerte"]
    elif isinstance(data, list):
        items = data
    else:
        return None

    if not isinstance(items, list):
        return None

    return [_compact_to_full(item) for item in items]


def _build_headers(provider_name: str, api_key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if provider_name == "openrouter":
        # OpenRouter consiglia questi header per identificare l'app
        headers.setdefault("HTTP-Referer", os.getenv("OPENROUTER_REFERER", "https://localhost"))
        headers.setdefault("X-Title", os.getenv("OPENROUTER_TITLE", "Comparatore Offerte"))
    return headers


def _call_openai_compatible(
    client: httpx.Client,
    batch: List[Offerta],
    model: str,
    base_url: str,
    compact: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    prompt = _build_prompt(batch, compact=compact)
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    # Alcuni provider/API supportano JSON mode; se fallisce, lo gestiamo a valle.
    try:
        payload["response_format"] = {"type": "json_object"}
        resp = client.post(
            f"{base_url}/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        # Se il provider rifiuta response_format, riprova senza
        if "response_format" in payload and (e.response.status_code in (400, 422)):
            payload.pop("response_format")
            resp = client.post(
                f"{base_url}/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
        else:
            raise

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return _parse_response(content)


def _call_ollama(
    client: httpx.Client,
    batch: List[Offerta],
    model: str,
    base_url: str,
    compact: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    prompt = _build_prompt(batch, compact=compact)
    resp = client.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        },
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["message"]["content"]
    return _parse_response(content)


def _call_provider(
    client: httpx.Client,
    provider_name: str,
    batch: List[Offerta],
    model: str,
    base_url: str,
    compact: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    if provider_name == "ollama":
        return _call_ollama(client, batch, model, base_url, compact=compact)
    return _call_openai_compatible(client, batch, model, base_url, compact=compact)


def _batch_offerte(
    offerte: List[Offerta], batch_size: int
) -> List[List[Offerta]]:
    return [offerte[i : i + batch_size] for i in range(0, len(offerte), batch_size)]


def extract_features(
    offerte: List[Offerta],
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    batch_size: int = 50,
    max_retries: int = 3,
    use_rule_based: bool = True,
    compact_output: bool = True,
    use_llm: bool = False,
) -> Tuple[Dict[str, Dict[str, bool]], Dict[str, List[Dict[str, Any]]]]:
    """
    Estrae feature da una lista di offerte.

    Modalità di default (Piano A):
      - Calcola le feature deterministiche con regole/keyword.
      - L'LLM NON viene chiamato di default: le euristiche sono sufficienti per
        la maggior parte delle offerte ARERA e l'LLM locale (Ollama) richiede
        tempi di elaborazione troppo lunghi per popolare l'intero dataset.
      - Se use_llm=True, l'LLM interviene solo sulle feature ancora ambigue (None).

    Args:
        use_rule_based: se False, tutte le feature iniziano come None.
        compact_output: se True, usa chiavi corte nel prompt JSON.
        use_llm: se True, attiva la chiamata LLM per i casi ambigui.

    Ritorna:
      - features_map: cod_offerta -> {feature: bool}
      - tags_map: cod_offerta -> [{tag, valore, tipo, ...}]
    """
    # 1. Rule-based pass
    t0 = time.perf_counter()
    rule_based_map: Dict[str, Dict[str, Optional[bool]]] = {}
    for o in offerte:
        if use_rule_based:
            rule_based_map[o.cod_offerta] = extract_rule_based_features(o)
        else:
            rule_based_map[o.cod_offerta] = {f: None for f in FEATURES_BOOLEAN}
    rule_time = time.perf_counter() - t0

    # 2. Filtra solo offerte con almeno un None
    offerte_llm = [
        o for o in offerte
        if use_llm and any(rule_based_map[o.cod_offerta][f] is None for f in FEATURES_BOOLEAN)
    ]

    print(
        f"[extractor] Rule-based: {len(offerte)} offerte elaborate in {rule_time:.3f}s; "
        f"{len(offerte_llm)} da verificare con LLM"
    )

    features_map: Dict[str, Dict[str, bool]] = {}
    tags_map: Dict[str, List[Dict[str, Any]]] = {}

    if offerte_llm:
        # Risolviamo provider e config solo se l'LLM è effettivamente richiesto.
        provider_name = resolve_provider(provider_name)
        cfg = get_provider_config(provider_name, model=model, base_url=base_url)

        if provider_name != "ollama" and not cfg["api_key"]:
            raise RuntimeError(
                f"Chiave mancante per provider {provider_name}. "
                f"Imosta {PROVIDERS[provider_name]['api_key_env']}"
            )

        # Per Ollama locale riduciamo il batch di default per non far scadere il timeout
        effective_batch_size = batch_size
        if provider_name == "ollama" and batch_size == 50:
            effective_batch_size = 10

        model = cfg["model"]
        base_url = cfg["base_url"]
        headers = _build_headers(provider_name, cfg["api_key"])

        timeout = httpx.Timeout(120.0, connect=10.0)
        if provider_name == "ollama":
            timeout = httpx.Timeout(300.0, connect=10.0)

        with httpx.Client(headers=headers, timeout=timeout) as client:
            if offerte_llm:
                batches = _batch_offerte(offerte_llm, effective_batch_size)
                for idx, batch in enumerate(batches, start=1):
                    for attempt in range(1, max_retries + 1):
                        try:
                            print(
                                f"[extractor:{provider_name}] batch {idx}/{len(batches)} "
                                f"({len(batch)} offerte, model={model})..."
                            )
                            results = _call_provider(
                                client, provider_name, batch, model, base_url,
                                compact=compact_output,
                            )
                            expected_codes = {o.cod_offerta for o in batch}
                            if (
                                not isinstance(results, list)
                                or len(results) != len(batch)
                                or {item.get("cod_offerta") for item in results} != expected_codes
                            ):
                                raise RuntimeError("Risposta incompleta o codici non corrispondenti")
                            for item in results:
                                cod = item.get("cod_offerta")
                                if not cod:
                                    continue
                                llm_feats = {f: bool(item.get(f)) for f in FEATURES_BOOLEAN}
                                # Merge: regole sovrascrivono, LLM riempie i None
                                merged = rule_based_map[cod].copy()
                                for f in FEATURES_BOOLEAN:
                                    if merged[f] is None:
                                        merged[f] = llm_feats.get(f, False)
                                features_map[cod] = {f: bool(merged[f]) for f in FEATURES_BOOLEAN}
                                tags = item.get("tags", [])
                                if isinstance(tags, list):
                                    tags_map[cod] = [
                                        {
                                            "tag": t.get("tag"),
                                            "valore": str(t.get("valore")),
                                            "tipo": t.get("tipo", "text"),
                                            "source": "llm",
                                            "modello": model,
                                            "ts_estrazione": None,
                                        }
                                        for t in tags
                                        if t.get("tag")
                                    ]
                            break
                        except Exception as e:
                            print(f"[extractor:{provider_name}] batch {idx} tentativo {attempt} fallito: {e}")
                            if attempt == max_retries:
                                # Fallback: tutti false per non bloccare il pipeline
                                for o in batch:
                                    features_map[o.cod_offerta] = {
                                        f: bool(rule_based_map[o.cod_offerta][f])
                                        if rule_based_map[o.cod_offerta][f] is not None
                                        else False
                                        for f in FEATURES_BOOLEAN
                                    }
                                    tags_map[o.cod_offerta] = []

    # 3. Offerte non inviate all'LLM: usa direttamente il rule-based
    for o in offerte:
        if o.cod_offerta not in features_map:
            features_map[o.cod_offerta] = {
                f: bool(rule_based_map[o.cod_offerta][f]) for f in FEATURES_BOOLEAN
            }
            tags_map[o.cod_offerta] = []

    return features_map, tags_map


if __name__ == "__main__":
    # Test di integrazione su campione di offerte (default 20)
    from parser import parse_xml_offerte
    from config import DATA_DIR
    import sys

    sample_size = 20
    if len(sys.argv) > 1:
        try:
            sample_size = int(sys.argv[1])
        except ValueError:
            pass

    xml_files = sorted(DATA_DIR.glob("offerte_elettrico_MLIBERO_*.xml"))
    if not xml_files:
        print("Nessun file XML trovato in data/")
        sys.exit(1)

    db_file = xml_files[-1]
    print(f"Carico {sample_size} offerte da {db_file.name}...")
    offerte = parse_xml_offerte(db_file)[:sample_size]

    t0 = time.perf_counter()
    fm, tm = extract_features(offerte, batch_size=5)
    total = time.perf_counter() - t0

    print(f"\nCompletato in {total:.2f}s")
    print(f"Offerte processate: {len(fm)}")

    # Statistiche sull'origine dei valori (approssimativa: i None non compaiono
    # nel risultato finale, quindi non possiamo sapere quanti fossero; però
    # possiamo stimare quanti hanno dovuto passare per l'LLM)
    for cod, feats in fm.items():
        print(f"{cod}: {feats}")
        tags = tm.get(cod, [])
        if tags:
            print(f"  tags: {tags}")

    sys.exit(0)
