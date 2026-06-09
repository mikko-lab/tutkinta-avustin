"""
app.py — Streamlit-demonakyma (ohut kerros logiikan paalla).

Nayttaa saman synteettisen tapauksen kolmesta nakokulmasta ja uudet mahdollisuudet.
EI sisalla saantoja — kutsuu pipeline.py / guardrails.py / demo_*.py -logiikkaa.

Aja:  streamlit run app.py

HUOM: demotyokalu, ei tuotantoarkkitehtuuri. Taysin synteettinen data.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

import pipeline as P
from audit import AuditLog
from demo_contrast import naive_ai, governed
from demo_perspectives import traditional

st.set_page_config(page_title="Tutkinta-avustin — demo", layout="wide")


@st.cache_data
def load_case() -> dict:
    p = Path(__file__).parent / "data" / "synthetic_case.json"
    return json.loads(p.read_text(encoding="utf-8"))


case = load_case()

st.title("Tutkinta-avustin — kolme nakokulmaa")
st.caption("Demo. Taysin synteettinen tapaus, kaikki nimet keksittyja paikkamerkkeja. "
           "Ei oikeaan dataan eika henkiloon. AI jasentaa, deterministinen koodi valvoo, ihminen paattaa.")

trad = traditional(case)
naive = naive_ai(case)
gov = governed(case)

# --- kolme nakokulmaa ---
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("⚫ Perinteinen")
    st.metric("Lahteita luettavana kasin", trad["items_to_review"])
    st.write("• Kohina sekoittuu signaaliin")
    st.write("• 0 ristiriitaa merkitty")
    st.write("• Yhteydet ihmismuistin varassa")
    st.info("Harkinta ja vastuu ihmisella — mutta ei skaalaudu.")

with c2:
    st.subheader("🔴 AI yksin")
    st.error(f"Johtopaatos: \"{naive['conclusion']}\"")
    st.write("→ nimeaa tekijan")
    st.write("→ lahteeton")
    st.write("→ ei audit-jalkea")
    st.warning("Nopea, suodattaa kohinaa — mutta kelpaamaton oikeudessa.")

with c3:
    st.subheader("🟢 AI + kerros")
    fb, v = gov["blocked"]
    st.error(f"Syytos estetty  [{v.rule}]")
    st.success(f"Lahteistetyt faktat: {', '.join(gov['relevant'])}")
    st.write("**Suodatettu kohina:**")
    for sid, reason in gov["filtered"].items():
        st.write(f"• [{sid}] {reason}")
    st.write("**Ristiriidat (nostettu, ei ratkaistu):**")
    for cc in gov["contradictions"]:
        st.write(f"• {cc['detail']}")
    if gov["audit_ok"]:
        st.success(f"Audit: {gov['audit_events']} tapahtumaa — ketju eheä ✅")
    else:
        st.error("Audit-ketju rikki ❌")

# --- mittarit ---
st.divider()
st.markdown("**Suodatustehon mittarit (synteettinen ground truth)**")
m1, m2, m3 = st.columns(3)
m1.metric("Kohina — precision", gov["metrics"]["noise_filter_precision"])
m2.metric("Kohina — recall", gov["metrics"]["noise_filter_recall"])
m3.metric("Signaali — recall", gov["metrics"]["signal_recall"])

# --- uudet mahdollisuudet ---
st.divider()
st.markdown("### Uudet mahdollisuudet")
p1, p2, p3 = st.columns(3)
with p1:
    st.markdown("#### 📂 Vanhat rikokset")
    st.write("Arkisto, jota ei ole luettu vuosiin, ajetaan lapi minuuteissa. "
             "Jarjestelma nostaa ohitetut yhteydet ja ristiriidat — ei nimea tekijaa, "
             "vaan antaa tutkijalle uuden todennettavan pohjan.")
with p2:
    st.markdown("#### 🔗 Tutkinnan laajuus")
    st.write("Tapausten valinen yhteys: sama tunniste tai toimintatapa eri jutuissa. "
             "Tutkijan aika siirtyy aineiston kahlaamisesta sen arviointiin.")
with p3:
    st.markdown("#### 🔍 Lapinakyva suodatus")
    st.write("Mitaan ei poisteta, vain siirretaan syrjaan perusteluineen. "
             "Ihminen nakee aina mita jai syrjaan — suodatus on peruttavissa.")

# --- chain of custody: interaktiivinen peukalointidemonstraatio ---
st.divider()
st.markdown("### Chain of custody")
st.caption("Hash-ketjutettu audit-loki: mika tahansa jalkikateinen muutos rikkoo ketjun.")
tamper = st.checkbox("Simuloi peukalointi (muuta yhta tapahtumaa)")

audit = AuditLog()
audit.record("pipeline", "load", {"case_id": case["case_id"]})
dispo = P.disposition(case, audit)
P.reconcile_and_contradict(case, dispo, audit)
if tamper and len(audit) > 2:
    list(audit)[2].payload["id"] = "TAMPERED"

if audit.verify():
    st.success("Ketju eheä ✅")
else:
    st.error("Peukalointi havaittu ❌ — ketju ei laillinen")
