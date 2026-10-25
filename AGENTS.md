# AGENTS.md

Istruzioni operative per un coding agent che lavora su questo repository.

## Contesto del progetto

`comparatore_offerte` è uno script Python (CLI + modalità interattiva) che:

- scarica gli Open Data ARERA / Acquirente Unico (XML offerte, CSV parametri di sistema, CSV prezzi storici);
- salva le offerte in un database SQLite locale (`data/offerte.db`);
- applica filtri (cliente, consumo, tariffa, attivazione, regione, condizioni limitanti, penali, sconti);
- calcola la spesa annua stimata (componente venditore + PUN + oneri di sistema + IVA);
- mostra una tabella a terminale ed eventualmente esporta CSV;
- con `--verifica` controlla su Google (Serper.dev) se l'offerta è pubblicata sul sito del venditore.

Lingua del progetto: italiano (messaggi CLI, docstring, README). Mantieni questo stile.

## Ambiente

- Python 3.12 (`/usr/bin/python3`), ambiente virtuale in `.venv/`.
- Installazione dipendenze:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

- Dipendenze: `tabulate`, `python-dotenv`, `httpx`. Il resto è standard library.
- Il programma funziona anche con il `python` di sistema, ma `python-dotenv` serve per `--popola-db` con LLM. `main.py` ha un fallback manuale per leggere `.env` se `python-dotenv` non è installato.

## Comandi utili

```bash
# Esecuzione base
.venv/bin/python main.py --consumo-annuo 1000

# Gas (DB separato)
.venv/bin/python main.py --popola-db --commodity gas
.venv/bin/python main.py --commodity gas --consumo-annuo 208 --regione toscana

# Popolamento DB (default: rule-based, veloce)
.venv/bin/python main.py --popola-db

# Popolamento senza feature
.venv/bin/python main.py --popola-db --no-llm

# Popolamento con LLM (lento, solo API veloci)
.venv/bin/python main.py --popola-db --no-rule-based --llm-provider openrouter

# Verifica presenza sul sito venditore
.venv/bin/python main.py --consumo-annuo 2700 --senza-vincoli --verifica

# Verifica strict (solo offerte verificate, chiede quante cercarne)
.venv/bin/python main.py --consumo-annuo 2700 --senza-vincoli --max 10 --verifica strict

# Controllo sintassi (non esiste lint/typecheck configurato)
.venv/bin/python -m py_compile main.py verifica.py popola_db.py extractor.py cli.py
```

Non esiste una suite di test automatica. Per verificare una modifica usa `py_compile` e un'esecuzione reale con un profilo piccolo (es. `--consumo-annuo 400 --max 5`). Evita `--verifica` nei test se non indispensabile: consuma chiamate Serper.

## Architettura

| File | Responsabilità |
|---|---|
| `main.py` | Entry point e orchestrazione; carica `.env`, controlla `SERPER_API_KEY`, calcola e stampa. |
| `cli.py` | Argparse e modalità interattiva. |
| `downloader.py` | Download condizionato dei file Open Data. |
| `parser.py` | Parsing XML offerte (unità commodity-aware) e CSV parametri/prezzi. |
| `database.py` | Schema SQLite, upsert e lettura. |
| `extractor.py` | Estrazione feature testuali: rule-based di default, LLM opzionale. |
| `popola_db.py` | Popolamento/aggiornamento DB. Import di `extractor` lazy dentro `popola()`. |
| `filters.py` | Motore filtri. |
| `penali.py` | Stima penali di recesso dall'XML e filtri `--penale-mese-max` / `--penale-12m-max`; override in `data/penali_manuali.json`. |
| `calculator.py` | Calcolo spesa annua elettrico e gas (oneri, accise, IVA). |
| `formatter.py` | Tabella terminale e CSV (PUN/PSV, kWh/Smc). |
| `venditori.py` | Mappa PIVA -> nome commerciale. |
| `verifica.py` | Verifica Serper.dev, cache e URL dei risultati. |
| `config.py` | Costanti, mapping codici XML elettrico/gas, profili consumo, `.env`. |

Flusso: `downloader` -> `parser` -> `database`/`extractor` -> `filters` -> `calculator` -> `formatter`.

## Decisioni di progetto (non regressionare)

### Estrazione feature

- Il default è **rule-based** (`use_rule_based=True`, `use_llm=False`): veloce, adatto a ~3.300 offerte.
- L'LLM è opzionale e si attiva con `--no-rule-based`. Con modelli locali (es. Gemma 3 12B Q8_0) richiede ~15-20 s/offerta: non usarlo per popolamenti completi.
- `--no-llm` salta del tutto l'estrazione (booleani a 0).
- `popola_db.py` importa `extractor` **lazy** dentro `popola()` per non richiedere `python-dotenv` all'avvio di `main.py`.

### Verifica Serper (`--verifica`)

