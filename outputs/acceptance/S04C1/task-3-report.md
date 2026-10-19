# Task 3 验收工具与真实证据（进行中）

脚本 scripts/verify_daily_monthly.py 为只读离线审计；独立从原始 JSON 按 timezone 还原日期，使用官方样例的字面假期集合和月末日期，直接算两端比值，与生产三张表核对。不会再次下载，不把当前版本变成历史可得证据。

TDD：初始4项 FAILED，缺 scripts.verify_daily_monthly 模块；脚本实现后4项通过。新增旧S01显式复算入口，先1项FAILED（缺 verify_legacy），实现后5项通过。CLI初次运行因标准安装未包含新核心而 ModuleNotFoundError，按项目 probe_sources 惯例在入口绑定本地src后运行成功，避免查验当前源码时误用旧安装。测试有两个上游XHKG NumPy弃用提示，未全局屏蔽。

新在线尝试：20261016T132413936814Z-c784827343704f318c02d12381d2abbb，2024-12-01（含）至2025-02-01（不含），SPY timeout、2800.HK transport_error。每项一次，无重试，无响应文件；原manifest保留。审计命令 --run-id 返回1，完整性核验成功但无可预览来源。online_attempt/independent_verification.json 保存事实。

显式旧来源复算：--s01-manifest outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json --output outputs/acceptance/S04C1/legacy_replay，退出0。完整旧快照所有文件哈希校验后，从唯一历史响应读取；目标窗口Dec2024/Jan2025逐日完整。本次不是新在线下载成功，不声明旧快照整体合格。

| 产品 | 原始起点 | 原始终点 | 直接比值与核心收益 |
|---|---:|---:|---:|
| SPY / USD | 2024-12-31: 574.7880859375 | 2025-01-31: 590.2247314453125 | 0.026856237777849623 |
| 2800.HK / HKD | 2024-12-31: 19.488393783569336 | 2025-01-28: 19.70022201538086 | 0.010869455644421322 |

来源raw SHA256、原始下载时间、空available_at、historical_eligible=false和库版本保存各metadata。完整suite、UI浏览器与最终审查由控制代理完成后附结果。

最终结果（2026-10-17）：布尔复权价漏洞修复后完整360项通过，25.77秒，保留两个上游XHKG NumPy弃用提示；整体独立复审Approved。安装包刷新且monthly_cache字节匹配源码，Streamlit重启后HTTP健康检查200；实际浏览器1440/720无横向页面溢出或框架异常，Material字体正常，原生CSV下载及撤销确认后结果撤下均通过。独立真实S01重放仍得到同一结果；所有旧Yahoo与reference快照全文件哈希通过。本轮续作未再次下载行情。
