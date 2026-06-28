# Comparatore Offerte Energia Elettrica (Mercato Libero)

Script Python per interrogare, filtrare e confrontare le offerte di energia elettrica del **Mercato Libero** pubblicate nel Portale Offerte di ARERA / Acquirente Unico.

Utilizza i **dati aperti** (Open Data) aggiornati quotidianamente dal portale [ilportaleofferte.it](https://www.ilportaleofferte.it).

---

## Funzionalità

- **Download automatico condizionato** dei file open data (XML offerte, CSV parametri di sistema, CSV prezzi storici PUN)
- **Parsing intelligente** del grande file XML delle offerte con `iterparse` (gestisce file da decine di MB)
- **Nomi venditori leggibili**: le PIVA vengono automaticamente convertite in nomi commerciali (es. "Dolomiti Energia", "E.ON", "Iren") usando il dominio del sito venditore e il nome offerta
- **Filtri avanzati**:
  - Tipologia cliente (domestico / altri usi)
  - Tipologia offerta (prezzo fisso / variabile)
  - Tipologia tariffa (**tutte** / monoraria / bioraria / trifaria)
  - Tipo attivazione (**tutte** / nuova / cambio / voltura / subentro)
  - Range di consumo
  - Esclusione offerte con **condizioni limitanti** (vincoli, penali, obblighi socio, pannelli fotovoltaici, ecc.)
  - Esclusione offerte con **oneri di recesso**
  - Filtro per parole chiave nelle condizioni contrattuali
  - Filtro per venditore
  - Filtro per zona geografica (codice ISTAT o nome regione, es. `02` / `"valle d'aosta"`)
  - **Verifica presenza sul sito venditore** via Google (Serper.dev, opzionale, colonna Check ✓/✗)
  - **Colonna Confidenza** (● verde/giallo/rosso): segnala se gli sconti hanno durata certa o incerta
  - **Esclusione automatica** di offerte geolimitate con `--zona` se non compatibili con la regione specificata
- **Calcolo spesa annua stimata**:
  - Componenti del venditore (spread, quote fisse, quote potenza)
  - PUN parametrico (ultimo mensile o valore custom)
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

Dipendenze:
- `tabulate` (per la tabella a terminale)
- Solo librerie standard Python (no dipendenze pesanti)

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
| **trifaria** | `3`, `t`, `tri` |
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
python main.py --non-residente --consumo-annuo 100 --tipo-offerta fisso --tipo-attivazione cambio --solo-semplici --no-oneri-recesso --confronto-portale

# Solo prezzo variabile, seconda casa, PUN custom
python main.py --non-residente --consumo-annuo 2000 --tipo-offerta variabile --pun 0.12

# Solo prezzo fisso, trifaria, escludi offerte complicate, esporta CSV
python main.py \
  --consumo-annuo 1500 \
  --tipo-tariffa trifaria \
  --tipo-offerta fisso \
  --solo-semplici \
  --no-oneri-recesso \
  --download \
  --output both

# Prezzo variabile, escludi sconti promozionali (prime 5 offerte)
python main.py \
  --consumo-annuo 100 \
  --tipo-offerta variabile \
  --solo-semplici \
  --no-oneri-recesso \
  --confronto-portale \
  --ignora-sconti-promo \
  --max 5

# Filtra per zona geografica (solo offerte disponibili in Toscana)
python main.py \
  --consumo-annuo 2700 \
  --tipo-offerta tutte \
  --solo-semplici \
  --zona toscana

# Verifica presenza offerte sul sito venditore (richiede chiave Serper.dev)
export SERPER_API_KEY="la_tua_chiave"
python main.py \
  --consumo-annuo 2700 \
  --solo-semplici \
  --no-oneri-recesso \
  --verifica

# Verifica strict: solo offerte verificate (chiede tetto chiamate)
export SERPER_API_KEY="la_tua_chiave"
python main.py \
  --consumo-annuo 2700 \
  --solo-semplici \
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
| `--consumo-annuo` | Consumo stimato in kWh/anno | *richiesto* |
| `--potenza` | Potenza impegnata in kW | `3` |
| `--tipo-tariffa` | `tutte` / `monoraria` / `bioraria` / `trifaria` | `tutte` |
| `--tipo-offerta` | `tutte` / `fisso` / `variabile` | `tutte` |
| `--tipo-attivazione` | `tutte` / `nuova` / `cambio` / `voltura` / `subentro` | `tutte` |
| `--pun` | Valore PUN in €/kWh (sovrascrive l'ultimo mensile) | auto |
| `--solo-semplici` | Esclude offerte con `LIMITANTE=01` (vincoli) | - |
| `--no-oneri-recesso` | Esclude offerte con oneri di recesso (`LIMITANTE=01` come il portale) | - |
| `--confronto-portale` | Esclude costi fissi identici (sigma1/sigma2) per allinearsi al portale ARERA | - |
| `--exclude-condizioni` | Parole chiave da escludere (virgola) | - |
| `--venditori` | Filtra per PIVA venditori (virgola) | - |
| `--download` | Forza download file aggiornati | - |
| `--output` | `terminal` / `csv` / `both` | `terminal` |
| `--csv-path` | Percorso file CSV di output | auto |
| `--confronta` | Confronta con la mia offerta attuale da `data/my_offer.json` (vedi nota sotto) | - |
| `--max` | Numero massimo di offerte da mostrare in tabella | `50` |
| `--ignora-sconti-promo` | Ignora sconti promozionali e temporanei: `VALIDITA=02` (promozioni esplicite) + sconti `VALIDITA=01` con durata incerta e keyword promozionali (es. "primo anno", "attivazione", "benvenuto") | - |
| `--zona` | Filtra per zona geografica (codice ISTAT o nome, es. `02` / `"valle d'aosta"`). Se specificato, mostra solo offerte senza restrizioni geografiche o disponibili nella zona indicata. | - |
| `--verifica` | Verifica presenza offerte sul sito venditore via Google (Serper.dev). `--verifica` = colonna Check; `--verifica strict` = solo offerte verificate (scorre in batch, chiede tetto chiamate). Richiede `SERPER_API_KEY`. | - |

---

### Confronto con la mia offerta attuale (`--confronta`)

Per confrontare le offerte del mercato con la tua tariffa attuale:

```bash
# 1. Copia lo stub
cp data/my_offer_stub.json data/my_offer.json

# 2. Modifica data/my_offer.json con i tuoi dati reali (prezzo energia, quote, ecc.)

# 3. Esegui con --confronta
python main.py --consumo-annuo 1000 --tipo-offerta fisso --solo-semplici --no-oneri-recesso --confronta
```

La tua offerta comparirà in fondo alla tabella con `★` e label "Attuale".  
`my_offer.json` è in `.gitignore` (dati personali), `my_offer_stub.json` è tracciato come template.

---

### Verifica presenza sul sito venditore (`--verifica`)

Alcune offerte presenti negli Open Data potrebbero non essere effettivamente pubblicate sul sito del venditore.  
Con `--verifica` lo script cerca il codice offerta su Google tramite **Serper.dev**:

- **`--verifica`** (normale): mostra colonna `Check` (✓ trovata, ✗ non trovata). Le prime N offerte restano le più economiche.
- **`--verifica strict`**: mostra **solo** le offerte verificate, scorrendo verso il basso finché non ne trova a sufficienza. Chiede all'utente quante offerte verificate cercare. Se la cache è già piena, processa tutto in un colpo solo (senza chiamate API). La colonna Check e la riga ★ (mia offerta) sono sempre visibili.

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

#### Ottenere una chiave Serper.dev

1. Vai su [serper.dev](https://serper.dev) e registrati (gratuito, 2500 ricerche/mese)
2. Nella dashboard troverai la tua **API Key**
3. Imposta la variabile d'ambiente prima di lanciare lo script:

```bash
export SERPER_API_KEY="la_tua_chiave"
```

In alternativa, aggiungila al tuo `~/.bashrc` o `~/.zshrc` per averla sempre disponibile:

```bash
echo 'export SERPER_API_KEY="la_tua_chiave"' >> ~/.bashrc
source ~/.bashrc
```

Senza la chiave, `--verifica` mostrerà un avviso e salterà la verifica.

---

## Architettura

```
comparatore_offerte/
├── main.py              # Entry point e orchestrazione
├── cli.py               # Argparse + modalità interattiva
├── downloader.py        # Download condizionato file open data
├── parser.py            # Parsing XML offerte + CSV parametri/prezzi
├── filters.py           # Motore filtri offerte
├── calculator.py        # Calcolo spesa annua (venditore + PUN + oneri sistema)
├── formatter.py         # Output tabella terminale + CSV
├── venditori.py         # Mappa PIVA → nome commerciale
├── verifica.py          # Verifica presenza offerte su Google (Serper.dev) + cache
├── config.py            # Costanti, mappature codici XML, profili consumo
├── requirements.txt
├── README.md
└── data/                # Cache file scaricati + mappa venditori
```

### Flusso dati

1. `downloader` → scarica XML offerte ML + CSV parametri ML + CSV prezzi storici (solo se non aggiornati)
2. `parser` → converte XML in oggetti `Offerta` (con `ComponenteImpresa`, `CondizioneContrattuale`)
3. `filters` → applica filtri utente (tipo cliente, consumo, condizioni, ecc.)
4. `calculator` → per ogni offerta filtrata:
   - Somma componenti venditore (fisse, potenza, energia)
   - Aggiunge PUN per offerte a prezzo variabile
   - Aggiunge oneri di sistema dal CSV parametri
   - Applica IVA
5. `formatter` → stampa tabella ordinata per spesa + esporta CSV

---

## Note tecniche

- **XML parsing**: il file offerte può superare i 20 MB. Usiamo `xml.etree.ElementTree.iterparse` con `clear()` per evitare saturazione RAM.
- **PUN dinamico**: il valore di default è l'**ultimo PUN mensile** disponibile nel CSV prezzi storici (aggiornato mensilmente dal portale). L'utente può sovrascriverlo con `--pun` per simulare scenari.
- **Oneri di sistema**: calcolati usando i parametri del CSV `PO_Parametri_Mercato_Libero_E_YYYYMMDD.csv`. I valori sono sommati in base al profilo (domestico residente / non residente / non domestico). La stima è approssimata ma confrontabile tra offerte.
- **Condizioni limitanti**: nel XML, il campo `LIMITANTE` con valore `01` indica condizioni vincolanti. Il flag `--solo-semplici` le esclude controllando sia `LIMITANTE=01` sia la descrizione dell'offerta per parole chiave (pannelli fotovoltaici, socio, obblighi, bozza, ecc.).
- **Sconti automatici**: il parser estrae e applica gli sconti senza condizioni (`CONDIZIONE_APPLICAZIONE=00`, es. sconti attivazione) dal XML. Gli sconti condizionali (fattura elettronica, SDD) non vengono applicati automaticamente.
- **Sconti promozionali**: alcuni sconti hanno validità limitata (`VALIDITA=02`, es. "sconto primo mese", "sconto primi 6 mesi"). Usa `--ignora-sconti-promo` per escluderli dal calcolo annuale. Il flag ora rileva anche sconti `VALIDITA=01` con keyword promozionali nel nome/descrizione (es. "primo anno", "attivazione", "benvenuto", "nei primi", "una tantum") per compensare dati XML imprecisi.
- **Colonna Confidenza** (`Conf`): ● verde = sconti con durata certa; ● giallo = sconti `VALIDITA=01` senza durata specificata nel XML (incertezza moderata); ● rosso = sconti `VALIDITA=01` con keyword promozionali e durata sconosciuta (probabile sconto temporaneo, il prezzo annuale potrebbe essere ottimista). La colonna è indipendente dal flag `--ignora-sconti-promo`.
- **Tipo attivazione**: ogni offerta nel XML specifica per quali tipi di attivazione è valida (nuova, cambio fornitore, voltura, subentro). Usa `--tipo-attivazione cambio` per vedere solo offerte per cambio fornitore (switching).
- **Nomi venditori**: generati automaticamente dal dominio del sito web di ogni venditore. La mappa viene cachata in `data/venditori.json`. Se un nome non viene riconosciuto, viene mostrata la PIVA.
- **Verifica offerte (`--verifica`)**: usa l'API Serper.dev per cercare il codice offerta e il nome offerta su Google. Per ogni offerta vengono fatte sempre **entrambe** le ricerche (codice esatto + nome rilassato). Necessita della variabile d'ambiente `SERPER_API_KEY`. Gratuito 2500 ricerche/mese. I risultati sono cachati in `data/verifica_cache.json` (formato v2 con timestamp).
- **Residenza**: la distinzione è tra **prima casa** (`--residente`) e **seconda casa** (`--non-residente`), non tra residenza anagrafica in Italia/estero.
- **Zone geografiche**: l'XML include il campo `ZoneOfferta` con restrizioni regionali (`REGIONE`, codici ISTAT 01-20) e provinciali (`PROVINCIA`). Le offerte con restrizioni geografiche sono escluse automaticamente quando si usa `--zona`. Senza `--zona` vengono mostrate tutte. Usa `--zona toscana` o `--zona 09` per vedere solo quelle disponibili in Toscana.

---

## Esempio output terminale

```
RISULTATI (1344 offerte trovate, prime 8 mostrate)

   PUN: 0.1434 €/kWh
   Oneri fissi sistema: 155.53 €/anno | Oneri energia: 11.93 €/anno

#   Venditore         Offerta                                  Cod.Offerta                      Tipo  Tariffa Check  Conf  Spesa Tot.   Spesa Vend.
---------------------------------------------------------------------------------------------------------------------------------------------------
1   CVA               CVA EASYFLEX (Sconto_Residenza 80€)      000784ESVFL04XXCVAEASYFLEXDRCASA Var            ✗ ✗    ●    204.30       0.00
2   SEL               Offerta Luce Sprint fasce                027095ESVFL02XXLUCESPRINTFASCEXX Var   Tri      ✗ ✗    ●    212.91       7.06
...
5   Polisenergia      KINETICA (trifaria, QF 72€, spread 0.0   017247ESVFL08XX00000KINETICA2026 Var   Tri      ✓ ✗    ●    247.54       35.44
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
