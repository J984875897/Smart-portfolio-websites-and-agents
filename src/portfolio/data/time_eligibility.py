"""Read-only local capture evidence; never certifies a historical universe."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import re

import pandas as pd

from .fx_cache import cached_daily_fx
from .snapshots import load_snapshot


@dataclass(frozen=True)
class CaptureEvidence:
    source_hash: str
    completed_utc: str
    source_status: str
    run_id: str


@dataclass
class TimeEligibilityResult:
    rows: pd.DataFrame
    metadata: dict


def _instant(value, *, utc=False):
    if not isinstance(value, str) or 'T' not in value:
        raise ValueError('timestamp must include time and explicit timezone')
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError('timestamp requires explicit timezone')
    if utc and timestamp.utcoffset() != timedelta(0):
        raise ValueError('capture timestamp must be UTC')
    try:
        return timestamp.astimezone(timezone.utc)
    except OverflowError as error:
        raise ValueError('timestamp outside supported UTC range') from error


def load_price_capture(root, run_id, symbol):
    """Rehash the immutable snapshot, binding the selected price raw bytes."""
    manifest = load_snapshot(root, run_id)
    if manifest['schema_version'] != 1 or symbol == 'HKD=X':
        raise ValueError('not a price snapshot')
    items = [i for i in manifest['items'] if i['symbol'] == symbol]
    if len(items) != 1:
        raise ValueError('price symbol not uniquely present')
    item = items[0]
    return CaptureEvidence(item['raw_sha256'] or '', manifest.get('completed_utc', ''), item['status'], run_id)


def load_fx_capture(root, run_id):
    """Reparse hash-verified raw FX, including the ordered HKMA page hashes."""
    attrs = cached_daily_fx(root, run_id).attrs
    return CaptureEvidence(attrs['source_hash'], attrs['manifest'].get('completed_utc', ''), attrs['source_status'], run_id)


def _capture_errors(capture, expected_hash, decision, label):
    if capture is None:
        return [label + '_capture_missing']
    errors = []
    if capture.source_status != 'success':
        errors.append(label + '_source_not_success')
    if (not isinstance(expected_hash, str) or not re.fullmatch('[0-9a-f]{64}', expected_hash)
            or capture.source_hash != expected_hash):
        errors.append(label + '_hash_mismatch')
    if not capture.completed_utc:
        errors.append(label + '_time_evidence_missing')
    else:
        try:
            completed = _instant(capture.completed_utc, utc=True)
        except ValueError:
            errors.append(label + '_time_evidence_invalid')
        else:
            if completed > decision:
                errors.append(label + '_capture_after_decision')
    return errors


def qualify_daily_hkd(result, *, decision_at, price_capture=None, fx_capture=None, declared_available_at=''):
    """Qualify version timing only; inputs and the original eligibility stay intact.

    CaptureEvidence is a trusted internal value supplied by the verified loaders.
    Manually instantiating it is useful for SYNTH scenarios, not real certification.
    """
    decision = _instant(decision_at)
    declaration = _instant(declared_available_at) if declared_available_at else None
    rows = result.reconciliation.copy(deep=True)
    rows.attrs = {}
    currency = result.prices.metadata['currency']
    errors = _capture_errors(price_capture, result.prices.metadata.get('source_hash'), decision, 'price')
    if currency == 'USD':
        errors += _capture_errors(fx_capture, result.metadata.get('fx_source_hash'), decision, 'fx')
    elif currency != 'HKD':
        errors.append('unsupported_currency')
    statuses, reasons, qualified = [], [], []
    for row in rows.to_dict('records'):
        problems = list(errors)
        if row.get('status') != 'valid' or not pd.notna(row.get('hkd_return')):
            problems.insert(0, 'base_return_invalid')
        eligible = not problems
        status = 'eligible_from_snapshot' if eligible else ('declaration_only' if declaration and declaration <= decision else 'blocked')
        if declaration and declaration > decision:
            problems.append('declaration_after_decision')
        statuses.append(status)
        reasons.append(';'.join(problems) or 'ok')
        qualified.append(eligible)
    rows['time_status'] = statuses
    rows['time_reason'] = reasons
    rows['historical_observation_eligible'] = qualified
    rows['historical_universe_eligible'] = False
    rows['decision_at'] = decision.isoformat()
    rows['declared_available_at'] = declaration.isoformat() if declaration else ''
    for label, capture in [('price', price_capture), ('fx', fx_capture if currency == 'USD' else None)]:
        rows[label + '_capture_completed_utc'] = capture.completed_utc if capture else ''
        rows[label + '_capture_hash'] = capture.source_hash if capture else ''
        rows[label + '_capture_run_id'] = capture.run_id if capture else ''
    metadata = dict(decision_at=decision.isoformat(), declared_available_at=declared_available_at,
                    price_capture=asdict(price_capture) if price_capture else None,
                    fx_capture=asdict(fx_capture) if fx_capture and currency == 'USD' else None,
                    expected_price_hash=result.prices.metadata.get('source_hash', ''),
                    expected_fx_hash=result.metadata.get('fx_source_hash', '') if currency == 'USD' else '',
                    historical_universe_eligible=False,
                    scope='local capture version timing only; no provider publication or historical universe certification')
    return TimeEligibilityResult(rows, metadata)
