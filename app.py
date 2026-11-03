import os
import streamlit as st

st.set_page_config(page_title="TransitWise Boston", page_icon="♿", layout="centered")
print("app: starting", flush=True)

from dotenv import load_dotenv
load_dotenv()

print("app: importing agents", flush=True)
from agents.db import get_connection
from agents.planner import build_graph
from agents.replanner import replanner_agent
from agents.monitor import start_trip, check_trip
print("app: agents imported", flush=True)

MBTA_KEY = os.getenv("MBTA_KEY")

# ---------- setup ----------
missing = [k for k in ("SNOWFLAKE_PASSWORD", "MBTA_KEY", "LLM_API_KEY") if not os.getenv(k)]
if missing:
    st.error("Missing in .env: " + ", ".join(missing))
    st.stop()


@st.cache_resource
def get_conn():
    print("app: connecting to Snowflake", flush=True)
    c = get_connection()
    print("app: connected", flush=True)
    return c


@st.cache_resource
def get_stations():
    print("app: building graph", flush=True)
    G, names, accessible, lines_at = build_graph(get_conn())
    step_free = {names[s]: accessible.get(s, False) for s in names}
    print("app: graph ready", flush=True)
    return sorted(step_free), step_free

# ---------- trip input ----------
st.title("♿ TransitWise Boston")
st.caption("Step-free MBTA subway trips, checked against live elevator outages")

c1, c2 = st.columns(2)
origin = c1.selectbox("From", stations, format_func=label,
                      index=stations.index("Harvard") if "Harvard" in stations else 0)
dest = c2.selectbox("To", stations, format_func=label,
                    index=stations.index("Back Bay") if "Back Bay" in stations else 1)

if st.button("Plan step-free trip", type="primary", use_container_width=True):
    if origin == dest:
        st.warning("Pick two different stations.")
    else:
        with st.spinner("Planning your route and checking live elevator outages..."):
            st.session_state.result = replanner_agent(conn, origin, dest, MBTA_KEY, log_source="app")
            st.session_state.od = (origin, dest)
            st.session_state.pop("trip", None)

# ---------- results ----------
r = st.session_state.get("result")
if r:
    st.divider()
    if not r["ok"]:
        st.error(r["reason"])
    elif not r["changed"]:
        st.success("Your route is clear. No elevator outages affect this trip.")
        show_route(r["plan"], "Your route")
    else:
        st.error(f"{len(r['problems'])} elevator problem(s) affect your usual route")
        for p in r["problems"]:
            st.markdown(f"- **{p['station']}** ({p['role']}): {p['alert']}")
        show_route(r["original_plan"], "Usual route")
        if r["new_plan"]:
            st.success("Step-free alternative found")
            show_route(r["new_plan"], "Recommended route")
        else:
            st.warning("No fully step-free train route right now.")
        st.subheader("What to do")
        st.markdown(r["explanation"])
        if r["sources"]:
            st.caption("Sources: " + ", ".join(r["sources"]))
        if r.get("guardrails"):
            st.caption("Safety checks applied: " + ", ".join(r["guardrails"]))

    # ---------- monitor ----------
    if r["ok"]:
        st.divider()
        st.subheader("Trip monitor")
        o, d = st.session_state.od
        if "trip" not in st.session_state:
            st.caption("Watches your trip for new elevator outages while you travel.")
            if st.button("Start monitoring this trip"):
                st.session_state.trip = start_trip(conn, o, d, MBTA_KEY)
                st.rerun()
        else:
            trip = st.session_state.trip
            if not trip["ok"]:
                st.error(trip["reason"])
            else:
                b1, b2 = st.columns(2)
                if b1.button("Check again now", use_container_width=True):
                    with st.spinner("Checking live outages..."):
                        check_trip(conn, trip, MBTA_KEY)
                if b2.button("Simulate a new outage (demo)", use_container_width=True):
                    trip["known_alerts"] = set()
                    with st.spinner("Re-checking and replanning..."):
                        check_trip(conn, trip, MBTA_KEY)
                st.caption(f"Monitoring {o} → {d}. Checks so far: {len(trip['history'])}")
                for ev in reversed(trip["history"]):
                    if ev["new_problems"]:
                        names_ = ", ".join(p["station"] for p in ev["new_problems"])
                        st.error(f"{ev['time']}: new outage at {names_}. Trip replanned.")
                        if ev["replan"] and ev["replan"].get("explanation"):
                            with st.expander("See updated guidance"):
                                st.markdown(ev["replan"]["explanation"])
                    elif ev["resolved"]:
                        st.success(f"{ev['time']}: an outage on your route was resolved.")
                    else:
                        st.info(f"{ev['time']}: no new problems on your route.")