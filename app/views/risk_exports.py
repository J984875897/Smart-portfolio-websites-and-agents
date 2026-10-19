"""Weight-file validation and complete decimal-valued research exports."""
from io import BytesIO
import csv
from io import StringIO
import json
import numpy as np
import pandas as pd


def parse_weights(payload,asset_ids):
    try:
        rows=list(csv.reader(StringIO(payload.decode('utf-8-sig')),strict=True))
    except (UnicodeError,csv.Error) as exc:
        raise ValueError('无法读取权重 CSV，请核对 UTF-8 编码及引号。') from exc
    if not rows or any(len(row) != 2 for row in rows):
        raise ValueError('权重 CSV 每行必须恰好两列，不接受额外字段或空行。')
    try:
        frame=pd.read_csv(BytesIO(payload),dtype=str,keep_default_na=False,encoding='utf-8-sig')
    except (ValueError,pd.errors.ParserError) as exc:
        raise ValueError('无法读取权重 CSV，请核对表头及两列字段。') from exc
    if list(frame.columns) != ['asset_id','weight']:
        raise ValueError('权重 CSV 必须只有 asset_id,weight 两列，且顺序一致。')
    if frame.asset_id.duplicated().any(): raise ValueError('资产标识重复，请每项仅填写一行。')
    expected=set(asset_ids);actual=set(frame.asset_id)
    if expected != actual:
        missing=sorted(expected-actual);extra=sorted(actual-expected)
        raise ValueError(f'资产标识不匹配。缺少：{", ".join(missing) or "无"}；多出：{", ".join(extra) or "无"}。零持仓请填0。')
    try: values=pd.to_numeric(frame.weight,errors='raise').to_numpy(dtype=float)
    except (ValueError,TypeError) as exc: raise ValueError('权重必须是有限小数，不能是布尔、文字或空值。') from exc
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('多头权重必须是有限、非负的小数。')
    if not np.isclose(values.sum(),1,rtol=0,atol=1e-10):
        raise ValueError(f'权重合计为 {values.sum():.12g}，必须等于1；系统不会自动归一化。')
    return pd.Series(values,index=frame.asset_id,name='weight').reindex(sorted(asset_ids))


def correlation_pairs(matrix):
    i,j=np.triu_indices(len(matrix),1)
    frame=pd.DataFrame({'asset_a':matrix.index.to_numpy()[i],
                        'asset_b':matrix.columns.to_numpy()[j],
                        'correlation':matrix.to_numpy()[i,j]})
    return frame.dropna().reset_index(drop=True)


def preview_exports(preview):
    e=preview.estimate
    tables={'return_estimates.csv':e.summary,'sample_covariance_ann.csv':e.sample_cov_ann,
            'model_covariance_ann.csv':e.shrunk_cov_ann,'correlation.csv':preview.correlation.matrix,
            'correlation_status.csv':preview.correlation.asset_status,
            'sample_risk_contributions.csv':preview.sample_risk.contributions,
            'model_risk_contributions.csv':preview.model_risk.contributions,
            'risk_comparison.csv':pd.DataFrame({'sample':preview.sample_risk.metrics,
                                               'ledoit_wolf':preview.model_risk.metrics}).T}
    files={name:frame.to_csv(index=True,index_label='asset_id' if name != 'risk_comparison.csv' else 'method').encode('utf-8-sig')
           for name,frame in tables.items()}
    data=dict(evidence=preview.evidence,preview_fingerprint=preview.fingerprint,
              estimation_diagnostics=e.diagnostics,correlation_diagnostics=preview.correlation.diagnostics,
              sample_metrics=preview.sample_risk.metrics,model_metrics=preview.model_risk.metrics,
              sample_diagnostics=preview.sample_risk.diagnostics,model_diagnostics=preview.model_risk.diagnostics)
    files['risk_evidence.json']=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    return files
