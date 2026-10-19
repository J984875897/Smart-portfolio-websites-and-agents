# S04-B：French 因子与 HKMA 汇率下载

用户已批准分步开发流程，并在 S04-A 交付后要求进行下一步。本设计落实流程中已约定的 S04-B，不增加选品、回归或回测功能。

## 范围与选择

采用独立来源适配器及独立“因子与官方汇率”查验页，复用现有快照的原始字节、哈希校验、原子发布和离线读取约定。相比把不同表强塞进 Yahoo 产品导入格式，这样能保留因子／汇率身份；相比另建第二套缓存框架，继续使用 snapshots 的路径及完整性检查更容易维护。现有 Yahoo schema 1 和页面保持兼容；新来源使用 schema 2，默认单独存储于 data/reference_downloads。

固定五个数据集：US_FF3、US_FF5、AP_EX_JP_FF3、AP_EX_JP_FF5、HKMA_USDHKD。免费无 key，只有用户明确开始下载时联网；不引入付费 API。French 全量 ZIP 每个文件一次请求，保留 ZIP 及解出的原始 CSV，月度小数表只取请求月份。FF3／FF5 的 SMB 分开，地区代理不是香港专属，USD RF 不是港币现金代理。HKMA 使用官方 er-eeri-daily，usd 为 HKD per USD，不替换为 Yahoo。HKAB HIBOR 不在本步。

## 日期、分页与质量

统一请求区间为月初 YYYY-MM-DD（含）至月初（不含），默认 2025-01-01 至 2026-01-01。French 月度块复用 S01 解析口径；百分数除以 100，-99.99／-999 转缺失，不混入年度块，模型列精确匹配。要求请求月份齐全、数值有限才成功。

HKMA 参数 choose=end_of_day、from=start、to=end-1 日、fields=end_of_day,usd、sortby=end_of_day、sortorder=asc、offset、pagesize。默认 pagesize=1000，max_pages=20（允许 1–100），offset 按实际返回行数递增；短页／空页才结束，满页到上限为 partial。逐页保留原始响应。拒绝跨页重复、顺序倒退、越界和无效日期／汇率；可解析数据缺失保留诊断。覆盖只检查每个请求月份存在真实观察，并披露首末观察日及分页是否结束，**不认证逐日交易日历完整性**。datasize 仅作响应信息，不推断为全结果总数。

## 版本与失败

每次尝试新 run_id，保存来源、固定请求参数、UTC 下载时间、适配器及客户端版本、每项状态、原始文件哈希和数据表。原始响应在解析前保存，包括非 200 响应。成功后原子发布完整快照；失败尝试也形成独立记录，但不能替换当前成功缓存。取消在请求前／返回后检查；界面支持开始前取消，不承诺中途打断同步请求。超时、TLS、429、HTTP、格式变化、分页上限、覆盖不足分别固定原因代码，不记录异常原文或凭据。

缓存读取及每次导出校验全部文件；禁止路径穿越、符号链接、未列出的或无引用文件。成功数据须有原始证据和派生表；partial 表仅诊断，不进入正式输入。新历史修订保存新版本，旧版可离线重读。页面导出表、清单、逐项日志及原始证据，不自动保存到 DataBundle，不将日线冒充 S03 月度认证。

## 验收

先完成核心离线失败检查，再接页面，再真实请求四份 French 和一个月／年度 HKMA 小样本。HKMA 此环境预检仍是 TLS 中断，若正式请求仍失败，如实标 unavailable，分页和恢复仅记录为模拟验证，不能写“官方在线路径已打通”。核对至少一行原百分数／小数、不同模型 SMB、实际覆盖、哈希、离线重读、旧版保留和页面预览／取消不联网。运行受影响检查及全套回归，提供 outputs/acceptance/S04B/README.md 和可操作界面。

官方核对（2026-10-16）：[French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)、[地区因子](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html)、[HKMA 字段](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily/)、[HKMA 分页与区间参数](https://apidocs.hkma.gov.hk/documentation/)。
