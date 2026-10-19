"""French monthly factors and bounded in-memory archive decoding."""
import csv
import io
import re
import zipfile
from datetime import datetime
import numpy as np
import pandas as pd

def parse_french(text: str, *, require_contiguous=True) -> pd.DataFrame:
    """Only the monthly block; convert percentage points, preserve sentinels."""
    header, records = None, []
    for row in csv.reader(io.StringIO(text)):
        row = [value.strip() for value in row]
        if header is None:
            if row and row[0] == "" and {"Mkt-RF", "SMB", "HML", "RF"}.issubset(row):
                header = row
            continue
        if not row or not row[0]:
            if records:
                break
            continue
        if not re.fullmatch(r"\d{6}", row[0]):
            break  # annual block and footnotes must not enter monthly data
        if len(row) != len(header):
            raise ValueError("French field count changed")
        period = datetime.strptime(row[0], "%Y%m").strftime("%Y-%m")
        values = [float(value) for value in row[1:]]
        values = [np.nan if value in (-99.99, -999.0) else value / 100 for value in values]
        records.append([period, *values])
    if not records:
        raise ValueError("French monthly block missing")
    table = pd.DataFrame(records, columns=["month", *header[1:]])
    if table["month"].duplicated().any():
        raise ValueError("French duplicate month")
    periods = pd.PeriodIndex(table["month"],freq="M")
    if require_contiguous and len(pd.period_range(periods.min(),periods.max(),freq="M").difference(periods)):
        raise ValueError("French missing whole month")
    return table.sort_values("month").reset_index(drop=True)



FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FACTOR_URLS = {
    "US_FF3": FRENCH_BASE + "F-F_Research_Data_Factors_CSV.zip",
    "US_FF5": FRENCH_BASE + "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "AP_EX_JP_FF3": FRENCH_BASE + "Asia_Pacific_ex_Japan_3_Factors_CSV.zip",
    "AP_EX_JP_FF5": FRENCH_BASE + "Asia_Pacific_ex_Japan_5_Factors_CSV.zip",
}


def extract_csv(body, expected_name=None):
    if len(body)>10*1024*1024: raise ValueError('archive too large')
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        members=[m for m in archive.infolist() if m.filename.lower().endswith('.csv')]
        if len(members)!=1 or members[0].file_size>50*1024*1024:
            raise ValueError('unexpected archive')
        if expected_name is not None and members[0].filename.lower()!=expected_name.lower(): raise ValueError('unexpected source identity')
        return archive.read(members[0])
