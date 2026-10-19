"""Read importer-declared product structure evidence; no selection policy here."""
import pandas as pd
from portfolio.data.returns import strict_date
from .input_evidence import frame_evidence

STRUCTURE_COLUMNS = ['asset_id', 'market', 'canonical_tool_type', 'structure',
                     'review_status', 'source_name', 'source_reference', 'source_as_of']
BINDING_COLUMNS = [*STRUCTURE_COLUMNS, 'binding_status', 'source_file', 'source_sheet',
                   'source_row', 'source_hash', 'sources']


def bind_structures(frame, asset_ids):
    if not frame.empty and not set(STRUCTURE_COLUMNS) <= set(frame.columns):
        raise ValueError('missing structure columns')
    evidence = frame_evidence(frame)
    groups = {}
    physical = frame.attrs.get('source_rows', list(range(2, len(frame) + 2)))
    for i, original in enumerate(frame.to_dict('records')):
        row = {k: original.get(k, '') for k in STRUCTURE_COLUMNS}
        if any(not isinstance(v, str) for v in row.values()):
            raise ValueError('structure fields must be text')
        aid = row['asset_id']
        if aid not in asset_ids:
            raise ValueError('unknown structure asset_id')
        if row['review_status'] not in {'declared', 'pending'}:
            raise ValueError('invalid structure review_status')
        if row['source_as_of'] and strict_date(row['source_as_of']) is None:
            raise ValueError('invalid structure source_as_of')
        if row['review_status'] == 'declared' and any(not row[k].strip() for k in STRUCTURE_COLUMNS):
            raise ValueError('declared structure requires complete fields and source')
        source = dict(source_file=evidence['source_file'], source_sheet=evidence['source_sheet'],
                      source_row=physical[i], source_hash=evidence['raw_sha256'] or evidence['content_sha256'])
        if aid in groups:
            if any(groups[aid][k] != row[k] for k in STRUCTURE_COLUMNS):
                raise ValueError('conflicting structure rows')
            groups[aid]['sources'].append(source)
        else:
            groups[aid] = dict(row, binding_status=row['review_status'], **source, sources=[source])
    rows = []
    for aid in sorted(asset_ids):
        rows.append(groups.get(aid, dict.fromkeys(BINDING_COLUMNS, '') | dict(
            asset_id=aid, binding_status='missing', sources=[])))
    return pd.DataFrame(rows, columns=BINDING_COLUMNS)
