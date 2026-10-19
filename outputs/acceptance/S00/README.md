# S00 开发基线与最小可复现样例

日期：2026-10-12（Asia/Hong_Kong）。状态：**通过（开发验收，供小组查验）**。

## 输入与交付

固定合成 HKD 价格 `[100, 110, 120]`，初始资金 1,000 HKD，第一期买入并持有，无交易费和滑点，允许小数单位。无真实交易日期、分红或汇率换算。该样例用于环境验证。

交付包括项目打包配置、精确版本依赖快照、离线计算入口、14 项检查、政策草案和运行说明。Python 实际路径指向项目 `.venv`；完整环境信息见 [environment.txt](environment.txt)。

## 如何查验

在项目根目录运行：

```bash
.venv/bin/python -m portfolio.demo
.venv/bin/python -m pytest tests/test_smoke.py -q
.venv/bin/python -m pip check
```

打开 [smoke_result.csv](smoke_result.csv)，核对价值为 1,000／1,100／1,200 HKD。累计收益为 0／0.10／0.20；每期收益为 0／0.10／0.090909…。最后一期每期收益与累计收益的分母不同。

| 查验项 | 独立预期 | 实际结果／证据 |
| --- | --- | --- |
| 标准样例 | 1,000÷100=10 单位；10×120=1,200；累计收益 20% | CSV 和自动检查一致 |
| 亏损与小数单位 | 资金 100、价格 80→100→60；持有 1.25 单位，期末 75，累计收益 −25% | 自动检查通过 |
| 无效价格 | 空列表、单个观察、0、负数、NaN、无穷、多维输入均拒绝 | 7 项检查通过，抛出 ValueError |
| 无效资金 | 0、负数、NaN、无穷均拒绝 | 4 项检查通过，抛出 ValueError |
| 重复导出及安装入口 | 移除 PYTHONPATH 后运行两次，两份 CSV 字节一致 | 自动检查通过 |
| 依赖完整性 | pip check 无冲突 | 项目环境、新环境均通过 |
| 从空环境复现 | 锁定版本一致，14 项检查通过，CSV 与项目环境字节一致 | 77 个版本一致；14/14 通过；CSV 一致 |

当前项目环境最终运行记录见 [checks.txt](checks.txt)。最终新环境记录见 [fresh_environment_checks.txt](fresh_environment_checks.txt)，完整依赖安装过程见 [rebuild_checks.txt](rebuild_checks.txt)。

两套环境生成的 CSV SHA-256 均为 `d0a0e817ed5e38fb065604c6009416046d0a059dfc11ef75eed78c4322d04dda`。

## 验证中发现并处理的问题

先写检查时，样例模块尚不存在，14 项检查按预期失败；记录见 [red_checks.txt](red_checks.txt)。实现后，初版检查通过，但直接运行安装入口失败。

根因是当前 macOS 环境对开发安装的 `.pth` 文件设置了 `UF_HIDDEN`；Python 3.14 的 `site.addpackage` 会跳过该文件。源码路径设置掩盖了这个问题。现已从命令行测试中移除 `PYTHONPATH`，保留失败记录 [entrypoint_red_checks.txt](entrypoint_red_checks.txt)，并改为标准包安装。清除隐藏标记的尝试未在后续独立调用中持续生效，最终方案依靠标准安装。

`rebuild_checks.txt` 还保留早期开发安装及复核过程；其早期 CSV 比较在项目 CSV 尚未生成时未能完成。最终结论以 `checks.txt` 和 `fresh_environment_checks.txt` 为准。

## 适用范围与后续条件

- 本机 Python 3.14.6／macOS arm64 为当前验证范围；跨系统兼容性需另验。
- S00 没有验证行情下载、完整候选池、收益风险模型、优化、回测或界面。
- [政策草案](../../../configs/research_policy.yaml) 的主案例决策仍为空；空值表示待定。真实主案例前须落实投资者、目标、持有期、资产范围、个股／做空政策和基准。
- 1 项合成资产不属于正式基金，不适用正式 20–100 项和候选池比例验收；规则将在 S05 实施。
- 下一验收单元为 S01：美港产品、FX 和因子来源的小样本可行性。
