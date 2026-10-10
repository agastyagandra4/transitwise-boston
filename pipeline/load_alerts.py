import os
from datetime import datetime, timezone

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

resp = requests.get(
    "https://api-v3.mbta.com/alerts",
    params={"filter[activity]": "ALL"},
    headers={"x-api-key": os.getenv("MBTA_API_KEY")},
    timeout=30,
)
resp.raise_for_status()

alerts = pd.DataFrame([
    {
        "id": a["id"],
        "effect": a["attributes"]["effect"],
        "severity": a["attributes"]["severity"],
        "header": a["attributes"]["header"],
    }
    for a in resp.json()["data"]
])
alerts["loaded_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
alerts.columns = [c.upper() for c in alerts.columns]

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA"),
)
success, _, rows, _ = write_pandas(
    conn, alerts, "ALERTS_HISTORY", use_logical_type=True
)
conn.close()
print(f"{datetime.now():%Y-%m-%d %H:%M} | Loaded {rows} alerts | success={success}")