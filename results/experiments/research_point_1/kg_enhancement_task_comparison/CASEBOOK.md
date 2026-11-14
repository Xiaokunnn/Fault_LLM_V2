# 五类知识增强任务逐案证据册

66个不同机会ID，含固定主样本和单列补充对照。部分案例共享原文，不能当66个独立事实。
当前AI非盲源文审查；不是人工Gold或独立模型评审。原始完整载荷见evaluation_v2/cases.jsonl。

状态针对每例明确的被审命题，不是统一准确率标签。下述源文仅供知识表示调查，不构成运行/维护授权。

## A-RAW-01565

原文支持液压锁闭报警识别故障系统，但该对象属于舵机。

样本组：A
来源判断：explicit_support；结果：continue_reject_domain；基线：partial；范围：outside

MP003 p355页眉为Steering Gears，且有navigation bridge/rudder语境。地址与类型通过不足以恢复为泵系知识。

### MP003 物理页 355

记录：MPT-ddd1404221f39f291fa4
液压锁闭报警 —indicates→ 故障系统

> visual hydraulic lock alarm, which identifies the failed system

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0355.json)

## A-RAW-03430

SA泵无/低流量且旋向错误时，从轴端看按箭头改为顺时针是相应措施。

样本组：A
来源判断：conditional_support；结果：recover_with_cause_guard；基线：partial；范围：in_scope

MP004 p11同一故障块有7种原因及对应措施。原候选只连接故障和措施；应补旋向原因、观察端及泵型，不无条件放行整块措施。

### MP004 物理页 11

记录：MPT-c98b9441b43b732aed72
泵无流量或流量过低 —mitigated_by→ 从轴端看改为顺时针旋转（按箭头方向）

> The pump has no or
> too low capacity
> --- CELL ---
> Change direction of rotation
> to clockwise when viewed
> from shaft end (the direction
> of the arrow)
> Clean or replace
> Clean the pump
> Find the leakage, repair the
> fault, non-return valve not
> submerged
> Check data sheet Q/H curve
> and NPSH or contact DESMI
> As 5
> Fit smaller V-belt pulley on
> pump. Change RPM of
> electric motor

[原始文档来源](https://www.desmi.com/media/4num3fbn/t1345uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP004_p0011.json)

## A-RAW-07936

LKH Prime装配中安装58号放气螺钉并按所属型号扭矩拧紧。

样本组：A
来源判断：conditional_support；结果：recover_with_model_parameter_guard；基线：partial；范围：in_scope

MP022 p34 PDF中Prime10/20共用20Nm，40为40Nm。引句只说see table below；地址和核心元组匹配不能完成参数绑定。

### MP022 物理页 34

记录：MPT-6326068eb54b6cd382f7
放气螺钉 —maintained_by→ 安装放气螺钉并用扳手拧紧

> 4. Fit air screw (58) and tighten with a spanner (Torque: see table        
>          below)

[原始文档来源](https://www.alfalaval.com/globalassets/documents/products/fluid-handling/pumps/centrifugal-pumps/lkh-prime/lkh-prime-pump-instruction-manual.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP022_p0034.json)

## A-RAW-04371

NSL300-418-12组合泵备件表包括后盖。

样本组：A
来源判断：explicit_support；结果：structural_membership_candidate；基线：partial；范围：in_scope

MP005 p131表头型号和18 Rear cover可回读；这是备件成员关系，未证明精确空间位置，原located_in的使用语义仍需明确。

### MP005 物理页 131

记录：MPT-96992b7ca23700808115
后盖 —located_in→ NSL300-418-12组合泵

> Spare parts list NSL300-418 -12 combination                       
>                                                                                   
>                                                                                   
>         Pos. No Description              Pos. No Description                      
>           1     Pump casing                58    Pipe                             
>                                                                                   
>           2     Pipe plug                  59    Hexagon nipple                   
>           3     Pipe plug                  61    Hexagon nipple                   
>                                                                                   
>           4     Sealing ring               64    Set screw                        
>           5     Impeller                   71    Set screw                        
>                                                                                   
>           6     Nut                        73    Pointed screw                    
>           7     Spring washer              75    INSEX-screw                      
>                                                       

上文为显示节选，完整原文载荷未截断，保留于逐案JSONL。

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0131.json)

## A-RAW-04370

NSL300-418-12组合泵备件表包括4号密封环。

样本组：A
来源判断：explicit_support；结果：structural_membership_candidate；基线：partial；范围：in_scope

与上一项同页，不是独立来源。零件号4和型号可定位，但不能与同手册其他型号或27号密封环直接合并。

### MP005 物理页 131

记录：MPT-2926ef5986c500acc821
密封环 —located_in→ NSL300-418-12组合泵

> Spare parts list NSL300-418 -12 combination                       
>                                                                                   
>                                                                                   
>         Pos. No Description              Pos. No Description                      
>           1     Pump casing                58    Pipe                             
>                                                                                   
>           2     Pipe plug                  59    Hexagon nipple                   
>           3     Pipe plug                  61    Hexagon nipple                   
>                                                                                   
>           4     Sealing ring

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0131.json)

## A-RAW-01670

原文要求用连续油液磨粒监测等方式监测吊舱轴承劣化。

样本组：A
来源判断：explicit_support；结果：continue_reject_domain；基线：partial；范围：outside

MP003 p395明确是pod shaft bearing和machinery control station，不能未经迁移验证恢复为泵轴承操作要求。

### MP003 物理页 395

记录：MPT-9d9e0dcf4c8b1e491720
吊舱轴轴承劣化 —inspected_by→ 连续油液磨粒监测系统

> Permanent means of continuous monitoring of shaft system vibration, or alternatively, a
>                  continuous oil-debris monitoring system to detect the passage of metallic particles in the bearing
>                  lubricating oil lines is to be provided at the machinery control station(s) in order to detect early
>                  sign of pod shaft bearing deterioration.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0395.json)

## A-RAW-06467

转子断条/松动可造成电机达不到额定转速，须先核对已有同义知识。

样本组：A
来源判断：explicit_support；结果：semantic_duplicate_not_new_fact；基线：partial；范围：in_scope

法语MP019 p55与当前图p19的转子断条或转子松动—电机达不到额定转速对应。核心字串不同；词汇检索给出正确首候选，但没有完成语义等价判定。

### MP019 物理页 55

记录：MPT-5e175b4b80b845a27361
转子导条开裂或转子松动 —causes→ 电机无法达到额定转速

> Le moteur est
> incapable de
> parvenir à la
> vitesse nominale
> --- CELL ---
> Barres de rotor fissurées ou rotor
> desserré

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0055.json)

## A-RAW-07663

Viking泵吸入口真空表高读数可指示吸入管径过小这一可能原因。

样本组：A
来源判断：conditional_support；结果：recover_with_gauge_port_context；基线：partial；范围：in_scope

MP021 p16原文列出High reading的多个可能原因。原引句带人工省略号，须重建表头/列表项原生证据并保留吸入口、可能性，不能将高读数唯一归因于管径。

### MP021 物理页 16

记录：MPT-01d73ecc318fc9302ce3
真空表高读数 —indicates→ 管路尺寸过小

> VACUUM GAUGE - SUCTION PORT 1. High reading would indicate: ... d. Line is too small.

[原始文档来源](https://www.vikingpump.com/sites/default/files/2025-09/Technical_Service_Manual__1600_0.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP021_p0016.json)

## A-RAW-00016

预防维护计划所列活动包括轴承更换。

样本组：A
来源判断：explicit_support；结果：continue_reject_schema；基线：resolved；范围：in_scope

MP001 p12支持活动成员关系，但原候选contains的主体/客体不满足现有Schema。类型控制可阻断，不能靠放宽准入恢复原三元组。

### MP001 物理页 12

记录：MPT-b2aa5a6775e3ab44a953
预防性维护计划 —contains→ 轴承更换

> Such schedules are generally established by the machinery manufacturer and include
>             lubrication servicing; filter, bearing and seal replacements; as well as major overhaul.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP001_p0012.json)

## A-RAW-06301

多相电机单相运行—电机振动在德语来源中也有支持。

样本组：A
来源判断：explicit_support；结果：duplicate_same_family_evidence；基线：resolved；范围：in_scope

MP019 p38与当前图p20同一核心关系，属于ABB同手册语言复述；同元组和来源族控制可避免计为新事实/独立互证。

### MP019 物理页 38

记录：MPT-844b7c76f27b9d7ce9fb
多相电机单相运行 —causes→ 电机振动

> Motorschwingungen
> --- CELL ---
> Mehrphasenmotor läuft einphasig

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0038.json)

## A-RAW-06644

机械故障—电机无法启动有西班牙语来源支持。

样本组：A
来源判断：explicit_support；结果：duplicate_same_family_evidence；基线：resolved；范围：in_scope

MP019 p73与当前图p19已有关系相同，不应因原候选被拒绝就算待新增知识。

### MP019 物理页 73

记录：MPT-873189a464b3fec945c1
机械故障 —causes→ 电机无法启动

> El motor no
> arranca
> --- CELL ---
> Avería mecánica

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0073.json)

## A-RAW-02451

尽量减少油水进入压缩空气系统的要求已有对应核心关系。

样本组：A
来源判断：explicit_support；结果：duplicate_core_with_scope_caveat；基线：resolved；范围：uncertain

