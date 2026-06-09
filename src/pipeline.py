"""
pipeline.py — Deterministinen jasennysputki synteettiselle tapaukselle.

Ajaa lahteet lapi, soveltaa turvakerroksen saannot, tuottaa tutkijan tyopoydan
ja laskee suodatustehon (precision/recall) tunnettua ground truthia vasten.

LLM-pohjaiset agentit (poiminta, entiteetinratkaisu) ovat Claude Code -jatko;
tama runko nayttaa kovan ytimen ilman mallia.
"""

from __future__ import annotations
import json
from pathlib import Path

import guardrails as g
from audit import AuditLog


def load_case(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def disposition(case: dict, audit: AuditLog) -> dict[str, dict]:
    """Paataa jokaiselle lahteelle: relevant vai filtered (ja miksi)."""
    win = case["case_window"]
    weather = case["weather_windows"]
    out: dict[str, dict] = {}

    # esivalmistelu: korroboroituuko 'auto'-havainto muista lahteista?
    car_mentions = [s for s in case["sources"]
                    if "auto" in s.get("mentions", []) or "auto" in s["text"].lower()]
    car_corroborated = len(car_mentions) > 1

    # aikaikkuna koskee vain tapahtumalahteita, ei dokumentteja (esim. tyomaarays)
    EVENT_TYPES = {"access_log", "camera_meta", "witness_statement", "alarm_log"}

    for s in case["sources"]:
        sid = s["id"]
        ts = s.get("timestamp") or s.get("timestamp_start")

        # R6: ajallinen relevanssi (vain tapahtumat)
        if s["type"] in EVENT_TYPES and ts and not g.in_window(ts, win["start"], win["end"]):
            out[sid] = {"disposition": "filtered",
                        "reason": "Ajallisesti relevantin ikkunan ulkopuolella."}
            audit.record("guardrail", "filter", {"id": sid, "rule": "R6"})
            continue

        # todistajan luotettavuus
        if g.witness_unreliable(s, weather, car_corroborated):
            out[sid] = {"disposition": "filtered",
                        "reason": "Epaluotettava: huono nakyvyys, ei tukea muista lahteista."}
            audit.record("guardrail", "filter", {"id": sid, "rule": "R-witness"})
            continue

        out[sid] = {"disposition": "relevant", "reason": "Lahde sailytetty."}
        audit.record("guardrail", "keep", {"id": sid})

    return out


def reconcile_and_contradict(case: dict, dispo: dict, audit: AuditLog):
    """Korjaa kellopoikkeamat, sitten etsi aidot ristiriidat."""
    offsets = case.get("clock_offsets", {})
    # normalisoi kamera-aikaleimat
    norm = {}
    for s in case["sources"]:
        dev = s.get("device", "")
        off = offsets.get(dev, 0)
        if "timestamp_start" in s and off:
            norm[s["id"]] = g.normalize_timestamp(s["timestamp_start"], off)
            audit.record("reconcile", "clock_offset",
                         {"id": s["id"], "offset_min": off})

    # ristiriidat: sama tunniste, eri paiva
    contradictions = []
    by_ident: dict[str, list] = {}
    for s in case["sources"]:
        if s.get("identifier") and dispo[s["id"]]["disposition"] == "relevant":
            by_ident.setdefault(s["identifier"], []).append(s)
    for ident, items in by_ident.items():
        days = {i["id"]: (i.get("timestamp") or i.get("timestamp_start"))[:10] for i in items}
        uniq = set(days.values())
        if len(uniq) > 1:
            contradictions.append({
                "identifier": ident,
                "between": list(days.keys()),
                "detail": f"Tunniste {ident}: eri paivamaarat {sorted(uniq)}.",
            })
            audit.record("contradiction", "surface", {"identifier": ident})
    return norm, contradictions


def metrics(case: dict, dispo: dict) -> dict:
    gt = case["ground_truth"]
    true_noise = set(gt["noise"])
    true_signal = set(gt["signal"])
    filtered = {sid for sid, d in dispo.items() if d["disposition"] == "filtered"}
    relevant = {sid for sid, d in dispo.items() if d["disposition"] == "relevant"}

    def safe(n, d): return round(n / d, 2) if d else 1.0
    return {
        "noise_filter_precision": safe(len(filtered & true_noise), len(filtered)),
        "noise_filter_recall": safe(len(filtered & true_noise), len(true_noise)),
        "signal_recall": safe(len(relevant & true_signal), len(true_signal)),
    }


def workbench(case: dict, dispo: dict, contradictions: list, audit: AuditLog):
    print("=" * 64)
    print(f"TUTKIJAN TYOPOYTA — tapaus {case['case_id']}")
    print("=" * 64)

    print("\nAIKAJANA (sailytetyt lahteet):")
    rows = []
    for s in case["sources"]:
        if dispo[s["id"]]["disposition"] == "relevant":
            t = s.get("timestamp") or s.get("timestamp_start")
            rows.append((t, s["id"], s["source_label"], s["text"]))
    for t, sid, lbl, txt in sorted(rows):
        print(f"  {t}  [{sid}] {lbl}: {txt}")

    print("\nRISTIRIIDAT (nostetaan, ei ratkaista):")
    if contradictions:
        for c in contradictions:
            print(f"  - {c['detail']}  (lahteet {c['between']})")
    else:
        print("  (ei havaittu)")

    print("\nAVOIMET KYSYMYKSET:")
    print("  - Kuka kaytti tunnistetta K-1148 palon aikaan?")
    print("  - Miksi huoltokaynti on merkitty eri paivalle kuin kulunvalvonnan tapahtuma?")
    print("  - Mita tapahtui klo 22:52 jalkeen (ei kameradataa)?")

    print("\nSUODATETTU POIS (kohina / eparelevantti):")
    for sid, d in dispo.items():
        if d["disposition"] == "filtered":
            print(f"  - [{sid}] {d['reason']}")

    print("\nTURVAKERROS — demonstraatio (R1: ei syytosta):")
    forbidden = "Tunniste K-1148:n haltija sytytti palon."
    v = g.check_claim(forbidden, has_source=True)
    print(f"  Yritetty vaite: \"{forbidden}\"")
    print(f"  -> ESTETTY [{v.rule}]: {v.reason}")
    audit.record("guardrail", "block_claim", {"rule": v.rule})

    allowed = "Tunniste K-1148 avasi takaoven klo 22:47 (lahde S1)."
    v2 = g.check_claim(allowed, has_source=True)
    print(f"  Sallittu vaite: \"{allowed}\"")
    print(f"  -> {'SALLITTU (faktapohjainen, lahteistettu)' if v2 is None else v2.reason}")


def main():
    here = Path(__file__).parent.parent
    case = load_case(str(here / "data" / "synthetic_case.json"))
    audit = AuditLog()
    audit.record("pipeline", "load_case", {"case_id": case["case_id"]})

    dispo = disposition(case, audit)
    _, contradictions = reconcile_and_contradict(case, dispo, audit)
    workbench(case, dispo, contradictions, audit)

    print("\n" + "=" * 64)
    print("MITTARIT (synteettinen ground truth):")
    for k, v in metrics(case, dispo).items():
        print(f"  {k}: {v}")

    print("\nAUDIT-KETJU:")
    print(f"  tapahtumia: {len(audit)}")
    print(f"  ketju eheä (verify): {audit.verify()}")
    # demonstroi havaitseminen: peukaloidaan ja tarkistetaan uudelleen
    ev = list(audit)[2]
    ev.payload["id"] = "TAMPERED"
    print(f"  ketju peukaloinnin jalkeen: {audit.verify()}  (havaittu)")


if __name__ == "__main__":
    main()
