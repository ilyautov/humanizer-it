#!/usr/bin/env python3
"""Test di regressione dello score di pulizia. Senza pytest: assert puri,
esecuzione `python scripts/test_score.py`.

Fissano la calibrazione, perché una futura modifica dei pesi non rompa in
silenzio la separazione:
- testo IA e testo umano si separano nettamente per score;
- un testo umano denso/enciclopedico (molti nomi astratti, trattini) NON
  precipita in «riscrittura» per via di segnali deboli (morfosintassi/trattini);
- le fasce (pulito/ritocco/riscrittura) corrispondono al numero.

NB: le soglie sono euristiche e da ri-tarare sul corpus A/B italiano
(DeSegMa/Profiling-UD, vedi HANDOFF «sonda di misura»).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "humanizer-it" / "scripts"))

from humanizer_metrics import analyze, cleanliness_score

passed = 0


def check(cond: bool, msg: str) -> None:
    global passed
    assert cond, f"FAIL: {msg}"
    passed += 1


def score(text: str) -> int:
    return cleanliness_score(analyze(text)).score


def band(text: str) -> str:
    return cleanliness_score(analyze(text)).band


# --- IA e umano si separano nettamente -----------------------------------
ai = ("Nel mondo di oggi la tecnologia è uno strumento fondamentale. È importante "
      "notare che questo approccio non solo cambia il mercato, ma anche apre nuovi "
      "orizzonti. In conclusione, una soluzione completa porta il business al livello successivo.")
human = ("Ci ho provato tre volte. Niente. Poi ho capito qual era il problema: avevo "
         "scordato la cache. L'ho svuotata e è partito al primo colpo.")
check(score(ai) < score(human), "lo score dell'IA deve essere più basso di quello umano")
check(score(ai) < 40, f"il testo IA saturo deve essere basso, ottenuto {score(ai)}")
check(score(human) >= 85, f"il testo umano pulito ≥85, ottenuto {score(human)}")

# --- testo enciclopedico denso non deve precipitare in riscrittura --------
# Molti nomi astratti e un trattino, ma senza costrutti IA: i segnali deboli
# non devono affondarlo.
enc = ("Il Lago di Garda è il maggiore lago italiano per superficie. La sua "
       "estensione supera i trecentosettanta chilometri quadrati. La profondità "
       "massima raggiunge i trecentoquarantasei metri. Il bacino riceve le acque "
       "del fiume Sarca e si svuota nel Mincio, emissario verso la pianura padana.")
check(band(enc) != "rewrite",
      f"il testo enciclopedico denso senza costrutti IA non deve richiedere riscrittura, "
      f"ottenuto {score(enc)} [{band(enc)}]")

# --- le fasce corrispondono al numero ------------------------------------
for text in (ai, human, enc):
    s = score(text)
    b = band(text)
    expect = "clean" if s >= 85 else ("edit" if s >= 60 else "rewrite")
    check(b == expect, f"la fascia {b} non combacia con lo score {s} (atteso {expect})")

# --- score sempre nel range 0..100 ---------------------------------------
for text in (ai, human, enc, "", "una parola"):
    s = score(text)
    check(0 <= s <= 100, f"score fuori range: {s}")


# --- metriche document-level (S9 listicle, S8 paragrafi uniformi) ---------
def penalty_reasons(text: str) -> str:
    return " | ".join(r for r, _ in cleanliness_score(analyze(text)).penalties)


# Listicle: 8 voci uguali devono dare la penalità «listicle».
listicle = "Vantaggi\n\n" + "\n".join(f"- Punto numero {i} sulla qualità" for i in range(1, 9)) + "\n"
check("listicle" in penalty_reasons(listicle), "un listicle di 8 voci deve essere penalizzato")

# Paragrafi uniformi: 6 paragrafi della stessa lunghezza danno «paragrafi uniformi».
para = "Questa è la prima frase del paragrafo. Questa è la seconda frase del paragrafo."
uniform = "\n\n".join([para] * 6)
check("uniform paragraphs" in penalty_reasons(uniform), "6 paragrafi uniformi devono essere penalizzati (S8)")

# Inerzia sulla prosa breve: né listicle né paragrafi uniformi su 1-2 paragrafi senza elenchi.
short_prose = "Ci ho provato tre volte. Niente. Poi ho capito: avevo scordato la cache."
check("listicle" not in penalty_reasons(short_prose), "la prosa breve senza elenchi non è listicle")
check("uniform paragraphs" not in penalty_reasons(short_prose), "sulla prosa breve i paragrafi non si giudicano")

# Sotto la soglia di voci (3) — non è listicle.
small_list = "Elenco\n\n- uno\n- due\n- tre\n"
check("listicle" not in penalty_reasons(small_list), "3 voci non raggiungono la soglia del listicle")


# --- prosa viva: non deve essere falsamente penalizzata -------------------
# Stress-case dei falsi positivi: prosa con ritmo vario, frasi corte e lunghe
# alternate, qualche clitico — le metriche intelligenti devono leggerla come umana.
lit = ("Pioveva. Marco guardò fuori e non disse niente per un po'. "
       "Poi, come se quella pioggia gli avesse messo addosso una fretta improvvisa, "
       "afferrò il cappotto, lo infilò di corsa e uscì sbattendo la porta. "
       "Che freddo, però. Ci pensò solo dopo, sul tram.")
check(band(lit) != "rewrite",
      f"la prosa viva non deve richiedere riscrittura, ottenuto {score(lit)} [{band(lit)}]")
check(analyze(lit).rhythm.cv_len >= 0.45,
      "la prosa viva ha ritmo vario (CV alto) — la metrica intelligente legge l'umano")
check("uniform paragraphs" not in penalty_reasons(lit),
      "i paragrafi di lunghezza diversa non vanno penalizzati (S8 tace)")


if __name__ == "__main__":
    print(f"OK — {passed} controlli superati.")