MP003 p643与当前图p616对应，精确核心覆盖足以阻止重复恢复；能否迁移到泵系仍是另一问题。

### MP003 物理页 643

记录：MPT-487cb2591df19694911c
油或水进入压缩空气系统 —prevented_by→ 采取措施尽量减少油或水进入压缩空气系统

> Provisions are to be made to minimize the entry of oil or water into the
>                  compressed air system.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0643.json)

## B-EXA-60591b991e3b8f6a16a26910

皮带拉力过大—减小张力应保留原表Hot bearings故障上下文。

样本组：B
来源判断：explicit_support；结果：text_only；基线：resolved；范围：in_scope

MP019 p20的同一原因/措施行r026与故障合并组g025可直接回读。此例是原生行/组合并工程可以处理的，不作为复杂绑定难例。

### MP019 物理页 20

Assertion：EXA-60591b991e3b8f6a16a26910
Claim：EXC-6da3b0e1bc3e5eca7fbc18c8
记录：MPT-04e92bf24a8d95e90b13
皮带拉力过大 —mitigated_by→ 减小皮带张力

> Excessive belt pull
> --- CELL ---
> Decrease belt tension.

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0020.json)

## B-EXA-57e178a68ffd532ac0356bbc

当前O型圈损坏—更换记录已保存泄漏故障、原因和措施的原生角色结构。

样本组：B, B_supplement
来源判断：explicit_support；结果：correctly_structured；基线：resolved；范围：in_scope

MP007 p17的conditions_source三角色及原生单元逐一匹配，PDF一致。不能因正文没有if就认定缺条件，也不重复新增。

### MP007 物理页 17

Assertion：EXA-57e178a68ffd532ac0356bbc
Claim：EXC-ecb759b7c66ac4e350e6922b
记录：EXP-7ed8a3d6dda3045741e30175
o型圈损坏 —mitigated_by→ 更换o型圈

> The O-ring is damaged
> --- CELL ---
> Replace the O-ring

[原始文档来源](https://www.desmi.com/media/c35h1n0d/t1536uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP007_p0017.json)

## B-EXA-23fdf521028f4667b3c752a5

过载—电机堵转的现有原因/故障绑定符合原表角色。

样本组：B
来源判断：explicit_support；结果：correctly_structured_for_local_relation；基线：resolved；范围：in_scope

MP019 p19的Overload与Motor stalls通过合并故障组对应；已有类型方向和原生单元可表达该局部因果，不要求额外制造工况。

### MP019 物理页 19

Assertion：EXA-23fdf521028f4667b3c752a5
Claim：EXC-8a76f2d2f67e04e9bb82da7b
记录：MPT-a83846643071df23524f
过载 —causes→ 电机堵转

> Motor stalls
> --- CELL ---
> Overload

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0019.json)

## B-EXA-5672baf4a29e34a80aa14b37

高液位报警的安装是所引防溢油要求，应保存requirement模态。

样本组：B
来源判断：explicit_support；结果：text_only；基线：resolved；范围：in_scope

MP003 p596的is to be为单一要求；强版子句控制保留完整高液位告警对象。此例不需要新模型。

### MP003 物理页 596

Assertion：EXA-5672baf4a29e34a80aa14b37
Claim：EXC-a3d7e99167fe80e3c23f4c2a
记录：MPT-770f45517bf287967046
溢油 —prevented_by→ 安装高液位报警

> To prevent spillage, an alarm is to be fitted to warn of the level
>                  reaching a predetermined high level.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0596.json)

## B-EXA-cab808554d5780ffd47d7a19

避免凝露环境安装、加热器保护和适应该环境设计不是三个无条件并列动作。

样本组：B
来源判断：conditional_support；结果：binding_incomplete；基线：partial；范围：uncertain

MP003 p986的avoid unless...or...要求绑定例外与设计选择。关键词和完整子句已找全，但未产生对象与算子嵌套结构；设备柜知识的泵系适用性也待确认。

### MP003 物理页 986

Assertion：EXA-cab808554d5780ffd47d7a19
Claim：EXC-7b7c8bf2bb54d5cd66008822
记录：MPT-f117ed6d9f822d6c8327
设备外壳内部凝露 —prevented_by→ 避免安装在易凝露位置或使用空间加热器保护或采用适应该环境的设计

> Installation of equipment in locations where ambient temperature fluctuations can lead to accumulation of
>             moisture condensation inside equipment enclosure is to be avoided unless the equipment is protected by,
>             for instance, space heaters, or such equipment is to be designed and constructed to function in this
>             environment.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0986.json)

## B-EXA-58eb77ad6563b3e08952dba4

机械接头试件应按规定拆装10次，再进行规定密性试验。

样本组：B
来源判断：explicit_support；结果：text_only；基线：partial；范围：in_scope

MP003 p521强版恢复完整句并保住4-6-2/5.9.2(e).i，但未把同一试件、重复次数、前后两个事件及引用试验条款绑定为可检验结构。不是换行问题。

### MP003 物理页 521

Assertion：EXA-58eb77ad6563b3e08952dba4
Claim：EXC-2054ebaef7569e4c05970a2e
记录：MPT-4d7b94ad70056921c74b
机械接头试件 —inspected_by→ 重复装配试验

> Repeated Assembly Test. The mechanical joint test specimen are to be dismantled
>                            and reassembled 10 times in accordance with manufacturer's instructions and
>                            then subjected to a tightness test as defined in 4-6-2/5.9.2(e).i.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0521.json)

## B-EXA-cc3beed72dfe697b268bb06f

45°C空气温度是吊舱推进装置冷却设计条件，不能当任意泵的运行条件。

样本组：B
来源判断：explicit_support；结果：binding_and_scope_problem；基线：partial；范围：outside

MP003 p391还限定maximum continuous rating和32°C海水。量值命中并未处理设计要求或配对工况，且对象不是泵系。

### MP003 物理页 391

Assertion：EXA-cc3beed72dfe697b268bb06f
Claim：EXC-3bc5fbeeea965cf90a26f5de
记录：MPT-38a2c9b13dc9674eba8a
吊舱推进装置 —operates_under→ 环境空气温度45°c

> The cooling arrangements of the pod propulsor are to consider the machinery and equipment
>                  operating at the maximum continuous rating and apply the ambient air temperature of 45°C and
>                  ambient sea water temperature of 32°C indicated in 4-1-1/7.11 and 4-1-1/9 TABLE 8.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0391.json)

## B-EXA-b189096e5da927bd26b71c7d

轴/转子齿弯曲与校直/更换的OR选择已字面保留。

样本组：B
来源判断：explicit_support；结果：text_only；基线：resolved；范围：in_scope

MP021 p17头尾内的or可直接分组，May仍是可能性，不应改成唯一原因或同时执行全部措施；此局部目标可用简单字段适配。

### MP021 物理页 17

Assertion：EXA-b189096e5da927bd26b71c7d
Claim：EXC-deb394e00be465c74bc0ad19
记录：MPT-e822b0a565c8dac80fe1
轴弯曲或转子齿弯曲 —mitigated_by→ 校直或更换

> May have a bent shaft or rotor tooth. Straighten or replace.

[原始文档来源](https://www.vikingpump.com/sites/default/files/2025-09/Technical_Service_Manual__1600_0.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP021_p0017.json)

## B-EXA-319ea694a2f79b1fb4b0fb5f

使用垫片防止泵脚应力需保留安装紧固时这一触发条件。

样本组：B
来源判断：explicit_support；结果：text_only；基线：resolved；范围：in_scope

MP005 p43强版得到完整when the installation is secured；弱版仅得到when the，已将这一失败归为排版处理缺陷而非算法难例。

### MP005 物理页 43

Assertion：EXA-319ea694a2f79b1fb4b0fb5f
Claim：EXC-0c5b8fcc6087d494d1b9d0a9
记录：MPT-2115ec706e03a3c76fa4
泵脚应力 —prevented_by→ 在泵底板与基础之间使用垫片

> Use shims between pump base plate and foundation to avoid tension in the pump foot when the
>                                                                                   
>       installation is secured.

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0043.json)

## B-EXA-ce5e84b1fe933576f22c4d3b

密封水条件不当可导致填料过早失效，应保留可能性而非必然性。

样本组：B
来源判断：explicit_support；结果：text_only；基线：resolved；范围：in_scope

MP018 p11同一主语支配一组后果，强版can子句完整包含目标结果；本例局部模态补充可简单处理。

### MP018 物理页 11

Assertion：EXA-ce5e84b1fe933576f22c4d3b
Claim：EXC-c6760b354db6c8320f8db158
记录：MPT-1df567a8e155e971db68
密封水条件不当 —causes→ 填料过早失效

> Improper seal water conditions can cause air leakage into the pump,
>                       excessive seepage out of the pump, overheating of packing and premature failure
>                       of packing and scoring of shaft sleeve.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0011.json)

## B-EXA-a16cf539e1d1c2570004426a

在管道进入轴承箱的位置施加密封材料是建议性措施。

样本组：B
来源判断：explicit_support；结果：text_only；基线：resolved；范围：in_scope

MP018 p24位置已在端点保留；should可作为单一建议模态补充，不应声称位置从未抽出。

### MP018 物理页 24

Assertion：EXA-a16cf539e1d1c2570004426a
Claim：EXC-e3cf6a2a3f24db8573d6aa43
记录：MPT-e91907a66e9de2c14b2a
水尘进入并损坏轴承 —prevented_by→ 在排水管进入轴承箱处涂抹密封胶

