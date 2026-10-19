"""Versioned local import contracts; no downstream return normalization."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import hashlib
import json
import pandas as pd

TABLE_COLUMNS = {
    'assets': ['asset_id','ticker','name','tool_type','asset_class','exchange','currency','share_class','frequency'],
    'observations': ['date','asset_id','value','value_kind','currency','frequency','source_file','source_sheet','source_row','source_hash'],
    'provenance': ['source_file','source_sheet','source_row','source_hash','source_name','asset_id','status'],
    'issues': ['source_file','source_sheet','source_row','source_hash','asset_id','code','severity','message'],
    'aliases': ['source_name','exchange','ticker','share_class','currency','asset_id'],
    'classification_history': ['asset_id','field','old_value','new_value','source_file','source_sheet','source_row','timestamp'],
    'returns': ['date','asset_id','value','value_kind','currency','frequency'],
    'fx': [], 'factors': [],
}

@dataclass(frozen=True)
class ImportConfig:
    mapping: dict[str,str]
    source_name: str
    defaults: dict[str,str] = field(default_factory=dict)
    value_kind: str = 'price'
    return_unit: str = 'decimal'
    date_format: str = '%Y-%m-%d'
    sheet_name: str | int = 0
    classification_overrides: dict[str,dict[str,str]] = field(default_factory=dict)
    alias_mappings: dict[tuple[str,str,str,str,str],str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.source_name.strip(): raise ValueError('source_name is required')
        if self.value_kind not in {'price','adjusted_price','total_return','price_return'}: raise ValueError('invalid value_kind')
        if self.return_unit not in {'decimal','percent'}: raise ValueError('invalid return_unit')

@dataclass
class ImportPreview:
    rows: pd.DataFrame
    issues: pd.DataFrame
    config: ImportConfig
    source_hash: str
    source_file: str
    raw_bytes: bytes | None = None

    @property
    def counts(self):
        return self.rows.status.value_counts().to_dict()

@dataclass
class DataBundle:
    assets: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TABLE_COLUMNS['assets']))
    observations: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TABLE_COLUMNS['observations']))
    provenance: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TABLE_COLUMNS['provenance']))
    issues: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TABLE_COLUMNS['issues']))
    aliases: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TABLE_COLUMNS['aliases']))
    classification_history: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TABLE_COLUMNS['classification_history']))
    returns: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TABLE_COLUMNS['returns']))
    fx: pd.DataFrame = field(default_factory=pd.DataFrame)
    factors: pd.DataFrame = field(default_factory=pd.DataFrame)
    configs: list = field(default_factory=list)
    raw_sources: dict[str,bytes] = field(default_factory=dict, repr=False)

    def save(self, path: str | Path):
        path=Path(path); path.mkdir(parents=True,exist_ok=False)
        manifest={'version':1,'tables':{},'configs':self.configs,'raw_sources':{}}
        for name in TABLE_COLUMNS:
            frame=getattr(self,name); payload=frame.to_csv(index=False).encode()
            filename=f'{name}.csv'; (path/filename).write_bytes(payload)
            manifest['tables'][name]={'file':filename,'sha256':hashlib.sha256(payload).hexdigest(),'columns':list(frame.columns)}
        for digest,payload in self.raw_sources.items():
            filename=f'raw_{digest}.bin'; (path/filename).write_bytes(payload)
            manifest['raw_sources'][digest]={'file':filename,'sha256':hashlib.sha256(payload).hexdigest()}
        (path/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

    @classmethod
    def load(cls,path: str | Path):
        path=Path(path); manifest=json.loads((path/'manifest.json').read_text())
        if manifest.get('version')!=1: raise ValueError('unsupported bundle version')
        bundle=cls(configs=manifest.get('configs',[]))
        if set(manifest.get('tables',{})) != set(TABLE_COLUMNS): raise ValueError('missing or unknown tables')
        def checked_payload(spec):
            filename=spec['file']
            if Path(filename).name != filename or Path(filename).is_absolute(): raise ValueError('invalid manifest path')
            return (path/filename).read_bytes()
        for name,spec in manifest['tables'].items():
            if name not in TABLE_COLUMNS: raise ValueError('unknown table schema')
            payload=checked_payload(spec)
            if hashlib.sha256(payload).hexdigest()!=spec['sha256']: raise ValueError(f'hash mismatch: {name}')
            from io import BytesIO
            frame=pd.read_csv(BytesIO(payload),dtype=str,keep_default_na=False) if spec['columns'] else pd.DataFrame()
            if spec['columns']!=TABLE_COLUMNS[name] or list(frame.columns)!=spec['columns']: raise ValueError('schema mismatch')
            if 'value' in frame: frame['value']=pd.to_numeric(frame.value,errors='coerce')
            if 'source_row' in frame: frame['source_row']=pd.to_numeric(frame.source_row)
            setattr(bundle,name,frame)
        for digest,spec in manifest.get('raw_sources',{}).items():
            payload=checked_payload(spec)
            if hashlib.sha256(payload).hexdigest()!=spec['sha256'] or digest!=spec['sha256']: raise ValueError('raw hash mismatch')
            bundle.raw_sources[digest]=payload
        return bundle
