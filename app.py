"""
app.py — Kolme näkökulmaa samaan aineistoon.

Ohut näkymäkerros src/:n logiikan päällä.
Aja: streamlit run app.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
from demo_contrast import naive_ai, governed
from demo_perspectives import traditional

# ---------------------------------------------------------------------------
# Data — lasketaan kerran
# ---------------------------------------------------------------------------

@st.cache_data
def load():
    path = Path(__file__).parent / "data" / "synthetic_case.json"
    return json.loads(path.read_text(encoding="utf-8"))

case = load()
source_map = {s["id"]: s for s in case["sources"]}

t = traditional(case)
a = naive_ai(case)
b = governed(case)

# ---------------------------------------------------------------------------
# Sivurakenne
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Tutkinta-avustin",
    page_icon="⚖️",
    layout="wide",
)

st.title("Tutkinta-avustin — kolme näkökulmaa samaan aineistoon")
st.caption(
    f"Tapaus **{case['case_id']}** · {case['description']}"
)
st.divider()

col_t, col_a, col_b = st.columns(3, gap="large")

# ---------------------------------------------------------------------------
# 1) PERINTEINEN
# ---------------------------------------------------------------------------

with col_t:
    st.markdown("## ⚫ Perinteinen tutkinta")
    st.markdown("*Ihminen kahlaa aineiston itse*")

    st.markdown("#### Aineisto käsin")
    for s in case["sources"]:
        st.markdown(f"- [{s['id']}] **{s['source_label']}**  \n  *{s['text']}*")

    st.markdown("#### Takeet")
    st.markdown(
        "- Kohina eroteltu: **EI** — sekoittuu signaaliin\n"
        "- Ristiriitoja merkitty: **0** — piilossa massaan\n"
        "- Lähdeviittaukset: **ihmismuistin varassa**\n"
        "- Audit-jälki: **ei automaattista**"
    )

    st.info(
        "✅ Harkinta ja vastuu ihmisellä  \n"
        "❌ Ei skaalaudu — massa-aineisto vie tunteja tai viikkoja"
    )

# ---------------------------------------------------------------------------
# 2) AI YKSIN
# ---------------------------------------------------------------------------

with col_a:
    st.markdown("## 🔴 AI yksin — ei turvakerrosta")
    st.markdown("*Nopea, mutta vastuuton*")

    st.error(f'Johtopäätös: **"{a["conclusion"]}"**')
    st.markdown("Järjestelmä nimesi tekijän — **lähteetta, ilman tarkistusta**.")

    st.markdown("#### Kaikki lähteet mukana")
    for f in a["facts"]:
        if "sytytti" in f.lower():
            st.markdown(f"- 🔴 `{f}`")
        elif any(x in f for x in ["S4", "S6"]):
            st.markdown(f"- 🟡 `{f}`  ← kohina mukana")
        else:
            st.markdown(f"- `{f}`")

    st.markdown("#### Takeet")
    c1, c2 = st.columns(2)
    c1.metric("Lähdesidonta", "EI")
    c2.metric("Audit-jälki", "EI")

    st.warning(
        "✅ Nopea, suodattaa kohinaa  \n"
        "❌ Nimeää tekijän ilman lähteitä tai jälkeä  \n"
        "❌ Kelpaamaton oikeudessa"
    )

# ---------------------------------------------------------------------------
# 3) AI + DETERMINISTINEN KERROS
# ---------------------------------------------------------------------------

with col_b:
    st.markdown("## 🟢 AI + deterministinen kerros")
    st.markdown("*Skaala ja vastuu*")

    blocked_text, violation = b["blocked"]
    st.success(
        f"**ESTETTY [{violation.rule}]** — syytös ei pääse läpi  \n"
        f"*\"{blocked_text}\"*"
    )

    st.markdown("#### Säilytetyt lähteet — lähteistettu")
    for sid in b["relevant"]:
        s = source_map[sid]
        st.markdown(f"- ✅ **[{sid}]** {s['source_label']}  \n  *{s['text']}*")

    st.markdown("#### Suodatettu kohina — syineen, läpinäkyvästi")
    for sid, reason in b["filtered"].items():
        s = source_map[sid]
        st.markdown(f"- ❌ **[{sid}]** {s['source_label']}  \n  ↳ *{reason}*")

    st.markdown("#### Ristiriidat — nostettu, ei ratkaistu (R3)")
    for c in b["contradictions"]:
        st.markdown(
            f"- ⚠️ {c['detail']}  \n"
            f"  *(lähteet: {', '.join(c['between'])})*"
        )

    m = b["metrics"]
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Kohina — tarkkuus", f"{m['noise_filter_precision']:.0%}")
    mc2.metric("Kohina — kattavuus", f"{m['noise_filter_recall']:.0%}")
    mc3.metric("Signaali", f"{m['signal_recall']:.0%}")

    audit_ok = b["audit_ok"]
    st.markdown(
        f"#### Audit-ketju  \n"
        f"{'✅' if audit_ok else '❌'} **{b['audit_events']} tapahtumaa** · "
        f"{'eheä' if audit_ok else 'rikki'} · peukalointi havaittavissa"
    )

    st.info(
        "✅ Nopea kuin AI  \n"
        "✅ Ei nimeä ketään — ihminen päättää  \n"
        "✅ Jokainen fakta sidottu lähteeseen  \n"
        "✅ Audit kestää oikeudellisen tarkastelun"
    )

# ---------------------------------------------------------------------------
# Uudet mahdollisuudet
# ---------------------------------------------------------------------------

st.divider()
st.markdown("## Mitä kolmas tila tuo — uudet mahdollisuudet")

p1, p2, p3 = st.columns(3, gap="large")

with p1:
    st.markdown("#### 📂 Vanhojen rikosten selvittäminen")
    st.markdown(
        "Arkisto, jota kukaan ei ole lukenut vuosiin, ajetaan läpi minuuteissa. "
        "Järjestelmä nostaa ristiriidat ja yhteydet, jotka ihminen ohitti — "
        "mutta **ei nimeä tekijää**, vaan antaa tutkijalle uuden todennettavan pohjan."
    )
    st.markdown(
        "Kun uutta dataa tulee — uusi rekisteri, tekniikan kehitys, DNA — "
        "koko aineisto voidaan ajaa uudelleen automaattisesti."
    )

with p2:
    st.markdown("#### 🔗 Tutkinnan laajuus")
    st.markdown(
        "Tapausten välinen yhteys: sama tunniste tai toimintatapa eri jutuissa "
        "nousee esiin automaattisesti — ei ihmismuistin varassa."
    )
    st.markdown(
        "Tutkijan aika siirtyy **aineiston kahlaamisesta sen arviointiin**. "
        "Skaala ilman vastuun luopumista."
    )

with p3:
    st.markdown("#### 🔍 Läpinäkyvä suodatus — reunaehto")
    st.markdown(
        "Suodatus on **läpinäkyvä ja peruttavissa** — mitään ei poisteta, "
        "vain siirretään syrjään perusteluineen. Ihminen näkee aina mitä jäi syrjään."
    )
    st.markdown(
        "Ilman tätä kohinan suodatus olisi vaarallinen — se voisi haudata "
        "ratkaisevan vihjeen. Tämän kanssa se on työkalu, johon voi luottaa."
    )

st.divider()
st.caption(
    "Vain synteettinen data. Ei oikeaan henkilöön, ei aktiiviseen juttuun. "
    "· EU AI Act art. 5(1)(d) · GDPR/LED · Chain of custody: hash-ketjutettu audit"
)
