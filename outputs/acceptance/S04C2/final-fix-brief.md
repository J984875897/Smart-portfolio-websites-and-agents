# S04-C2 最终审查修复

先阅读 final-review.md 的三项 Important 及各复现证据；binding设计与计划路径见 final-review-brief.md。通过测试验证问题再修复，不改已有金融口径或缓存 partial 规则。

修改 `src/portfolio/data/fx_cache.py`、`scripts/verify_daily_hkd.py` 和相关 `tests/test_fx_cache.py`、`tests/test_daily_hkd_verification.py`。追加的第4项允许必要窄修 `src/portfolio/data/monthly_cache.py`、`tests/test_daily_monthly.py`，以及在 `providers/yahoo.py` 新增共用原始时间戳证据校验helper；保持已有parse_yahoo_chart/audit_price行为不变。其余源码如确需修改先说明。不联网、不安装依赖、不重启服务、不写原始缓存。

1. 原始 Yahoo FX 时间戳无法定位时（含null/NaT）必须失败关闭，不能经日期范围筛选丢掉问题行后得到有效收益。在 raw parse/filter 前拒绝或完整保留不可定位诊断；bool/nonfinite等时间戳不得被默认为有效。覆盖有效两月端点之外额外null时间戳的原始响应（上游可标success）并证明旧实现错误通过。期望公开缓存入口拒绝ValueError即可，UI已能撤下输出。
2. Yahoo FX source_row 必须对应原始 JSON timestamp/quote数组1起序号，不是排序后表索引。原始顺序倒置时，正确端点日期/值和来源行号均须与原数组一致；不改变raw文件。利用 parser保留timestamp_utc做映射或在严格验证原始日期之后构造正确行号；重复/无效时间戳仍失败关闭。
3. 独立验收必须核对端点数量、自然月标签唯一性/覆盖、以及每条reconciliation FX起止实际日期与年龄/报价。不能因zip截短而忽略缺行，也不能只比较端点表不比较最终输出。写参数化篡改测试（删除全部/部分端点、重复端点或错日期；reconciliation日期/年龄/报价损坏）。所有篡改必须被识别，实际完整和缺FX诊断仍如实核对通过。独立参考继续直接JSON，不能用生产函数生成预期结果。
4. 审查追踪到C2依赖的C1价格缓存同样会在范围筛选时丢掉null时间戳：完整41个Dec/Jan SPY日线加1个无法定位日期的正价行，仍被标success并生成valid10%。在价格缓存边界复用共用时间戳校验，筛选前失败关闭，补独立失败案例。只修这一相关入口，不扩大日历、历史可得性或共享parser行为；如绑定原始行号则同样测试倒序原始记录。

按TDD先运行新检查并保存RED，再最小修改，再跑覆盖检查：`.venv/bin/python -m pytest tests/test_fx_cache.py tests/test_daily_hkd.py tests/test_daily_hkd_verification.py tests/test_daily_hkd_view.py tests/test_daily_monthly.py tests/test_updates.py -q`。保存 final-fix-red.txt / final-fix-green.txt。最后实际旧快照CLI重放到 legacy_replay，并保存 final-fix-replay.txt。

完整报告写 `outputs/acceptance/S04C2/final-fix-report.md`：每条发现是否复现、修复机制、RED/GREEN命令及结果、修改文件、自查和剩余问题。无Git不提交。本次所有三项一起修复，但可逐项RED/GREEN。不要重复完整全套测试；控制者在审查通过后做最终完整检查并重新安装/重启。返回简短DONE/concerns及报告路径。