> a sealing material such as caulk
>        should be applied around the pipe where it enters into the bearing housing to prevent water, dust, etc.,
>        from entering and damaging the bearings

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0024.json)

## B-EXA-86924cb6b0f51ddbb2e3c555

按指定吊装方式运输避免轴封损坏，需要保持图示/运输工况引用。

样本组：B
来源判断：conditional_support；结果：text_only_with_external_figure_reference；基线：partial；范围：in_scope

MP005 p18 PDF有运输风险及as shown below，但该文字没有完整描述图示。补图引用/页接口优先，不把它直接包装成新的语义模型难题。

### MP005 物理页 18

Assertion：EXA-86924cb6b0f51ddbb2e3c555
Claim：EXC-0df9b7474e9d9d5a6c7241a6
记录：MPT-4b96187a9ad695b873c4
轴封损坏 —prevented_by→ 按图示吊装方式运输泵/泵组

> RISK OF DAMAGING TO THE SHAFT SEAL!                         
>                                                                                   
>                       Transport the pump incorrectly could cause damage to the shaft seal!
>                                                                                   
>           To transport the pump / pump set from the lifting, tackle as shown below.

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0018.json)

## C-ee29bb1c039cde6095635ac7

泵和电机轴/泵与电机轴可作为概念级命名变体关联，同时保留各自来源。

样本组：C
来源判断：explicit_support；结果：cleanable_alias；基线：resolved；范围：in_scope

MP015 p22/p34同类型源语表述与同手册上下文支持名称统一，不表示同一台物理设备。

### MP015 物理页 22

Assertion：EXA-323deecff5d3fb8c87ea9a61
Claim：EXC-98df30b5a6952b492274cd94
记录：MPT-cdbc175ed7a5d7f79ba9
泵与电机轴 —inspected_by→ 检查泵与电机轴对中

> Check the alignment of pump and motor shafts and if necessary realign, see
>                          paragraph 3.4.3 "Alignment of the coupling".

[原始文档来源](https://www.spxflow.com/assets/original/johnson-pump-im-fre-gb.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP015_p0022.json)

### MP015 物理页 34

Assertion：EXA-d709c591723e51dea3ce7f18
Claim：EXC-ef1c041ed00ee274e0a9370f
记录：MPT-714e18efe8c209dcde01
泵和电机轴 —inspected_by→ 检查泵和电机轴的对中

> Check the alignment of pump and motor shaft, see paragraph 3.4.3 "Alignment of the
>                          coupling".

[原始文档来源](https://www.spxflow.com/assets/original/johnson-pump-im-fre-gb.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP015_p0034.json)

## C-8b463d83a4c034937e9f5259

两条relief-valve operation可无条件合并为同一Component实例。

样本组：C
来源判断：insufficient_evidence；结果：unresolved_referent_and_type；基线：unresolved；范围：uncertain

MP003 p343与p362分属不同设备章节，operation本身不是已定位阀实例。源语、类型和宽泛文档范围相同仍不充分。

### MP003 物理页 362

Assertion：EXA-a02e674be4868f2fd5054b78
Claim：EXC-415894f9c17e5dc474c27f3b
记录：MPT-84947a21a010c3d96270
溢流阀动作 —inspected_by→ 溢流阀动作检查

> including a
>             check of the relief valve operation in the presence of the Surveyor

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0362.json)

### MP003 物理页 343

Assertion：EXA-9d5a2f3a262a4c954b687743
Claim：EXC-dda476b1bb78abb533b796ea
记录：MPT-01a122f76457ea9117bc
安全阀动作 —inspected_by→ 验证

> Relief-valve
>             operation is to be verified.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0343.json)

## C-63488bc583a3b62120c4e7a9

轴承损坏/损坏轴承在概念层可以关联为命名变体。

样本组：C
来源判断：conditional_support；结果：cleanable_alias_with_scope_preservation；基线：resolved；范围：in_scope

同FaultMode及damage the bearing(s)支持名词化归一；必须保留泵/驱动电机和各证据范围，不能把概念相同变成工况相同。

### MP005 物理页 13

Assertion：EXA-9043620a8b40d66413c3e2ac
Claim：EXC-00d60a14759953d4a1c48667
记录：MPT-484a272c6a3059198814
轴承损坏 —prevented_by→ 遵守产品文献中规定的最大流量信息

> Observe the information on maximum flow rates specified in the product literature (to prevent
>         overheating, mechanical seal damage, cavitation damage, bearing damage, etc.).

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0013.json)

### MP005 物理页 13

Assertion：EXA-85d5a13eae67b0c346cd36a7
Claim：EXC-7b4971af0aef074057ab5083
记录：MPT-e62c605c9a35521c0f65
轴承损坏 —prevented_by→ 遵守产品文献中规定的最小流量信息

> Observe the information on minimum flow rates specified in the product literature (to prevent
>         overheating, bearing damage, etc.).

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0013.json)

### MP019 物理页 60

Assertion：EXA-8b4a4f67853fda975e64f9a8
Claim：EXC-2dde39f87c92525164fce54c
记录：MPT-e1fcd22160681a9896c1
静止状态下的外部振动 —causes→ 轴承损坏

> El motor no debe ser sometido a vibraciones externas en                      
>      reposo, para evitar daños en los rodamientos.

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0060.json)

### MP018 物理页 15

Assertion：EXA-c3e5430cd099a6f5050aa7b5
Claim：EXC-13d7f9f5ebd2cfc6752f20ea
记录：MPT-ae8b5a667cee094cc81c
使用错误的润滑脂或油 —causes→ 轴承损坏

> Mixing of different greases or oils and use of the wrong grease or oil
>                       will damage the bearings.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0015.json)

### MP019 物理页 53

Assertion：EXA-2ae18b28919ce4e91299db30
Claim：EXC-567c4157bf82ee5ee88d3e84
记录：MPT-a558abecabbee5b5167c
不相容润滑剂 —causes→ 损坏轴承

> Des lubrifiants non miscibles peuvent                                      
>        endommager les roulements.

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0053.json)

### MP018 物理页 21

Assertion：EXA-190607152a1106fccfbefcc9
Claim：EXC-8cdcf8c1fdf90517b11344a2
记录：MPT-a34e3835ffb2dfb8769d
未使用该程序 —causes→ 损坏轴承

> Failure to use this procedure can damage the bearing.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0021.json)

### MP019 物理页 60

Assertion：EXA-47debecdbe14f2623d80afb2
Claim：EXC-9b3fc76411c197d48e9ba736
记录：MPT-f3738eb8324c1b20a469
轴承损坏 —prevented_by→ 避免静止时承受外部振动

> El motor no debe ser sometido a vibraciones externas en                      
>      reposo, para evitar daños en los rodamientos.

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0060.json)

### MP004 物理页 12

Assertion：EXA-ba19937bb9a1d7c121f5b62a
Claim：EXC-f8aeeac94630c5a99c076c45
记录：EXP-ad1fb10b2b1669f523f4a5f6
轴承损坏 —causes→ 泵产生噪声

> The pump makes
> noise
> --- CELL ---
> 1. Cavitation in pump
> 2. Incorrect alignment
> 3. Defective bearings

[原始文档来源](https://www.desmi.com/media/4num3fbn/t1345uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP004_p0012.json)

### MP004 物理页 12

Assertion：EXA-133872741cd764d2a420b285
Claim：EXC-f17b91cb239486814efb50a9
记录：EXP-a1952d208c1598666283727d
轴承损坏 —mitigated_by→ 更换轴承

> 1. Cavitation in pump
> 2. Incorrect alignment
> 3. Defective bearings
> --- CELL ---
> Suction lift too high/ Suction
> line wrongly
> dimensioned/Liquid
> temperature too high.
> Align the pump and motor
> (see para. about alignment)
> Replace bearings

[原始文档来源](https://www.desmi.com/media/4num3fbn/t1345uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP004_p0012.json)

## C-7a7ca834969b20fa500fe6a8

只凭滤器堵塞同中文名就能忽略类型/介质直接合并全部实例。

样本组：C
来源判断：contradiction；结果：unsafe_same_name_merge_control；基线：resolved；范围：in_scope

润滑系统微生物堵塞与柔性叶轮泵冷却水滤器不同，Cause/Symptom角色也不同。类型控制可阻止无条件合并。

### MP001 物理页 66

Assertion：EXA-b0bf62c42e0599e5cf0d5cd9
Claim：EXC-aec112044897c353cd490fc9
记录：MPT-9f49aeabffd8bdb9d50f
微生物 —causes→ 滤器堵塞

> These micro-organisms can degrade the lubricant’s properties causing blocked filters
>             and increased corrosion in the equipment thereby leading to system malfunctions.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP001_p0066.json)

### MP016 物理页 47

Assertion：EXA-23c3d78b1665df7a7779a493
Claim：EXC-e9d43d01310ed8f1406cd0ef
记录：MPT-db6e3e9655fc5c74f0f0
滤器堵塞 —causes→ 汽蚀

> Si el filtro está obstruido provocará cavitación.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0047.json)

### MP016 物理页 34

Assertion：EXA-b216935a75264cb1de38ba3a
Claim：EXC-e9d43d01310ed8f1406cd0ef
记录：MPT-c74a12b163a9e2f535ad
滤器堵塞 —causes→ 汽蚀

