"""Optional importer-declared cross-listing groups with an explicit representative."""
import pandas as pd
from portfolio.data.returns import strict_date
from .input_evidence import verified_frame

RELATION_COLUMNS = ['asset_id','product_group','representative_asset_id','review_status',
                    'source_name','source_reference','source_as_of']


def listing_identity(frame, asset_ids):
    frame = pd.DataFrame(columns=RELATION_COLUMNS) if frame is None else verified_frame(frame, 'listing_relations')
    if not set(RELATION_COLUMNS) <= set(frame.columns):
        raise ValueError('missing listing relation columns')
    if frame.asset_id.duplicated().any() or not set(frame.asset_id) <= set(asset_ids):
        raise ValueError('duplicate or unknown listing relation asset_id')
    for row in frame.to_dict('records'):
        if any(not isinstance(row[k],str) or row[k] != row[k].strip() for k in RELATION_COLUMNS):
            raise ValueError('listing relation fields must be canonical text')
        if not row['product_group'] or row['review_status'] not in {'declared','pending'}:
            raise ValueError('invalid listing relation group or review status')
    reasons = {aid: [] for aid in asset_ids}
    statuses = {aid: 'not_verified' for aid in asset_ids}
    for _, group in frame.groupby('product_group', sort=True):
        ids = set(group.asset_id)
        representatives = set(group.representative_asset_id)
        valid = (len(representatives) == 1 and next(iter(representatives)) in ids
                 and group.review_status.eq('declared').all()
                 and all(group[k].str.strip().ne('').all() for k in ['source_name','source_reference'])
                 and all(strict_date(d) is not None for d in group.source_as_of))
        for aid in ids:
            statuses[aid] = 'declared' if valid else 'pending'
            if not valid: reasons[aid].append('listing_relationship_pending')
            elif aid not in representatives: reasons[aid].append('duplicate_product_listing')
    return frame, reasons, statuses
