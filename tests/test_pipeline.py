"""
Regressiotestit deterministiselle ytimelle.

Varmistaa että jokaisen koodimuutoksen jälkeen:
  - R1 estää syyttävän väitteen
  - R2 estää lähteettömän väitteen
  - kohina suodatetaan oikein (S4 todistaja, S6 aikaikkuna)
  - signaali säilyy (S1, S2, S3)
  - ristiriita K-1148:lla nousee esiin
  - precision/recall pysyy 1.0 synteettistä ground truthia vasten
  - audit-ketju havaitsee peukaloinnin
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import guardrails as g
import pipeline as p
from audit import AuditLog


@pytest.fixture(scope="module")
def case():
    path = Path(__file__).parent.parent / "data" / "synthetic_case.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dispo(case):
    return p.disposition(case, AuditLog())


# --- R1: syyttävä väite estetään ---

def test_r1_estaa_syyttavan_vaitteet():
    v = g.check_claim("K-1148:n haltija sytytti palon.", has_source=True)
    assert v is not None and v.rule == "R1"

def test_r1_sallii_faktaväitteen():
    v = g.check_claim("Tunniste K-1148 avasi takaoven klo 22:47 (lähde S1).", has_source=True)
    assert v is None

@pytest.mark.parametrize("teksti", [
    "Henkilo X teki murron.",
    "Epailty on syyllinen.",
    "Han murhasi uhrin.",
    "Haltija varasti laitteen.",
    "Han on todennäköinen tekijä.",
])
def test_r1_kaikki_kiellettyt_predikaatit(teksti):
    v = g.check_claim(teksti, has_source=True)
    assert v is not None and v.rule == "R1", f"Pitäisi estää: {teksti!r}"


# --- R2: lähteeton väite estetään ---

def test_r2_estaa_lahteettoman_vaitteet():
    v = g.check_claim("Jotain tapahtui.", has_source=False)
    assert v is not None and v.rule == "R2"

def test_r2_sallii_lahteistetyn_vaitteet():
    v = g.check_claim("Takaovi avattiin (lähde S1).", has_source=True)
    assert v is None


# --- Suodatus: kohina pois, signaali säilyy ---

def test_todistaja_sumun_aikaan_suodatetaan(dispo):
    # S4: havainto huonon näkyvyyden aikana, ei korroborointia → R-witness
    assert dispo["S4"]["disposition"] == "filtered"

def test_aikaikkuna_suodattaa_vanhan_halytin(dispo):
    # S6: murtoalytin 2kk ennen palon yötä → R6
    assert dispo["S6"]["disposition"] == "filtered"

@pytest.mark.parametrize("sid", ["S1", "S2", "S3"])
def test_signaalilahteet_sailyvat(dispo, sid):
    assert dispo[sid]["disposition"] == "relevant", f"{sid} pitäisi säilyä"


# --- Ristiriita: K-1148 kahdella eri päivämäärällä ---

def test_ristiriita_nousee_esiin(case, dispo):
    _, contradictions = p.reconcile_and_contradict(case, dispo, AuditLog())
    assert len(contradictions) == 1
    c = contradictions[0]
    assert c["identifier"] == "K-1148"
    assert "2024-03-15" in c["detail"]
    assert "2024-03-16" in c["detail"]

def test_ristiriita_ei_ratkaise(case, dispo):
    # Järjestelmä nostaa ristiriidan — ei valitse "oikeaa" versiota (R3)
    _, contradictions = p.reconcile_and_contradict(case, dispo, AuditLog())
    c = contradictions[0]
    # Molemmat lähteet mainitaan, kumpaakaan ei hylätä
    assert "S1" in c["between"] and "S3" in c["between"]


# --- Mittarit: precision/recall 1.0 ground truthia vasten ---

def test_mittarit_taydelliset(case, dispo):
    m = p.metrics(case, dispo)
    assert m["noise_filter_precision"] == 1.0, "kohinaa säilytetty väärin"
    assert m["noise_filter_recall"] == 1.0, "kohinaa jäi läpi"
    assert m["signal_recall"] == 1.0, "signaali katosi"


# --- Audit-ketju ---

def test_audit_ketju_eheä():
    audit = AuditLog()
    audit.record("testi", "toiminto", {"arvo": 1})
    audit.record("testi", "toiminto", {"arvo": 2})
    assert audit.verify() is True

def test_audit_havaitsee_peukaloinnin():
    audit = AuditLog()
    audit.record("testi", "toiminto", {"arvo": 1})
    audit.record("testi", "toiminto", {"arvo": 2})
    list(audit)[0].payload["arvo"] = 999  # peukalointi
    assert audit.verify() is False

def test_audit_kirjaa_kaikki_askeleet(case):
    audit = AuditLog()
    p.disposition(case, audit)
    # Jokaisesta lähteestä pitää olla kirjaus
    actors = {e.actor for e in audit}
    assert "guardrail" in actors
