"""Bind data values and file evidence without trusting stale DataFrame attrs."""
import hashlib
import json
from zipfile import BadZipFile
import pandas as pd
from portfolio.data.importer import read_file
from portfolio.data.contracts import TABLE_COLUMNS


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def verified_frame(frame, name):
    if not isinstance(frame, pd.DataFrame) or not frame.columns.is_unique:
        raise ValueError(f'{name}: unique DataFrame columns required')
    if 'raw_bytes' not in frame.attrs:
        checked = frame.copy(deep=True)
        # Physical file rows require reparsed bytes; memory rows get ordinal IDs.
        checked.attrs.pop('source_rows', None)
        return checked
    try:
        loaded = read_file(frame.attrs['raw_bytes'], filename=frame.attrs.get('source_file'),
                           sheet_name=frame.attrs.get('source_sheet') or 0)
    except (ValueError, TypeError, KeyError, IndexError, OSError, BadZipFile) as exc:
        raise ValueError(f'{name}: file evidence must be readable and unchanged') from exc
    if not frame.equals(loaded) or not frame.index.equals(loaded.index):
        raise ValueError(f'{name}: file-backed frame must be unchanged; reload original')
    return loaded


def frame_evidence(frame):
    csv = frame.to_csv(index=True).encode()
    raw = frame.attrs.get('raw_bytes')
    return dict(content_sha256=digest(csv), rows=len(frame), columns=list(frame.columns),
                dtypes=[str(t) for t in frame.dtypes],
                source_file=frame.attrs.get('source_file', ''),
                source_sheet=frame.attrs.get('source_sheet', ''),
                raw_sha256=digest(raw) if raw is not None else '',
                evidence_kind='file_bytes' if raw is not None else 'in_memory_declared')


def input_evidence(bundle, fx, timing, structures, *, end_month, decision_at, adjusted_price_assets):
    for name in TABLE_COLUMNS:
        verified_frame(getattr(bundle, name), 'bundle.' + name)
    raw_hashes = {}
    for key, payload in bundle.raw_sources.items():
        if not isinstance(payload, bytes) or digest(payload) != key:
            raise ValueError('bundle raw source hash mismatch')
        raw_hashes[key] = digest(payload)
    frames = {'fx': fx, 'timing': timing, 'structures': structures}
    checked = {k: verified_frame(v, k) for k, v in frames.items()}
    evidence = dict(
        bundle_tables={k: frame_evidence(getattr(bundle, k)) for k in TABLE_COLUMNS},
        bundle_configs=bundle.configs, bundle_raw_sources=raw_hashes,
        inputs={k: frame_evidence(v) for k, v in checked.items()},
        parameters=dict(end_month=end_month, decision_at=decision_at,
                        adjusted_price_assets=sorted(set(adjusted_price_assets))),
        research_mode='current_universe_retrospective', base_currency='HKD',
        window_months=60, timing_basis='importer_declared', historical_universe_certified=False)
    rendered = json.dumps(evidence, ensure_ascii=False, sort_keys=True, allow_nan=False)
    # JSON round-trip detaches mutable configs and all nested evidence.
    return json.loads(rendered), digest(rendered.encode()), checked
