# Tutkinta-avustin (konsepti + ajettava ydin)

Monen agentin jasennysputki rikostutkinnan massa-aineistolle, **deterministisella
turvakerroksella**. Periaate: *AI jasentaa, deterministinen koodi valvoo, ihminen päättää.*

Järjestelma **ei** nimeä epäiltyä, **ei** profiloi eikä ennusta. Se jäsentää aineiston
niin, etta jokainen väite on sidottu lähteeseen, ristiriidat nousevat esiin, aukot
näkyvät — ja koko ketju on auditoitavissa (chain of custody).

## Mikä ajetaan nyt (ilman mallia)
Kova ydin on puhdasta Pythonia ja pyorii sellaisenaan:
- `data/synthetic_case.json` — täysin fiktiivinen tapaus, istutettu signaali + kohina + ground truth
- `guardrails.py` — deterministinen turvakerros (R1 ei syytösta, R2 ei lähdettä->ei väitettä, ajallinen relevanssi, todistajan luotettavuus, kellopoikkeaman korjaus)
- `audit.py` — hash-ketjutettu, append-only audit-loki; havaitsee peukaloinnin
- `pipeline.py` — ajaa tapauksen, tuottaa tutkijan työpoydan ja laskee precision/recall

```bash
python3 pipeline.py
```

Nykyinen ajo: noise_filter_precision 1.0, recall 1.0, signal_recall 1.0; audit-ketju eheä,
peukalointi havaitaan.

## Claude Code -jatko (LLM-agentit)
Tämä runko näyttää kovan ytimen ilman mallia. Seuraavat agentit toteutetaan
LangGraph-tilakoneena, paikallisella itse hostatulla mallilla (ei pilvi-API:a — aineisto
ei poistu omalta palvelimelta):
- poiminta-agentti (lahteiden normalisointi)
- entiteetinratkaisu-agentti (graafi: Neo4j; luottamusarvot)
- semanttinen haku (Qdrant / pgvector)

Deterministinen kerros ja audit pysyvät agenttien ylapuolella: agentti ehdottaa, kerros
valvoo, mikaan syyttävä tai lähteetön output ei läpäise.

## Suunnittelu seuraa laista
- EU AI Act art. 5(1)(d): ei profilointiin perustuvaa rikosriskin arviota -> R1
- Annex III (korkea riski): läpinäkyvyys, ihmisvalvonta, audit
- GDPR / rikosasioiden tietosuojadirektiivi: datan rajaus, erityistietoluokat
- Chain of custody -> hash-ketjutettu loki

## Rajat
Vain synteettinen data. Ei oikeaan aktiiviseen juttuun, ei oikeaan henkilöön, ei
profilointia, ei kasvojentunnistusta, ei elävien ihmisten tietojen haravointia.
