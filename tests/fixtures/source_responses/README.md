# S01 模拟响应

这些小文件是手工构造的测试输入，**不是真实行情，也不是在线验证证据**。Yahoo 样例含分红和拆股；French 样例含年度区块和缺失哨兵；HKMA 样例以倒序日期检查排序。

真实响应存放在 `outputs/acceptance/S01/snapshots/`，通过 manifest 的 SHA-256 核验；不在测试中实时下载，也不提交认证 cookie 或 API key。
