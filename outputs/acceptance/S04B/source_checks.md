# S04-B 官方资料与在线核验

2026-10-16 已阅读 French Data Library、developed markets FF5 说明、HKMA 日汇率字段、Swagger 及通用参数文档。

- [French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)：四份月度 CSV ZIP 为公开文件；美国自 2025 年发布使用 CRSP CIZ 口径，下载时版本可能修订历史。
- [French 地区 FF5](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html)：USD、非对数收益；亚太除日本为地区代理。原始说明文件完整保留，不能将 USD RF 当作 HKD 现金收益。
- [HKMA 字段](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily/)：usd 单位 HKD per unit of foreign currency；API 为公开 er-eeri-daily。
- [HKMA 参数](https://apidocs.hkma.gov.hk/documentation/)：pagesize 最大 1000，offset 为跳过行数，choose/from/to 为含两端区间；对外统一 end_exclusive 后转 to=end-1日；按日期升序、短页终止。datasize 文档为返回行数，不将其当作全历史总数。

预检：请求 2025-01-01 至 2025-01-31、page_size=5、offset=0，curl_cffi TLS 错误码 35，未取得 HTTP 正文。未关闭 TLS 验证，未替换 Yahoo，未购买服务。此为独立预检，不是正式已缓存下载；正式验收状态以 online_run.json 为准。

正式批次：20261016T122003876246Z-5ad84dbff22343d99fe0fe73ee5d800f，UTC 创建 2026-10-16T12:20:03.876246+00:00，请求范围 2025 全年。四份 French 取得原始 ZIP 与 CSV，均各 12 月，共 240 个数值逐值对照通过；HKMA 未返回正文，原清单 reason=transport_error。离线复算 JSON 与在线相同。CLI 在线及离线退出码 1 表示来源未全成功，snapshot_integrity_verified=true。

本次保存的适配器版本 reference-v1；独立审查后未来写入 reference-v2，增加单独 tls_error 分类及 UTC 检查。没有改写原快照，没有为获得全成功而重复请求。HKMA 分页和失败恢复仍仅为模拟验证。
