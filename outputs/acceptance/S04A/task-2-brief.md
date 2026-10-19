# Global constraints


- 范围固定为 AAPL、0700.HK、SPY、2800.HK、AGG、GLD、HKD=X 七个识别样本，可多选。
- 日期严格 YYYY-MM-DD，起日包含、止日不含，start < end；每项一次公开 chart 请求，不自动重试、不接收 key、不登录。
- 超时默认 15 秒，范围 1–30 秒。
- 每项状态 success / partial / unavailable / cancelled；success 只表示来源字段检查通过，不代表完整交易日历、历史可得时间或 S05 候选合格。
- 原始 chart 响应按原字节保存；所有派生文件在清单校验内；旧目录始终不修改。
- 使用缓存不触发任何网络；更新结果与已打开缓存分开，失败后仍显示旧缓存及其日期。
- 不记录异常文本、认证头、cookie、crumb 或密钥。
- 不自动 commit 或保存 bundle；本步不计算月度 HKD 收益、Sharpe 或候选资格。
- 当前无 Git，以 /private/tmp/portfolio-s04a-before 生成文件差异代替提交，不初始化仓库。

## Task 2: 可查验页面与导入交接

**Files:** 新建 app/views/downloads.py、tests/test_downloads_view.py；修改 app/main.py、app/views/data_center.py（仅交接所需）。输出 outputs/acceptance/S04A/task-2-report.md。

**Consumes:** Task 1 所有公开接口。缓存根目录 PORTFOLIO_DOWNLOADS_ROOT，默认 ROOT/data/downloads。统一由 view.downloads_root() 取值方便隔离；不在导入时创建/下载。

**Produces:** 侧栏“下载与缓存”，原页面默认不变。控件 key 前缀 dl_，symbols 多选默认 SPY/2800.HK，date_input 默认 2025-01-01/2025-02-01，timeout 默认15。`dl_prepare` 生成纯计划；`dl_start` 开始下载；`dl_cancel` 取消计划。参数指纹变化清计划，结果带原请求范围，不作为新参数的结果。用原生控件和中文状态/原因，预览逐项身份及请求数。清楚提示取消在开始前，下载进行中单请求超时上限。

缓存区域列已完成 run；打开 run 校验全部文件；展示逐项状态和时间，只有 success 项可作为缓存使用。`dl_open` 打开所选run，`dl_active` 存已验证manifest/run identity；失败打开或失败下载不替换旧active。更新结果 `dl_result` 与active分开，不自动覆盖。可选择已打开缓存中的成功 symbol，显示原币日线和原始清单；导出 update_log.csv、snapshot_manifest.json、日线与对应导入CSV。点击缓存操作、改变参数及导航都零网络。

`dl_to_import` 通过回调交接至 S02（回调先于侧栏radio渲染）。调用 set_source，kind=adjusted_price，unit=decimal，supplier 写 Yahoo chart/run_id/raw sha256。用生成的同名 CSV，不自动 commit。旧file_uploader可能仍带内容：需清除旧 uploader session state/token，使交接内容保持不被覆盖；不要破坏普通上传重选。S02来源显示 filename 包含 run_id 方便追踪。HKD=X 导出日线并说明方向、不提供送入产品导入。未交接时 S02 bundle 无变化。

- [ ] 写 AppTest：默认零下载、计划+取消零下载、参数变更清计划、显式按钮才下载、部分结果逐项显示、失败保留active、离线打开与导出、损坏不替换active、交接精确字段/口径/来源和保留bundle、旧上传不覆盖、FX禁止产品导入。

```python
def test_no_auto_download(monkeypatch, tmp_path):
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT',str(tmp_path))
    monkeypatch.setattr('app.views.downloads.run_update',lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected download')))
    at=AppTest.from_file('app/main.py').run()
    at.radio(key='workspace').set_value('下载与缓存').run()
    at.button(key='dl_prepare').click().run()
    at.button(key='dl_cancel').click().run()
    assert not at.exception
```

- [ ] 运行该测试，记录 RED；实现最小页面和交接后记录 GREEN。
- [ ] 运行 tests/test_data_center.py（若实际名不同用 rg 确认原 S02 view 测试）和新测试；报告精确测试命令、结果、自查发现。不要联网或运行全套，controller 统一集成验证。
