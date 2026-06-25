# humanizer-it site (GitHub Pages)

The project's SEO/GEO site. Static HTML, no build step, no Jekyll.
URL: https://ilyautov.github.io/humanizer-it/

The site copy is in **Italian** (the target audience searches in Italian), while
the skill's own UI/output language is English.

## Enabling GitHub Pages

1. Open the repo on GitHub → **Settings** → **Pages**.
2. Under **Build and deployment** → **Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`. Save.
4. After a minute the site is live at https://ilyautov.github.io/humanizer-it/

## Structure

- `index.html` — landing page.
- `togliere-tracce-ia.html` — practical how-to guide.
- `segni-testo-ia.html` — reference of the 52 AI-text markers (IA-taliano).
- `rilevatori-ia-italiano.html` — do AI detectors work on Italian (GEO asset).
- `antiplagio-vs-ia.html` — plagiarism checkers vs AI detectors.
- `style.css` — shared styles.
- `sitemap.xml`, `robots.txt` — for search engines.

## Local preview

```
cd docs && python3 -m http.server 8000
```

Open http://localhost:8000

## Principles

- Plain HTML5 + one CSS, no frameworks, no external JS/CDN.
- Each page: unique title/description, canonical, Open Graph, Twitter card, JSON-LD.
- Italian copy with no em-dashes and no burocratese: the site is itself a sample
  of what the skill does.
