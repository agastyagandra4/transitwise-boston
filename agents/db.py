import snowflake.connector
from getpass import getpass

def get_connection(user="tejastadla"):
    return snowflake.connector.connect(
        account="VGIFDCN-FU80974",
        user=user,
        password=getpass("Snowflake password: "),
        warehouse="COMPUTE_WH",
        database="TRANSITWISE_DB",
        schema="RAW",
    )