> Een verstopt filter veroorzaakt cavitatie.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0034.json)

## C-db919e4d79eb03aa5e18dab2

只凭泄漏二字可把所有对象视为同一设备故障实例。

样本组：C
来源判断：contradiction；结果：unsafe_same_name_merge_control；基线：resolved；范围：in_scope

泵、柔性叶轮泵及半导体冷却等对象不同。同名角色/实例不可直接合并；类型约束在本目标上提供保守阻断。

### MP016 物理页 28

Assertion：EXA-56beba2bec51e6bf4f8fef0e
Claim：EXC-c601eb0eba4f8c9aa9ddabba
记录：MPT-6d1fafd0766955b4f94d
泄漏 —diagnosed_by→ 检查是否存在泄漏

> Verificare la presenza di perdite.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0028.json)

### MP005 物理页 20

Assertion：EXA-8363ab6c367824ff11d179b1
Claim：EXC-651563f5b6cba5b8f62795cb
记录：MPT-5cea97da04089cfcb74d
潮湿、污染或损坏的开口及连接件 —causes→ 泄漏

> Wet, contaminated or damaged openings and connections could cause leakage or
>                       damage to the pump!

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0020.json)

### MP016 物理页 47

Assertion：EXA-29518f15100423d3eaa6e278
Claim：EXC-216db80b4c4ebe62078e08dd
记录：MPT-7dd88748ad739e3522f6
泄漏 —diagnosed_by→ 检查泄漏

> Verifique si hay fugas.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0047.json)

### MP003 物理页 794

Assertion：EXA-7aa9389aa948b50975ac5098
Claim：EXC-e1de7a823b7a32d2ccd51e1c
记录：MPT-81d58867a689b0b99f36
泄漏 —diagnosed_by→ 泄漏检测装置

> Semiconductor assemblies with liquid cooling are to be provided with a means to detect leakage.
>                  In case of leakage, an audible and visible alarm is to be initiated locally and remotely at a
>                  continuously manned location.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0794.json)

### MP016 物理页 5

Assertion：EXA-7bb9075043c60f0da9e12680
Claim：EXC-216db80b4c4ebe62078e08dd
记录：MPT-e383bcbc959a607bcf57
泄漏 —diagnosed_by→ 检查泄漏

> Check for leaks.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0005.json)

### MP003 物理页 498

Assertion：EXA-eff48c1c835d7827600ec773
Claim：EXC-54f055dfd23039ca74154ba4
记录：MPT-4f71ff6de05809ee4747
泄漏 —mitigated_by→ 安全防护措施

> Safeguards are measures undertaken to reduce leakage possibility and limiting its consequences

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0498.json)

### MP004 物理页 8

Assertion：EXA-f11c61a4bc317c76e3c6a7a0
Claim：EXC-23b23694d705056933bfce9b
记录：MPT-34d4fb4b6c95e83723cd
泄漏 —diagnosed_by→ 通过观察泄漏孔检查

> After start, check by
>         viewing the leak hole that there are no leaks.

[原始文档来源](https://www.desmi.com/media/4num3fbn/t1345uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP004_p0008.json)

### MP003 物理页 519

Assertion：EXA-efce11310c6d5d4709c38b5c
Claim：EXC-e542e14dd56f9ab86fb60bb3
记录：MPT-27fd0fcec5ba7379e896
泄漏 —diagnosed_by→ 目视检查

> The mechanical joint is to be examined
>                            visually for sign of leakage or damage during the test.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0519.json)

### MP005 物理页 99

Assertion：EXA-ff7886588e7928f06ab3bf29
Claim：EXC-54cd52c1552a76049c29fe91
记录：MPT-ed210076622570d2f0ae
泄漏 —diagnosed_by→ 观察泄漏孔

> After start, check by viewing the leak
>                        hole that there are no leaks.

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0099.json)

## C-a58c1e302a5669bdc3b764aa

所有磨损节点均可无条件合成同一物理磨损实例。

样本组：C
来源判断：contradiction；结果：unsafe_same_name_merge_control；基线：resolved；范围：in_scope

源文涉及叶轮/耐磨环、轴承表面和一般机理，FailureMechanism/FaultMode有角色差别。不能凭名称消除来源对象。

### MP001 物理页 93

Assertion：EXA-0569ef98f77d97e4f805976f
Claim：EXC-f42ab5ba5f1f19c6d6eeb450
记录：MPT-6ea48a1c0e16b8d37ac2
磨损 —causes→ 表面不连续或裂纹

> surface discontinuities or cracks due to problems such as
>             fatigue, wear, surface shrinkage, and grinding

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP001_p0093.json)

### MP001 物理页 94

Assertion：EXA-04ec97581f652b4c4a7afdf6
Claim：EXC-64664e7bb8dcacc363341717
记录：MPT-90d4a9a6ae813b66b1b6
磨损 —causes→ 表面/近表面裂纹及不连续缺陷

> surface/near-surface cracks and discontinuities
>             caused by problems such as fatigue, wear, inclusions, laminations, heat treatment, hydrogen embrittlement,
>             seams, and corrosion

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP001_p0094.json)

### MP005 物理页 67

Assertion：EXA-b072c605c9d88fb54d2ea737
Claim：EXC-9da9d764b4cd2203382ff3f7
记录：MPT-9c7276d71a80158b9647
振动、噪声及电流输入增加 —indicates→ 磨损

> Vibrations, noise and an increased incurrent input occurring during unchanged operating
>       conditions indicate wear.

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0067.json)

### MP015 物理页 40

Assertion：EXA-fcc80945149eaac10e5de2ae
Claim：EXC-1a233aa3eb02a6607fbb900a
记录：MPT-8aa6d5aa205493ac751b
磨损 —occurs_at→ 叶轮与耐磨环之间

> For pump with a closed impeller the wear occurs between the impeller and the wear ring.

[原始文档来源](https://www.spxflow.com/assets/original/johnson-pump-im-fre-gb.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP015_p0040.json)

### MP020 物理页 24

Assertion：EXA-36518bd6067d76a7ee3cca2d
Claim：EXC-85196a2890f032d55abe9c45
记录：MPT-386215da48825c293d1f
泵送介质中的磨料 —causes→ 磨损

> Wear may be caused by abrasives in the pumpage, unsupported piping
>      loads, or other causes.

[原始文档来源](https://www.cornellpump.com/site/wp-content/uploads/2023/12/Installation-and-Care.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP020_p0024.json)

### MP018 物理页 26

Assertion：EXA-e397d396c0e1c5512d910ea8
Claim：EXC-65352cd5de14b65f2663d7f1
记录：MPT-040af521dbf72786150c
磨损 —manifests_as→ 轴承外圈内孔和外径擦伤或编织状损伤

> Wear
> --- CELL ---
> Bore and OD of outer ring of bearing galled or
> braided.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0026.json)

### MP020 物理页 24

Assertion：EXA-7425845410b7402900f99db4
Claim：EXC-2fe5773ed005ed9c9a996ac9
记录：MPT-cdaa3230515c6e565376
管道支撑不足载荷 —causes→ 磨损

> Wear may be caused by abrasives in the pumpage, unsupported piping
>      loads, or other causes.

[原始文档来源](https://www.cornellpump.com/site/wp-content/uploads/2023/12/Installation-and-Care.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP020_p0024.json)

### MP018 物理页 26

Assertion：EXA-e33b7f9a2302dcd36270b774
Claim：EXC-15dddacc2b20b79e468384d2
记录：EXP-a268a75c19c74cee8d1836f0
轴或壳体配合过松 —causes→ 磨损

> Wear
> --- CELL ---
> 1. Fit on the shaft or in housing too
> loose.
> 2. Bearing locked by dirt and
> turning of shaft or in housing.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0026.json)

### MP018 物理页 26

Assertion：EXA-0ee632670b50a45bc55506fc
Claim：EXC-b5d44aaceb0c2ebd9ba3cafc
记录：EXP-27274dcec1303576ddc0b49b
污物卡滞导致轴承在轴或壳体内转动 —causes→ 磨损

> Wear
> --- CELL ---
> 1. Fit on the shaft or in housing too
> loose.
> 2. Bearing locked by dirt and
> turning of shaft or in housing.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0026.json)

## C-25eab0e754446b1a01e86709

两条尺寸A调整可合为同一Claim家族，但执行时须保留FRES/FREM及相应支架参数。

样本组：C
来源判断：conditional_support；结果：claim_family_needs_assertion_context；基线：partial；范围：in_scope

MP015 p49 FRES表有支架1/2/3，p50 FREM表只有1/2。相同核心句不是同一无条件程序，元组/来源族匹配未绑定章节与参数表；不应据此删除Claim家族。

### MP015 物理页 49

Assertion：EXA-15628a6fd0f8d53a4e7e1685
Claim：EXC-8b4e519bc54d2ad1f894614c
记录：MPT-5292fc6a22c422d4ffba
叶轮 —maintained_by→ 调整叶轮与中间盖之间的尺寸a

> 2 Adjust the impeller to size A between the rear of the impeller and the intermediate
>                          cover.

