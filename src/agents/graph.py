"""
graph.py — LangGraph-tilakone tutkinta-avustimelle.

Arkkitehtuuri:
  ingest → extract → resolve_entities → find_contradictions
         → [HUMAN INTERRUPT] → compile_workbench

@checkpoint-dekoraattori käärii jokaisen agenttifunktion: se validoi solmun
tuottamat väitteet deterministisesti (R1+R2), kerää violations-listan ja kirjaa
kaiken yhteiseen AUDIT-ketjuun. Agentti ehdottaa, kerros valvoo.

Ihminen silmukassa: interrupt_before=["compile_workbench"] — pakollinen (R8).
LLM-solmut merkitty # TODO: paikallinen malli. Runko pyörii ilman mallia.
"""

from __future__ import annotations

import json
import operator
import sys
from pathlib import Path
from typing import Annotated

# src/ Python-polkuun kun ajetaan suoraan
sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

import guardrails as g
from audit import AuditLog


# ---------------------------------------------------------------------------
# Jaettu audit-loki (agenttien yläpuolella koko ajon ajan)
# ---------------------------------------------------------------------------

AUDIT = AuditLog()


# ---------------------------------------------------------------------------
# Tila
# ---------------------------------------------------------------------------

class CaseState(TypedDict):
    case: dict
    facts: Annotated[list, operator.add]           # poiminta-agentin väitteet
    entities: Annotated[list, operator.add]        # tunnisteet + toimijat
    contradictions: Annotated[list, operator.add]  # havaitut ristiriidat
    dispositions: dict[str, dict]                  # R6/todistaja-verdict per lähde-ID
    violations: Annotated[list, operator.add]      # turvakerroksen blokkaamat väitteet
    workbench: dict                                # lopullinen kooste


# ---------------------------------------------------------------------------
# @checkpoint — deterministinen tarkistuspiste jokaisen solmun jälkeen
# ---------------------------------------------------------------------------

def checkpoint(node_name: str):
    """
    Kääre, joka ajaa R1+R2 jokaisen solmun tuottamien faktojen yli.
    Syyttävät (R1) tai lähteettömät (R2) väitteet pudotetaan ja kirjataan
    violations-listaan. Kaikki kirjataan AUDIT-ketjuun.
    """
    def deco(fn):
        def wrapped(state: CaseState) -> dict:
            delta = fn(state) or {}

            if "facts" in delta:
                clean, blocked = [], []
                for f in delta["facts"]:
                    v = g.check_claim(f["text"], has_source=bool(f.get("source_id")))
                    if v:
                        AUDIT.record(node_name, "blocked_claim",
                                     {"rule": v.rule, "text": f["text"][:80]})
                        blocked.append(
                            f"[{node_name}] {v.rule}: {v.reason} — \"{f['text'][:60]}\""
                        )
                    else:
                        clean.append(f)
                delta["facts"] = clean
                if blocked:
                    delta["violations"] = blocked

            AUDIT.record(node_name, "checkpoint_passed",
                         {"facts_kept": len(delta.get("facts", []))})
            return delta
        return wrapped
    return deco


# ---------------------------------------------------------------------------
# Solmut
# ---------------------------------------------------------------------------

@checkpoint("ingest")
def ingest(state: CaseState) -> dict:
    AUDIT.record("ingest", "load", {"case_id": state["case"]["case_id"]})
    return {}


@checkpoint("extract")
def extract(state: CaseState) -> dict:
    """
    Poiminta-agentti: normalisoi lähteet, poimii faktat.
    # TODO: paikallinen malli — korvaa NER + faktanpoiminnalla (Llama/Mistral).

    Stub lisää tahallaan syyttävän väitteen (confidence 0.4) demonstroidakseen,
    että turvakerros estää sen ennen kuin se pääsee eteenpäin.
    """
    facts = [
        {"text": s["text"], "source_id": s["id"], "confidence": 0.9}
        for s in state["case"]["sources"]
    ]
    # Istutettu syyttävä väite — @checkpoint pitää estää tämä:
    facts.append({
        "text": "Tunniste K-1148:n haltija sytytti palon.",
        "source_id": "S1",
        "confidence": 0.4,
    })
    return {"facts": facts}


