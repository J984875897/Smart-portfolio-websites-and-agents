"""Read-only presentation of research state. Never calculates or certifies data."""
from dataclasses import dataclass
from typing import Literal, Mapping


@dataclass(frozen=True)
class WorkspaceStatus:
    code: str
    label: str
    tone: Literal['ready', 'review', 'blocked', 'input']
    detail: str
    route: str


@dataclass(frozen=True)
class WorkspaceSnapshot:
    data: WorkspaceStatus
    candidates: WorkspaceStatus
    target: WorkspaceStatus
    risk: WorkspaceStatus
    daily: bool = False


def workspace_snapshot(state: Mapping[str, object]) -> WorkspaceSnapshot:
    bundle = state.get('bundle')
    assets = len(getattr(bundle, 'assets', ()))
    observations = getattr(bundle, 'observations', None)
    daily = observations is not None and 'frequency' in observations and bool(observations.frequency.eq('daily').any())
    version = str(state.get('bundle_version', 'empty'))
    data = WorkspaceStatus('data', '数据版本', 'review' if assets else 'input',
                           f'{version} · 产品 {assets} · 待核对研究资格' if assets else '尚未打开数据版本', 'prepare_data')
    result = state.get('cs_result')
    if state.get('cs_source') == '当前已打开导入版本' and state.get('cs_previous_source') != ('当前已打开导入版本', version):
        result = None
    if state.get('cs_token') != state.get('cs_result_token'):
        result = None
    gate = getattr(result, 'cardinality', None)
    k = getattr(gate, 'k', state.get('cs_k', 30))
    if gate is None:
        candidates = WorkspaceStatus('candidates', '候选资格', 'input', '尚未查验候选；设定范围后重新筛选', 'screen_candidates')
    elif gate.status == 'passed':
        candidates = WorkspaceStatus('candidates', '候选资格', 'ready',
            f'N = {gate.n} · K/N = {gate.k / gate.n:.1%} · 数量条件通过；历史候选池未认证', 'screen_candidates')
    else:
        minimum = getattr(gate, 'minimum_n', None)
        candidates = WorkspaceStatus('candidates', '候选资格', 'blocked',
            f'候选产品池过小：N = {gate.n} · 最低需要 {minimum} · 尚缺 {max(0, (minimum or 0) - gate.n)} 项；核对范围与排除原因', 'screen_candidates')
    target = WorkspaceStatus('target', '目标持仓', 'review', f'K = {k} · 要求 20–100 项且 K/N ≤ 30%；尚未最终选品', 'screen_candidates')
    current_risk = (gate is not None and gate.status == 'passed' and state.get('ra_preview') is not None
                    and bool(state.get('ra_result_token')) and state.get('ra_result_token') == state.get('ra_input_token'))
    risk = WorkspaceStatus('risk', '风险预览', 'ready' if current_risk else 'input',
        '研究预览已完成；正式成员选择与优化尚未实施' if current_risk else '尚未计算有效预览；候选通过后选择权重并计算', 'risk_preview')
    return WorkspaceSnapshot(data, candidates, target, risk, daily)


def next_step(snapshot: WorkspaceSnapshot) -> WorkspaceStatus:
    if snapshot.candidates.tone == 'blocked':
        return snapshot.candidates
    if snapshot.candidates.tone == 'ready':
        return snapshot.risk
    if snapshot.data.tone == 'input':
        return snapshot.data
    if snapshot.daily:
        return WorkspaceStatus('eligibility', '核对资格', 'review', '需要月度准备：当前含日线资料，先核对月度端点、港币收益和时间证据', 'eligibility')
    return snapshot.candidates
