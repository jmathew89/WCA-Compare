# WCA Head-to-Head Comparator

A Flask web app that compares two speedcubers in each WCA event using the WCA API.

## Features
- Personal records (PRs) for all events (singles and averages)
- World rank for each result
- Compares number of total competitions
- Counts wins and losses across all events (wins/losses determined relatively by comparing one person's time to the other)
- Dark mode and light mode

## Setup

```bash
cd wca_compare
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000 in your browser.

## Usage

Enter two WCA IDs (e.g. `2023MATH18` and `2003POCH01`) and click Compare.

## Notes

- The WCA public API is used: https://api.worldcubeassociation.org
- No API key required
- All data is fetched live on each comparison
