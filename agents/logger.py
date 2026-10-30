import json
import sys


def log_trip(conn, origin, dest, result, source="notebook"):
    """Write one row to AGENT_LOG. Never raises: logging must not break a trip."""
    try:
        plan = result.get("original_plan") or result.get("plan") or {}
        new_plan = result.get("new_plan") or {}
        problems = result.get("problems", [])
        safe = (not result.get("changed")) if result.get("ok") else None

        conn.cursor().execute("""
            INSERT INTO TRANSITWISE_DB.LOGS.AGENT_LOG
              (source, origin, destination, ok, safe, rerouted,
               original_route, new_route, minutes,
               blocking_stations, guardrails, sources, reason, explanation)
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s), %s, %s
        """, (
            source, origin, dest,
            bool(result.get("ok")), safe, bool(new_plan),
            " → ".join(plan.get("stations", [])) or None,
            " → ".join(new_plan.get("stations", [])) or None,
            new_plan.get("minutes") or plan.get("minutes"),
            json.dumps([p["station"] for p in problems]),
            json.dumps(result.get("guardrails", [])),
            json.dumps(result.get("sources", [])),
            result.get("reason"),
            (result.get("explanation") or "")[:2000],
        ))
    except Exception as e:
        print(f"(logging skipped: {e})", file=sys.stderr)