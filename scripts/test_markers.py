#!/usr/bin/env python3
"""Test di regressione delle metriche. Senza pytest: assert puri, esecuzione
`python scripts/test_markers.py`.

Fissano classi di errore già viste, perché non tornino:
- il parallelismo negativo «non è X, è Y» richiede la virgola (niente falso ban
  sulla coordinazione «non è qui ma è arrivato»);
- il trattino lungo viene contato, il trattino corto no;
- gli artefatti copia-incolla dal chatbot vengono colti (regola indipendente
  dalla lingua, tenuta verbatim dal RU);
- testo IA e testo umano si separano nettamente per metriche.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "humanizer-it" / "scripts"))

from humanizer_metrics import analyze
from humanizer_metrics.markers import scan_hard_bans, scan_markers

passed = 0


def check(cond: bool, msg: str) -> None:
    global passed
    assert cond, f"FAIL: {msg}"
    passed += 1


def ban_names(text: str) -> set[str]:
    return {h.marker for h in scan_hard_bans(text)}


# --- parallelismo negativo ------------------------------------------------
check("Non solo X, ma anche Y" in ban_names("Non solo migliora i processi, ma anche apre nuovi scenari."),
      "«non solo… ma anche» viene colto")
check("Non è X, (ma) è Y" in ban_names("Non è un costo, è un investimento."),
      "«non è X, è Y» (con virgola) viene colto")
check("Non è X, (ma) è Y" not in ban_names("Non è qui ma è arrivato poco fa."),
      "coordinazione senza virgola NON viene bannata")

# --- trattino -------------------------------------------------------------
check("Trattino lungo (em-dash «—»)" in ban_names("Questo è un trattino lungo — marcatore."),
      "trattino lungo colto")
check("Trattino lungo (em-dash «—»)" not in ban_names("Questo trattino-corto va bene."),
      "trattino corto non colto come em-dash")
check(analyze("Testo — con trattino.").rhythm.em_dash == 1, "em_dash contato")
check(analyze("Testo con parola-composta.").rhythm.em_dash == 0, "trattino corto non conta come em_dash")

# --- HARD BANS di base ----------------------------------------------------
check("Gioca/svolge un ruolo cruciale/fondamentale/chiave" in ban_names("L'IA gioca un ruolo fondamentale qui."),
      "«gioca un ruolo fondamentale» colto")
check("È importante notare/sottolineare che" in ban_names("È importante notare che funziona."),
      "«è importante notare che» colto")
check("Vale la pena ricordare/sottolineare/notare" in ban_names("Vale la pena ricordare questo aspetto."),
      "«vale la pena ricordare» colto")
check("Sfruttare/sbloccare il (pieno) potenziale" in ban_names("Permette di sfruttare il pieno potenziale dei dati."),
      "«sfruttare il pieno potenziale» colto")

# --- conclusione formulaica: solo a inizio frase/clausola -----------------
INC = "In conclusione / In sintesi / In definitiva / Per concludere / Riassumendo"
check(INC in ban_names("Il mercato cresce. In conclusione, la scelta è ovvia."),
      "«In conclusione» a inizio frase (dopo punto) colto")
check(INC in ban_names("In sintesi, vediamo il risultato."),
      "«In sintesi» a inizio testo colto")
check(INC not in ban_names("Sono giunti in conclusione del viaggio dopo ore."),
      "«in conclusione» a metà frase (non connettivo) NON bannato")

# --- copertura: OGNI hard ban ha un esempio positivo ----------------------
# Gate durevole: se si aggiunge un ban senza esempio (o se ne rompe il regex),
# il test cade. Le chiavi devono coincidere con HARD_BANS uno a uno.
from humanizer_metrics.markers import HARD_BANS

HARD_BAN_SAMPLES = {
    "Non solo X, ma anche Y": "Non solo migliora i processi, ma anche apre nuovi scenari.",
    "Non si tratta (solo) di X, ma di Y": "Non si tratta di un costo, ma di un investimento.",
    "Non è X, (ma) è Y": "Non è un costo, è un investimento.",
    "Gioca/svolge un ruolo cruciale/fondamentale/chiave": "L'IA gioca un ruolo fondamentale qui.",
    "In conclusione / In sintesi / In definitiva / Per concludere / Riassumendo": "Il mercato cresce. In conclusione, la scelta è ovvia.",
    "È importante notare/sottolineare che": "È importante notare che funziona.",
    "Va notato/detto/sottolineato che": "Va sottolineato che i numeri salgono.",
    "È interessante notare che": "È interessante notare che il trend cambia.",
    "Vale la pena ricordare/sottolineare/notare": "Vale la pena ricordare questo aspetto.",
    "Trattino lungo (em-dash «—»)": "Questo è un trattino lungo — marcatore.",
    "Sfruttare/sbloccare il (pieno) potenziale": "Permette di sfruttare il pieno potenziale dei dati.",
    "Nel mondo di oggi / Nell'era digitale / Al giorno d'oggi": "Nel mondo di oggi tutto cambia in fretta.",
    "In un mondo/contesto/scenario sempre più …": "In un contesto sempre più competitivo, serve metodo.",
    "Portare al livello successivo / al prossimo livello": "Questo porta il prodotto al livello successivo.",
    "Aprire nuovi orizzonti / scenari / prospettive": "Questa scelta apre nuovi orizzonti per il team.",
}
check(set(HARD_BAN_SAMPLES) == {name for name, _ in HARD_BANS},
      "ogni hard ban ha un esempio di copertura (chiavi == HARD_BANS)")
for _name, _sample in HARD_BAN_SAMPLES.items():
    check(_name in ban_names(_sample), f"hard ban «{_name}» scatta sul suo esempio")

# --- scanner rapido (densità) ---------------------------------------------
check(len(scan_markers("Inoltre, tuttavia, pertanto, di conseguenza.")) >= 3,
      "i connettivi vengono colti dallo scanner")
check(len(scan_markers("Una soluzione completa con approccio olistico.")) >= 1,
      "i marcatori marketing vengono colti")


# --- artefatti copia-incolla dai chatbot (indipendente dalla lingua) ------
def marker_cats(text: str) -> set[str]:
    return {h.category for h in scan_markers(text)}


check("Copy-paste-artifacts" in marker_cats(
    "Maggiori dettagli nella fonte :contentReference[oaicite:3]{index=3} a riguardo."),
    "nota oaicite colta")
check("Copy-paste-artifacts" in marker_cats(
    "Il link https://example.com/?utm_source=chatgpt.com porta al sito."),
    "utm_source=chatgpt.com colto")
check("Copy-paste-artifacts" in marker_cats("Vedi turn3search7 e turn12file1."),
    "etichette turnN con qualsiasi numero colte (regex)")
check("Copy-paste-artifacts" in marker_cats("L'output citeturn0file2 è rimasto."),
    "citeturn unito colto")
check("Copy-paste-artifacts" in marker_cats("File: [scarica](sandbox:/mnt/data/report.pdf)"),
    "link sandbox colto")
check("Copy-paste-artifacts" in marker_cats(f"Testo con{chr(0xE200)}etichette{chr(0xE204)} invisibili."),
    "separatori invisibili U+E200-E204 colti")
check("Copy-paste-artifacts" in marker_cats("È rimasto </think> dal ragionamento."),
    "residuo del tag think colto")
check("Copy-paste-artifacts" not in marker_cats(
    "Testo normale con note Markdown [^1] e [^3^], e link https://example.com?utm_source=newsletter."),
    "note Markdown e utm_source altrui non danno falsi artefatti")
check("Copy-paste-artifacts" not in marker_cats(
    "Testo normale con link https://example.com e nota [3]."),
    "testo pulito non dà falsi artefatti")

from humanizer_metrics.markers import marker_verdict
check("pasted from an AI response" in marker_verdict(scan_markers("Vedi citeturn0search1.")),
    "un solo artefatto = verdetto univoco, fuori scala")

# --- separazione IA vs umano per metriche ---------------------------------
ai = analyze("Nel mondo di oggi la tecnologia gioca un ruolo fondamentale. "
             "È importante notare che questo approccio apre nuovi orizzonti.")
human = analyze("Ci ho provato tre volte. Niente. Poi ho capito: avevo scordato la cache.")
check(ai.hard_ban_count > human.hard_ban_count, "l'IA ha più HARD BANS dell'umano")
check(human.rhythm.cv_len > ai.rhythm.cv_len, "l'umano ha ritmo più vario (CV più alto)")


if __name__ == "__main__":
    print(f"OK — {passed} controlli superati.")
