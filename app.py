from flask import Flask, render_template, request, jsonify
from concurrent.futures import ThreadPoolExecutor
import requests

app = Flask(__name__)

WCA_BASE = "https://www.worldcubeassociation.org/api/v0"

HEADERS = {
    "User-Agent": "wca-h2h/1.0",
    "Accept": "application/json",
}

# This is the order in which events appear on the WCA rankings 
ORDERED_EVENTS = [
    ("333", "3x3"), ("222", "2x2"), ("444", "4x4"), ("555", "5x5"),
    ("666", "6x6"), ("777", "7x7"), ("333bf", "3BLD"), ("333fm", "FMC"),
    ("333oh", "OH"), ("clock", "Clock"), ("minx", "Megaminx"),
    ("pyram", "Pyraminx"), ("skewb", "Skewb"), ("sq1", "Square-1"),
    ("444bf", "4BLD"), ("555bf", "5BLD"), ("333mbf", "Multi-BLD"),
]


def centiseconds_to_str(cs, event_id):
    if cs is None or cs <= 0:
        return "-"

    # FMC results are stored as move count directly because not timed
    if event_id == "333fm":
        return str(cs)

    # MBLD encoding here is in accordance with WCA regulations
    # value = (99 - score) * 1e7 + time_in_seconds * 100 + missed
    if event_id == "333mbf":
        diff = 99 - (cs // 10000000)
        remainder = cs % 10000000
        missed = remainder % 100
        solved = diff + missed
        attempted = solved + missed
        seconds = (remainder // 100) % 10000
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        t = f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
        return f"{solved}/{attempted} {t}"

    mins = cs // 6000
    secs = (cs % 6000) // 100
    centis = cs % 100
    if mins:
        return f"{mins}:{secs:02}.{centis:02}"
    return f"{secs}.{centis:02}"


def get_competitor(wca_id):
    try:
        resp = requests.get(
            f"{WCA_BASE}/persons",
            params={"wca_ids": wca_id},
            headers=HEADERS,
            timeout=10
        )
        print(f"{wca_id} -> {resp.status_code}")
        if resp.status_code != 200:
            return None
        payload = resp.json()
    except Exception as e:
        print(f"error fetching {wca_id}: {e}")
        return None

    rows = payload if isinstance(payload, list) else payload.get("results", [])
    if not rows:
        return None

    row = rows[0]
    info = row.get("person", row)

    # personal_records can come back as either a dict keyed by event
    # or a flat list depending on the API version
    raw_pbs = row.get("personal_records", {})
    pbs = {}

    if isinstance(raw_pbs, dict):
        for eid, types in raw_pbs.items():
            pbs[eid] = {}
            if isinstance(types, dict):
                for result_type, val in types.items():
                    if isinstance(val, dict):
                        pbs[eid][result_type] = {
                            "best": val.get("best"),
                            "wr": val.get("world_rank"),
                            "nr": val.get("national_rank"),
                            "cr": val.get("continental_rank"),
                        }
    elif isinstance(raw_pbs, list):
        for pb in raw_pbs:
            eid = pb.get("event_id")
            result_type = pb.get("type")
            if not eid or not result_type:
                continue
            pbs.setdefault(eid, {})[result_type] = {
                "best": pb.get("best"),
                "wr": pb.get("world_rank"),
                "nr": pb.get("national_rank"),
                "cr": pb.get("continental_rank"),
            }

    raw_medals = row.get("medals", {})
    medals = {
        "gold":   (raw_medals.get("gold")   or 0) if isinstance(raw_medals, dict) else 0,
        "silver": (raw_medals.get("silver") or 0) if isinstance(raw_medals, dict) else 0,
        "bronze": (raw_medals.get("bronze") or 0) if isinstance(raw_medals, dict) else 0,
    }

    country = info.get("country", {})
    country_name = country.get("name", "") if isinstance(country, dict) else str(country)

    return {
        "id": wca_id,
        "name": info.get("name", wca_id),
        "country_iso": info.get("country_iso2", ""),
        "country": country_name,
        "comps": row.get("competition_count", 0),
        "medals": medals,
        "pbs": pbs,
    }


def pick_winner(a, b):
    if a is None and b is None:
        return "tie"
    if a is None:
        return "2"
    if b is None:
        return "1"
    if a < b:
        return "1"
    if b < a:
        return "2"
    return "tie"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/search_name")
def search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        resp = requests.get(
            f"{WCA_BASE}/search/users",
            params={"q": q, "persons_table": "true"},
            headers=HEADERS,
            timeout=6
        )
        if resp.status_code != 200:
            return jsonify([])
        hits = resp.json().get("result", [])
        out = []
        for u in hits[:8]:
            uid = u.get("wca_id") or u.get("id", "")
            if uid and u.get("name"):
                out.append({"id": uid, "name": u["name"], "country": u.get("country_iso2", "")})
        return jsonify(out)
    except Exception:
        return jsonify([])


@app.route("/compare")
def h2h():
    id1 = request.args.get("id1", "").strip().upper()
    id2 = request.args.get("id2", "").strip().upper()
    if not id1 or not id2:
        return jsonify({"error": "Need two WCA IDs."}), 400

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(get_competitor, id1)
        f2 = pool.submit(get_competitor, id2)
        p1, p2 = f1.result(), f2.result()

    if not p1:
        return jsonify({"error": f"Couldn't find {id1}"}), 404
    if not p2:
        return jsonify({"error": f"Couldn't find {id2}"}), 404

    results = []
    for eid, ename in ORDERED_EVENTS:
        pb1 = p1["pbs"].get(eid, {})
        pb2 = p2["pbs"].get(eid, {})
        if not pb1 and not pb2:
            continue

        s1 = pb1.get("single", {}).get("best") if pb1.get("single") else None
        s2 = pb2.get("single", {}).get("best") if pb2.get("single") else None
        a1 = pb1.get("average", {}).get("best") if pb1.get("average") else None
        a2 = pb2.get("average", {}).get("best") if pb2.get("average") else None

        results.append({
            "id": eid,
            "name": ename,
            "single1": centiseconds_to_str(s1, eid),
            "single2": centiseconds_to_str(s2, eid),
            "avg1": centiseconds_to_str(a1, eid),
            "avg2": centiseconds_to_str(a2, eid),
            "raw_single1": s1, "raw_single2": s2,
            "raw_avg1": a1,    "raw_avg2": a2,
            "single_wr1": pb1.get("single", {}).get("wr") if pb1.get("single") else None,
            "single_wr2": pb2.get("single", {}).get("wr") if pb2.get("single") else None,
            "avg_wr1":    pb1.get("average", {}).get("wr") if pb1.get("average") else None,
            "avg_wr2":    pb2.get("average", {}).get("wr") if pb2.get("average") else None,
            "single_nr1": pb1.get("single", {}).get("nr") if pb1.get("single") else None,
            "single_nr2": pb2.get("single", {}).get("nr") if pb2.get("single") else None,
            "avg_nr1":    pb1.get("average", {}).get("nr") if pb1.get("average") else None,
            "avg_nr2":    pb2.get("average", {}).get("nr") if pb2.get("average") else None,
            "single_winner": pick_winner(s1, s2),
            "avg_winner":    pick_winner(a1, a2),
        })

    return jsonify({
        "p1": {k: v for k, v in p1.items() if k != "pbs"},
        "p2": {k: v for k, v in p2.items() if k != "pbs"},
        "events": results,
    })


if __name__ == "__main__":
    app.run(debug=True)
