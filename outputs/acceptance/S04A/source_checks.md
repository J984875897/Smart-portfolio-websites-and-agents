# S04-A 来源预检（2026-10-16）

- 本机 yfinance 1.7.0，curl_cffi 0.16.3；未增加依赖。先 import yfinance 可完成本机 curl 动态库初始化，单独 import curl_cffi 曾报 CoreFoundation 符号缺失。最终 provider 必须包含初始化顺序；不把此异常当网络错误。
- https://github.com/ranaroussi/yfinance 与 https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html 已经官方网页核对。本轮使用 Yahoo 公共 chart 原始响应，未调用 history，因此不会把输出冒称为 yfinance history 核验结果。
- 预检：query1.finance.yahoo.com/v8/finance/chart/SPY，interval=1d，events=div,splits,capitalGains，2025-01-01（含）至 2025-02-01（不含）；只读公开请求，HTTP200、3307字节、20条时间戳；响应身份SPY。此为预检，完整原始响应由最终小样本下载另行保存。
- 沙盒内最初 DNS 失败；授权网络执行后成功。客户端 TLS 认证未关闭，无 key 或账户。
- 默认页面不联网；付费、需要 key 的来源不接入。本轮不重试 HKMA，不把 S01 的 TLS 失败写为已修复。

## 正式真实小样本（与预检分开）

初次 run `20261016T032413288256Z-59063f7bab694be2b37f76b2ec4f1b51`：SPY transport_error（无响应体），2800.HK 19行、HKD=X 22行，后两者字段检查通过。整个批次保持部分成功；online_run.json 的 all_source_checks_success=false，验收命令相应返回1。

之后明确对 SPY 单独发起新更新，run `20261016T032452138649Z-fcda073218944f5fab7663e1add7e088`，成功20行。没有自动重试或改写初次run；见 online_recovery.json。三个实际成功数据的 JSON价格序列与派生CSV直接比较一致，时间戳按响应市场时区取日期，窗口内缺Close均为0。此比较不证明逐交易日覆盖完整。

SPY恢复版本离线重放命令返回0；初次混合版本离线重放再次保留SPY失败，返回1（表示来源并非全部成功，非字节完整性失败），见 mixed_replay/offline_replay.json。运行环境包版本另存 runtime_versions.json；run created_utc 是尝试开始时间，不是假定历史 available_at。