[原始文档来源](https://www.spxflow.com/assets/original/johnson-pump-im-fre-gb.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP015_p0049.json)

### MP015 物理页 50

Assertion：EXA-a05c991e4f7da17953c38bd5
Claim：EXC-8b4e519bc54d2ad1f894614c
记录：MPT-b53acf75a9448c4532c9
叶轮 —maintained_by→ 调整叶轮与中间盖之间的尺寸a

> Adjust the impeller to size A between the rear of the impeller and the intermediate
>                          cover.

[原始文档来源](https://www.spxflow.com/assets/original/johnson-pump-im-fre-gb.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP015_p0050.json)

## C-2da504c43dc370ae54d2241f

西班牙语和荷兰语滤器堵塞—汽蚀属于同手册复述，不是独立互证。

样本组：C
来源判断：explicit_support；结果：existing_same_family_aggregation；基线：resolved；范围：in_scope

MP016 p47/p34同一来源族，当前已在同一Claim中；保持证据即可。

### MP016 物理页 47

Assertion：EXA-23c3d78b1665df7a7779a493
Claim：EXC-e9d43d01310ed8f1406cd0ef
记录：MPT-db6e3e9655fc5c74f0f0
滤器堵塞 —causes→ 汽蚀

> Si el filtro está obstruido provocará cavitación.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0047.json)

### MP016 物理页 34

Assertion：EXA-b216935a75264cb1de38ba3a
Claim：EXC-e9d43d01310ed8f1406cd0ef
记录：MPT-c74a12b163a9e2f535ad
滤器堵塞 —causes→ 汽蚀

> Een verstopt filter veroorzaakt cavitatie.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0034.json)

## C-785b0dae3388d4ff4c57bbf7

入口压力不足—汽蚀的三种语言页不构成三份独立来源。

样本组：C
来源判断：explicit_support；结果：existing_same_family_aggregation；基线：resolved；范围：in_scope

MP016 p39/p3/p20同一手册，已有正确家族聚合，不计新增关系。

### MP016 物理页 39

Assertion：EXA-3d4954bd0444d42aa6150e33
Claim：EXC-c9e30bfbaf2316d3f34e55ca
记录：MPT-cb593808d53b00478439
入口压力不足 —causes→ 汽蚀

> Otillräckligt inloppstryck kommer att få pumpen att kavitera

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0039.json)

### MP016 物理页 3

Assertion：EXA-d39f07dca276e9a7c8098167
Claim：EXC-c9e30bfbaf2316d3f34e55ca
记录：MPT-66c6afcd9247f25e5d3c
入口压力不足 —causes→ 汽蚀

> Insufficient inlet pressure will cause the pump to cavitate leading
>                              to low performance, noise and short pump life.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0003.json)

### MP016 物理页 20

Assertion：EXA-e4378601f9ab4b95955891d5
Claim：EXC-c9e30bfbaf2316d3f34e55ca
记录：MPT-7a93e603933718bbdc81
入口压力不足 —causes→ 汽蚀

> Ein unzureichender Einlassdruck verursacht Kavitationen in der
>                              Pumpe

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0020.json)

## C-68ce04fc5ff624785ec031d1

西语/英语检查泄漏是同手册中可聚合的同一局部建议。

样本组：C
来源判断：explicit_support；结果：existing_same_family_aggregation；基线：resolved；范围：in_scope

MP016 p47/p5具备相同泵型和动作。来源族去重可直接阻止伪独立支持。

### MP016 物理页 47

Assertion：EXA-29518f15100423d3eaa6e278
Claim：EXC-216db80b4c4ebe62078e08dd
记录：MPT-7dd88748ad739e3522f6
泄漏 —diagnosed_by→ 检查泄漏

> Verifique si hay fugas.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0047.json)

### MP016 物理页 5

Assertion：EXA-7bb9075043c60f0da9e12680
Claim：EXC-216db80b4c4ebe62078e08dd
记录：MPT-e383bcbc959a607bcf57
泄漏 —diagnosed_by→ 检查泄漏

> Check for leaks.

[原始文档来源](https://www.xylem.com/siteassets/brand/jabsco/resources/manual/user-guide---engine-cooling-flexible-impeller-pumps.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP016_p0005.json)

## C-2b738893cf0614960f93df09

SA与NSL泵的汽蚀—噪声可共用概念家族，但不是独立厂商证据。

样本组：C
来源判断：conditional_support；结果：existing_claim_family_keep_model_scopes；基线：resolved；范围：in_scope

MP004 p12与MP005 p61同属DESMI，模型范围已在来源元数据中区分。原生表与来源族控制足以处理本次互证目标。

### MP004 物理页 12

Assertion：EXA-17e5e9d008dca84cf32750c5
Claim：EXC-60fb4722727dde5d049917c6
记录：EXP-190e36ba6bc894c228211322
泵内汽蚀 —causes→ 泵产生噪声

> The pump makes
> noise
> --- CELL ---
> 1. Cavitation in pump
> 2. Incorrect alignment
> 3. Defective bearings

[原始文档来源](https://www.desmi.com/media/4num3fbn/t1345uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP004_p0012.json)

### MP005 物理页 61

Assertion：EXA-4b1918211d9350639f8ad3a1
Claim：EXC-60fb4722727dde5d049917c6
记录：EXP-457462fcfe3d2c31e9950224
泵内汽蚀 —causes→ 泵产生噪声

> The pump makes
> noise
> --- CELL ---
> 1. Cavitation in pump

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0061.json)

## C-3d9b8eebe09dc11cd36900eb

状态监测术语可概念关联，但不能忽略P-F间隔而合并诊断有效性断言。

样本组：C
来源判断：conditional_support；结果：role_and_condition_sensitive_alignment；基线：partial；范围：in_scope

MP001 p30给出方法定义，p31说采样间隔超过P-F时可能检不出。类型阻断不会恢复条件，词典等价也不等于有条件断言等价。

### MP001 物理页 31

Assertion：EXA-68ec95fbaaad2f49264acbf6
Claim：EXC-83a46ff81fcf17c866074aac
记录：MPT-178a6f7f78715b394659
潜在故障 —diagnosed_by→ 状态监测任务

> If a condition-monitoring task is performed on
>             intervals longer than the P-F interval, the potential failure may not be detected.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP001_p0031.json)

### MP001 物理页 30

Assertion：EXA-cfcc8cdd7cf149190383797d
Claim：EXC-c185c1180a42b7b53082fea9
记录：MPT-8790a983c921c148bd3d
潜在故障 —diagnosed_by→ 状态监测任务

> Tasks designed to detect
>             potential failure are known as condition-monitoring tasks

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP001_p0030.json)

### MP001 物理页 24

Assertion：EXA-fc21113057ce6959e120a625
Claim：EXC-ce5fd99d965df7c19fb0b5df
记录：MPT-0ee7848d73bd6706408f
由维护错误或机械退化引起的潜在设备故障 —diagnosed_by→ 状态监测任务

> condition-monitoring tasks may aid in identifying impending equipment
>             failures introduced by maintenance errors or machinery degradation

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP001_p0024.json)

## D-EXA-26ad2e25ba5d1b68e46c28b6

所引not to cause设计要求不足以支持当前观察性正causes，应阻止该正因果使用。

样本组：D
来源判断：explicit_support；结果：clear_normative_to_causal_mismatch；基线：resolved；范围：uncertain

MP003 p861规则已能识别此明确模板并建议隔离，而不是翻成物理上绝不会发生。工程可处理已知例。

### MP003 物理页 861

Assertion：EXA-26ad2e25ba5d1b68e46c28b6
Claim：EXC-394b80fdb60767e8b8a7a532
记录：MPT-378b01dee8ae2c9e563c
再生功率 —causes→ 原动机超速

> the regenerative power is not to cause
>                  over speeding of the prime mover

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0861.json)

## D-EXA-298a245da0bfbf7d58b67d18

控制信号失效—螺旋桨超速的正causes缺少所引规范支持，且对象越出泵系。

样本组：D
来源判断：explicit_support；结果：clear_normative_to_causal_and_scope_mismatch；基线：resolved；范围：outside

MP003 p864的not to cause是设计义务。规则可隔离该模板，不能据此声称现实因果被证伪。

### MP003 物理页 864

Assertion：EXA-298a245da0bfbf7d58b67d18
Claim：EXC-81ca772eee0129d32f31427e
记录：MPT-8035602d5b050a3e2add
控制信号失效 —causes→ 螺旋桨转速过度升高

> Failure of a control signal is not to cause an excessive increase in propeller speed

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0864.json)

## D-EXA-635a40aea27f56c635c90125

不得无液运行不能表达为正向运行于无液条件。

样本组：D
来源判断：explicit_support；结果：clear_prohibition_mismatch；基线：resolved；范围：in_scope

MP005 p67的Do not与正向尾条件不一致。适合明确否定准入/隔离回归，不需把单例当复杂算法贡献。

### MP005 物理页 67

Assertion：EXA-635a40aea27f56c635c90125
Claim：EXC-a5ad2169c39bf636b88d7308
记录：MPT-0927c8970e1124c5c738
泵组 —operates_under→ 无液体充注

> Do not operate the pump set without liquid fill.

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0067.json)

## D-EXA-0e3a98f3dbe8dd694efd4244

该记录已经丢失不得关阀运行超过几分钟的否定。

样本组：D
来源判断：contradiction；结果：retained_negation_false_positive；基线：resolved；范围：in_scope

MP018 p14的禁令完整在中文尾文本。初始词汇触发器有误报；强版端点否定检查可保留原记录，不能把原义保留误判成已发生语义反转。

