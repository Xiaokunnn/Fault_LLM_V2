# 定向新增来源纳入记录 v3

冻结日期：2026-07-26  
对应划分：`marine_pump_document_split_v3`

## 选择依据和偏差披露

326页大候选池完成后，严格Silver覆盖仅有水力堵塞通过。泵—电机不对中、电机电气驱动、空气侵入或失去自吸、干运转或维护引入故障，以及管路/阀件检查维护仍存在证据角色或独立来源缺口。MP017和MP018因此属于观察缺口后的构建集补充，不是预先冻结的盲测来源，也不能用于宣称无偏泛化性能。

## MP017：Gorman-Rupp

- 文档：Self-Priming Centrifugal Pumps Installation and Operation Manual OM-04760
- 官方URL：https://assets.grpumps.com/manuals/OM-04760.pdf
- 本地文件：`data/source_docs/marine_pump/raw/Gorman_Rupp_Self_Priming_OM_04760.pdf`
- PDF页数：21
- 字节数：262936
- SHA256：`C297530EBA7B1FB070E603DDEA58F884EC48861A988CF3F11A2416D865C5403B`
- 来源家族：`GORMAN_RUPP`
- 数据划分：`build_train`
- 主要用途：自吸和空气泄漏、泵—动力源对中、三相电机旋向、吸排管路及空气释放阀检查维护。
- 适用范围：自吸离心泵；不得自动推广到结构差异明显的泵型。

已视觉核验物理页13–15。页面为清晰双栏或图文布局，明确包含空气释放阀安装、泵与动力源对中和电气连接说明。后续解析必须按阅读顺序保留栏位，禁止左右栏拼接成伪句子。

## MP018：Patterson Pump Company

- 文档：Non-Clog Pump Operation and Maintenance Manual
- 官方URL：https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf
- 本地文件：`data/source_docs/marine_pump/raw/Patterson_Non_Clog_Pump_OM.pdf`
- PDF页数：30
- 字节数：479650
- SHA256：`27A4E082135006AEAFCF68297E619960A8BB899DCCD05B81EC59DD8F02CAA6D9`
- 来源家族：`PATTERSON_PUMP`
- 数据划分：`build_train`
- 主要用途：不对中症状与检查、电机低压/旋向/驱动过载、泵未灌注与吸入管进气、阀门和管路状态、维护和部件检查。
- 适用范围：非堵塞离心泵；跨对象使用时只保留离心泵组通用机理和动作。

已视觉核验物理页24–27。物理页27“Locating Operating Difficulties”以症状标题和原因列表组织，可作为E1连续条目抽取；不得把相邻列表项跨行拼接为单条证据。

## MP019：ABB

- 文档：Manual for Low Voltage Motors
- 官方URL：https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf
- 本地文件：`data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf`
- PDF页数：136；字节数：1485741
- SHA256：`EA9AB6352EAE9A994FFE8C9C34F0D8DC9EE4AC537874557D17796B4701731861`
- 来源家族：`ABB`
- 主要用途：物理页19–20的电机故障—原因—处理表，覆盖无法启动、缺相、过载、低电压和开路。
- 范围限制：只使用可迁移到泵驱动电机的英文证据；同一内容的多语言重复页不得重复计数。

## MP020：Cornell Pump

- 文档：Installation and Care of Cornell General Purpose Pumps
- 官方URL：https://www.cornellpump.com/site/wp-content/uploads/2023/12/Installation-and-Care.pdf
- 本地文件：`data/source_docs/marine_pump/raw/Cornell_General_Purpose_Pumps_Installation_Care.pdf`
- PDF页数：28；字节数：3699392
- SHA256：`5C6A4F621596B298E52CD2957C2C15BAC31D953D2B401BCBB3BE762C9A2000C4`
- 来源家族：`INDICOR__CORNELL_PUMP`
- 主要用途：对中、未灌泵、吸入空气泄漏、管阀检查、驱动过载、电机故障和纠正措施。
- 范围限制：通用离心泵，不自动声明船舶工况特异性。

已视觉核验物理页20–22和26。物理页26为清晰的三列表格，但每一原因—措施必须保持同行，禁止跨行组合。

## MP021：Viking Pump

- 文档：Technical Service Manual TSM 1600
- 官方URL：https://www.vikingpump.com/sites/default/files/2025-09/Technical_Service_Manual__1600_0.pdf
- 本地文件：`data/source_docs/marine_pump/raw/Viking_Pump_TSM_1600.pdf`
- PDF页数：20；字节数：2234609
- SHA256：`5B41CAD880F474C680651E299EE32FDE3958587BE57EBE5426FA6B7389BE5162`
- 来源家族：`IDEX__VIKING_PUMP`
- 主要用途：吸入管空气泄漏、失去自吸、干运转、阀和管路检查以及错误冲洗引入损伤。
- 范围限制：回转容积泵。只有吸入管路和操作层面的通用关系可跨泵型迁移。

已视觉核验物理页16–17，页面明确将真空表读数、吸入空气泄漏、泵未灌注和干运转联系起来。

## 完整性结论

- 五份PDF均由发布者官方域名公开提供，已核验PDF文件头、页数、字节数和SHA256。
- 五个来源家族均不同于既有构建来源、开发集Grundfos和保留测试集Sulzer/MAIB。
- 所有自动抽取、关系规范化和模型复审结果只能称为Silver。
- 新增来源不自动补足覆盖门槛；只有带页码、连续原文、来源URL、适用范围并通过严格校验的证据才能计数。
