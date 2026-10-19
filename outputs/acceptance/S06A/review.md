# S06-A 独立只读审查

按 requesting-code-review 技能调用独立 reviewer，审查实现、设计及测试；审查者未修改文件。

初次审查：核心公式、类别对齐、训练隔离、ddof、Ledoit–Wolf、年化、常数诊断与 S05 连接未发现重要偏差。42 项新目标测试通过。发现 1 项 Important：验收脚本直接写出会跟随既有输出符号链接，且源哈希检查仅在写出前，可能覆盖源后错误声明未改变。只在临时复制源中复现，实际源未修改。

修复：新增失败回归；全部产物先写到临时目录，统一拒绝目标符号链接、硬链接及非普通文件，通过 replace 替换，不跟随目标别名；发布前后均核对源文件哈希；成功打印在发布完成后。回归覆盖符号链接和硬链接。

最终复查：原 Important 关闭，未发现新增 Critical／Important／Minor。独立执行：

```bash
.venv/bin/python -m pytest tests/test_estimation_verification.py -q --basetemp=/tmp/s06a-review-fix-pytest
```

结果：3 passed in 24.83s。审查不代替最终完整回归，最终结果见 full_test_checks.txt。
