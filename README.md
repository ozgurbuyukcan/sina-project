# SINA — Hydraulic Monitoring & Decision Support

Public, static **project showcase** for SINA Prototype 1 and the Xylem Global Student Innovation Challenge 2026.

**This repository contains only the website, not the private/local SINA application code or sensor database.**

## What is included
- A responsive GitHub Pages presentation of the **SCAN → IDENTIFY → NAVIGATE → ASSESS** workflow and **LEARNING DATA** research loop.
- Five actual application screenshots made with a **synthetic offline demo**.
- One SVG graph generated directly from a verified slice of **911 real but unlabeled irrigation measurements**. Source: [Walid et al. (2024), Mendeley Data v2](https://doi.org/10.17632/w9594tjkwp.2).
- Transparent statements about earlier exploratory controlled hydraulic tests and current software-test coverage.

## Run locally
Open `docs/index.html` in a browser, or use `python -m http.server 8000 --directory docs` and visit `http://localhost:8000`.

## Publish on GitHub Pages
Go to repository **Settings → Pages → Build and deployment → Deploy from a branch → main → /docs → Save**. The published address will be `https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/` for a repository-based Pages site.

## Research and attribution
The archived sensor source is ©/licensed as specified by its authors (dataset page indicates **CC0 1.0**). Local scored exports were used to create an original graph, but no private source rows, local credentials, or SQLite records are included in this website.

SINA is a *research-stage operator decision-support prototype*, not a field-certified leak detector. A measured fluctuation or anomaly score is not proof of a leak. Historical controlled-leak comparison results are not claimed as Prototype 1 metrics.

The website's code has no license selected yet. Please choose an explicit repository license if you wish to grant reuse rights.
