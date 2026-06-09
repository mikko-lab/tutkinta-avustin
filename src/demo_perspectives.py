"""
demo_perspectives.py — Kolme nakokulmaa samaan aineistoon.

Nayttaa miten PERINTEINEN tutkinta, AI YKSIN ja AI + DETERMINISTINEN KERROS
kasittelevat saman synteettisen tapauksen — ja mita uutta kolmas tila tuo
rikostutkintaan ja vanhojen rikosten selvittamiseen.

Ydinviesti:
  perinteinen      = harkinta & vastuu, mutta ei skaalaa
  AI yksin         = skaala, mutta ei vastuuta (nimeaa, ei lahteita, ei jalkea)
  AI + det. kerros = skaala JA vastuu -> tutkija saa todennettavan pohjan
"""

from __future__ import annotations
import json
from pathlib import Path

import pipeline as P
from audit import AuditLog
from demo_contrast import naive_ai, governed


def traditional(case: dict) -> dict:
    """Perinteinen: ihminen saa raakamateriaalin, lukee kaiken itse."""
    items = case["sources"]
    return {
        "items_to_review": len(items),
        "noise_separated": False,       # kohina sekoittuu signaaliin
        "contradictions_flagged": 0,    # piiloon massaan
        "cross_source_links": 0,        # ihmismuistin varassa
        "note": "Ihminen lukee kaiken lineaarisesti; harkinta ja vastuu ihmisella.",
    }


def main():
    case = json.loads(
        (Path(__file__).parent / "data" / "synthetic_case.json").read_text(encoding="utf-8"))

    t = traditional(case)
    a = naive_ai(case)
    b = governed(case)

    print("=" * 70)
    print("KOLME NAKOKULMAA SAMAAN AINEISTOON")
    print("=" * 70)

    print("\n--- PERINTEINEN TUTKINTA ---")
    print(f"  Luettavaa kasin: {t['items_to_review']} lahdetta")
    print(f"  Kohina eroteltu: {'kylla' if t['noise_separated'] else 'EI (sekoittuu)'}")
    print(f"  Ristiriitoja merkitty: {t['contradictions_flagged']}")
    print(f"  + Harkinta ja vastuu ihmisella")
    print(f"  - Ei skaalaudu: massa-aineisto vie tunteja/viikkoja")

    print("\n--- AI YKSIN (ei kerrosta) ---")
    print(f"  Johtopaatos: \"{a['conclusion']}\"")
    print(f"  + Nopea, suodattaa kohinaa")
    print(f"  - Nimeaa tekijan, ei lahteita, ei audit-jalkea -> kelpaamaton")

    print("\n--- AI + DETERMINISTINEN KERROS ---")
    fb, v = b["blocked"]
    print(f"  Syytos \"{fb}\" -> ESTETTY [{v.rule}]")
    print(f"  Sailytetyt lahteistetut faktat: {len(b['relevant'])}")
    print(f"  Suodatettu kohina (syineen): {len(b['filtered'])}")
    print(f"  Ristiriitoja nostettu: {len(b['contradictions'])}")
    print(f"  Audit: {b['audit_events']} tapahtumaa, eheä: {b['audit_ok']}")
    print(f"  + Skaala JA vastuu: tutkija saa todennettavan pohjan")
    print(f"  + EI nimea ketaan -> ihminen paattaa")

    print("\n" + "=" * 70)
    print("UUDET MAHDOLLISUUDET")
    print("=" * 70)
    print("""  Vanhojen rikosten selvittaminen:
    - Arkisto, jota kukaan ei ole lukenut uudelleen vuosiin, ajetaan lapi
      minuuteissa. Jarjestelma nostaa ristiriidat ja yhteydet, jotka ihminen
      ohitti — mutta EI nimea tekijaa, vaan antaa tutkijalle uuden pohjan.
    - Kun uutta dataa tulee (uusi rekisteri, tekniikan kehitys kuten DNA),
      koko aineisto voidaan ajaa uudelleen automaattisesti.

  Tutkinnan laajuus:
    - Tapausten valinen yhteys: sama tunniste / toimintatapa eri jutuissa.
    - Tutkijan aika siirtyy aineiston kahlaamisesta sen arviointiin.

  Reunaehto, joka tekee taman mahdolliseksi:
    - Suodatus on LAPINAKYVA ja PERUTTAVISSA — mitaan ei poisteta, vain
      siirretaan syrjaan perusteluineen. Ihminen nakee aina mita jai syrjaan.
    - Vain AI + deterministinen kerros on kaytettava: AI yksin ei kelpaa
      oikeudessa, perinteinen ei skaalaa.""")
    print("=" * 70)


if __name__ == "__main__":
    main()
