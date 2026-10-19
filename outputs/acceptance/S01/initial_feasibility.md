# S01 自动可行性结果

快照：`20261012T143920Z-6f4d426f`；产品请求窗口 2014-12-01 至 2026-01-01（不含末日）。

本步数据门槛：未通过；不得将缺失分支显示为可用

| 数据集 | 状态 | 行数 | 首日／月 | 末日／月 | 原因 |
| --- | --- | --- | --- | --- | --- |
| AAPL | success | 2788 | 2014-12-01 | 2025-12-31 | fields_verified  |
| 0700.HK | success | 2730 | 2014-12-01 | 2025-12-31 | fields_verified  |
| SPY | success | 2788 | 2014-12-01 | 2025-12-31 | fields_verified  |
| 2800.HK | partial | 2730 | 2014-12-01 | 2025-12-31 | missing_invalid_prices_or_months  |
| AGG | success | 2788 | 2014-12-01 | 2025-12-31 | fields_verified  |
| GLD | success | 2788 | 2014-12-01 | 2025-12-31 | fields_verified  |
| HKD=X | partial | 2893 | 2014-12-01 | 2025-12-31 | missing_invalid_prices_or_months  |
| HKMA_USDHKD | unavailable |  |  |  | request_or_format_failed SSLError |
| US_FF3 | success | 1202 | 1926-07 | 2026-08 | monthly_percent_converted_to_decimal  |
| US_FF5 | success | 758 | 1963-07 | 2026-08 | monthly_percent_converted_to_decimal  |
| AP_EX_JP_FF3 | success | 434 | 1990-07 | 2026-08 | monthly_percent_converted_to_decimal  |
| AP_EX_JP_FF5 | success | 434 | 1990-07 | 2026-08 | monthly_percent_converted_to_decimal  |

AAPL 2020-08-31 的 4:1 拆股与拆股调整后价格连续性核对：通过。独立事件依据：[Apple 分红与拆股记录](https://investor.apple.com/dividend-history/default.aspx)。

分红日的调整价收益与现金再投资收益仅作数值诊断，供应商调整算法可能产生小差异；不把此检查称为完整总收益审计。详见 corporate_actions.csv。

缺 key／付费来源不发送请求；来源条件与后续处理见项目 docs/data/source_matrix.md。CSV/XLSX 导入在 S02 实现。本步没有进行 HKD 收益换算、投资优化或候选池数量校验。
