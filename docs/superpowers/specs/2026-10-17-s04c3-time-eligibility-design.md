# S04-C3 历史观测时间资格

用户已确认：采用本地快照证据与人工声明分层的方案。

查验对象是 C2 港币收益所用的价格及汇率版本。下载器在所有响应和派生文件写入后记录 `completed_utc`，它证明本地已取得该版本；`created_utc` 仅表示开始。旧快照保持可读，不回填时间。完成时点须为 UTC，且不早于开始。

只有基础收益有效、来源 success、重新读取并通过散列查验的快照与 C2 原始散列一致、所需快照完成时间均不晚于含时区的 decision_at，才能得到 eligible_from_snapshot。边界相等允许。USD 需要价格及 FX；HKD 仅需价格。未取得快照、时间缺失、下载较晚、散列不一致或 partial 必须说明原因。

人工 available_at 只能得到 declaration_only，不升级观测资格。缺少源站历史发布时间时，不声称源站当时未发布。输出 historical_observation_eligible 与 historical_universe_eligible（始终 false）分离；原 C2 historical_eligible 保持 false。此步骤不解决退市产品、历史候选池或幸存者偏差。

核心 `qualify_daily_hkd(result, *, decision_at, price_capture=None, fx_capture=None, declared_available_at='')` 返回独立结果与元数据，不修改 C2。证据加载器从本地快照重新验证文件；缓存损坏时撤下结果与导出。SYNTH 示例明确标识，不能作为真实投资证据。

界面新增「历史资格查验」：选择上一页 C2 结果或合成示例，输入决策时点与可选声明，显示资格、阻止原因、完成时间和散列，下载 CSV/JSON。每次输入改变立即重算，避免残留结果。无联网、无数据保存或候选池升级。

验收：完成时刻/前一微秒、缺失时间、无时区、错误时间顺序、partial、散列不匹配、USD 缺 FX、HKD 无 FX、人工声明、旧快照、缓存破坏、输入失效、无修改；运行针对测试及全套回归。