- Per ogni offerta si fanno **sempre due ricerche**:
  - codice: ricerca esatta `"cod_offerta" site:dominio`;
  - nome: ricerca non esatta con parole obbligatorie `+parola1 +parola2 site:dominio` (l'ordine può cambiare: non usare la frase esatta).
- `--verifica` (normale): mostra la colonna Check, le offerte restano ordinate per spesa.
- `--verifica strict`: chiede quante offerte verificate cercare, scorre in batch con `offset`, si ferma quando ne ha abbastanza e **taglia il risultato al numero richiesto** (non a `--max`). La riga ★ della mia offerta è sempre visibile.
- Se `SERPER_API_KEY` manca e `--verifica` è attivo, `main.py` esce subito con errore chiaro (`sys.exit(1)`), prima di calcolare/filtrare.
- `SERPER_API_KEY` può essere in variabile d'ambiente o in `.env`. Le variabili d'ambiente hanno precedenza.
- Cache in `data/verifica_cache.json` (formato v2: `cod`, `url_cod`, `nome`, `url_nome`, `ts`).
- Gli URL dei match sono salvati anche in `data/verifica_urls.json` per diagnosticare falsi positivi (es. offerta trovata in un PDF o in una pagina generica).
- La verifica dice "il testo esiste sul dominio", non "l'offerta è attiva e raggiungibile". Falsi positivi da PDF/pagine generiche sono noti e accettati.

### Configurazione `.env`

Variabili supportate:

- `SERPER_API_KEY` (verifica)
- `PUN_MANUALE` (PUN di default in €/kWh, ha precedenza sul CSV ma non su `--pun`)
- `PSV_MANUALE` (PSV gas di default in €/Smc, ha precedenza sul CSV ma non su `--psv`)
- `ZENMUX_API_KEY`, `ZENMUX_BASE_URL`, `ZENMUX_MODEL`
- `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

`.env` è in `.gitignore`: non committare mai chiavi.

### Gas

- Il gas è supportato con `--commodity gas` e DB separato (`data/offerte_gas.db`).
- Nel XML gas `UNITA_MISURA=04` significa **€/Smc** (nell'elettrico è percentuale). La mappatura è in `MAPPING_GAS`.
- Le offerte gas variabili usano il **PSV** (o CMEM); non usare il PUN. `PSV_MANUALE`/`--psv` hanno precedenza sul CSV.
- Il calcolo oneri gas è in `_calcola_oneri_sistema_gas`: esclude QVD e UG2, usa `tau1_cc1_<ambito>` (classe <G6, es. G4) e gli scaglioni `tau3`. L'ambito (a1–a6) deriva da `--regione`.
- Le accise gas non sono nel CSV ARERA: la tabella è in `ACCISE_GAS_DOMESTICO`. L'IVA gas è 10% fino a 480 Smc/anno (domestico, prima casa) e 22% oltre; 22% per seconda casa e non domestico.
- Il calcolo gas è una stima: non include l'addizionale regionale e usa il PSV anche per offerte eventualmente indicizzate al CMEM.
- `data/my_offer_gas.json` è la configurazione personale gas (template in `data/my_offer_gas_stub.json`).

## GOTCHA importanti

- I tag XML ARERA sono **MAIUSCOLI**: `COD_OFFERTA`, `PIVA_UTENTE`, `NOME_OFFERTA`, `DESCRIZIONE`, `LIMITANTE`, ecc. Non usare `CodiceOfferta`.
- Il file XML può superare 20 MB e 390.000 righe: usare `iterparse` con `clear()`, non caricarlo interamente.
- `LIMITANTE=01` = condizione limitante, `02` = non limitante. Alcune descrizioni burocratiche ("ATTIVAZIONE FORNITURA", "DISATTIVAZIONE FORNITURA") sono normali e non vanno trattate come trappole.
- `UNITA_MISURA`: `01` euro/anno, `02` euro/kW/anno, `03` euro/kWh, `04` percentuale.
- Fasce `07`/`08` (non standard) vanno mappate a F1/F2 con profilo bioraria 50/50.
- Il PUN è unico per tutte le fasce anche nelle offerte multioraria: semplificazione accettata.
- IVA: 10% prima casa/residente, 22% seconda casa/altri usi.
- `--confronto-portale` esclude i costi fissi identici (sigma1/sigma2) per allinearsi al portale ARERA.
- `--no-oneri-recesso` esclude tutte le offerte con penali di recesso (`tipologia=05`), sia limitanti sia non limitanti.
- Condizioni presenti solo nei PDF del venditore (es. sconto soci Coop di SMARTLUCE) **non sono nell'XML ARERA**: l'estrattore non può rilevarle. Non cercare di inferirle dal nome offerta.

## Convenzioni di codice

- Nessun commento superfluo; commenti solo per logica non ovvia.
- Type hints e docstring brevi in italiano dove già presenti.
- Messaggi utente in italiano, con emoji coerenti con lo stile esistente (🔍, 📄, ⚠️, ✅) solo nei punti già previsti.
- Non introdurre nuove dipendenze senza aggiornare `requirements.txt` e il README.
- Non committare file in `data/` (XML, CSV, DB, cache) né `.env`.

## Documentazione

Il `README.md` è la documentazione utente e va tenuto allineato a ogni modifica di comportamento (flag CLI, configurazione `.env`, verifica, popolamento DB). Aggiornalo quando cambi qualcosa che l'utente vede.
