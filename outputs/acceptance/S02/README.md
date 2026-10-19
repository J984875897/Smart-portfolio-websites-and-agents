# S02：文件导入、分类和质量检查

日期：2026-10-13（香港时间）。状态：**开发验收通过，供小组查验**。

本轮范围依据 [S02 设计](../../../docs/superpowers/specs/2026-10-13-s02-import-design.md) 与分步计划。核心与界面分开；只导入原币价格／已提供收益，没有生成 HKD 收益、候选资格或投资组合。

## 现在已验证的结果

- 完整测试 91 项通过：原有 45 项、导入核心 33 项、界面 AppTest 13 项。独立审查通过。
- 本地界面首页返回 HTTP 200，健康检查返回 200／ok；在项目目录之外加载已安装核心并完成界面导入、保存和重读，无异常。
- 10 个合成产品首次导入，重复上传 2 个后仍为 10 个；观察值仍为 10 条，来源追踪增至 12 条。
- 合成百分数 2 转成 0.02；股票 ETF 工具类型保持 ETF；必要分类缺失阻止导入，原始缺失数值保留 NaN。
- 原币真实数据离线复用 S01 的 AAPL、SPY、2800.HK，共接受 8,305 条调整价格。2800.HK 的 2025-10-24 空记录保留为被阻止行，没有补零。
- 极端收益与重复关系分别检查；重复记录不能绕过核对。分类修改、来源别名和原始文件可追踪；DataBundle 保存／重读已核验。

## 可复查文件

[导入预览](import_preview.csv)、[重复上传预览](repeat_preview.csv)、[异常数据预览](dirty_preview.csv)、[质量报告](quality_report.csv)、[数量前后对照](before_after_counts.csv)、[真实样本导入数量](real_import_counts.csv)、[真实空价格问题](real_missing_price_report.csv)。保存版本位置见 [验收摘要](import_summary.json)；其中原始文件、所有表及校验值可离线读取。

审查过程：[核心实现](core_implementation.md)、[核心修复](core_fixes.md)、[核心审查](core_review.md)、[界面实现](ui_implementation.md)、[界面修复](ui_fix.md)、[最终审查](final_review.md)。7 项重要发现均已修复并复查，没有未解决的 Critical／Important 问题；密集语句的可读性属于后续维护事项，不阻塞本步。实际 RED／GREEN 输出保存在本目录。

[总验收记录](checks.txt)、[完整测试输出](test_checks.txt)、[页面检查](server_checks.json)、[目录外安装验证](installed_ui_checks.txt)、[断网恢复后的离线复查](resume_import_summary.json)。

## 复查命令

在项目根目录执行：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/verify_import.py --output /private/tmp/cityu-s02-recheck
.venv/bin/python -m pip check
```

验收脚本不联网，读取合成 CSV 与已保存的 S01 CSV；每次生成独立保存版本，拒绝覆盖旧版本。只有验证结果 CSV／摘要在指定输出目录更新。导入前检查和具体格式见 [导入说明](../../../docs/data/import_format.md)。

## 界面查验步骤

在项目目录运行以下命令，终端保持开启；已有服务运行时直接打开 [本地界面](http://127.0.0.1:8501)：

```bash
.venv/bin/python -m streamlit run app/main.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

1. 选择 `ten_products.csv`，点击「载入合成示例」与「质量检查」。10 行可接受，百分数 2 已变为 0.02，工具类型为 ETF、经济类别为 equity。
2. 点击「仅保存可接受行」，查看下方 10 个产品／10 条原币观察；「来源追踪」应为 10 条。
3. 载入 `repeated_two.csv`，检查再保存。产品仍为 10、观察仍为 10，来源追踪增为 12，不以重复记录凑数量。
4. 载入 `dirty_data.csv`，检查应为 6 行阻止、1 行待核对。未确认时保存按钮不可用；明确核对后，仅 0.70 待核对收益可入库，阻止行仍不会入库。这里的 0.70 是合成异常测试值。
5. 在顶部「打开已保存版本」重读某个版本，核对产品、原币观察、来源、分类修改和质量报告六个页签。

自己的文件可通过 CSV／XLSX 选择器上传，Excel 可选择工作表。查看原始记录后映射字段，明确类型、原币、频率与数值口径；缺少单产品信息时可填默认值，默认值仅填空白。必要时明确修正分类或关联来源别名，随后重新检查。更改文件、映射、口径、分类或数据版本后，旧预览与确认失效，须重新检查。

用户保存版本位于项目 `data/processed/imports/`；本目录的验收 bundles 用于自动复查，不会自动列入用户版本选择器。重复运行以上操作时，以空数据版本／新会话核对首次导入数量；已有数据会累积，页面会显示当前版本和总数。

## 假设和边界

绝对单期收益 ≥50% 是本步的核对提示阈值；合法的 -100% 也需核对，不截断或当作无效。月频同月多个日期会提示核对，完整估值规则后续确定。Excel 中已经变成数字的产品代码不能恢复此前丢失的前导零，代码应以文本提供。

分类和别名修正是用户明确操作，自动匹配只使用完整的上市身份。稳定 ID 可以在无 ticker 时保留，不因空 ticker 合并产品。不根据相似名称合并；也不强行合并不同交易所、币种或份额。

S02 保存目录拒绝覆盖，校验表和原文件；生产级下载、缓存更新与崩溃恢复在 S04。质量检查通过不代表正式合格候选数 N，尚待后续共同收益窗口与范围规则。

Streamlit／openpyxl 及必要依赖新增 22 个，原锁定 77 个版本保持不变，现锁定 99 个；参见 [依赖变化](dependency_changes.json)。依赖检查通过，无冲突。

界面测试采用 Streamlit AppTest；同文件重选回归在上传控件边界使用模拟文件。实际原生浏览器文件选择和下载交付未自动查验，不能由 HTTP 或 AppTest 通过推断。小组可按上述步骤手动检查。下一次开发范围仅 S03：总收益、HKD 换算与共同窗口；本轮未启动。

## 图标重叠修复（2026-10-13）

用户查验发现箭头／上传图标文字覆盖标签；已移除覆盖图标字体的通用选择器并重启本地服务。实际 Chrome 回归从失败到通过，折叠／展开及 1440／720 像素截图均已查验；13 项界面交互回归通过。[修复记录](ui_icons_fix.md)、[浏览器结果](ui_icons_green_checks.json)、[修复后截图](ui_icons_green.png)、[窄窗口展开截图](ui_icons_green_expanded_720.png)。原生文件选择与下载仍未覆盖。