### MP018 物理页 14

Assertion：EXA-0e3a98f3dbe8dd694efd4244
Claim：EXC-a3a633fcfdeabf1a3c086b32
记录：MPT-f18cfcbaa1e251c5d1cb
泵 —operates_under→ 不得在阀门关闭状态下运行泵超过几分钟

> CAUTION: - Do not operate pump with the valve closed for
>                  more than a few minutes.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0014.json)

## D-EXA-11bb334508fb84acd10f941c

完工螺旋桨静平衡检验不应无条件进入泵系建议。

样本组：D
来源判断：explicit_support；结果：clear_scope_mismatch；基线：resolved；范围：outside

MP003 p342明确finished propellers；设备范围词与章节足以提供保守隔离。

### MP003 物理页 342

Assertion：EXA-11bb334508fb84acd10f941c
Claim：EXC-be9b2328c85d7c4e394f644b
记录：MPT-f1412b467f7361a6d3bf
完工螺旋桨 —maintained_by→ 静平衡校正

> All finished propellers are to be statically
>             balanced in the presence of the Surveyor.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0342.json)

## D-EXA-9054fbfa7c2a3bd0ec68e896

绳索侵入导致螺旋桨缠绕不是泵系原子诊断事实。

样本组：D
来源判断：explicit_support；结果：clear_scope_mismatch；基线：resolved；范围：outside

MP003 p321因果本身有源文支持，问题在声明范围；不能改成泵叶轮缠绕。

### MP003 物理页 321

Assertion：EXA-9054fbfa7c2a3bd0ec68e896
Claim：EXC-43eaa67418f335609c07cf2c
记录：MPT-4b2d580b44453057628b
绳索侵入 —causes→ 螺旋桨缠绕

> propeller entanglement and shaft seal damage caused by line intrusion

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0321.json)

## D-EXA-a4bbc36e5a83002953037c4a

螺旋桨毂与尾轴锥面接触检验应与泵系检验范围区分。

样本组：D
来源判断：explicit_support；结果：clear_scope_mismatch；基线：resolved；范围：outside

MP003 p343明确部件对象，简单设备/章节范围检查可处理本例。

### MP003 物理页 343

Assertion：EXA-a4bbc36e5a83002953037c4a
Claim：EXC-2b6a65032870e40fea59b0e1
记录：MPT-9bae1588763e5789a796
螺旋桨毂与尾轴锥体接触面积 —inspected_by→ 验船师在场检查

> Propeller hub to tail shaft taper contact area is to be checked in the presence of a Surveyor.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0343.json)

## D-EXA-eec1327bd95144134852fb28

推进电机因螺旋桨丢失等发生超速不应直接作为泵驱动故障关系。

样本组：D
来源判断：explicit_support；结果：clear_scope_mismatch；基线：resolved；范围：outside

MP003 p867对象和原因是推进系统。标记范围比修改物理因果更合适。

### MP003 物理页 867

Assertion：EXA-eec1327bd95144134852fb28
Claim：EXC-b581e0b0432bbfbbc1c83131
记录：MPT-12061f94056b3aab0870
轻载、螺旋桨丢失等 —causes→ 推进电机过度超速

> excessive overspeeding of the propulsion motors due to light loads, loss of propeller, etc.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0867.json)

## D-EXA-a4cde51bf8b5a02f4db23da7

压气机/涡轮转子平衡要求能否直接用于泵转子。

样本组：D
来源判断：insufficient_evidence；结果：unresolved_transferability；基线：unresolved；范围：uncertain

MP003 p164的原机组要求清楚，普遍动平衡原则可能可迁移，但不能从关键词决定具体质控要求适用于泵。

### MP003 物理页 164

Assertion：EXA-a4cde51bf8b5a02f4db23da7
Claim：EXC-f0805d7cc7c4c247a45c12f9
记录：MPT-74734feaf8f8ccf62491
压气机与涡轮、轴及叶轮、整个旋转组件 —maintained_by→ 按制造商质控程序单独动平衡

> The compressor and turbine, the shaft and bladed wheels, as well as the full rotating assembly, are
>                  to be dynamically balanced individually in accordance with the manufacturer’s quality control
>                  procedure, accepted by ABS.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0164.json)

## D-EXA-9a9d132e4087f8f1d964029c

曲轴臂距差测量应与泵系部件检查隔离。

样本组：D
来源判断：explicit_support；结果：clear_scope_mismatch；基线：resolved；范围：outside

MP003 p56明确crankshaft及设计规定条件，不能当普通泵轴测量。

### MP003 物理页 56

Assertion：EXA-9a9d132e4087f8f1d964029c
Claim：EXC-1b39184a40e7179f40e5346d
记录：MPT-d4659100e3dc806a9806
曲轴臂距差 —diagnosed_by→ 在设计规定条件下测量

> The crankshaft deflections are to be
>                  measured in the specified (by designer) condition

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0056.json)

## D-EXA-a02e674be4868f2fd5054b78

可直接把溢流阀动作这一Component改写为某个唯一确定的阀实例。

样本组：D
来源判断：insufficient_evidence；结果：unresolved_event_component_referent；基线：partial；范围：uncertain

MP003 p362能支持检查其动作，但动作/部件的重述及具体阀指代需要上下文；Schema静态类型合法不等于语义唯一。

### MP003 物理页 362

Assertion：EXA-a02e674be4868f2fd5054b78
Claim：EXC-415894f9c17e5dc474c27f3b
记录：MPT-84947a21a010c3d96270
溢流阀动作 —inspected_by→ 溢流阀动作检查

> including a
>             check of the relief valve operation in the presence of the Surveyor

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0362.json)

## D-EXA-9d5a2f3a262a4c954b687743

可直接把安全阀动作这一Component替换为同一具体阀实例。

样本组：D
来源判断：insufficient_evidence；结果：unresolved_event_component_referent；基线：partial；范围：uncertain

MP003 p343与另一阀动作不同章节。应区分待改写类型与已确认实体错误，暂不强行判错。

### MP003 物理页 343

Assertion：EXA-9d5a2f3a262a4c954b687743
Claim：EXC-dda476b1bb78abb533b796ea
记录：MPT-01a122f76457ea9117bc
安全阀动作 —inspected_by→ 验证

> Relief-valve
>             operation is to be verified.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0343.json)

## E-A-RAW-02441

承插焊接头的80mm限制须关联气动管路等级I/II，不能删除等级III无限制分支。

样本组：E
来源判断：conditional_support；结果：qualified_association_not_unconditional_edge；基线：partial；范围：in_scope

MP003 p642表格I/II为Max80，III为No limitation。简单地址和裸specified_by不足以表达分级限制，还应确认气动管系向目标泵辅助系统的范围。

### MP003 物理页 642

记录：MPT-b50d0189a2b78aaa692d
承插焊接头 —specified_by→ 最大80毫米(3英寸)

> Socket welded joint (1)
> --- CELL ---
> Max. 80 mm (3 in.)
> --- CELL ---
> Max. 80 mm (3 in.)
> --- CELL ---
> No limitation

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0642.json)

## E-A-RAW-04016

正常应用下电机电流/功率正常范围检查对应Daily列的I，并保留全表适用条件。

样本组：E
来源判断：conditional_support；结果：inspection_schedule_association；基线：partial；范围：in_scope

MP005 p69原生Daily列和PDF确认每日检查；页首正常应用/新应用半间隔及远程监测建议不在原候选里。候选inspected_by的活动角色也需重述，不能仅恢复原三元组。

### MP005 物理页 69

记录：MPT-6458f79fab6305e7259c
电机电流及功率消耗正常范围检查 —inspected_by→ 每日检查

> Motor ampere and/or power                                                  
>        consumption within normal range
> --- CELL ---
> I

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0069.json)

## E-A-RAW-03031

自动启动可被备用泵自动启动并报警这一措施缓解。

样本组：E
来源判断：contradiction；结果：reject_definition_as_mitigation；基线：resolved；范围：in_scope

MP003 p949是在定义Auto start的复合动作，不是给其提供缓解措施。原类型不满足现有Schema，强版控制足以阻断该原三元组；另建正确复合事件不是本次阻断成功的含义。

### MP003 物理页 949

记录：MPT-8cc00613e5ab7931cb6e
自动启动 —mitigated_by→ 备用泵自动启动并触发报警

> Auto start = automatic starting of a standby pump, along with activation of suitable alarm.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0949.json)

## E-A-RAW-06540

收货时应立即检查驱动电机外部损伤，且保留收货触发条件。

样本组：E
来源判断：conditional_support；结果：qualified_recovery_same_family_variants；基线：partial；范围：in_scope

MP019 p60源文支持；跨页检索还找出6/24/42/78/96/114等同族语言候选，当前图未命中相应检查。不能把每种语言记作新增事实或独立支持。

### MP019 物理页 60

记录：MPT-2b4df1166028e4d7ed69
外部损伤 —inspected_by→ 立即检查电机是否存在外部损伤

> A su recepción, verifique inmediatamente si el motor presenta daños externos (por ejemplo en las salidas de eje, las bridas y las superficies pintadas)

