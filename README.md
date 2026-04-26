# WCA Head-to-Head Comparator

A Flask web app to compare two speedcubers side-by-side using the WCA API.

## Features
- Personal bests for all events (singles and averages)
- World rank and national rank for each result
- Competition count comparison
- Win/loss breakdown across events
- Clean dark-themed UI

## Setup

```bash
cd wca_compare
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000 in your browser.

## Usage

Enter two WCA IDs (e.g. `2015SCHU01` and `2003POCH01`) and click Compare.

## Notes

- The WCA public API is used: https://api.worldcubeassociation.org
- No API key required
- All data is fetched live on each comparison
