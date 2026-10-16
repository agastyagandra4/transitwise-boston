import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

from agents.db import get_connection
from agents.planner import planner_agent
from agents.checker import checker_agent, get_live_alerts
from agents.retriever import search_policies

mcp = FastMCP("transitwise")
MBTA_KEY = os.getenv("MBTA_KEY")
_conn = None


def conn():
    global _conn
    if _conn is None:
        _conn = get_connection()
    return _conn


@mcp.tool()
def plan_route(origin: str, destination: str, avoid: list[str] | None = None) -> dict:
    """Find a step-free MBTA subway route between two stations.
    Optionally avoid station IDs such as 'place-dwnxg' (Downtown Crossing)."""
    return planner_agent(conn(), origin, destination, avoid=avoid)


@mcp.tool()
def check_route(origin: str, destination: str) -> dict:
    """Plan a route and check it against live MBTA elevator and escalator outages.
    Returns whether the trip is safe and any blocking problems."""
    plan = planner_agent(conn(), origin, destination)
    if not plan["ok"]:
        return plan
    return {"route": plan["stations"], "check": checker_agent(plan, MBTA_KEY)}


@mcp.tool()
def get_accessibility_alerts(limit: int = 20) -> list[dict]:
    """List current MBTA elevator and escalator outage alerts."""
    alerts = get_live_alerts(MBTA_KEY)[:limit]
    return [{"effect": a["attributes"]["effect"], "header": a["attributes"]["header"]}
            for a in alerts]


@mcp.tool()
def search_mbta_policy(question: str, k: int = 4) -> list[dict]:
    """Search official MBTA accessibility policy documents.
    Returns the most relevant passages with their source files."""
    return search_policies(conn(), question, k=k)


if __name__ == "__main__":
    mcp.run()