# S04-C2 最终审查范围

只读审查本步全量代码差异（`final-code.diff`），对照设计 `docs/superpowers/specs/2026-10-17-s04c2-daily-hkd-design.md`、实施计划 `docs/superpowers/plans/2026-10-17-s04c2-daily-hkd-implementation.md`。使用 requesting-code-review/code-reviewer 模板给出 Critical/Important/Minor 与整体结论；每个发现需 file:line、后果和修复方向。任务报告和实测日志由控制者提供，不能以报告代替代码核验。

重点是金融数值连接、端点日期与年龄、来源完整性、确认和旧结果失效、真实独立复算是否真正独立。检查 C1 blocked 是否继续保持，HKD 是否不依赖 FX，公式是否复用 S03；文件字节/工作表/hash/manifest 是否绑定当前输出；Yahoo 与 HKMA/人工是否有明确区分。历史可得性永远未认证，本步不生成候选/回测。

没有 Git 仓库，差异由原副本生成；不创建仓库、分支或提交。任务1/2各自已经做过针对性审查；未完成警告项记在 progress.md。已有两个日历依赖弃用提示不得静默忽略；它们是否影响本步结论按实际风险判断。最终完整检查只由控制者运行一次，审查者只为明确疑点运行具体小测试。

将审查写入 `outputs/acceptance/S04C2/final-review.md`，返回简洁结论与需要修复的发现。无代码修改权限（仅写审查文档）。
