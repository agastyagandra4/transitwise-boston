import networkx as nx

_cache = None


def build_graph(conn):
    cur = conn.cursor()
    stops = cur.execute("""
        SELECT rs.ROUTE_ID, rs.STOP_SEQUENCE, rs.STATION_ID, rs.STATION_NAME
        FROM ROUTE_STOPS rs
        JOIN ROUTES r ON r.ROUTE_ID = rs.ROUTE_ID
        WHERE r.ROUTE_TYPE IN (0, 1)
        ORDER BY rs.ROUTE_ID, rs.STOP_SEQUENCE
    """).fetch_pandas_all()

    stations = cur.execute("SELECT * FROM STATIONS").fetch_pandas_all()
    wc_col = [c for c in stations.columns if c.startswith("WHEELCHAIR")][0]
    accessible = dict(zip(stations["STATION_ID"], stations[wc_col].astype(str) == "1"))
    names = dict(zip(stops["STATION_ID"], stops["STATION_NAME"]))

    G = nx.Graph()
    for route, group in stops.groupby("ROUTE_ID"):
        ids = group["STATION_ID"].tolist()
        line = route.split("-")[0]
        for a, b in zip(ids, ids[1:]):
            G.add_edge(a, b, line=line)

    for wrong_a, wrong_b, branch_start in [("place-asmnl", "place-nqncy", "place-nqncy"),
                                           ("place-brntn", "place-shmnl", "place-shmnl")]:
        if G.has_edge(wrong_a, wrong_b):
            G.remove_edge(wrong_a, wrong_b)
            G.add_edge("place-jfk", branch_start, line="Red")

    return G, names, accessible


def planner_agent(conn, origin_name, dest_name, avoid=None):
    global _cache
    if _cache is None:
        _cache = build_graph(conn)
    G, names, accessible = _cache

    lookup = {n.lower(): sid for sid, n in names.items()}
    origin, dest = lookup.get(origin_name.lower()), lookup.get(dest_name.lower())
    if not origin or not dest:
        return {"ok": False, "reason": "Station name not found"}
    if not accessible.get(origin):
        return {"ok": False, "reason": f"{origin_name} is not wheelchair accessible"}
    if not accessible.get(dest):
        return {"ok": False, "reason": f"{dest_name} is not wheelchair accessible"}

    graph = G.copy()
    graph.remove_nodes_from([s for s in (avoid or []) if s not in (origin, dest)])
    try:
        path = nx.shortest_path(graph, origin, dest)
    except nx.NetworkXNoPath:
        return {"ok": False, "reason": "No route found avoiding those stations"}

    lines = [graph[a][b]["line"] for a, b in zip(path, path[1:])]
    transfers = [path[i] for i in range(1, len(lines)) if lines[i] != lines[i - 1]]
    return {
        "ok": True,
        "path": path,
        "stations": [names[s] for s in path],
        "transfers": [names[s] for s in transfers],
        "transfer_ids": transfers,
    }