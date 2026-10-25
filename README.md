# Comparatore Offerte Energia Elettrica (Mercato Libero)

Script Python per interrogare, filtrare e confrontare le offerte di energia elettrica del **Mercato Libero** pubblicate nel Portale Offerte di ARERA / Acquirente Unico.

Utilizza i **dati aperti** (Open Data) aggiornati quotidianamente dal portale [ilportaleofferte.it](https://www.ilportaleofferte.it).

> **Nota**: il comparatore supporta anche il **gas naturale** con `--commodity gas` (vedi la sezione [Gas](#gas)).

---

## Funzionalità

- **Download automatico condizionato** dei file open data (XML offerte, CSV parametri di sistema, CSV prezzi storici PUN)
- **Supporto gas** con `--commodity gas`: offerte, parametri di sistema, PSV e accise gas
- **Parsing intelligente** del grande file XML delle offerte con `iterparse` (gestisce file da decine di MB)
- **Nomi venditori leggibili**: le PIVA vengono automaticamente convertite in nomi commerciali (es. "Dolomiti Energia", "E.ON", "Iren") usando il dominio del sito venditore e il nome offerta
- **Filtri avanzati**:
  - Tipologia cliente (domestico / altri usi)
  - Tipologia offerta (prezzo fisso / variabile)
  - Tipologia tariffa (**tutte** / monoraria / bioraria / trioraria)
  - Tipo attivazione (**tutte** / nuova / cambio / voltura / subentro)
  - Range di consumo
  - Esclusione offerte con **condizioni limitanti** (vincoli, penali, obblighi socio, pannelli fotovoltaici, ecc.)
  - Esclusione offerte con **oneri di recesso**
  - Filtro per parole chiave nelle condizioni contrattuali
  - Filtro per venditore
  - Filtro per zona geografica (codice ISTAT o nome regione, es. `02` / `"valle d'aosta"`)
   - **Verifica presenza sul sito venditore** via Google (Serper.dev, opzionale, colonna Check ✓/✗). Senza `--verifica`, la colonna è sempre visibile con `? ?` (giallo).
   - **Colonna Confidenza** (● verde/giallo/rosso): segnala se gli sconti hanno durata certa o incerta
  - **Esclusione automatica** di offerte geolimitate con `--regione` se non compatibili con la regione specificata
- **Calcolo spesa annua stimata**:
   - Componenti del venditore (spread, quote fisse, quote potenza, **scaglioni di consumo**)
   - PUN parametrico (ultimo mensile o valore custom) con **perdite di rete** (λ) applicate a tutte le offerte variabili (parametro `lambda` del CSV, sovrascrivibile in `my_offer.json`)
   - Oneri di sistema (accise, trasporto, distribuzione, ARIM, ASOS, ecc.)
   - IVA applicata (10% prima casa, 22% seconda casa / altri usi)
- **Output doppio**: tabella a terminale + esportazione CSV
- **Modalità interattiva** se si lancia senza argomenti

---

## Installazione

```bash
cd comparatore_offerte
pip install -r requirements.txt
```

Dipendenze principali:
- `tabulate` (per la tabella a terminale)
- `python-dotenv` (per caricare `.env` con le API key)
- `httpx` (per chiamate LLM, usato solo con `--no-rule-based`)
- Il resto sono librerie standard Python

---

## Configurazione via `.env`

Puoi salvare le API key in un file `.env` nella root del progetto. Le variabili supportate sono:

- `SERPER_API_KEY` → per `--verifica` (Serper.dev)
- `ZENMUX_API_KEY` → per `--no-rule-based` con provider ZenMux
- `OPENROUTER_API_KEY` → per `--no-rule-based` con provider OpenRouter
- `PUN_MANUALE` → PUN in €/kWh usato come default al posto dell'ultimo mensile del CSV (es. `0.228296`). Ha precedenza sul CSV ma non su `--pun`.
- `PSV_MANUALE` → PSV in €/Smc per il gas (es. `0.831535`). Ha precedenza sul CSV ma non su `--psv`.

Esempio:

```bash
SERPER_API_KEY=la_tua_chiave_serper
ZENMUX_API_KEY=la_tua_chiave_zenmux
PUN_MANUALE=0.228296
```

Il file `.env` viene caricato automaticamente all'avvio. Le variabili d'ambiente hanno la precedenza sul file `.env`.

---

## Utilizzo

### Modalità interattiva
```bash
python main.py
```
Lo script chiederà i dati essenziali (consumo, tariffa, prima/seconda casa) e le opzioni avanzate.  
Premi Ctrl+C in qualsiasi momento per uscire.  
Accetta **shortcut** per le scelte testuali:

| Scelta | Shortcut valide |
|--------|-----------------|
| **tutte (tariffa)** | `0`, `a`, `all`, `tut` |
| **monoraria** | `1`, `m`, `mono` |
| **bioraria** | `2`, `b`, `bio` |
| **trioraria** | `3`, `t`, `tri` |
| **tutte (prezzo)** | `0`, `a`, `all` |
| **fisso** | `1`, `f` |
| **variabile** | `2`, `v`, `var` |
| **domestico** | `1`, `d`, `dom` |
| **altri_usi** | `2`, `a`, `alt`, `au` |
| **elettrico** | `1`, `e`, `ele`, `el` |
| **gas** | `2`, `g`, `ga` |
| **terminal** | `1`, `t`, `term` |
| **csv** | `2`, `c` |
| **both** | `3`, `b` |
| **sì (prima casa)** | `s`, `si`, `y`, `yes`, `1` |
| **no (seconda casa)** | `n`, `no`, `0` |
| **tutte (attivazione)** | `0`, `a` |
| **nuova** | `1`, `n` |
| **cambio** | `2`, `c` |
| **voltura** | `3`, `v` |
| **subentro** | `4`, `s` |

### Modalità CLI (argomenti diretti)

```bash
# Ricerca base: tutte le tariffe, 1000 kWh, prima casa
python main.py --consumo-annuo 1000

# Ricerca come sul portale ARERA: cambio fornitore, prezzo fisso, escludi oneri
python main.py --non-residente --consumo-annuo 100 --tipo-offerta fisso --tipo-attivazione cambio --senza-vincoli --no-oneri-recesso --confronto-portale

# Solo prezzo variabile, seconda casa, PUN custom
python main.py --non-residente --consumo-annuo 2000 --tipo-offerta variabile --pun 0.12

# Solo prezzo fisso, trioraria, escludi offerte complicate, esporta CSV
python main.py \
  --consumo-annuo 1500 \
  --tipo-tariffa trioraria \
  --tipo-offerta fisso \
  --senza-vincoli \
  --no-oneri-recesso \
  --aggiorna-dati \
  --output both

# Prezzo variabile, escludi sconti promozionali (prime 5 offerte)
python main.py \
  --consumo-annuo 100 \
  --tipo-offerta variabile \
  --senza-vincoli \
  --no-oneri-recesso \
  --confronto-portale \
  --ignora-sconti-promo \
  --max 5

# Filtra per regione (solo offerte disponibili in Toscana)
python main.py \
  --consumo-annuo 2700 \
  --tipo-offerta tutte \
  --senza-vincoli \
  --regione toscana

# Verifica presenza offerte sul sito venditore (richiede chiave Serper.dev)
# Imposta la chiave in .env o via export:
# echo 'SERPER_API_KEY="la_tua_chiave"' >> .env
python main.py \
  --consumo-annuo 2700 \
  --senza-vincoli \
  --no-oneri-recesso \
  --verifica

# Verifica strict: solo offerte verificate (chiede tetto chiamate)
python main.py \
  --consumo-annuo 2700 \
  --senza-vincoli \
  --no-oneri-recesso \
  --max 10 \
  --verifica strict
```

### Argomenti CLI

| Argomento | Descrizione | Default |
|-----------|-------------|---------|
| `--commodity` | Tipo: `elettrico` o `gas` | `elettrico` |
| `--tipo-cliente` | `domestico` / `altri_usi` | `domestico` |
| `--residente` | Residenza principale (prima casa) | - |
| `--non-residente` | Seconda casa / non residente | - |
| `--consumo-annuo` | Consumo stimato in kWh/anno (elettrico) o Smc/anno (gas) | *richiesto* |
| `--potenza` | Potenza impegnata in kW | `3` |
| `--tipo-tariffa` | `tutte` / `monoraria` / `bioraria` / `trioraria` | `tutte` |
| `--tipo-offerta` | `tutte` / `fisso` / `variabile` | `tutte` |
| `--tipo-attivazione` | `tutte` / `nuova` / `cambio` / `voltura` / `subentro` | `tutte` |
| `--pun` | Valore PUN in €/kWh per l'elettrico (sovrascrive l'ultimo mensile). Se omesso usa `PUN_MANUALE` del `.env`, poi il CSV. | auto |
| `--psv` | Valore PSV in €/Smc per il gas (sovrascrive l'ultimo mensile). Se omesso usa `PSV_MANUALE` del `.env`, poi il CSV. | auto |
| `--senza-vincoli` | Esclude offerte con condizioni limitanti (`LIMITANTE=01`: vincoli, obblighi, requisiti particolari) | - |
| `--no-oneri-recesso` | Esclude le offerte con penali di recesso (condizioni `tipologia=05`), sia `limitante` che `non limitante`. Le offerte che dichiarano esplicitamente "nessun onere/penale" non vengono escluse. Quando attivo, la colonna `Pen` sarà vuota perché le penali sono già escluse. Omettilo per vedere le penali evidenziate con ⚠. | - |
| `--penale-mese-max` | Esclude le offerte con penale superiore a X €/mese residuo. Si applica alle penali mensili; i cap espliciti passano (per questi usa `--penale-12m-max`). Le penali non quantificabili vengono escluse con avviso. | - |
| `--penale-12m-max` | Esclude le offerte con penale massima a 12 mesi superiore a Y €: cap esplicito oppure €/mese × mesi residui. Le penali non dichiarate/quantificabili nell'XML vengono escluse con un avviso. | - |
| `--sconti-condizionati` | Applica gli sconti condizionati di pagamento/fatturazione (`CONDIZIONE_APPLICAZIONE` diversa da `00`): SDD/domiciliazione, fattura elettronica, dematerializzazione, convergenza bundle. Non applica sconti legati a orari, consumi, appartenenza o fedeltà. Assume che le condizioni siano soddisfatte. | - |
| `--confronto-portale` | Esclude costi fissi identici (sigma1/sigma2) per allinearsi al portale ARERA | - |
| `--escludi-parole` | Esclude offerte con queste parole nelle condizioni contrattuali. Lista separata da virgola. Es: `--escludi-parole "fotovoltaico, pannelli"` | - |
| `--filtra-venditori` | Mostra **solo** le offerte dei venditori con queste PIVA (separate da virgola). Es: `--filtra-venditori 01877220366,001046` | - |
| `--aggiorna-dati` | Forza download file aggiornati dal portale (anziché usare la cache) | - |
| `--output` | `terminal` / `csv` / `both` | `terminal` |
| `--csv-path` | Percorso file CSV di output | auto |
| `--confronto-mia-offerta` | Confronta con la mia offerta attuale da `data/my_offer.json` (mostra riga ★ in fondo) | - |
| `--max` | Numero massimo di offerte da mostrare in tabella | `50` |
| `--ignora-sconti-promo` | Ignora sconti promozionali e temporanei: `VALIDITA=02` (promozioni esplicite) + sconti `VALIDITA=01` con durata incerta e keyword promozionali (es. "primo anno", "attivazione", "benvenuto") | - |
| `--regione` | Filtra per regione (codice ISTAT a 2 cifre o nome). Es: `--regione toscana` o `--regione 09`. Senza il flag, mostra tutte le offerte incluse quelle geolimitate. | - |
| `--verifica` | Verifica presenza offerte sul sito venditore via Google (Serper.dev). `--verifica` = colonna Check; `--verifica strict` = solo offerte verificate (scorre in batch, chiede tetto chiamate). Richiede `SERPER_API_KEY`. | - |
| `--popola-db` | Scarica i dati aperti, popola/aggiorna il database SQLite ed estrae le feature testuali con euristica rule-based | - |
| `--db-path` | Percorso del database SQLite (default: `data/offerte.db` per elettrico, `data/offerte_gas.db` per gas) | auto |
| `--no-llm` | Durante `--popola-db`, salta del tutto l'estrazione delle feature (booleani a 0) | - |
| `--batch-size` | Numero di offerte per chiamata LLM durante `--popola-db` (auto 10 per Ollama). Usato solo con `--no-rule-based` | `50` |
| `--llm-provider` | Provider LLM: `auto`, `zenmux`, `openrouter`, `ollama`. Usato solo con `--no-rule-based` | `auto` |
| `--llm-model` | Modello LLM da usare (sovrascrive variabile d'ambiente). Usato solo con `--no-rule-based` | quello del provider |
| `--llm-base-url` | Base URL custom per il provider LLM. Usato solo con `--no-rule-based` | quello del provider |
| `--no-rule-based` | Durante `--popola-db`, forza l'estrazione di tutte le feature con LLM, saltando l'euristica rule-based. ATTENZIONE: con LLM locali i tempi sono molto lunghi | - |

---

### Filtro penali (`--penale-mese-max` / `--penale-12m-max`)

Invece di escludere tutte le penali con `--no-oneri-recesso`, puoi usare due soglie:

```bash
# Penale max 2 €/mese residuo (es. Bee Flat 1,99 €/mese passa, Dolomiti 8 €/mese no)
python main.py --consumo-annuo 3559 --residente --penale-mese-max 2

# Penale max 300 € se recedi dopo 12 mesi (Dolomiti 48 = 288 € passa, Dolomiti 120 = 864 € no)
python main.py --consumo-annuo 3559 --residente --penale-12m-max 300

# Entrambe: la penale deve rispettare tutte e due le soglie
python main.py --consumo-annuo 3559 --residente --penale-mese-max 2 --penale-12m-max 300
```

Come vengono stimate:

- **cap esplicito** (es. “massimo 150 €”) → usato come penale a 12 mesi;
- **€/mese residuo** (es. “1,99 € per ogni mese residuo”) → rate × mesi residui (12 mesi);
- **nessuna penale dichiarata** → 0 €;
- **penale non dichiarata o solo formula** (es. “Oneri di Recesso Anticipato” senza importo, formule sui prezzi) → **esclusa con un avviso**, perché non è quantificabile in modo affidabile dall’XML.

Se una penale non è nell’XML ma la conosci dalla CTE, puoi aggiungerla in `data/penali_manuali.json` (file locale, non committato):

```json
{
  "DOLOMITI FISSO LUCE 48": {"tipo": "mensile", "rate": 8.0, "durata_mesi": 48}
}
```

Tipi supportati: `mensile` (`rate`, `durata_mesi`), `cap` (`importo`), `nessuna`. La chiave può essere il nome offerta esatto o il `cod_offerta`.

### Confronto con la mia offerta attuale (`--confronto-mia-offerta`)

Per confrontare le offerte del mercato con la tua tariffa attuale:

```bash
# 1. Copia lo stub
cp data/my_offer_stub.json data/my_offer.json

# 2. Modifica data/my_offer.json con i tuoi dati reali (prezzo energia, quote, ecc.)

# 3. Esegui con --confronto-mia-offerta
python main.py --consumo-annuo 1000 --tipo-offerta fisso --senza-vincoli --no-oneri-recesso --confronto-mia-offerta
```

La tua offerta comparirà in fondo alla tabella con `★` e label "Attuale".  
`my_offer.json` è in `.gitignore` (dati personali), `my_offer_stub.json` è tracciato come template.

#### Campi di `my_offer.json`

| Campo | Obbligatorio | Descrizione |
|---|---|---|
| `venditore` | ★ | Nome visualizzato (es. `"Edison"`) |
| `nome_offerta` | ★ | Nome offerta (es. `"EDISON DYNAMIC LUCE"`) |
| `tipo` | ★ | `"fisso"` o `"variabile"` |
| `tariffa` | ★ | `"monoraria"`, `"bioraria"` o `"trioraria"` |
| `prezzo_energia` | ★ | €/kWh. Spread sul PUN (variabile) o prezzo fisso. Se `scaglioni_energia` è presente, viene sovrascritto. |
| `quota_fissa` | ★ | €/anno |
| `quota_potenza` | ☆ | €/kW/anno (default 0) |
| `sconti` | ☆ | €/anno (negativo = risparmio, default 0) |
| `perdite_rete` | ☆ | Moltiplicatore PUN (es. `0.10` = +10% sul PUN). Se omesso usa `lambda` del CSV ARERA (0.10). |
| `altri_costi` | ☆ | Costi annui aggiuntivi non inclusi nelle quote (es. assicurazione gas 0.45 €/anno). Default 0. |
| `scaglioni_energia` | ☆ | Lista scaglioni consumo (opzionale). Es: `[{"da": 0, "a": 2200, "prezzo": 0.021}, {"da": 2201, "prezzo": 0.0}]`. `"a"` assente = infinito. Sostituisce `prezzo_energia`. |

---

### Verifica presenza sul sito venditore (`--verifica`)

Alcune offerte presenti negli Open Data potrebbero non essere effettivamente pubblicate sul sito del venditore.  
Con `--verifica` lo script cerca il codice offerta su Google tramite **Serper.dev**:

- **`--verifica`** (normale): mostra colonna `Check` (✓ trovata, ✗ non trovata). Le prime N offerte restano le più economiche.
- **`--verifica strict`**: mostra **solo** le offerte verificate, scorrendo verso il basso in batch finché non ne trova a sufficienza. Chiede all'utente quante offerte verificate cercare. La colonna Check e la riga ★ (mia offerta) sono sempre visibili.

La verifica usa **sempre entrambe** le ricerche:
- **Codice esatto**: `"cod_offerta" site:dominio_venditore` (con virgolette)
- **Nome rilassato**: `+parola1 +parola2 site:dominio_venditore` (tutte le parole obbligatorie)

La colonna Check mostra due simboli: es. `✓ ✗` (trovato per codice, non per nome) o `✗ ✓` (trovato solo per nome).

- **✓** (verde): trovata sul sito del venditore
- **✗** (rosso): non trovata
- **!** (rosso): errore di rete

I risultati vengono cachati in `data/verifica_cache.json` in formato v2 con timestamp (`cod`, `nome`, `ts` ISO8601).  
La cache permette riutilizzo parziale: se un'offerta ha solo la ricerca codice cachata, viene fatta solo la ricerca nome.  
Al termine dell'esecuzione, `warn_cache_stale(14)` segnala eventuali entry più vecchie di 14 giorni.

Per diagnosticare falsi positivi, gli URL dei risultati trovati vengono salvati in `data/verifica_urls.json` (struttura: codice offerta → `url_cod`, `url_nome`, `nome_offerta`, `venditore`, `ts`). Così puoi verificare manualmente in quale pagina/PDF Google ha trovato il match.

#### Ottenere una chiave Serper.dev

1. Vai su [serper.dev](https://serper.dev) e registrati (gratuito, 2500 ricerche/mese)
2. Nella dashboard troverai la tua **API Key**
3. Puoi impostare la chiave in uno dei seguenti modi:

   **Via variabile d'ambiente:**
   ```bash
   export SERPER_API_KEY="la_tua_chiave"
   ```

   **Via file `.env` nella root del progetto** (consigliato, caricato automaticamente):
   ```bash
   echo 'SERPER_API_KEY="la_tua_chiave"' >> .env
   ```

   **In alternativa**, aggiungila al tuo `~/.bashrc` o `~/.zshrc` per averla sempre disponibile:
   ```bash
   echo 'export SERPER_API_KEY="la_tua_chiave"' >> ~/.bashrc
   source ~/.bashrc
   ```

Senza la chiave, `--verifica` termina con un errore chiaro prima di iniziare la ricerca.

---

## Gas

Il comparatore supporta anche il **gas naturale** con `--commodity gas`.

```bash
# Popola il DB gas (separato da quello elettrico)
python main.py --popola-db --commodity gas

# Confronto gas: consumo in Smc, regione per l'ambito di distribuzione
python main.py --commodity gas --consumo-annuo 208 --regione toscana

# Confronto con la propria offerta gas
python main.py --commodity gas --consumo-annuo 208 --regione toscana --confronto-mia-offerta
```

- **Unità**: il consumo è in **Smc/anno**; `--potenza` e `--tipo-tariffa` non servono (gas monorario).
- **Prezzo**: per le offerte variabili si usa il **PSV** (`--psv` o `PSV_MANUALE`), non il PUN.
- **DB**: `data/offerte_gas.db` (separato da `data/offerte.db`).
- **Regione**: `--regione` serve per l'ambito di distribuzione gas (a1–a6). Senza regione viene usato l'ambito CENTRALE (a3).
- **Mia offerta gas**: `data/my_offer_gas.json` (template in `data/my_offer_gas_stub.json`). Per una variabile, `prezzo_energia` è lo spread sul PSV; `perdite_rete` va lasciato 0.
- **Prima/seconda casa**: per il gas usa `--residente` (prima casa, IVA 10% fino a 480 Smc) o `--non-residente` (seconda casa, IVA 22%).

### Approssimazioni del calcolo gas

Il calcolo gas è una prima implementazione, validata sulle offerte fisse contro Altroconsumo:

- oneri da `qt`, `qvd` (esclusa), `re`, `gs`, `rs`, `ug1`, `ug2` (esclusa), `ug3`, `tau1`, `tau3`, `st`/`vr`;
- contatore **classe <G6** (es. G4/G6) e uso **domestico**;
- scaglioni di consumo gas 0–120, 120–480, 480–1.560, 1.560–5.000, 5.000–80.000, oltre 80.000 Smc;
- **accise** gas domestiche stimate per scaglione (non sono nel CSV ARERA);
- **IVA**: 10% fino a 480 Smc/anno per uso domestico in prima casa, 22% oltre; 22% per seconda casa e non domestico;
- non è inclusa l'addizionale regionale gas;
- per le variabili si usa il PSV, non il CMEM; eventuali offerte indicizzate al CMEM vanno verificate.

Per questo i totali gas vanno considerati **stime** e vanno confrontati con la bolletta/CTE e con un comparatore esterno. La componente venditore e le offerte fisse sono le più affidabili.

## Architettura

```
comparatore_offerte/
├── main.py              # Entry point e orchestrazione
├── cli.py               # Argparse + modalità interattiva
├── downloader.py        # Download condizionato file open data
├── parser.py            # Parsing XML offerte + CSV parametri/prezzi
├── database.py          # Schema SQLite e funzioni upsert/lettura
├── extractor.py         # Estrazione feature testuali con euristiche rule-based (LLM opzionale)
├── popola_db.py         # Popolamento/aggiornamento del database
├── filters.py           # Motore filtri offerte
├── penali.py            # Stima penali di recesso + filtri --penale-mese-max/--penale-12m-max
├── calculator.py        # Calcolo spesa annua (venditore + PUN + oneri sistema)
├── formatter.py         # Output tabella terminale + CSV
├── venditori.py         # Mappa PIVA → nome commerciale
├── verifica.py          # Verifica presenza offerte su Google (Serper.dev) + cache
├── config.py            # Costanti, mappature codici XML, profili consumo
├── requirements.txt
├── README.md
└── data/                # Cache file scaricati + mappa venditori + offerte.db
```

### Flusso dati

1. `downloader` → scarica XML offerte ML + CSV parametri ML + CSV prezzi storici (solo se non aggiornati)
2. `parser` → converte XML in oggetti `Offerta` (con `ComponenteImpresa`, `CondizioneContrattuale`)
3. `database` → salva le offerte in SQLite; `extractor` estrae feature testuali con euristiche rule-based (LLM opzionale con `--no-rule-based`)
4. `filters` → applica filtri utente (tipo cliente, consumo, condizioni, ecc.)
5. `calculator` → per ogni offerta filtrata:
   - Somma componenti venditore (fisse, potenza, energia)
   - Aggiunge PUN per offerte a prezzo variabile
   - Aggiunge oneri di sistema dal CSV parametri
   - Applica IVA
6. `formatter` → stampa tabella ordinata per spesa + esporta CSV

---

### Database locale (opzionale)

Puoi usare un database SQLite al posto del parsing XML diretto. Questo permette:

- query esplorative sulle offerte;
- estrazione strutturata di informazioni dai campi testuali con euristiche rule-based;
- confronti più rapidi nelle esecuzioni successive.

Per popolare/aggiornare il DB:

```bash
# Popola il DB usando i dati aperti più recenti (default: euristica rule-based, veloce)
python main.py --popola-db

# Popola il DB senza estrarre le feature (booleani a 0)
python main.py --popola-db --no-llm

# Popola il DB usando un LLM (lento con modelli locali; utile solo con API veloci)
python main.py --popola-db --no-rule-based

# Scegli provider e modello esplicitamente (solo con --no-rule-based)
python main.py --popola-db --no-rule-based --llm-provider openrouter --llm-model deepseek/deepseek-v4-flash
python main.py --popola-db --no-rule-based --llm-provider ollama --llm-model phi4
```

Dopo il primo popolamento, `main.py` legge automaticamente le offerte dal DB. Se il DB è vecchio, le offerte mostrate sono quelle del giorno di popolamento: rilancia `--popola-db` per aggiornarle. Se vuoi forzare anche il re-download dei file:

```bash
python main.py --popola-db --aggiorna-dati
```

**Configurazione provider LLM** (variabile d'ambiente o `.env`, usata solo con `--no-rule-based`):

| Provider | Variabili | Default |
|---|---|---|
| ZenMux | `ZENMUX_API_KEY`, `ZENMUX_BASE_URL`, `ZENMUX_MODEL` | `https://zenmux.ai/api/v1`, `deepseek/deepseek-v4-flash` |
| OpenRouter | `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` | `https://openrouter.ai/api/v1`, `deepseek/deepseek-v4-flash` |
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `http://localhost:11434`, `phi4` |

Il provider può essere scelto anche a riga di comando con `--llm-provider`. Se imposti più chiavi, l'ordine di fallback è ZenMux → OpenRouter → Ollama.

**Nota sui tempi con LLM locali**: testato su Gemma 3 12B Q8_0 via Ollama, il modello impiega circa 15-20 secondi per offerta. Per questo motivo l'estrazione di default usa solo euristiche rule-based. L'LLM rimane disponibile come opzione avanzata per chi vuole verificarne i risultati o ha accesso a API remote veloci.

---

## Note tecniche

- **XML parsing**: il file offerte può superare i 20 MB. Usiamo `xml.etree.ElementTree.iterparse` con `clear()` per evitare saturazione RAM.
- **PUN dinamico**: il valore di default è l'**ultimo PUN mensile** disponibile nel CSV prezzi storici (aggiornato mensilmente dal portale). L'utente può sovrascriverlo con `--pun` (o con `PUN_MANUALE` nel `.env`) per simulare scenari. Se il CSV è fermo da più di 2 mesi, il programma stampa un avviso e suggerisce di usare `--pun`/`PUN_MANUALE`. Sulle offerte variabili il PUN viene maggiorato delle perdite di rete usando il parametro `lambda` del CSV ARERA (0.10); `my_offer.json` può sovrascrivere il valore con `perdite_rete`.
- **Oneri di sistema**: calcolati usando i parametri del CSV `PO_Parametri_Mercato_Libero_E_YYYYMMDD.csv`. I valori sono sommati in base al profilo (domestico residente / non residente / non domestico). La stima è approssimata ma confrontabile tra offerte.
- **Dispacciamento e Capacity Market**: il parametro `cdispd` del CSV ARERA è già la somma della quota Capacity Market (media di `cpty_mrkt_1/2/3`) e delle voci Terna (`msd`, `terna`, `interr`, `uniess`, `modeol`). Il calcolatore usa `cdispd` e non risomma i singoli parametri, evitando un doppio conteggio di ~0,06 €/kWh; i sotto-componenti sono usati solo come fallback se `cdispd` manca. `cpty_mrkt_mt` non è incluso in `cdispd` e non viene aggiunto.
- **Condizioni limitanti**: nel XML, il campo `LIMITANTE` con valore `01` indica condizioni vincolanti. Tuttavia alcune descrizioni standard come "ATTIVAZIONE FORNITURA" o "DISATTIVAZIONE FORNITURA` sono procedure burocratiche normali, non trappole. Il flag `--senza-vincoli` le esclude controllando `LIMITANTE=01`, la descrizione dell'offerta e una blacklist di parole chiave (pannelli fotovoltaici, socio, obblighi, bozza, ecc.). L'estrazione delle feature dal DB è basata su euristiche rule-based; l'LLM rimane opzionale.
- **Sconti automatici**: il parser estrae e applica gli sconti senza condizioni (`CONDIZIONE_APPLICAZIONE=00`, es. sconti attivazione) dal XML. Gli sconti condizionali (fattura elettronica, SDD) non vengono applicati automaticamente.
- **Sconti promozionali**: alcuni sconti hanno validità limitata (`VALIDITA=02`/`03`, es. "sconto primo mese", "sconto 1° anno", "sconto 2° anno"). Usa `--ignora-sconti-promo` per escluderli dal calcolo annuale. Il flag ora rileva anche sconti `VALIDITA=01` con keyword promozionali nel nome/descrizione (es. "primo anno", "attivazione", "benvenuto", "nei primi", "una tantum") per compensare dati XML imprecisi. **Attenzione**: gli sconti mensili ("primo mese", "secondo mese", "dodicesimo mese") senza `DURATA` esplicita vengono altrimenti applicati all'intero consumo annuale; per un confronto prudente usa `--ignora-sconti-promo`.
- **Sconti percentuali**: `UNITA_MISURA=06` (o nome/descrizione con `%`) viene trattato come percentuale. La base è il costo energia, salvo indicazioni di "quota fissa"/"commercializzazione" o "totale"; gli sconti dello stesso tipo ripetuti per 1° e 2° anno vengono applicati una sola volta per evitare doppi conteggi. `UNITA_MISURA=05` è trattato come importo una tantum in euro.
- **Sconti ripetuti per fascia**: alcuni XML ripetono lo stesso prezzo per F1/F2/F3 senza valorizzare `FASCIA_COMPONENTE`. Il calcolatore assegna le voci alle fasce del profilo (o usa la media se il numero non coincide) invece di sommarle sull'intero consumo, evitando di triplicare lo sconto.
- **Sconti con `UNITA_MISURA` mancante**: alcuni sconti nel XML hanno `UNITA_MISURA` vuota. L'euristica interna li classifica: se nome/descrizione contiene `%` → percentuale; se il nome è nella forma `sconto f[123]` (es. "Sconto F1") → €/kWh applicati alla fascia corrispondente (richiede offerta bioraria/trioraria); altrimenti → importo fisso annuo (€/anno).
- **Tipologie non gestite**: le offerte con `TIPO_OFFERTA` non mappato (es. `04`, offerte ibride) vengono saltate con un avviso, perché il calcolatore non saprebbe se applicare il PUN. Sono pochissime unità.
- **Fasce non standard (07/08)**: alcune offerte (~30) hanno `TIPOLOGIA_FASCE` vuota e componenti con fasce `07`/`08` (sempre in coppia sul componente energia, 07 > 08). Vengono mappate a `F1`/`F2` e si applica il profilo bioraria 50/50. Mappatura inferita dal pattern dei prezzi (non documentata ufficialmente da ARERA).
- **PUN unico per offerte variabili multioraria**: il calcolo applica un PUN mensile unico a tutto il consumo, anche per bioraria/trioraria. Il PUN reale è fasciato (PUN F1/F2/F3) e differisce per fascia. La distorsione è limitata (~18 offerte con spread diverso per fascia sono sensibili al problema); per la maggior parte delle offerte variabili multioraria lo spread è uniforme e il PUN unico è una semplificazione accettabile.
- **Colonna Confidenza** (`Conf`): ● verde = sconti con durata certa; ● giallo = sconti `VALIDITA=01` senza durata specificata nel XML (incertezza moderata); ● rosso = sconti `VALIDITA=01` con keyword promozionali e durata sconosciuta (probabile sconto temporaneo, il prezzo annuale potrebbe essere ottimista). La colonna è indipendente dal flag `--ignora-sconti-promo`.
- **Colonna Check**: sempre visibile. Senza `--verifica` mostra `? ?` in giallo (non verificato). Con `--verifica` mostra ✓/✗ (trovato/non trovato) per codice offerta e nome offerta.
- **Colonna Pen**: indica la presenza di penali/oneri di recesso anticipato (`tipologia=05`). ⚠ giallo = penale non limitante; ⚠ rosso = penale limitante (già escluse da `--senza-vincoli`). Vuoto = nessuna penale o dichiarazione esplicita di assenza di penali. **Attenzione**: con `--no-oneri-recesso` attivo, le offerte con penali vengono escluse (tranne quelle che dichiarano "nessun onere"), quindi la colonna Pen sarà naturalmente vuota — il filtro e l'indicatore visivo sono complementari (scegline uno). Usa `--no-oneri-recesso` per escludere a priori; omettilo per vederle evidenziate con ⚠.
- **Scaglioni di consumo**: l'XML può contenere componenti con fasce di consumo (`CONSUMO_DA`/`CONSUMO_A`) che applicano prezzi diversi a diverse soglie di kWh/anno (es. 0–2200 kWh a spread A, oltre 2200 a spread B). Il calcolatore supporta sia scaglioni su `euro_kwh` (ripartizione proporzionale) sia su `euro_anno` (selezione dell'unica fascia applicabile). Il formato `my_offer.json` supporta scaglioni via campo `scaglioni_energia`.
- **Tipo attivazione**: ogni offerta nel XML specifica per quali tipi di attivazione è valida (nuova, cambio fornitore, voltura, subentro). Usa `--tipo-attivazione cambio` per vedere solo offerte per cambio fornitore (switching).
- **Nomi venditori**: generati automaticamente dal dominio del sito web di ogni venditore. La mappa viene cachata in `data/venditori.json`. Se un nome non viene riconosciuto, viene mostrata la PIVA.
- **Verifica offerte (`--verifica`)**: usa l'API Serper.dev per cercare il codice offerta e il nome offerta su Google. Per ogni offerta vengono fatte sempre **entrambe** le ricerche (codice esatto + nome rilassato). Necessita di `SERPER_API_KEY` (variabile d'ambiente o `.env`). Gratuito 2500 ricerche/mese. I risultati sono cachati in `data/verifica_cache.json` (formato v2 con timestamp); gli URL dei match trovati sono salvati in `data/verifica_urls.json` per facilitare la diagnosi di falsi positivi.
- **Residenza**: la distinzione è tra **prima casa** (`--residente`) e **seconda casa** (`--non-residente`), non tra residenza anagrafica in Italia/estero.
- **Regioni**: l'XML include il campo `ZoneOfferta` con restrizioni regionali (`REGIONE`, codici ISTAT 01-20) e provinciali (`PROVINCIA`). Le offerte con restrizioni geografiche sono escluse automaticamente quando si usa `--regione`. Senza `--regione` vengono mostrate tutte. Usa `--regione toscana` o `--regione 09` per vedere solo quelle disponibili in Toscana.

---

## Esempio output terminale

Esempio illustrativo: PUN, oneri, offerte e valori cambiano ogni giorno e dipendono dai parametri usati.

```
RISULTATI (1344 offerte trovate, prime 8 mostrate)

   PUN: 0.1434 €/kWh
   Oneri fissi sistema: 155.53 €/anno | Oneri energia: 11.93 €/anno

#   Venditore         Offerta                                  Cod.Offerta                      Tipo  Tariffa Pen   Check  Conf  Spesa Tot.   Spesa Vend.
----------------------------------------------------------------------------------------------------------------------------------------------------------
1   CVA               CVA EASYFLEX (Sconto_Residenza 80€)      000784ESVFL04XXCVAEASYFLEXDRCASA Var                  ? ?    ●    204.30       0.00
2   SEL               Offerta Luce Sprint fasce                027095ESVFL02XXLUCESPRINTFASCEXX Var   Tri            ? ?    ●    212.91       7.06
...
5   Polisenergia      KINETICA (trioraria, QF 72€, spread 0.0   017247ESVFL08XX00000KINETICA2026 Var   Tri      ✓ ✗    ●    247.54       35.44
...
8   Sinergas          ALL DAY WEB LUCE                         000753ESFML06XXP0114PB3338260623 Fix   Mono     ✓ ✗    ●    265.00       49.75


Nota: gli importi sono stimati (IVA inclusa in Spesa Tot.).
PUN usato: 0.1434 €/kWh. Usa --pun per cambiarlo.
Usa --confronto-portale per escludere i costi fissi identici (sigma1/sigma2) e allinearti ai valori del portale ARERA.
```

---

## Licenza

Progetto personale / educativo basato su dati aperti pubblicati da ARERA / Acquirente Unico.
I dati sono proprietà del Portale Offerte luce e gas.

---

## Autore

Creato per uso personale di confronto offerte energetiche.

Sviluppato con [opencode](https://opencode.ai) e modelli DeepSeek V4 Flash e DeepSeek V4 Pro.
