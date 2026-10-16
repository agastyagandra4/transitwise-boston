import os
import pandas as pd
import snowflake.connector
from getpass import getpass
from dotenv import load_dotenv

load_dotenv()


def get_connection(user="tejastadla"):
    return snowflake.connector.connect(
        account="VGIFDCN-FU80974",
        user=user,
        password=os.getenv("SNOWFLAKE_PASSWORD") or getpass("Snowflake password: "),
        warehouse="COMPUTE_WH",
        database="TRANSITWISE_DB",
        schema="RAW",
    )


def query_df(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [c[0] for c in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)