[原始文档来源](https://library.e.abb.com/public/b72746520683cd05c1257dd90035fed7/Standard_Manual_Low_Voltage_all_lang_lowres01-2010.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP019_p0060.json)

## E-SRC-0fba9ab597f7f07481373e20

已识别关注区域可采用Pareto分析或结构化RCA这一后续分析步骤。

样本组：E
来源判断：conditional_support；结果：source_supported_analysis_association_probe；基线：partial；范围：in_scope

来源优先命中MP002 p84后才查候选。Pareto分支定向检索未见，RCA在其他页已有相关知识；不能把整组全部算成新发现或直接因果。

### MP002 物理页 84


> Identified areas of concern should then undergo a Pareto analysis or a Structured Root Cause Failure

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/survey_and_inspection/121-guide-for-surveys-based-on-machinery-reliability-and-maintenance-techniques/MRM_Guide_e-Jan23.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP002_p0084.json)

## E-SRC-36d7aa9bcd349928e65d9f29

SA-50-180/8作为消防泵时最大3000RPM是已有来源明确限定的知识。

样本组：E
来源判断：explicit_support；结果：already_generated_and_published_control；基线：resolved；范围：in_scope

MP004 p14已在原始候选MPT-d4c10b1dd3ef97b9a57b及当前EXA-4437fa5af5663baa8fe60645出现，不是候选遗漏或图缺边。

### MP004 物理页 14


> * SA-50-180/8 is, however, allowed to run at max. 3000 RPM when used as a fire pump.

