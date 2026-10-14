import requests

ACCESS_EFFECTS = {"ELEVATOR_CLOSURE", "ESCALATOR_CLOSURE", "ACCESS_ISSUE"}


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


def checker_agent(plan, mbta_key):
    if not plan.get("ok"):
        return {"ok": False, "reason": "No route to check"}

    path = plan["path"]
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
                })

    blocking = [p for p in issues
                if p["role"] != "pass-through" and p["effect"] != "ESCALATOR_CLOSURE"]

    return {"ok": True, "safe": len(blocking) == 0,
            "blocking": blocking, "all_issues": issues}