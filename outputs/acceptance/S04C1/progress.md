# S04-C1 进度

范围：日线交易日检查和原币月度价格／收益，C2 汇率配对、C3 历史可得性独立验收。

- 设计与接口：已写入 spec 和 implementation plan，并自审范围、状态及时间语义；既有用户分步授权下执行。
- 环境：327 项基线通过，25.09 秒；无 Git，备份 /private/tmp/portfolio-s04c1-before.k1tmG8。
- 依赖：新增 exchange_calendars 4.13.2、korean_lunar_calendar 0.4.0、pyluach 2.3.0、toolz 1.2.0、tzdata 2026.5，旧版本不升级。
- Task 1：完成；初审发现计算溢出状态被覆盖及重复列歧义，均 TDD 修复；修复检查35通过，复审 Approved。上游XHKG两项NumPy弃用提示作为已知依赖限制记录。
- Task 2：完成，独立审查 Approved；8项新增AppTest、指定回归20项通过。未来月份测试按审查Minor固定as_of，8项复查通过。无Critical/Important。
- Task 3：完成。独立检查5项通过；本次联网SPY timeout、2800.HK transport_error保留；S01旧快照全文件哈希校验后，Jan2025真实原币收益SPY0.026856237777849623、2800.HK0.010869455644421322与独立直接比值一致；Oct17最终重放仍一致，非新在线成功。
- 2026-10-17续作完成：原始JSON布尔复权价True/False转换前拒绝，RED2项失败→GREEN54项通过，快照不改；最终全套360项通过25.77秒，上游弃用提示2项保留。整体复审Approved，无Critical/Important。
- 本地包重装且最终monthly_cache源码与安装字节一致；服务重启、健康检查200；刷新后浏览器1440/720无越界或框架异常，Material字体正常，真实CSV及旧结果撤下通过；所有原Yahoo/reference快照哈希核验通过。
- C1开发验收通过，下一次仅推进C2日线FX端点与HKD连接；C3历史时间认证仍未完成。
