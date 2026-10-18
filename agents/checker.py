import requests

ACCESS_EFFECTS = {"ELEVATOR_CLOSURE", "ESCALATOR_CLOSURE", "ACCESS_ISSUE"}

# Words in alert text that tell us which line/platform a facility serves
LINE_WORDS = {
    "Red": ["red line", "alewife", "ashmont", "braintree"],
    "Orange": ["orange line", "oak grove", "forest hills"],
    "Blue": ["blue line", "bowdoin", "wonderland"],
    "Green": ["green line", "boston college", "cleveland circle", "riverside",
              "heath street", "medford", "union square"],
    "Mattapan": ["mattapan"],
    "Other": ["commuter rail", "silver line", "bus", "ferry"],
}


def get_live_alerts(mbta_key):
    r = requests.get(
        "https://api-v3.mbta.com/alerts",
        params={"filter[activity]": "USING_WHEELCHAIR,USING_ESCALATOR",
                "filter[datetime]": "NOW"},
        headers={"x-api-key": mbta_key},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]


def lines_mentioned(text):
    t = text.lower()
    return {line for line, words in LINE_WORDS.items() if any(w in t for w in words)}


def serves_rider(alert_text, rider_lines):
    """True if the facility may serve the rider's line. Unclear → True (safe default)."""
    mentioned = lines_mentioned(alert_text)
    if not mentioned or not rider_lines:
        return True
    rider = {line.split("-")[0] for line in rider_lines}   # Green-B → Green
    return bool(mentioned & rider)


def checker_agent(plan, mbta_key):
    if not plan.get("ok"):
        return {"ok": False, "reason": "No route to check"}

    path = plan["path"]
    station_lines = plan.get("station_lines", {})
    roles = {path[0]: "origin", path[-1]: "destination"}
    for sid in plan.get("transfer_ids", []):
        roles[sid] = "transfer"

    issues = []
    for alert in get_live_alerts(mbta_key):
        attrs = alert["attributes"]
        if attrs["effect"] not in ACCESS_EFFECTS:
            continue
        affected = {e.get("stop") for e in attrs.get("informed_entity", [])}
        for i, sid in enumerate(path):
            if sid in affected:
                issues.append({
                    "station_id": sid,
                    "station": plan["stations"][i],
                    "role": roles.get(sid, "pass-through"),
                    "effect": attrs["effect"],
                    "alert": attrs["header"],
                    "alert_id": alert["id"],
                    "serves_your_line": serves_rider(attrs["header"], station_lines.get(sid, [])),
                })

    blocking = [p for p in issues
                if p["role"] != "pass-through"
                and p["effect"] != "ESCALATOR_CLOSURE"
                and p["serves_your_line"]]

    return {"ok": True, "safe": len(blocking) == 0,
            "blocking": blocking, "all_issues": issues}