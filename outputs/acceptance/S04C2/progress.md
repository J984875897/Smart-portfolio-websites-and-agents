# S04-C2 进度

- [x] 检查现有计划及接口；选定 C1 价格预览 → FX 端点 → S03 公式连接。
- [x] 设计自查：自然月末标签与实际观察日分离；研究年龄政策与历史可得性分离；本轮不扩展 C3。
- [x] Task 1：核心端点、HKD 连接、原始缓存读取；79 项相关检查通过，审查 spec/quality 均 Approved。两个既有上游日历弃用提示保留。审查提示的价格 manifest/run 由 C1 cached_monthly_prices metadata（已有 manifest/run_id/raw_sha256）提供，连接保留完整 price_source，界面按此使用。
- [x] Task 2：三步查验页、状态撤下与导出；34 项相关检查通过，spec/quality Approved。Minor：缓存发现采取保守策略，未选快照损坏也可能阻止该来源列表；不静默跳过损坏。已实测1440/720无横向页面溢出或框架异常，实际下载CSV为11.410256%且日期/历史标记正确；取消汇率确认撤下结果。
- [x] Task 3：独立真实离线复算、最终审查、完整检查、实际界面及文档。

Task3初版：独立5项检查通过，真实离线SPY港币约3.0586128809%、2800.HK约1.0869455644%；全套初版420 passed/2既有warnings。最终审查 Needs fixes（3 Important）：Yahoo原始空时间戳在filter前丢失、排序后原始行号错误、auditor zip截短及最终FX日期/年龄未交叉核对。已调度一个fixer合并处理，必须新RED/GREEN、重放、复查及最终回归后才验收。

追加一项相关C1价格缓存边界缺陷（Important4）：同样的空时间戳在date filter前被丢掉。只修本步依赖路径，复用原始时间戳guard，不改共享parser既有行为或C3范围。审查已提供41+1日线复现，fixer补RED后合并修复。

final-fix完成：17项新失败及C1空timestamp另1项RED已保留，修后133相关检查通过/2既有warnings；新增共用validated_timestamp_rows只在两个缓存边界调用，FX原始行号恢复。auditor端点/目标行数量、标签、最终FX日期/年龄/报价均交叉核对。真实离线重放已更新，等待同一最终审查者复审；不能用初版420替代最终全套结果。

无 Git 仓库；沿用原工作区并在 /private/tmp 保存基线副本，使用文件差异包审查，不创建仓库或分支。

最终交付2026-10-17：四项Important及超大整数Minor复查Approved；最终445 passed/2既有warnings（30.38秒，exit0）。最终离线CLI exit0，源globalpartial保留。标准包重装后26源码文件字节一致、104锁版本匹配、34原数据文件及运行集合不变。工作台PID72574 / exec49546在127.0.0.1:8501；健康ok。最终浏览器主流程再次通过，缺FX流程和清理见后续记录；下步只做C3，不提前进入S05。

最终浏览器主流程与缺FX流程均通过；最终额外脚本改用键盘打开React Aria组合框，消除重渲染时鼠标坐标波动，未改产品代码。独立Chrome71840已用Browser.close关闭，日常浏览器未操作，Streamlit72574仍运行。文档链接/本步计划复选框/原生CSV最终值和日期核对完成。C2没有剩余必做项；下一次只进入C3。
