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
- **Condizioni limitanti**: nel XML, il campo `LIMITANTE` con valore `01` indica condizioni vincolanti. Il flag `--solo-semplici` le esclude controllando sia `LIMITANTE=01` sia la descrizione dell'offerta per parole chiave (pannelli fotovoltaici, socio, obblighi, ecc.).
- **Sconti automatici**: il parser estrae e applica gli sconti senza condizioni (`CONDIZIONE_APPLICAZIONE=00`, es. sconti attivazione) dal XML. Gli sconti condizionali (fattura elettronica, SDD) non vengono applicati automaticamente.
- **Tipo attivazione**: ogni offerta nel XML specifica per quali tipi di attivazione è valida (nuova, cambio fornitore, voltura, subentro). Usa `--tipo-attivazione cambio` per vedere solo offerte per cambio fornitore (switching).
- **Nomi venditori**: generati automaticamente dal dominio del sito web di ogni venditore. La mappa viene cachata in `data/venditori.json`. Se un nome non viene riconosciuto, viene mostrata la PIVA.
- **Residenza**: la distinzione è tra **prima casa** (`--residente`) e **seconda casa** (`--non-residente`), non tra residenza anagrafica in Italia/estero.

---

## Esempio output terminale

```
RISULTATI (1360 offerte trovate, prime 50 mostrate):

#   Venditore            Offerta                Tipo       Tariffa    Spesa Totale €/anno   Spesa Venditore    PUN      Condizioni
-------------------------------------------------------------------------------------------------------------------------------
1   Martelius            LUCE SPAZIALE          fisso      monoraria  363.58                97.90              0.1200   No
2   CVA                  CVA 7                  fisso      monoraria  364.46                98.70              0.1200   No
3   Dolomiti Energia     DOLOMITI FISSO LUCE    fisso      monoraria  364.79                99.00              0.1200   No
...

Nota: gli importi sono stimati (IVA inclusa: 10% prima casa / 22% seconda casa).
Il PUN è parametrico: usa --pun per simulare diversi scenari.
Usa --confronto-portale per escludere i costi fissi identici (sigma1/sigma2) e allinearti ai valori del portale ARERA.
```

---

## Licenza

Progetto personale / educativo basato su dati aperti pubblicati da ARERA / Acquirente Unico.
I dati sono proprietà del Portale Offerte luce e gas.

---

## Autore

Creato per uso personale di confronto offerte energetiche.
