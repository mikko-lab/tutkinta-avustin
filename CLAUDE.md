# CLAUDE.md — Tutkinta-avustin

Tämä tiedosto on projektin **perustuslaki**. Säännöt ovat ei-neuvoteltavia.
Claude Code noudattaa niitä automaattisesti eikä ehdota mitään, joka rikkoo rajat.

---

## Projekti lyhyesti

Monen agentin jäsennysputki rikostutkinnan massa-aineistolle,
deterministisella turvakerroksella. Periaate:

> **AI jäsentää → deterministinen koodi valvoo → ihminen päättää.**

Järjestelmä **ei** nimeä epäiltyä, **ei** profiloi eikä ennusta.
Se jäsentää aineiston niin, että jokainen väite on sidottu lähteeseen,
ristiriidat nousevat esiin, aukot näkyvät — ja koko ketju on auditoitavissa.

---

## Kahdeksan kovaa sääntöä (kaikki ei-neuvoteltavia)

### R1 — Ei syyttävää väitettä
Järjestelmä ei koskaan nimeä ketään tekijäksi, epäillyksi tai syylliseksi.
`check_claim()` estää syyttävät predikaatit deterministisesti ennen outputtia.
Mikään agenttisolmu ei saa ohittaa tätä tarkistusta.

### R2 — Ei lähdettä → ei väitettä
Jokainen tuotettu väite on sidottava konkreettiseen lähde-ID:hen (esim. S1).
Lähteeton väite suodatetaan ennen kuin se pääsee outputtiin.

### R3 — Ristiriidat nostetaan, ei ratkaista
Kun kaksi lähdettä ovat ristiriidassa (sama tunniste, eri päivämäärät jne.),
järjestelmä raportoi ristiriidan sellaisenaan. AI ei saa valita "oikeaa" versiota.

### R4 — Deterministinen kerros agenttien yläpuolella
`guardrails.py` on ehdoton portti jokaisen LLM-solmun jälkeen.
Agentti *ehdottaa*, kerros *valvoo*. Järjestys ei muutu.

### R5 — Kaikki kirjataan audit-ketjuun
Jokainen putken askel — suodatus, pidättäminen, ristiriita, väiteblokki —
kirjataan `AuditLog`-ketjuun. Hash-ketju havaitsee jälkikäteisen muokkauksen.
Älä koskaan ohita `audit.record()`-kutsua.

### R6 — Ajallinen rajaus
Vain tapahtumalähteet (`access_log`, `camera_meta`, `witness_statement`, `alarm_log`)
suodatetaan tapausikkunan perusteella. Dokumentit (esim. työmääräykset) pysyvät.

### R7 — Ihmisen kuittaus ennen koostetta
LangGraph-tilakoneessa `interrupt_before=["compile_workbench"]` on pakollinen.
Kooste ei saa ajaa ilman ihmisen hyväksyntää keskeytyspisteessä.

### R8 — Vain synteettinen data kehityksessä
Kehitys ja testaus käyttävät **ainoastaan** `data/synthetic_case.json`-tiedostoa
tai vastaavaa kokonaan keksittyä dataa. Oikeaa tutkinta-aineistoa ei lisätä repoon.

### R9 — Paikallinen malli, ei pilvi-API
LLM-solmut käyttävät paikallisesti ajettavaa mallia (Llama/Mistral via Ollama).
Tutkinta-aineisto ei poistu omalta palvelimelta. Älä lisää OpenAI- tai
Anthropic-API-kutsuja tuotantokoodiin.

---

## Kansiorakenne

```
tutkinta-avustin/
├── CLAUDE.md              ← tämä tiedosto (lue aina ensin)
├── README.md              ← projektin kuvaus ja ajaminen
├── pyproject.toml
├── data/
│   └── synthetic_case.json   ← ainoa sallittu testidata
├── src/
│   ├── guardrails.py      ← deterministinen turvakerros (R1–R6)
│   ├── audit.py           ← hash-ketjutettu audit-loki (R5)
│   ├── pipeline.py        ← ajettava ydin ilman mallia
│   └── agents/
│       ├── __init__.py
│       └── graph.py       ← LangGraph-tilakone (LLM-solmut tynkinä)
└── .claude/
    └── settings.json
```

---

## Tekninen arkkitehtuuri

### LangGraph-solmut (toteutusjärjestys)

```
ingest → extract → [CHECKPOINT] → resolve_entities → [CHECKPOINT]
       → contradictions → [CHECKPOINT] → [HUMAN INTERRUPT]
       → compile_workbench
```

- `[CHECKPOINT]` = `guardrails.py`-tarkistus, pakollinen jokaisen LLM-solmun jälkeen
- `[HUMAN INTERRUPT]` = `interrupt_before=["compile_workbench"]`
- LLM-solmut merkitty `# TODO: paikallinen malli` — runko pyörii ilman mallia

### Sallitut shell-komennot

```bash
python3 src/pipeline.py          # deterministinen ydin, ei mallitarvetta
python3 src/agents/graph.py      # LangGraph-runko tynkäsolmuilla
pytest tests/                    # testit
```

---

## Mitä ei saa tehdä

- Älä lisää koodia, joka tekee syyttäviä johtopäätöksiä automaattisesti
- Älä ohita `check_claim()`-kutsua missään polulla
- Älä lähetä dataesimerkkejä ulkoisiin API:hin (OpenAI, Anthropic jne.)
- Älä tallenna oikeaa tutkinta-aineistoa repoon (edes esimerkinomaisesti)
- Älä poista `interrupt_before` LangGraph-konfiguraatiosta ilman erillistä päätöstä
- Älä refaktoroi `audit.py`:tä niin, että hash-ketjun eheys vaarantuu

---

## Viitelainsäädäntö

- EU AI Act art. 5(1)(d): ei profilointiin perustuvaa rikosriskin arviota → R1
- Annex III (korkea riski): läpinäkyvyys, ihmisvalvonta, audit → R5, R7
- GDPR / rikosasioiden tietosuojadirektiivi: datan rajaus → R8
- Chain of custody → R5 (hash-ketjutettu loki)