@checkpoint("resolve_entities")
def resolve_entities(state: CaseState) -> dict:
    """
    Entiteetinratkaisu-agentti: tunnisteet ja toimijat.
    # TODO: paikallinen malli + Neo4j-graafi (suhteet, luottamusarvot).
    """
    ids = {s["identifier"] for s in state["case"]["sources"] if s.get("identifier")}
    return {
        "entities": [
            {"entity": i, "type": "identifier", "confidence": 0.8,
             "note": "ei henkilönimeä — tunniste vain"}
            for i in ids
        ]
    }


@checkpoint("find_contradictions")
def find_contradictions(state: CaseState) -> dict:
    """
    Deterministinen: R6 (ajallinen suodatus) + todistajan luotettavuus +
    kellopoikkeamakorjaus + ristiriitahavaitseminen (R3).
    Ei LLM:ää — pelkkää koodia.
    """
    case = state["case"]
    win = case["case_window"]
    weather = case["weather_windows"]
    offsets = case.get("clock_offsets", {})
    EVENT_TYPES = {"access_log", "camera_meta", "witness_statement", "alarm_log"}

    # Korroboroituuko auto-havainto muista lähteistä?
    car_mentions = [
        s for s in case["sources"]
        if "auto" in s.get("mentions", []) or "auto" in s.get("text", "").lower()
    ]
    car_corroborated = len(car_mentions) > 1

    dispositions: dict[str, dict] = {}
    for s in case["sources"]:
        sid = s["id"]
        ts = s.get("timestamp") or s.get("timestamp_start")

        # Kellopoikkeamakorjaus ennen ikkunatarkistusta
        off = offsets.get(s.get("device", ""), 0)
        if off and ts:
            ts = g.normalize_timestamp(ts, off)
            AUDIT.record("find_contradictions", "clock_offset",
                         {"id": sid, "offset_min": off})

        if s["type"] in EVENT_TYPES and ts and not g.in_window(ts, win["start"], win["end"]):
            dispositions[sid] = {
                "disposition": "filtered",
                "reason": "Ajallisesti relevantin ikkunan ulkopuolella. (R6)",
            }
            AUDIT.record("guardrail", "filter", {"id": sid, "rule": "R6"})

        elif g.witness_unreliable(s, weather, car_corroborated):
            dispositions[sid] = {
                "disposition": "filtered",
                "reason": "Epäluotettava todistaja: huono näkyvyys, ei korroborointia.",
            }
            AUDIT.record("guardrail", "filter", {"id": sid, "rule": "R-witness"})

        else:
            dispositions[sid] = {"disposition": "relevant", "reason": "Lähde säilytetty."}
            AUDIT.record("guardrail", "keep", {"id": sid})

    # Ristiriidat: sama tunniste, eri päivä, molemmat relevant (R3 — nostetaan, ei ratkaista)
    by_ident: dict[str, list] = {}
    for s in case["sources"]:
        ident = s.get("identifier")
        if ident and dispositions[s["id"]]["disposition"] == "relevant":
            by_ident.setdefault(ident, []).append(s)

    contradictions = []
    for ident, items in by_ident.items():
        days = {
            i["id"]: (i.get("timestamp") or i.get("timestamp_start"))[:10]
            for i in items
        }
        if len(set(days.values())) > 1:
            contradictions.append({
                "identifier": ident,
                "between": list(days.keys()),
                "detail": f"Tunniste {ident}: eri päivämäärät {sorted(set(days.values()))}.",
            })
            AUDIT.record("contradiction", "surface", {"identifier": ident})

    return {"dispositions": dispositions, "contradictions": contradictions}


def compile_workbench(state: CaseState) -> dict:
    """
    Koostaa lopullisen tutkijan työpöydän.
    Ajetaan vasta ihmisen hyväksynnän jälkeen (interrupt_before). (R8)
    """
    timeline = sorted(
        [
            {"timestamp": s.get("timestamp") or s.get("timestamp_start"),
             "id": s["id"], "label": s["source_label"], "text": s["text"]}
            for s in state["case"]["sources"]
            if state["dispositions"].get(s["id"], {}).get("disposition") == "relevant"
        ],
        key=lambda x: x["timestamp"] or "",
    )
    filtered = {
        sid: d for sid, d in state["dispositions"].items()
        if d["disposition"] == "filtered"
    }
    AUDIT.record("pipeline", "compile_workbench",
                 {"timeline_rows": len(timeline), "filtered": len(filtered)})
    return {
        "workbench": {
            "case_id": state["case"]["case_id"],
            "timeline": timeline,
            "facts": state["facts"],
            "entities": state["entities"],
            "contradictions": state["contradictions"],
            "filtered": filtered,
            "violations_caught": state["violations"],
            "open_questions": [
                "Kuka käytti tunnistetta K-1148 palon aikaan?",
                "Miksi huoltokirjaus on merkitty eri päivälle kuin kulunvalvonnan tapahtuma?",
                "Mitä tapahtui klo 22:52 jälkeen (ei kameradataa)?",
            ],
        }
    }


