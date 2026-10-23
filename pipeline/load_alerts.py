import os
from datetime import datetime, timezone

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

# 1. Extract: get all current MBTA alerts
resp = requests.get(
    "https://api-v3.mbta.com/alerts",
    params={"filter[activity]": "ALL"},
    headers={"x-api-key": os.getenv("MBTA_API_KEY")},
    timeout=30,
)
resp.raise_for_status()


# 2. Transform: flatten each alert into one row
def ids(entities, key):
    return ",".join(sorted({e[key] for e in entities if e.get(key)}))


rows = []
for a in resp.json()["data"]:
    attr = a["attributes"]
    ents = attr.get("informed_entity") or []
    periods = attr.get("active_period") or []
    rows.append({
        "id": a["id"],
        "effect": attr.get("effect"),
        "cause": attr.get("cause"),
        "severity": attr.get("severity"),
        "lifecycle": attr.get("lifecycle"),
        "header": attr.get("header"),
        "description": attr.get("description"),
        "facility_ids": ids(ents, "facility"),
        "station_ids": ids(ents, "stop"),
        "route_ids": ids(ents, "route"),
        "active_start": periods[0]["start"] if periods else None,
        "active_end": periods[-1]["end"] if periods else None,
        "updated_at": attr.get("updated_at"),
    })

alerts = pd.DataFrame(rows)
alerts["loaded_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
alerts.columns = [c.upper() for c in alerts.columns]

# 3. Load: append this snapshot to Snowflake
conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA"),
)
success, _, rows_loaded, _ = write_pandas(
    conn, alerts, "ALERTS_HISTORY",
    auto_create_table=True,
    use_logical_type=True,
)
conn.close()
print(
    f"{datetime.now():%Y-%m-%d %H:%M} | Loaded {rows_loaded} alerts | success={success}"
)
