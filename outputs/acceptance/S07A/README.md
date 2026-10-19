# S07-A：成员选择核心查验

日期：2026-10-19。状态：**S07-A 开发验收通过**。完整回归 **794 passed、2 条原有日历依赖弃用提示**，耗时 273.20 秒，见 [full_test_checks.txt](full_test_checks.txt)。本步新增 58 项；既有受影响基线 82 项通过。离线命令退出码 0，见 [verification_checks.txt](verification_checks.txt)；独立复审无未关闭问题。

本步把 100 项合格人工候选选成 **30 项研究成员草稿**，并说明每项如何入选。没有生成权重、utility 或正式投资组合；现有工作台页面保持原样，成员选择页面属于 S07-C。

## 直接查看

| 文件 | 如何检查 |
| --- | --- |
| [selection_reasons.csv](selection_reasons.csv) | 用 Excel 打开，筛选 selected=True，按 selection_step 排序，应恰好 30 项；selection_reason 说明入选原因 |
| [candidate_alternatives.csv](candidate_alternatives.csv) | 70 项未选候选及同组／同类对照；replacement_feasibility 为未评估，不是可直接替换建议 |
| [selected_correlation.csv](selected_correlation.csv) | 30×30 已选 Pearson 相关矩阵，基于共同 60 月 HKD 收益 |
| [cluster_memberships.csv](cluster_memberships.csv) | C 为已知相关性组，U 为未知相关性 |
| [manual_selection_reasons.csv](manual_selection_reasons.csv) | 手动纳入 001／002、仅不入选 000、bond 类别至少 20 项；N 仍为 100 |
| [identical_high_correlation_pairs.csv](identical_high_correlation_pairs.csv) | 全同向案例出现 435 对高相关，不能因数量达到 30 就宣称充分分散 |
| [constant_selection_reasons.csv](constant_selection_reasons.csv) | 常数案例相关性保持未知，不补零、不当作无风险 |
| [hand_correlation.csv](hand_correlation.csv)、[hand_cluster_memberships.csv](hand_cluster_memberships.csv) | A-B=.90、B-C=.90、A-C=.70：A/B 同组，C 不能被链式并入；NEG 与 A 负相关仍保留；CONST 未知 |
| [selection_evidence.json](selection_evidence.json)、[summary.json](summary.json) | 规则版本、训练窗口、筛选证据、指纹、可得时间和局限 |
| [review.md](review.md) | 两项 Important 的初审、修复及复审关闭记录 |

selection_reason 对照：`manual_inclusion`=手动纳入；`category_minimum`=补足类别最低数；`new_known_cluster`=覆盖新的已知相关性分组；`ranked_fill`=按规则补足数量；`member_excluded`=仅不入选；`not_selected_by_rule`=本次未选。

## 已核对的实际结果

| 情景 | 实际结果 |
| --- | --- |
| SYNTH 分组案例，N=100、K=30 | 30 个互异成员、覆盖 30 个已知组；重复调用和输入重排一致 |
| 手动项＋bond 最少 20 项 | 满足手动项及类别规则；覆盖 27 个已知组，重复敞口另行提示 |
| 全部同向、K=30 | 只覆盖 1 个已知组，输出 435 对高相关；不认证分散化 |
| 全部常数、K=30 | 已知组覆盖 0，30 项相关性未知 |
| 范围排除一项，N=99、K=30 | “候选产品池过小”，阻止选择 |
| 仅不入选 71 项 | N 仍为 100，但可选 29 项不足 K，阻止选择 |
| 手动纳入与排除冲突／类别无候选 | 明确冲突及缺口，不返回部分成功 |
| 已保存真实日线版本 | N=0，保持数据准备不足状态，没有真实成员草稿 |
| 文件排序资料 | CSV／XLSX 原字节验证后解析；篡改文件表拒绝；未来记录不参与选择 |

## 复算

在项目目录运行：

```bash
.venv/bin/python scripts/verify_selection.py
.venv/bin/python -m pytest tests/test_clustering.py tests/test_selection.py tests/test_selection_verification.py -q
.venv/bin/python -m pytest -q
```

本轮已重新安装 `.venv` 中的本地包，保证常规 Python 导入和测试源码一致。脚本不联网、不会写源数据；输出目录与真实源版本不得相交，已有输出文件为软链接／硬链接时拒绝发布。源文件哈希保存在 summary.json。

## 已知边界与下一步

这是预先声明规则的启发式选品，不是全局最优搜索。所有合格产品均为完整 60 月，数据质量排序并列，不额外虚构质量得分。未提供费用与可比 HKD 成交额时均为未知；已提供资料只按声明的决策时点判断可得，不认证供应商或新鲜程度。

相关性分组不是 ETF 底层持仓穿透；不同组之间仍可能高相关，所以另导出全体已选高相关配对。草稿不证明权重约束可行或未来保护，不绕过真实覆盖及历史候选认证缺口。

下一步 S07-B 检查同一估计窗口和协方差口径下增删／替换前后的等权或指定权重风险。随后 S07-C 接入统一页面，沿用既有藏蓝／青绿配色、导航、状态条、输入变更失效及宽窄屏验收。
