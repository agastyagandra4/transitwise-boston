import time
from agents.planner import planner_agent
from agents.checker import checker_agent
from agents.replanner import replanner_agent


def start_trip(conn, origin, dest, mbta_key):
    """Plan the trip and remember which outages already affect it."""
    plan = planner_agent(conn, origin, dest)
    if not plan["ok"]:
        return {"ok": False, "reason": plan["reason"]}

    check = checker_agent(plan, mbta_key)
    return {
        "ok": True,
        "origin": origin,
        "dest": dest,
        "plan": plan,
        "known_alerts": {p["alert_id"] for p in check["blocking"]},
        "history": [],
    }


def check_trip(conn, trip, mbta_key):
    """Re-check the trip once. Replan only if a NEW blocking outage appeared."""
    check = checker_agent(trip["plan"], mbta_key)
    current = {p["alert_id"]: p for p in check["blocking"]}

    new_problems = [p for aid, p in current.items() if aid not in trip["known_alerts"]]
    resolved = [aid for aid in trip["known_alerts"] if aid not in current]
    trip["known_alerts"] = set(current.keys())

    event = {
        "time": time.strftime("%H:%M:%S"),
        "new_problems": new_problems,
        "resolved": resolved,
        "replan": None,
    }
    if new_problems:
        event["replan"] = replanner_agent(conn, trip["origin"], trip["dest"], mbta_key)

    trip["history"].append(event)
    return event


def monitor_trip(conn, trip, mbta_key, interval_sec=120, max_checks=10, on_event=print):
    """Keep re-checking the trip every interval_sec seconds."""
    for i in range(max_checks):
        event = check_trip(conn, trip, mbta_key)
        on_event(event)
        if i < max_checks - 1:
            time.sleep(interval_sec)
    return trip["history"]