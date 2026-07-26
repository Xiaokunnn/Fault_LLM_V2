# 独立来源文档纳入记录 v2

冻结日期：2026-07-25  
对应划分：`marine_pump_document_split_v2`

## 纳入原因

构建集原有来源家族只有ABS与DESMI。试抽取在检查/维护证据上为零，且叶轮或耐磨件损坏缺少第二来源族的候选页面。为避免继续增加同一厂商文档却无法提高来源独立性，正式定向抽取前新增两个独立发布者来源。

## MP015：SPX FLOW / Johnson Pump

- 文档：FreFlow Horizontal Centrifugal Pump Instruction Manual
- 官方URL：https://www.spxflow.com/assets/original/johnson-pump-im-fre-gb.pdf
- 本地文件：`data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf`
- PDF页数：113
- 字节数：4769535
- SHA256：`D8C1C2EF24CF96EB8063884F7C50837A0B0B99DFF843FD0C98B232A6C30CE392`
- 下载时间（Asia/Shanghai）：2026-07-25 17:53:44 +08:00
- 来源家族：`SPX_FLOW__JOHNSON_PUMP`
- 数据划分：`build_train`
- 主要用途：维护、噪声/汽蚀、故障表现、可能原因、叶轮/耐磨件、密封、轴承、不对中和电机证据。
- 适用范围：水平自吸离心泵。通用机理可作为泵系补证，但不得自动声明船舶现场特异性。

已视觉核验PDF物理页30–32（印刷页28–30）。其中Table 4通过数字结构键引用后续Table 5；该跨页编号连接不是普通连续E1/E2，也不是同一视觉表格行。只有在保存表号、行号/编号键、两侧页码和原文，并通过专门结构键连接校验及人工复核后，才可升级为Silver候选；默认状态为待复核，不得直接补足覆盖门槛。

## MP016：Xylem / Jabsco

- 文档：Engine Cooling Flexible Impeller Pump Installation and Operation Manual
- 官方URL：https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf
- 本地文件：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`
- PDF页数：52
- 字节数：8142543
- SHA256：`F16031116867B123A662D4363DCCAF28466AFEA06D291BEFBA710FA9ADDC74B4`
- 下载时间（Asia/Shanghai）：2026-07-25 17:53:53 +08:00
- 来源家族：`XYLEM__JABSCO`
- 数据划分：`build_train`
- 主要用途：船用发动机冷却泵的汽蚀、干运转、密封与叶轮损伤、气密性、对中以及周期检查维护。
- 适用范围：`pump_type=flexible_impeller_pump`，`service=marine_engine_cooling`。柔性叶轮相关机理不得无条件推广至离心泵。

已视觉核验PDF物理页4–5。后续抽取必须把上述`pump_type`和`service`范围写入每条候选记录；缺失范围字段的候选不得进入Silver层。

## 完整性和隔离结论

- 两份文件均来自发布者官方域名并完成页数、字节数和SHA256登记。
- 两个来源家族均未出现在开发集Grundfos或保留测试集Sulzer/MAIB中。
- 新文档是在观察构建集缺口后定向选择，因此只进入构建集，不被包装为独立盲测资料。
- 新增文档只扩大“可抽取证据候选范围”，不代表任何故障类别已经通过正式三元组覆盖门槛。
