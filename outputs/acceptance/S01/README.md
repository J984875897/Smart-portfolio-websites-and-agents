# S01：小样本数据来源验收

状态：**通过（来源可行性开发验收，供小组查验）**。六类产品均有真实响应；5 个产品字段检查成功，2800.HK 日线仍为 partial。HKMA 当前 unavailable，另有覆盖请求期间的 Yahoo 月度 FX 可得性预览。此状态不等于正式候选数据合格，S02–S14 尚未开始。

## 输入版本与范围

- 项目 `.venv`：Python 3.14.6、yfinance 1.7.0；本步没有新增或升级依赖。
- 快照：`20261012T143920Z-6f4d426f`，UTC 时间见 manifest；香港时间为 2026-10-12 晚间。
- 产品日线请求：2014-12-01 至 2026-01-01（不含末日）；六类样本是 AAPL、0700.HK、SPY、2800.HK、AGG、GLD。
- 另请求 `HKD=X`、HKMA 最近 8 条及 French 美国／亚太除日本的 FF3／FF5 四个文件。
- [原始 manifest](snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json) 列 30 份保存文件的字节数、SHA-256、公开请求参数及可用 HTTP 状态。包括 14 个公开 chart 响应、7 份 yfinance 返回表、4 个 ZIP 与 4 份解压 CSV、1 份 HKMA 失败记录。认证内部请求不计入这 14 个 chart 响应，未保存 cookie／crumb／认证响应。

## 实际命令

在项目根目录执行。本次先在线获取，再修正检查规则并对同一原始快照离线重放，**没有为凑成功重新下载或修改原始值**：

```bash
.venv/bin/python scripts/probe_sources.py --sample-size 6
.venv/bin/python scripts/probe_sources.py --replay outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

在线命令会发起新的小样本请求并保存新的快照；只查验本次结果时用 `--replay`。重放使用快照的冻结期间，先核验全部文件哈希，不调用网络。可用 `--output /private/tmp/s01-review` 保存查验结果。退出码：0=本步门槛通过；1=门槛未通过但已生成明确状态；2=参数、快照完整性或文件错误。

## 预期与实际结果

| 检查 | 预期 | 实际 |
| --- | --- | --- |
| 六类样本 | 每类有身份、币种、获取状态和导入替代 | 已逐项记录，5 个 success、1 个 partial |
| 真实日线期间 | 请求区间内真实历史数据，不以模拟值替代 | 美国产品各 2,788 行；香港各 2,730 行；均覆盖 133 个日历月 |
| 原始响应与 yfinance 返回表 | Close／Adj Close 对齐，字段身份无冲突 | 七个 chart 数据集与对应返回表一致 |
| 原始汇率缺失 | 保留并报告，不补零／静默填充 | HKD=X 2,893 行，7 条无效，仍为 partial |
| 月度 FX 可得性 | 每个请求月份都有真实有效观察并显示实际日期 | 133 月，缺月 0、陈旧月 0；距月末最多 2 天 |
| HKMA | 成功或真实失败状态，不能用最近样本证明全历史 | TLS 握手失败，SSLError；保持 unavailable |
| 因子 | 月度区块、百分数→小数、独立 FF3／FF5、连续期间 | 四份成功；美国 FF3 1,202 月，FF5 758 月；地区各 434 月 |
| 公司行动 | 至少一个与独立公开记录匹配的真实事件 | AAPL 2020-08-31 4:1 拆股；当日 Close 收益约 3.39117%，没有重复拆股 |
| 离线复现 | 哈希核验，重复导出一致 | 结果与执行记录见 checks.txt、replay_checks.txt |

完整分类、字段、原始哈希和状态见 [source_probe.csv](source_probe.csv)；简明可行性结果见 [feasibility.md](feasibility.md)；免费／付费／缺 key 的路径见 [来源矩阵](../../../docs/data/source_matrix.md)。

## 可查看文件

- [USDHKD_monthly_spot_preview.csv](USDHKD_monthly_spot_preview.csv)：各月最后真实有效观察、日期、HKD per USD、距日历月末天数。7 天仅是 S01 筛查假设，尚不是 S03 的估值／换算规则。
- [2800.HK_daily.csv](2800.HK_daily.csv)：2025-10-24 一行价格与成交量缺失，原样保留；没有据此直接删除产品或宣布合格。
- [corporate_actions.csv](corporate_actions.csv)：256 条诊断。现金再投资收益和供应商调整价收益不强制相等；最大分红差约 12.81 bps，留到 S03 核对。
- [US_FF3_decimal.csv](US_FF3_decimal.csv)、[US_FF5_decimal.csv](US_FF5_decimal.csv)：两份独立因子预览；保留各自 SMB，不混用。原始说明及 ZIP 均在快照中。
- [derived_manifest.json](derived_manifest.json)：当前 17 份派生产物的哈希及原始 manifest 校验值。派生表随重放更新，原始快照不覆盖。

## 失败检查与修正记录

初始真实请求结果为 **门槛未通过**，原因是日线 FX 存在缺值且 HKMA 失败。保存 [initial_probe_summary.json](initial_probe_summary.json)、[initial_source_probe.csv](initial_source_probe.csv)、[initial_feasibility.md](initial_feasibility.md) 及 online_checks.txt。后来单独导出、核验月度 FX 可得性，满足月度研究路径；原始日线状态没有改成成功。

自动检查涵盖格式变化、错误响应、非法或缺失 FX、调整价缺失、产品代码／币种／工具类型冲突、OHLCV 缺失、请求边界月份缺失、因子缺月／年度区块／缺失哨兵、文件篡改／路径越界和失败重放后的旧导出文件清理。参数错误在发起网络请求前拒绝。坏快照不更改已有导出，合法但不可用的新快照不会残留上次的工具生成数据；用户笔记保留。

最终全量检查 **45 项通过**（S00 14 项、S01 31 项）；`pip check` 未发现依赖冲突。两次离线重放的 17 份派生产物及派生 manifest 字节一致，30 份原始文件哈希核验通过。

测试先失败再实现及审查后修正记录保存为 red_checks.txt、initial_green_checks.txt、review_red_checks.txt、review_green_checks.txt、stale_red_checks.txt、stale_green_checks.txt。独立只读审查记录见 review.md；最终命令以 checks.txt 为准。

## 局限及下一步

来源可用性及条款随时间变化；本次样本不证明免费全覆盖、完整总收益审计、历史可投资名单或候选数量条件。Yahoo 为非官方路径，HKMA 官方汇率分支仍未打通。亚太除日本是 USD 地区股票因子，不能当香港专属模型，也不直接套用于黄金／债券；本步没有回归。

日交易日历、跨市场估值时点和 HKD 无风险代理在 S03 验证。原始数据只保留在本地研究目录，没有自动公开上传。S04 才实现统一下载／更新、取消、缓存发布及恢复；当前 CLI 只是 S01 查验工具。

**下一轮只做 S02：CSV／XLSX 导入、分类映射与质量报告，并提供第一处可操作的导入预览。**