[原始文档来源](https://www.desmi.com/media/4num3fbn/t1345uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP004_p0014.json)

## E-SRC-5e5784f4afbca559223ace08

LKH Prime轴封表除既有温压等候选外，还提供分部件材料及标准/替代材质属性。

样本组：E
来源判断：conditional_support；结果：component_material_attribute_association_probe；基线：partial；范围：in_scope

MP022 p42原生单元包含多个字段；温压、用水、排气上限和SiC标记已有候选，不能再算漏抽。材料属性需逐项另核，不能把一个表格单元当一个新关系。

### MP022 物理页 42


> Seal types External single or double mechanical seal
> Max. temperature flush medium 70oC
> Max. water pressure (DMS) Normally atmospheric (max. 5 bar) (max. 72.5 psi)
> Water consumption (double mechanical seal) 0.25-0.5 l/min. (0.07-0.13 gl )
> Material, stationary seal ring Acid-resistant steel with sealing surface of silicon carbide
> Material, rotating seal ring Carbon (standard) or silicon carbide
> Material, O-rings EPDM (standard)
> Alternative material, O-rings Nitrile (NBR) and fluorinated rubber (FPM).
> Air release time (no medium supply) Max 15 min
> NNNOOOTTTEEE: If running SiC/SiC single seal, the static seal face must be marked “LKH Prime”.

[原始文档来源](https://www.alfalaval.com/globalassets/documents/products/fluid-handling/pumps/centrifugal-pumps/lkh-prime/lkh-prime-pump-instruction-manual.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP022_p0042.json)

## E-SRC-b1b2605725df1b5d8947a718

排水后再用、换排水阀、安装排水阀有不同的拧紧/松开顺序和触发条件。

样本组：E
来源判断：conditional_support；结果：source_supported_missing_procedure_probes；基线：partial；范围：in_scope

MP007 p15全页明确再用先拧紧通气塞/排水阀、换阀先松旁通阀再旋排水塞、安装先排水塞再旁通阀。原页11条候选未表达；全缓存定向命中仅p30/31部件清单，不是这些程序。

### MP007 物理页 15


> persons and objects during water drainage (cold or hot). When using the pump once again,

[原始文档来源](https://www.desmi.com/media/c35h1n0d/t1536uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP007_p0015.json)

## E-B-EXA-d0d58ceec94816a546d21640

润滑剂不足或污染条件下运行与性能下降/可能轴承失效应保留条件回指。

样本组：E
来源判断：conditional_support；结果：qualified_existing_claim_not_new_direct_cause；基线：partial；范围：in_scope

MP018 p15有if...or if...及under these conditions，后果还区分will与possible。既有核心关系存在，目标是条件和模态关联，不是发明新边。

### MP018 物理页 15

Assertion：EXA-d0d58ceec94816a546d21640
Claim：EXC-5ea404ff2d035de606f1fb9e
记录：MPT-82e3c63fca49d4c7ce82
轴承箱润滑剂不足 —causes→ 泵性能下降

> Do not
>                       operate pump if sufficient lubricant is not present in bearing housing or if lubricant
>                       is contaminated with dirt or moisture. Operation of the unit under these conditions
>                       will lead to impaired pump performance and possible bearing failure.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0015.json)

## E-B-EXA-e8f9e8fdc94b731233c7e9c1

22500小时更换要求应继承所在ATEX章节，而非作为全部NSL应用的统一周期。

样本组：E
来源判断：conditional_support；结果：section_level_applicability_enrichment；基线：partial；范围：in_scope

MP005 p9完整页明确ATEX；数字和90%已在端点中，不是数字漏抽。p69正常应用表有25000h或60月，必须先对齐范围而不是宣布矛盾。

### MP005 物理页 9

Assertion：EXA-e8f9e8fdc94b731233c7e9c1
Claim：EXC-3dbd302a2212953c0f3672e0
记录：MPT-a3ff5e46f917a090e774
轴承 —maintained_by→ 在额定寿命90%(即22500小时)后更换轴承

> User must replenish grease according to instruction manuals and replace bearings after
>                   90% of rated life i.e. 22500 hours.

[原始文档来源](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP005_p0009.json)

## E-B-EXA-cdd51c549c9482db598945e4

清洗检查所有零件及必要时更换须绑定到安全阀拆下的相应零件集合与条件。

样本组：E
来源判断：conditional_support；结果：referent_and_guarded_action_association；基线：partial；范围：in_scope

MP021 p10的all parts回指前列bonnet/spring guide/spring/poppet，不是所有泵零件。if necessary不在当前检查动作端点；仅全文词命中不完成对象及后续动作绑定。

### MP021 物理页 10

Assertion：EXA-cdd51c549c9482db598945e4
Claim：EXC-a97098148dbb084213ac18b2
记录：MPT-37df2edd75359d27a0f4
所有零件 —inspected_by→ 清洁并检查所有零件的磨损或损坏

> Clean and inspect all parts for wear or damage
>                                              and replace if necessary.

[原始文档来源](https://www.vikingpump.com/sites/default/files/2025-09/Technical_Service_Manual__1600_0.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP021_p0010.json)

## E-B-EXA-ecb29455d7f38d4759494419

膨胀节维护关联应保留可接近安装位置这一使能要求。

样本组：E
来源判断：conditional_support；结果：installation_inspection_enablement_association；基线：partial；范围：in_scope

MP003 p524要求installed in accessible locations to permit inspection/servicing，核心maintained_by已有，但位置—可检查性/维护的关系没有独立表达。它不是新的直接因果链。

### MP003 物理页 524

Assertion：EXA-ecb29455d7f38d4759494419
Claim：EXC-fcae174306c6955a4f542509
记录：MPT-51c80003d0c8e96b521b
膨胀节 —maintained_by→ 定期维护

> Expansion joints are to be installed in accessible locations to permit regular
>                  inspection and/or periodic servicing.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0524.json)

## B-EXA-43b60e04286c3bc0b8fe22e9

O型圈不耐介质—更换适配介质O型圈已具备故障/原因/措施结构。

样本组：B_supplement
来源判断：explicit_support；结果：correctly_structured；基线：resolved；范围：in_scope

补充对照：MP007 p17的三角色与PDF、原生单元一致；此例保留原结构即可。

### MP007 物理页 17

Assertion：EXA-43b60e04286c3bc0b8fe22e9
Claim：EXC-075895ba2d996f9e36e0f160
记录：EXP-ae875569eed062a2b192ca2f
o型圈不耐输送介质 —mitigated_by→ 更换为适合输送介质的o型圈

> The O-ring does not
> withstand the pumping
> medium
> --- CELL ---
> Replace with an O-ring
> suitable for the pumping
> medium

[原始文档来源](https://www.desmi.com/media/c35h1n0d/t1536uk.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP007_p0017.json)

## B-EXA-ec1bbe41528688abe6f25814

正常疲劳作为剥落/裂纹的可能原因有原表支持。

样本组：B_supplement
来源判断：explicit_support；结果：structured_roles_with_unsplit_context；基线：resolved；范围：in_scope

补充对照：MP018 p26的选定原因对应正确，possible与PROBABLE CAUSE相符。同一引文另含另一原因不自动构成选定关系错误或需要新增条件。

### MP018 物理页 26

Assertion：EXA-ec1bbe41528688abe6f25814
Claim：EXC-9133c34ee1e44b34f16346c2
记录：EXP-68cdfc24ff069b634f8bd8cd
正常疲劳失效 —causes→ 剥落与裂纹

> Flaking and cracking
> --- CELL ---
> 1. Normal fatigue failure.
> 2. Bearing loads in excess of
> bearing capacity caused by
> misalignment.

[原始文档来源](https://pattersonpumps.com/wp-content/uploads/OM-Manual-Non-Clog-New.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP018_p0026.json)

## D-EXA-3c06f91ad198d5f65d435522

泵未正确灌引水—无法输送液体的当前因果方向反了。

样本组：D_supplement
来源判断：contradiction；结果：table_header_direction_false_positive；基线：resolved；范围：in_scope

补充核查：MP020 p26的CAUSES是表头，原生CAUSES/SYMPTOMS角色支持当前方向。仅按词序的触发器误报；强版原生行列回读可消解。

### MP020 物理页 26

Assertion：EXA-3c06f91ad198d5f65d435522
Claim：EXC-5db709bc168c3e78a7a307fc
记录：MPT-9d5f5d61c973e53c5b05
泵未正确灌引水 —causes→ 泵无法输送液体

> SYMPTOMS
> Failure to pump
> --- CELL ---
> CAUSES
> Pump not properly primed

[原始文档来源](https://www.cornellpump.com/site/wp-content/uploads/2023/12/Installation-and-Care.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP020_p0026.json)

## D-EXA-5c4a9de8924fcc5440f9ec69

压气机叶轮超速试验的3分钟/20%/10%条件不能无条件作为泵试验规范。

样本组：D_supplement
来源判断：explicit_support；结果：clear_scope_mismatch；基线：resolved；范围：outside

补充核查：MP003 p164明确Compressor wheels，型号/试验环境还影响数值条件。

### MP003 物理页 164

Assertion：EXA-5c4a9de8924fcc5440f9ec69
Claim：EXC-e1fea4f4e3e1256afe89dc8f
记录：MPT-1d082fdd41e46cdf5c2b
压气机叶轮 —inspected_by→ 超速试验(3分钟/超报警转速20%常温或10%@45°c)

> Compressor wheels are to
>                  be overspeed tested for 3 minutes on a test bed at 20% above the alarm level speed at ambient
>                  temperature, or 10% above alarm level speed at 45°C inlet temperature when tested in the actual
>                  housing with the corresponding pressure ratio.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0164.json)

## D-EXA-fa8e9475fd494ec2e55ec00d

可调螺距螺旋桨液压管路的1.5倍试压要求是否可以迁移到泵管系。

样本组：D_supplement
来源判断：insufficient_evidence；结果：unresolved_transferability；基线：unresolved；范围：uncertain

补充核查：MP003 p343是明确液压管路要求，但未证明其适用于当前泵管系，不能一律删除或移植。

### MP003 物理页 343

Assertion：EXA-fa8e9475fd494ec2e55ec00d
Claim：EXC-8c027bb26ec09c20c814fa3a
记录：MPT-408793c77c0009b4b41f
可调螺距螺旋桨液压系统 —inspected_by→ 1.5倍设计压力静水压试验

> The completed piping system of the controllable pitch propeller hydraulic system is to be hydrostatically
>             tested at a pressure equal to 1.5 times the design pressure in the presence of a Surveyor.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0343.json)

## D-EXA-a407500e33e7a7d79e833205

尾轴油封不抽轴/不拆螺旋桨的可更换设计能否改成泵轴封维修建议。

样本组：D_supplement
来源判断：insufficient_evidence；结果：unresolved_transferability；基线：unresolved；范围：uncertain

补充核查：MP003 p315包含船舶尾轴设计约束，尚无泵型对象支持。

### MP003 物理页 315

Assertion：EXA-a407500e33e7a7d79e833205
Claim：EXC-ab0abc6d42b8ab303bcea0b3
记录：MPT-643b7258cc58eb1e3da6
油封 —maintained_by→ 无需抽轴或拆除螺旋桨即可更换

> Approved type oil seals are to be used which will allow for replacement without the shaft
>                  withdrawal or removal of the propeller.

[原始文档来源](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/archives/other/1_marinevesselrules_20211/mvr-part-4-jan21.pdf)

[完整原始解析页](E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/results/experiments/research_point_1/kg_enhancement_task_comparison/runs/20261113_v1/review/pages/MP003_p0315.json)

## 来源优先命题分解

下列10个限定框架出自4个原先固定的来源单元，8个是有界检索的遗漏线索，2个是已有候选对照。不是10条新因果边。

### SP01 / E-SRC-b1b2605725df1b5d8947a718

MP007 物理页 15 | explicit_support | candidate_omission_probe

```json
{
  "actions": [
    "tighten vent plug",
    "tighten drainage valve"
  ],
  "relation": "before_reuse",
  "trigger": "using the pump again after the described drainage/out-of-service context"
}
```

页内11条候选未含此过程，全文档定向检索仅见部件清单。重新运行条件与动作集合不可变成一般启动许可。

> When using the pump once again, firstly tighten the vent plug and drainage valve.

### SP02 / E-SRC-b1b2605725df1b5d8947a718

MP007 物理页 15 | explicit_support | candidate_omission_probe

```json
{
  "first": "loosen bypass valve",
  "relation": "trigger_scoped_sequence",
  "then": "unscrew drain plug",
  "trigger": "replacement of drainage valve"
}
```

不是把多跳路径推成因果，而是源文直接陈述的先后要求。现有关系表没有Action→precedes→Action这一原子关系。

> When it is necessary to replace the drainage valve, you must loosen the bypass valve, then unscrew the drain plug

### SP03 / E-SRC-b1b2605725df1b5d8947a718

MP007 物理页 15 | explicit_support | candidate_omission_probe

```json
{
  "first": "tighten drain plug",
  "relation": "trigger_scoped_sequence",
  "then": "tighten bypass valve",
  "trigger": "installation of drainage valve"
}
```

安装与更换触发条件不同，不能同上一条合成无条件阀门操作链；分句已能恢复，事件参数关系尚未完成。

> If you want to install the drainage valve, firstly tighten the drain plug, then tighten the bypass valve.

### SP04 / E-SRC-5e5784f4afbca559223ace08

MP022 物理页 42 | explicit_support | component_attribute_omission_probe

```json
{
  "attribute": "material",
  "component": "stationary seal ring",
  "equipment": "LKH Prime shaft seal",
  "value": "acid-resistant steel with silicon-carbide sealing surface"
}
```

原始候选命中静环拆装不等于表达此材料属性；实际材质与适用型号须保留。该属性不是新故障因果边。

> Material, stationary seal ring Acid-resistant steel with sealing surface of silicon carbide

### SP05 / E-SRC-5e5784f4afbca559223ace08

MP022 物理页 42 | explicit_support | component_attribute_omission_probe

```json
{
  "alternative": "silicon carbide",
  "attribute": "material",
  "component": "rotating seal ring",
  "default": "carbon",
  "equipment": "LKH Prime shaft seal"
}
```

default与alternative不是同时采用两种材料；其他页的磨料工况SiC/SiC选材措施不是这一完整规格。

> Material, rotating seal ring Carbon (standard) or silicon carbide

### SP06 / E-SRC-5e5784f4afbca559223ace08

MP022 物理页 42 | explicit_support | component_attribute_omission_probe

```json
{
  "attribute": "material",
  "component": "O-rings",
  "equipment": "LKH Prime shaft seal",
  "status": "standard",
  "value": "EPDM"
}
```

不能把整个表中所有EPDM或其他密封件的材料都当成本部件同一事实，需保留部件行和standard限定。

> Material, O-rings EPDM (standard)

### SP07 / E-SRC-5e5784f4afbca559223ace08

MP022 物理页 42 | explicit_support | component_attribute_omission_probe

```json
{
  "attribute": "allowed_material",
  "component": "O-rings",
  "equipment": "LKH Prime shaft seal",
  "status": "alternative",
  "values": [
    "NBR",
    "FPM"
  ]
}
```

该条与EPDM默认规格相联系但不是同一断言，也不是两个独立来源。

> Alternative material, O-rings Nitrile (NBR) and fluorinated rubber (FPM).

### SP08 / E-SRC-0fba9ab597f7f07481373e20

MP002 物理页 84 | conditional_support | new_analysis_branch_probe

```json
{
  "new_branch_probe": "Pareto analysis",
  "recommended_alternatives": [
    "Pareto analysis",
    "Structured Root Cause Failure Analysis"
  ],
  "trigger": "identified areas of concern"
}
```

全缓存中有RCA相关事实，未命中Pareto分支。仅把该分支记为候选新增，不把整组RCA知识算新事实；诊断关联是分析流程而非物理因果。

> Identified areas of concern should then undergo a Pareto analysis or a Structured Root Cause Failure Analysis (RCA).

### SP09 / E-SRC-36d7aa9bcd349928e65d9f29

MP004 物理页 14 | explicit_support | already_generated_and_current

```json
{
  "equipment": "SA-50-180/8",
  "maximum_speed_rpm": 3000,
  "mode": "fire pump"
}
```

作为遗漏反例，不计新增。2500RPM的普通上限与消防工况3000RPM不能不分条件判冲突。

> SA-50-180/8 is, however, allowed to run at max. 3000 RPM when used as a fire pump.

### SP10 / E-SRC-5e5784f4afbca559223ace08

MP022 物理页 42 | explicit_support | already_generated_not_source_omission

```json
{
  "attribute": "maximum_flush_medium_temperature_C",
  "equipment": "LKH Prime shaft seal",
  "value": 70
}
```

未发布与未生成分开。该参数已在初始候选，不能因整个原生表格单元被再次命中而重算遗漏。

> Max. temperature flush medium 70oC

## 维护周期表面冲突补充调查

22500h与25000h/60月是否是同一适用条件下的矛盾更换周期

p9为ATEX特别要求，p69为normal applications并有全表时间先到规则。元数据都写NSL不能证明工况相同；加入章节和列头回读后应保持条件差异，不宣布真实矛盾。

判定：insufficient_evidence；不计入C的12项主样本。
