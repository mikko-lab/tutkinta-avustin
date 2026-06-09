"""
guardrails.py — Deterministinen turvakerros.

Ei mallia, vaan koodia. Nama saannot patevat automaattisesti, eivatka agentit
voi ohittaa niita. Tama on koko jarjestelman ydin.

Saannot:
  R1  Ei syytosta / profilointia / ennustetta  (EU AI Act art. 5)
  R2  Ei lahdetta -> ei vaitetta
  R3  Ristiriita nostetaan, ei ratkaista
  R4  Luottamus nakyviin (ei toteutettu erikseen: jokainen disposition kantaa syyn)
  R5  Audit-loki hoidetaan audit.py:ssa
  R6  Datan rajaus (ajallinen relevanssi)
  R7/R8  kasitellaan putkessa / ihmisen kuittaus
"""

from __future__ import annotations
from datetime import datetime, timedelta
from dataclasses import dataclass


# --- R1: kielletyt, syyttavat predikaatit (henkiloon kohdistuva syyllisyys) ---
ACCUSATORY_PREDICATES = {
    "sytytti", "teki", "syyllinen", "tappoi", "murhasi", "varasti",
    "on tekija", "todennakoinen tekija", "syyllistyi",
}


@dataclass
class GuardrailViolation:
    rule: str
    reason: str


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def check_claim(claim_text: str, has_source: bool) -> GuardrailViolation | None:
    """R1 + R2. Palauttaa rikkomuksen tai None jos vaite sallitaan."""
    low = claim_text.lower()
    for pred in ACCUSATORY_PREDICATES:
        if pred in low:
            return GuardrailViolation(
                "R1", f"Estetty syyttava vaite (predikaatti '{pred}'). "
                      f"Jarjestelma ei nimea ketaan eika arvioi syyllisyytta.")
    if not has_source:
        return GuardrailViolation("R2", "Lahteeton vaite suodatettu.")
    return None


def in_window(ts: str, start: str, end: str) -> bool:
    return parse(start) <= parse(ts) <= parse(end)


def normalize_timestamp(ts: str, offset_min: int) -> str:
    """Korjaa tunnetun kellopoikkeaman ennen ristiriitatarkistusta."""
    return (parse(ts) + timedelta(minutes=offset_min)).isoformat()


def witness_unreliable(source: dict, weather_windows: list[dict],
                       corroborated: bool) -> bool:
    """R: todistaja epaluotettava, jos havainto osuu huonon nakyvyyden
    ikkunaan eika sita tue mikaan muu lahde."""
    if source["type"] != "witness_statement":
        return False
    t = parse(source["timestamp"])
    for w in weather_windows:
        if w.get("visibility") == "low" and parse(w["start"]) <= t <= parse(w["end"]):
            if not corroborated:
                return True
    return False
