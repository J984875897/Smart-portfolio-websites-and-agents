# Task 1 审查

初审 Important：build_local_returns 数学失败被覆盖成 valid；重复 DataFrame 列被 pandas 静默丢弃。
修复：保留计算器失败状态与 reason，转换前拒绝非唯一列；RED 2 failed/33 passed → GREEN 35 passed。
独立复审：Spec compliant；Task quality Approved；无 Critical/Important。
Minor：exchange_calendars 4.13.2 的 XHKG 构建触发两个 NumPy generic timedelta 弃用提示，跟踪依赖兼容性，未全局隐藏警告。
