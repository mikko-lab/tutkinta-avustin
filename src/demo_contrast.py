"""
demo_contrast.py — Esimerkki: mita deterministinen kerros + AI tuo rikostutkintaan.

Ajaa SAMAN synteettisen tapauksen kahdella tavalla:
  1) "AI yksin"            — ei turvakerrosta. Tuottaa itsevarman johtopaatoksen,
                             sekoittaa kohinan, ei lahteita, ei audit-jalkea.
  2) "AI + det. kerros"    — sama AI, mutta jokainen tuotos kulkee turvakerroksen lapi.

Ero naiden valilla ON se arvo, jonka kerros tuo: ei syytosta, lahteistetut faktat,
suodatettu kohina, nostetut ristiriidat, todennettava audit. Ihminen paattaa.
"""

from __future__ import annotations
import json
from pathlib import Path

import guardrails as g
from audit import AuditLog
import pipeline as P


def naive_ai(case: dict) -> dict:
    """AI ilman turvakerrosta: poimii kaiken ja tekee johtopaatoksen."""
    facts = [f'{s["text"]} (lahde {s["id"]})' for s in case["sources"]]
    conclusion = "Tunniste K-1148:n haltija sytytti palon."  # itsevarma, lahteeton syytos
    facts.append(conclusion)
    return {"facts": facts, "conclusion": conclusion,
            "noise_included": ["S4", "S6"], "sourced": False, "audit": False}


def governed(case: dict) -> dict:
    """AI + deterministinen kerros."""
    audit = AuditLog()
    audit.record("pipeline", "load", {"case_id": case["case_id"]})
    dispo = P.disposition(case, audit)
    _, contradictions = P.reconcile_and_contradict(case, dispo, audit)

    forbidden = "Tunniste K-1148:n haltija sytytti palon."
    blocked = g.check_claim(forbidden, has_source=True)

    return {
        "blocked": (forbidden, blocked),
        "relevant": [sid for sid, d in dispo.items() if d["disposition"] == "relevant"],
        "filtered": {sid: d["reason"] for sid, d in dispo.items()
                     if d["disposition"] == "filtered"},
        "contradictions": contradictions,
        "audit_events": len(audit),
        "audit_ok": audit.verify(),
        "metrics": P.metrics(case, dispo),
    }


def main():
    case = json.loads(
        (Path(__file__).parent / "data" / "synthetic_case.json").read_text(encoding="utf-8"))

    a = naive_ai(case)
    b = governed(case)

    print("=" * 68)
    print("ESIMERKKI: mita deterministinen kerros + AI tuo rikostutkintaan")
    print("=" * 68)

    print("\n--- 1) AI YKSIN (ei turvakerrosta) ---")
    print(f"  Johtopaatos: \"{a['conclusion']}\"")
    print(f"  -> nimeaa tekijan, lahteeton, itsevarma")
    print(f"  Kohina mukana: {a['noise_included']} (sumun todistaja, 2kk vanha halytys)")
    print(f"  Lahdesidonta: {'kylla' if a['sourced'] else 'EI'}")
    print(f"  Audit-jalki:  {'kylla' if a['audit'] else 'EI'}")
    print("  => Tama on Ulvila-tyyppinen virhe: vakuuttava, mutta todentamaton.")

    print("\n--- 2) AI + DETERMINISTINEN KERROS ---")
    fb, v = b["blocked"]
    print(f"  Sama syytos yritetaan: \"{fb}\"")
    print(f"  -> ESTETTY [{v.rule}]: {v.reason}")
    print(f"  Sailytetyt (lahteistetut) faktat: {b['relevant']}")
    print("  Suodatettu kohina:")
    for sid, reason in b["filtered"].items():
        print(f"    - [{sid}] {reason}")
    print("  Ristiriidat (nostettu, ei ratkaistu):")
    for c in b["contradictions"]:
        print(f"    - tunniste {c['identifier']}: {c['detail']}")
    print(f"  Audit: {b['audit_events']} tapahtumaa, ketju eheä: {b['audit_ok']}")
    print(f"  Mittarit: {b['metrics']}")

    print("\n" + "=" * 68)
    print("MITA KERROS TOI (arvon delta):")
    print("  AI yksin:        johtopaatos + nimi + kohina, ei lahteita, ei jalkea")
    print("  AI + det.kerros: rakenne + lahteet + suodatus + ristiriidat + audit,")
    print("                   EI nimea ketaan -> ihminen paattaa todennettavasta pohjasta")
    print("=" * 68)


if __name__ == "__main__":
    main()
