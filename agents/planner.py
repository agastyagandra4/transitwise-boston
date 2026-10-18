import math
import networkx as nx
from agents.db import query_df

_cache = None

SPEED_KM_PER_MIN = 0.5   # ~30 km/h average train speed
DWELL_MIN = 0.5          # time stopped at each station
TRANSFER_MIN = 5.0       # walking + waiting when changing lines

# Red Line data lists both branches as one chain; these consecutive pairs are fake links
RED_FAKE_LINKS = [{"place-asmnl", "place-nqncy"}, {"place-brntn", "place-shmnl"}]


def _km(a, b):
    """Straight-line distance in km between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def _ride_minutes(a, b, coords):
    if a in coords and b in coords:
        return _km(coords[a], coords[b]) / SPEED_KM_PER_MIN + DWELL_MIN
    return 2.0


def build_graph(conn):
    stops = query_df(conn, """
        SELECT rs.ROUTE_ID, rs.STOP_SEQUENCE, rs.STATION_ID, rs.STATION_NAME
        FROM ROUTE_STOPS rs
        JOIN ROUTES r ON r.ROUTE_ID = rs.ROUTE_ID
        WHERE r.ROUTE_TYPE IN (0, 1)
        ORDER BY rs.ROUTE_ID, rs.STOP_SEQUENCE
    """)
    stations = query_df(conn, "SELECT * FROM STATIONS")
    wc_col = [c for c in stations.columns if c.startswith("WHEELCHAIR")][0]
    accessible = dict(zip(stations["STATION_ID"], stations[wc_col].astype(str) == "1"))
    coords = {r.STATION_ID: (float(r.LATITUDE), float(r.LONGITUDE))
              for r in stations.itertuples() if r.LATITUDE is not None}
    names = dict(zip(stops["STATION_ID"], stops["STATION_NAME"]))

    G = nx.Graph()
    lines_at = {}

    # Ride edges: consecutive stops on the same line
    for route, group in stops.groupby("ROUTE_ID"):
        ids = group["STATION_ID"].tolist()
        for s in ids:
            lines_at.setdefault(s, set()).add(route)
        for a, b in zip(ids, ids[1:]):
            if route == "Red" and {a, b} in RED_FAKE_LINKS:
                continue
            G.add_edge((a, route), (b, route), kind="ride",
                       minutes=_ride_minutes(a, b, coords))

    # Red Line branches both start at JFK/UMass
    for branch_start in ["place-nqncy", "place-shmnl"]:
        G.add_edge(("place-jfk", "Red"), (branch_start, "Red"), kind="ride",
                   minutes=_ride_minutes("place-jfk", branch_start, coords))

    # Transfer edges: changing lines inside the same station
    for s, lines in lines_at.items():
        lines = sorted(lines)
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                G.add_edge((s, lines[i]), (s, lines[j]), kind="transfer", minutes=TRANSFER_MIN)

    return G, names, accessible, lines_at


def _remove_transfers(graph, station, lines_at):
    lines = sorted(lines_at.get(station, []))
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            if graph.has_edge((station, lines[i]), (station, lines[j])):
                graph.remove_edge((station, lines[i]), (station, lines[j]))


def planner_agent(conn, origin_name, dest_name, avoid=None):
    global _cache
    if _cache is None:
        _cache = build_graph(conn)
    G, names, accessible, lines_at = _cache

    lookup = {n.lower(): sid for sid, n in names.items()}
    origin, dest = lookup.get(origin_name.lower()), lookup.get(dest_name.lower())
    if not origin or not dest:
        return {"ok": False, "reason": "Station name not found"}
    if not accessible.get(origin):
        return {"ok": False, "reason": f"{origin_name} is not wheelchair accessible"}
    if not accessible.get(dest):
        return {"ok": False, "reason": f"{dest_name} is not wheelchair accessible"}

    graph = G.copy()

    # No transfers at inaccessible stations (trains can still pass through)
    for s in lines_at:
        if not accessible.get(s):
            _remove_transfers(graph, s, lines_at)

    # Issue 1: avoided stations can't be used to transfer, but trains pass through
    for s in (avoid or []):
        if s not in (origin, dest):
            _remove_transfers(graph, s, lines_at)

    # Virtual start/end nodes so the rider can board/exit on any line there
    for line in lines_at[origin]:
        graph.add_edge("START", (origin, line), minutes=0)
    for line in lines_at[dest]:
        graph.add_edge((dest, line), "END", minutes=0)

    try:
        nodes = nx.shortest_path(graph, "START", "END", weight="minutes")  # Dijkstra
        minutes = nx.shortest_path_length(graph, "START", "END", weight="minutes")
    except nx.NetworkXNoPath:
        return {"ok": False, "reason": "No step-free route found avoiding those stations"}

    nodes = nodes[1:-1]  # drop START and END

    path, station_lines = [], {}
    for s, line in nodes:
        if not path or path[-1] != s:
            path.append(s)
        station_lines.setdefault(s, []).append(line)

    transfer_ids = [nodes[i][0] for i in range(1, len(nodes)) if nodes[i][0] == nodes[i - 1][0]]

    return {
        "ok": True,
        "path": path,
        "stations": [names[s] for s in path],
        "transfers": [names[s] for s in transfer_ids],
        "transfer_ids": transfer_ids,
        "minutes": round(minutes),
        "station_lines": station_lines,
    }