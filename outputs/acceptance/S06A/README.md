# S06-A 收益与协方差：验收入口

本步交付可离线复算的计算核心，以及 S05 资格到估计的连接。工作台页面尚未接入；相关性、分散化、风险贡献将在 B 实现，页面在 C 实现。无成员选择、权重优化、utility 或因子回归。

## 先看三个文件

1. [手算收益对照](hand_calculation.csv)：A、B、C 的收缩年化均值分别 30%、42%、12%，与 expected 列比较。这是三个月的人工数学案例，不是投资预测。
2. [样本月协方差](sample_covariance_month.csv) 与 [独立手算期望](expected_sample_covariance_month.csv)：A、B 方差及彼此协方差 0.0001；与 C 的协方差 0.00005。另有 [收缩月协方差](shrunk_covariance_month.csv) 和月／年化对照。
3. [估计诊断](estimation_diagnostics.json)：hand 是手算案例；high_dimensional 是独立随机 60 月×100 资产；qualified_constant 是原有数量演示；qualified_nonconstant 是从原始人工表重新准备并筛选的非恒定案例。

收益以小数表示，0.30＝30%；协方差是收益小数的平方。年化算术均值与协方差乘 12，不是 CAGR。样本协方差分母 T−1；Ledoit–Wolf 收缩所用经验协方差分母 T，目标为平均经验方差乘单位矩阵，诊断保留系数、版本与分母。两种波动分别标记，不互相替代。

## 重要边界

- 原来 SYNTH100 的各月收益恒定：数量检查可以通过，但风险估计标记退化、不可直接供优化使用。零历史波动不代表真实资产无风险；混合样本中常数资产也可能被收缩模型赋予正方差。
- [合格非恒定人工结果](qualified_nonconstant_summary.csv) 有 100 项、两个类别；[来源及资格证据](qualified_nonconstant_evidence.json) 明确记录人工声明、当前候选回顾研究模式与历史认证未完成。
- N99 按原有 30% 规则阻止。真实日线仍 N0，详见 [真实排除表](real_blocked_audit.csv)；没有修改频率标签或绕过质量规则。
- [汇总](summary.json) 包含源文件哈希；源文件保持不变。`usable_for_optimization` 仅说明数值条件，不意味着真实数据、数量、投资政策或最终组合已通过。
- 100 资产／60 月的样本协方差奇异，诊断展示秩与最小特征值；不通过默默修改特征值让错误矩阵通过。

## 自己复算

在项目根目录执行：

```bash
.venv/bin/python scripts/verify_estimation.py
.venv/bin/python -m pytest tests/test_moments.py tests/test_estimation_input.py tests/test_estimation_verification.py -q
```

脚本只读取本地资料，不下载；默认产物写入本目录。自定义 `--output` 不得与 `--real-bundle` 输入目录重叠。所有人工资料标为 SYNTH；真实源数据只有阻止诊断，不冒充真实投资结论。

开发证据：[估计测试首次失败](core_red.txt)、[接入首次失败](input_red.txt)、[验收脚本首次失败](verification_red.txt)、[开发前基线](baseline_tests.txt)。输出别名问题先由[回归测试复现](alias_red.txt)，随后改为临时目录写出、逐文件拒绝别名、原子替换和发布后复核源哈希。最终回归见 [full_test_checks.txt](full_test_checks.txt)，依赖检查见 [dependency_checks.txt](dependency_checks.txt)。独立审查结论另见 review.md。

最终结果：**43项新增检查，完整回归637 passed、2条原有日历依赖弃用提示**（132.68秒）。[独立审查](review.md)发现的1项Important已修复并复查关闭。下一步仅B相关性与基础风险。
