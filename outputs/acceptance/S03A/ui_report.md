# S03A 界面查验

范围：`app/main.py`、`app/views/hkd_returns.py`、`tests/test_hkd_returns_view.py`。原入口备份：`main.py.before`。没有修改 S02 数据中心、导入契约或核心计算。

真实 red：`ui_red.txt`，四个界面测试因页面导航尚不存在而失败。真实 green：`ui_green.txt`，运行 `.venv/bin/python -m pytest tests/test_hkd_returns_view.py tests/test_data_center.py -q`，19 passed（6 个 S03A 测试 + 13 个原 S02 回归）。

界面默认进入「数据导入」，侧栏可以切换「港币收益查验」。当前 S02 bundle 为只读输入；人工案例通过 read_file → preview_import → commit_import 生成独立 bundle，明确接受人工 −100% 极端值，且不会保存或替换 S02 bundle。用户切换数据模式时清除复权确认；复权资产 multiselect 默认不勾选，人工案例同样要求明确确认。

人工案例解释美元收益 .01、FX 7.8 → 7.9，实际查验得到 .02294871794871795；HKD 收益 .01 无需 FX。调整价格 100 → 101 的月收益在明确确认后得到相同换算结果；首期仍阻止。缺末 FX 和完全没有 FX 都阻止外币换算，保留 NaN，同时 HKD 本币有效。

FX 支持 CSV/XLSX 及工作表选择，经 read_file 保留 source_file/source_sheet/source_row/source_hash。展示 validate_fx 的问题报告，提供 CSV 模板和已测试汇率案例下载。核心返回的原币收益、HKD 对照、FX 质量报告可下载 CSV；页面只调用核心，不包含金融换算公式、联网下载或行情 API。

指纹覆盖 assets、observations、provenance 的内容和列名、数据模式、FX 模式、FX 原始字节/文件名/工作表、明确确认集合。即使 bundle_version 未变化，当前数据内容变化也立即清除旧结果。任何读取/换算错误先清除结果；坏 XLSX 使用局部错误提示，不导致页面异常。测试还覆盖同文件名 FX 字节改变、撤销上传和 XLSX sheet 改变的即时失效及源 hash/工作表追踪。

页面持续说明 S03-B 时间对齐、60 月共同窗口与 S03-C 无风险代理未完成，当前结果不能用于组合估计、Sharpe 或回测。AppTest 对浏览器文件选择的能力有限，上传测试仅替换 file_uploader 返回值，使用实际 CSV/XLSX、实际导入和实际核心计算，其余未 mock。

## 主结果可读性补充

按最终审查反馈，在完整来源表前增加「收益查验结果」摘要，前六列为产品名称、资产标识、原币、期末日期、原币收益（%）、港币收益（%），随后显示起止 FX 及中文状态/原因。百分数仅为核心结果乘 100 的显示转换，不重新实现收益公式。空白 / NaN 明确标示缺失或不可用，阻止不能作为有效收益使用；不把 NaN 转为零。完整核心小数口径、来源证据、CSV 下载保持在「完整对照、来源证据及 CSV 下载」展开区。

实际 red：`ui_summary_red.txt`，新 AppTest 因页面没有中文百分数摘要列失败。实际 green：重新执行 `.venv/bin/python -m pytest tests/test_hkd_returns_view.py tests/test_data_center.py -q`，20 passed（7 个 S03A + 13 个 S02）。新增测试直接读取用户可见 dataframe，验证 USD 港币收益 2.294871794871795%、HKD 1%、原币 1%、未确认复权为 NaN、缺末 FX 为 NaN 且中文显示「阻止：缺失或不可用／缺少精确期末汇率」。