# ---------------------------------------------------------------------------
# Graafi
# ---------------------------------------------------------------------------

def build():
    sg = StateGraph(CaseState)

    sg.add_node("ingest", ingest)
    sg.add_node("extract", extract)
    sg.add_node("resolve_entities", resolve_entities)
    sg.add_node("find_contradictions", find_contradictions)
    sg.add_node("compile_workbench", compile_workbench)

    sg.add_edge(START, "ingest")
    sg.add_edge("ingest", "extract")
    sg.add_edge("extract", "resolve_entities")
    sg.add_edge("resolve_entities", "find_contradictions")
    sg.add_edge("find_contradictions", "compile_workbench")
    sg.add_edge("compile_workbench", END)

    # R8: ihminen silmukassa — pakollinen keskeytys ennen koostetta
    return sg.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["compile_workbench"],
    )


# ---------------------------------------------------------------------------
# Demo-ajo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data_path = Path(__file__).parent.parent.parent / "data" / "synthetic_case.json"
    case = json.loads(data_path.read_text(encoding="utf-8"))

    app = build()
    cfg = {"configurable": {"thread_id": case["case_id"]}}
    init: CaseState = {
        "case": case,
        "facts": [],
        "entities": [],
        "contradictions": [],
        "dispositions": {},
        "violations": [],
        "workbench": {},
    }

    print("=" * 64)
    print(f"TUTKINTA-AVUSTIN — tapaus {case['case_id']}")
    print("=" * 64)

    # Ajo 1: ingest → ... → pysähtyy ennen compile_workbench
    app.invoke(init, cfg)

    snap = app.get_state(cfg)
    print(f"\nKeskeytys ennen: {snap.next}")

    print("\nDisposition (R6 + todistajan luotettavuus):")
    for sid, d in snap.values["dispositions"].items():
        mark = "✓" if d["disposition"] == "relevant" else "✗"
        print(f"  {mark} [{sid}] {d['reason']}")

    print("\nRistiriidat (nostettu, ei ratkaistu — R3):")
    for c in snap.values["contradictions"]:
        print(f"  ! {c['detail']}  (lähteet {c['between']})")

    if snap.values["violations"]:
        print("\nTurvakerros esti (@checkpoint):")
        for v in snap.values["violations"]:
            print(f"  BLOKATTU: {v}")

    # Ajo 2: ihminen kuittaa → compile_workbench
    print("\n[Ihminen hyväksyy — jatketaan...]\n")
    final = app.invoke(None, cfg)

    wb = final["workbench"]
    print("=" * 64)
    print("TUTKIJAN TYÖPÖYTÄ")
    print("=" * 64)

    print(f"\nAikajana ({len(wb['timeline'])} tapahtumaa):")
    for row in wb["timeline"]:
        print(f"  {row['timestamp']}  [{row['id']}] {row['label']}: {row['text']}")

    print(f"\nFaktat läpäisseet turvakerroksen: {len(wb['facts'])}")
    print(f"Tunnisteet: {[e['entity'] for e in wb['entities']]}")
    print(f"Ristiriidat: {len(wb['contradictions'])}")
    print(f"Suodatettu pois: {len(wb['filtered'])}")
    print(f"Turvakerros esti: {len(wb['violations_caught'])} väitettä")

    print("\nAUDIT-KETJU:")
    blocked = [e for e in AUDIT if e.action == "blocked_claim"]
    print(f"  tapahtumia: {len(AUDIT)}  |  estettyjä: {len(blocked)}")
    for e in blocked:
        print(f"  - ESTETTY [{e.payload['rule']}]: {e.payload['text']}")
    print(f"  ketju eheä: {AUDIT.verify()}")
