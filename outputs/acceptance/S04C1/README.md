# S04-C1 日线转月度原币收益

状态：**S04-C1 开发验收通过（2026-10-17）**。最终360项检查通过，完整独立审查Approved；1440／720屏宽、真实CSV下载及旧结果撤下均通过。此步为价格日历预览；C2 港币汇率配对、C3 历史可得证据尚未交付。

## 先在页面看一遍

打开 [本机工作台](http://127.0.0.1:8501)，左侧选择「日线月度查验」。

1. 来源选「人工案例」，案例选「完整报价」，产品保留 SPY，月份保留 2025-01。
2. 勾选复权价格口径确认，点击「查验日线并计算月收益」。前月价格100、本月110，应有1个月可预览，收益10%。
3. 案例改为「缺最后交易日」后，旧结果撤下；重新查验应阻止一月，显示缺少1月31日报价。切到2800.HK，同一案例应显示缺1月28日。
4. 展开「逐日明细与来源证据」看缺日、月末价格、收益和来源；可导出CSV。这里先查看原币收益，美元价格尚未换成港币。

这些价格是人工验证值，日期按真实市场日历生成；10%不是投资表现预测。

选择「已下载缓存」可以查验已有Yahoo记录，全程不联网。旧的单月Jan2025缓存缺Dec2024起点，不能算出一月收益，这会明确显示为缺前月。计算一月收益须先在「下载与缓存」下载2024-12-01（含）至2025-02-01（不含）的完整两个月。新下载若失败会在原页面保留失败记录，本页不把它变为可用数据。

## 本轮真实证据

新联网尝试 `20261016T132413936814Z-c784827343704f318c02d12381d2abbb`：SPY超时，2800.HK连接失败，每项一次，无自动重试。原始manifest保存在data/downloads/runs，不覆盖旧记录。审计退出1表示本次来源不可预览；完整性核验通过，不是数据校验损坏。结果见 [online_attempt/independent_verification.json](online_attempt/independent_verification.json)。

为检验真实计算，显式离线读取S01旧快照 `20261012T143920Z-6f4d426f`，先核验所有文件SHA256，再选唯一历史原始响应。仅Dec2024/Jan2025目标窗口的日历价格通过；不对旧快照其他月份作整体合格结论，不冒充新下载成功。

| 产品及原币 | 月初锚点实际交易日／复权价 | 月末实际交易日／复权价 | 原币月收益 |
|---|---|---|---|
| SPY · USD | 2024-12-31／574.7880859375 | 2025-01-31／590.2247314453125 | 2.6856237778% |
| 2800.HK · HKD | 2024-12-31／19.488393783569336 | 2025-01-28／19.70022201538086 | 1.0869455644% |

直接读取原始JSON的两端价格相除减1，与生产输出完全一致。参考计算使用官方样例的明确假期和端点日期，不调用生产收益公式。完整结果见 [独立复算](legacy_replay/independent_verification.json)、[SPY月度价格](legacy_replay/SPY_monthly.csv)、[SPY收益](legacy_replay/SPY_returns.csv)、[2800.HK月度价格](legacy_replay/2800.HK_monthly.csv)、[2800.HK收益](legacy_replay/2800.HK_returns.csv)。来源hash、原下载时间、日历映射和版本保存在相应metadata。

复现（只读取旧数据、无网络）：

```bash
.venv/bin/python scripts/verify_daily_monthly.py --s01-manifest outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json --output outputs/acceptance/S04C1/legacy_replay
.venv/bin/python -m pytest -q
```

## 通过条件和限制

- 完整人工100→110输出10%；缺前月、缺末日、缺中间日、重复、周末额外行、无效日期／价格、未确认口径和月份未成熟均阻止相应收益，不补零或回退日期。
- 输入列名歧义显式拒绝；极端正端点导致比例溢出时保留计算失败，不能显示valid/NaN。
- 缓存原始JSON的布尔复权价True/False在数值转换前拒绝，不能被解析为价格1/0；原始响应保持不变。最终审查的该Important发现已修复并复审通过。
- 全部缓存文件验证后从原始JSON重读；partial只作诊断，收益全部阻止；损坏及身份不符失败关闭。参数／源版本变化后撤下旧结果及导出。
- 目标月之前还需要完整一个月。月成熟采用市场当地下一月1日00:00的保守规则，不在最后报价日提前宣称整月完成。
- 日历为锁定版本exchange_calendars 4.13.2的现金市场代理；已抽样核对2025-01假期／香港半日、2024-12提前收市和2025-03美国夏令时；不认证具体产品停牌、上市前数据或全历史异常休市。
- calendar_close_at是库的交易结束标签，香港可能还有收市竞价；Yahoo日线timestamp和交易结束时间均不表示价格发布时间。available_at保持空，historical_eligible始终false。
- 已知依赖限制：XHKG构建产生两个上游NumPy generic timedelta弃用提示，未全局隐藏，当前数值检查通过。

开发记录：[设计](../../../docs/superpowers/specs/2026-10-16-s04c1-daily-monthly-design.md)、[实施计划](../../../docs/superpowers/plans/2026-10-16-s04c1-daily-monthly-implementation.md)、[进度](progress.md)、[核心审查](task-1-review.md)。

最终证据：[完整检查](full_tests.txt)、[最终修复及RED/GREEN](final-fix-report.md)、[最终审查](final-review.md)、[浏览器结果](browser_checks.json)、[720屏宽截图](browser_720.png)、[收益表截图](browser_result.png)、[未确认时阻止截图](browser_blocked.png)、[实际浏览器下载CSV](browser_exports/verified_returns.csv)。服务已刷新，本机健康检查HTTP200。旧Yahoo／French／HKMA失败记录全部通过现有文件哈希核验；本轮未再次联网请求行情。
