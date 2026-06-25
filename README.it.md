# humanizer-it: umanizza il testo IA in italiano per Claude Code, Cursor, Codex e altri agenti

<p align="center">
  <a href="https://ilyautov.github.io/humanizer-it/"><img src="assets/social-preview.png" alt="humanizer-it — toglie i segni dell'IA dal testo italiano" width="640"></a>
</p>

🇬🇧 [English](README.md) · 🇮🇹 **Italiano**

Plugin per Claude Code / Cowork. Toglie l'odore dell'IA dal testo **italiano**. Lo [humanizer](https://github.com/blader/humanizer) inglese qui non serve, e nemmeno [humanizer-ru](https://github.com/ilyautov/humanizer-ru): i segni dell'IA in italiano sono una bestia a sé. È l'**«IA-taliano»** che la Treccani ha catalogato ufficialmente nel 2023 — i calchi dalla sintassi inglese (*impronte algoritmiche dell'inglese*, A.-M. De Cesare), il burocratese di stile nominale, gli *intercalari* mancanti (allora, insomma, magari) e i clitici ci/ne che fanno suonare vivo l'italiano, e l'ironia per *antifrasi* appiattita.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-blueviolet)](CHANGELOG.md)

> Fork italiano del collaudato [humanizer-ru](https://github.com/ilyautov/humanizer-ru). Stesso nucleo indipendente dalla lingua (perplexity/burstiness, modalità, sottrazione contrastiva, fact-lock, audit a quattro passaggi); il contenuto dei marcatori è ricostruito per l'italiano e fondato sulla ricerca in [CORPUS-MARKERS-IT / CORPUS-DESIGN-IT](https://github.com/ilyautov/humanizer-it).

## Cosa ottieni

Un catalogo di 52 segni in 12 categorie: burocratese / stile nominale (-zione, -mento), calchi dall'inglese e *translationese*, l'abuso della copula «è», le violazioni del pro-drop (io/tu/lui ridondanti) e i clitici ci/ne sotto-usati, i falsi amici (realizzare, eventualmente, attualmente), la sterilità emotiva, i trucchi di persuasione, il ritmo dell'informazione, più le impronte stilistiche del 2025-2026 (le frasi-meditazione di una sola parola, le catene pseudo-socratiche di domanda/risposta, l'emoji decorativa a ogni voce di elenco, il registro pseudo-terapeutico). **15 costruzioni vietate** che gridano «l'ha scritto un LLM», guidate dal parallelismo negativo «non solo… ma anche» e dal trattino lungo (in italiano nativo è più raro che in inglese — quindi *più* sospetto, e i rilevatori ne contano la frequenza).

Fa anche ciò che un rilevatore non sa fare: **rimette l'italiano vivo** — gli intercalari, i clitici ci/ne nei modi di dire, la dislocazione a sinistra («Il caffè lo prendo dopo»), l'ironia per litote e antifrasi, le espressioni idiomatiche vere. È questo che lo distingue da uno strumento di solo rilevamento come aipatterndetector.it.

Una sezione basata sulla ricerca spiega come funzionano davvero i rilevatori (perplexity, burstiness, morfosintassi nativa italiana) con il riferimento al benchmark italiano: **DeSegMa-IT @ EVALITA 2026** (UmBERTo ~0.9458) e l'intuizione chiave per cui i modelli nativi *from scratch* (Minerva-7B) vengono colti solo al ~50% di recall, mentre i modelli *English-first* trapelano oltre il 90% — perciò lo humanizer spinge il testo verso il baricentro dell'italiano nativo e zittisce i calchi dall'inglese.

## Scanner deterministico incluso — zero dipendenze

La skill include `scripts/scan.py`, la metà-macchina della modalità Audit. Conta ciò che un LLM valuta a occhio: i divieti assoluti, le categorie di marcatori, il ritmo delle frasi (burstiness) e la morfosintassi italiana (densità di nominalizzazioni, pro-drop, clitici ci/ne). A differenza della versione RU non serve **né spaCy né pymorphy** — solo la libreria standard di Python, così gira ovunque:

```bash
python3 skills/humanizer-it/scripts/scan.py file.txt
echo "il tuo testo" | python3 skills/humanizer-it/scripts/scan.py -
```

Stampa un punteggio `CLEANLINESS: N/100` e una fascia (pulito / ritocco / riscrittura). Vedi [`eval/`](eval/) per il banco di prova e [eval/RESULTS.md](eval/RESULTS.md) per i delta prima/dopo su un corpus stratificato (i testi IA puliti fino a zero divieti; i controlli umani da Wikipedia che passano puliti).

## Installazione

### 1. Claude.ai (interfaccia web)

1. Scarica il repo come ZIP: `https://github.com/ilyautov/humanizer-it/archive/refs/heads/main.zip`
2. Apri Claude.ai → **Settings** → **Capabilities** → **Skills**.
3. Clicca **Upload skill** e seleziona lo ZIP.

### 2. Organizzazioni (Enterprise e Team)

Gli amministratori dello workspace possono distribuire la skill da **Admin Console → Workspace Skills → Add skill**. Carica lo stesso ZIP, senza installazione per singolo utente.

### 3. Claude Code, Cowork, API (agenti locali)

**Marketplace dei plugin** (consigliato):

```
/plugin marketplace add ilyautov/humanizer-it
/plugin install humanizer-it@humanizer-it
```

**Manuale:**

```bash
git clone --depth 1 https://github.com/ilyautov/humanizer-it /tmp/humanizer-it
mkdir -p ~/.claude/skills
cp -r /tmp/humanizer-it/skills/humanizer-it ~/.claude/skills/
```

Copia l'intera cartella, non solo SKILL.md: la skill include lo scanner deterministico (`scripts/scan.py`). Nessun `pip install` — è solo libreria standard.

### 4. Codex CLI (OpenAI)

```bash
git clone --depth 1 https://github.com/ilyautov/humanizer-it
mkdir -p ~/.codex/skills
cp -r humanizer-it/skills/humanizer-it ~/.codex/skills/
```

Riavvia Codex dopo l'installazione; richiamala con `$humanizer-it` o lasciala attivare in automatico.

### 5. Altri agenti (standard SKILL.md condiviso)

Il formato Agent Skills è multipiattaforma. Altri agenti (Copilot, Cline, Roo Code, Goose, OpenCode, Cursor, Gemini CLI, …) leggono lo stesso `SKILL.md`: copia la cartella `skills/humanizer-it` nella directory delle skill dell'agente e riavvia.

## Modalità

- **Full edit** (predefinita): tutti i 52 segni, calibrazione della voce, audit a quattro passaggi.
- **Audit**: solo diagnosi, restituisce i segni rilevati con priorità A-D e un punteggio di pulizia.
- **Targeted fix**: lavora su una sola categoria.

## Uso

Chiedi in italiano:

```
Umanizza questo testo: [incolla il testo]
Riscrivilo, sembra un robot: [incolla il testo]
```

Attivatori: «umanizza», «togli i segni dell'IA», «rendilo naturale», «sembra artificiale», «riscrivi come un umano».

## Prima / Dopo

Prima:
> Nel mondo di oggi l'intelligenza artificiale riveste un ruolo sempre più importante. È importante notare che questa tecnologia rappresenta un potente strumento per l'ottimizzazione dei flussi di lavoro.

Dopo:
> Nell'ultimo anno ho messo strumenti IA in tre progetti. Due sono andati il doppio più veloci. Il terzo è saltato, perché il team ha smesso di controllare quello che sputava il modello.

In due frasi sono scattati diversi divieti assoluti («Nel mondo di oggi», «riveste un ruolo», «È importante notare che»). Tipico.

## I rilevatori IA funzionano sull'italiano?

Meglio che sulla maggior parte delle lingue, in realtà — l'italiano ha una sua linea di rilevamento nativa (DeSegMa-IT @ EVALITA 2026, UmBERTo ~0.9458 di accuratezza). Ma la lezione va nel verso opposto: i testi che sfuggono sono quelli generati da modelli **nativamente italiani**, mentre i modelli *English-first* vengono colti per la loro struttura anglosassone. Inseguire il «bypass del rilevatore» è l'obiettivo sbagliato. humanizer-it ottimizza la qualità reale del testo — toglie calchi, burocratese e cliché, rimette la voce dell'autore e il registro vivo — proprietà linguistiche misurabili (vedi [`eval/`](eval/)) indipendenti da qualsiasi classificatore. Perplexity e burstiness salgono come effetto collaterale.

## Fonti

Marcatori fondati sulla ricerca nativa italiana: Treccani («IA-taliano», stile nominale, segnali discorsivi, ironia), il gruppo ItaliaNLP / CNR-ISTI di Pisa (Puccetti, Pedrotti, Esuli, Dell'Orletta), DeSegMa-IT @ EVALITA 2026, Baroni & Bernardini 2006 (translationese), A.-M. De Cesare, più la letteratura sul rilevamento indipendente dalla lingua (DivEye, CoPA, AuthorMist). Provenienza completa e la distinzione tra marcatori candidati e misurati: `CORPUS-MARKERS-IT.md` / `CORPUS-DESIGN-IT.md`.

Changelog: [CHANGELOG.md](CHANGELOG.md). Metriche e banco di prova: [`scripts/`](scripts/) ed [`eval/`](eval/).

## Autore

Ilya Utov. Con la direzione e il reperimento delle fonti italiane di Mihai Istratii. Scrivo di IA e di lavoro con il testo su Telegram: [Under the Hood](https://t.me/gorilla_under_hood).

## Licenza

MIT
