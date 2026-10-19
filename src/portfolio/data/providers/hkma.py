"""Official HKMA observation parsing."""
import math
from datetime import date
import pandas as pd

HKMA_URL = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily"

def parse_hkma(payload: dict) -> pd.DataFrame:
    if payload.get("header", {}).get("success") is not True:
        raise ValueError("HKMA API did not report success")
    rows = payload.get("result", {}).get("records", [])
    if not rows:
        raise ValueError("HKMA records missing")
    result = []
    for row in rows:
        try:
            day = date.fromisoformat(row["end_of_day"]).isoformat()
            fx = float(row["usd"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("HKMA date/USD missing or invalid") from error
        if not math.isfinite(fx) or fx <= 0:
            raise ValueError("HKMA USD must be positive HKD per USD")
        result.append({"date":day, "hkd_per_usd":fx})
    table = pd.DataFrame(result).sort_values("date").reset_index(drop=True)
    if table["date"].duplicated().any():
        raise ValueError("HKMA duplicate date")
    return table


def parse_page(payload):
    if not isinstance(payload,dict) or payload.get('header',{}).get('success') is not True:
        raise ValueError('invalid HKMA response')
    records=payload['result']['records']
    if not isinstance(records,list): raise ValueError('invalid records')
    if not records: return pd.DataFrame(columns=['date','hkd_per_usd'])
    table=parse_hkma(payload)
    if table.date.tolist()!=[r['end_of_day'] for r in records]:
        raise ValueError('unordered dates')
    return table
