# 六页 v2.1 暂定参考

85 条核心候选参考、18 条辅助/未决项；独立专家完整性审核未完成。不是自动证据合格记录或图谱增量。此清单不保证穷尽，不可直接作为正式召回率分母。

## MP002:p0089

| ID | 主体 → 关系 → 客体 | 条件与模态 |
|---|---|---|
| — | v2 主任务目标为空 | 本页为一般可靠性背景，不能计为泵主任务知识 |

辅助/未决项：

- `MP002:p0089:AUX:001` 趋势分析关注系统/部件劣化，列出停机时间、振动/热成像/摩擦学和性能量等输入。（background：本段无明确泵应用连接，主任务分母为0；不称知识错误）
- `MP002:p0089:AUX:002` 至少每年复核维护要求文件以识别过时流程、工具与备件。（background：本段无明确泵应用连接，主任务分母为0；不称知识错误）
- `MP002:p0089:AUX:003` 定期复核维护任务打包间隔，以应对任务增删修改。（background：本段无明确泵应用连接，主任务分母为0；不称知识错误）
- `MP002:p0089:AUX:004` 数据不足或初始分析采用假设数据时实施寿命探索，反馈更新可靠性分析。（background：本段无明确泵应用连接，主任务分母为0；不称知识错误）

## MP004:p0010

| ID | 主体 → 关系 → 客体 | 条件与模态 |
|---|---|---|
| MP004:p0010:V21:001 | pump casing → maintained_by → Remove the plug, fill with cold liquid and refit the plug | SA 型自吸离心泵启动灌液程序；动作顺序保持；required |
| MP004:p0010:V21:002 | operation against closed discharge valve beyond the allowed limits → causes → damage to the pump | 标准泵；关排出阀运行仅短时，最多5分钟且最高80°C；超出该限制的风险，不将两限制改成必须同时超限；risk |
| MP004:p0010:V21:003 | operation against closed discharge valve beyond the allowed limits → causes → steam explosion | 标准泵；关排出阀运行仅短时，最多5分钟且最高80°C；超出该限制的风险，不将两限制改成必须同时超限；risk |
| MP004:p0010:V21:004 | damage or steam-explosion risk during unmonitored closed-discharge operation → prevented_by → installation of a safety device | 泵无人监控时；源文仅建议；安全装置未指明型号；recommended |
| MP004:p0010:V21:005 | shaft → inspected_by → check free rotation without jarring sounds | 启动前；required |
| MP004:p0010:V21:006 | pump casing → inspected_by → check filled with liquid | 启动前；required |
| MP004:p0010:V21:007 | pump → inspected_by → start briefly to check direction of rotation | 先短时启动核对；旋向与箭头一致才继续启动；required |
| MP004:p0010:V21:008 | considerably smaller delivery head than expected → causes → increased quantity of liquid delivered | SA 泵及管路；相对预期扬程；asserted |
| MP004:p0010:V21:009 | increased quantity of liquid delivered → causes → increased power consumption | 明显低于预期扬程导致的流量上升；asserted |
| MP004:p0010:V21:010 | increased quantity of liquid delivered → causes → cavitation in pump and piping | 明显低于预期扬程导致的流量上升；possible |
| MP004:p0010:V21:011 | cavitation → causes → heavy erosion of the impeller | SA 泵；源文 may；不推广为每次汽蚀必然严重侵蚀；possible |
| MP004:p0010:V21:012 | heavy erosion of the impeller → causes → impeller unfit for use | 源文 may at times；可能在很短时间内发生；possible |
| MP004:p0010:V21:013 | power consumption of the pump → diagnosed_by → measuring current intensity of the connected motor | 启动后检查；源文为示例 e.g.，不表示测量精度保证；example |
| MP004:p0010:V21:014 | quantity of water delivered → diagnosed_by → motor-current check together with differential pressure and pump characteristics | 启动后；保留电流检查、压差读数与泵特性联合语境；联合测量句法仍待专家裁定；conditional |

辅助/未决项：

- `MP004:p0010:AUX:001` 灌注液还用于冷却轴封；不得未灌液启动或干运转。（作用/禁止运行要求不强行映射为维护动作）
- `MP004:p0010:AUX:002` 泄压阀在预定压力打开；不得拆除或重新调整，排出液可能很热。（设备功能与禁止调节；不转换成正向维护动作）
- `MP004:p0010:AUX:003` 未按预期工作时按故障查找表处理；制造商称多数故障源于管路。（本页未给出具体故障表动作；总体经验不转成任意具体因果边）

## MP007:p0012

| ID | 主体 → 关系 → 客体 | 条件与模态 |
|---|---|---|
| MP007:p0012:V21:001 | dry running → causes → damage to pump bearing | MVA/MVS 泵；未灌水/排气时不得启动；asserted |
| MP007:p0012:V21:002 | dry running → causes → damage to shaft seal | MVA/MVS 泵；未灌水/排气时不得启动；asserted |
| MP007:p0012:V21:003 | foot bolts → inspected_by → check tightened | 7.2 启动前检查；If ... or not 表示检查是否；required |
| MP007:p0012:V21:004 | pump → inspected_by → check full of water | 7.2 启动前检查；If ... or not 表示检查是否；required |
| MP007:p0012:V21:005 | power grid → inspected_by → check correct voltage | 7.2 启动前检查；If ... or not 表示检查是否；required |
| MP007:p0012:V21:006 | pump → inspected_by → check direction of rotation | 7.2 启动前检查；If ... or not 表示检查是否；required |
| MP007:p0012:V21:007 | pipes → inspected_by → check tight connections | 7.2 启动前检查；If ... or not 表示检查是否；required |
| MP007:p0012:V21:008 | pipes → inspected_by → check normal water supply | 7.2 启动前检查；If ... or not 表示检查是否；required |
| MP007:p0012:V21:009 | valves on inlet pipes → inspected_by → check completely open | 7.2 启动前检查；If ... or not 表示检查是否；required |
| MP007:p0012:V21:010 | working pressure → diagnosed_by → check using a pressure meter | 启动前；已经安装压力表时；conditional |
| MP007:p0012:V21:011 | outlet valve → maintained_by → open slowly | 泵已启动后；不得把标题启动前条件覆盖此项目中的明确后置时序；required |

辅助/未决项：

- `MP007:p0012:AUX:001` 有向下排出管、虹吸或需阻止污水回流任一特征时，在泵附近安装真空阀。（正向安装要求；本页未为每个条件分别陈述明确预防因果，不拆成三个确定预防断言）
- `MP007:p0012:AUX:002` 电机可靠接地；拆接线盒或泵前断电；单相和三相采用不同热保护配置。（电气安全及配置辅助要求，本轮核心参考不据此补造故障事件）
- `MP007:p0012:AUX:003` 压力开关控制时检查/调节启停压力并检查满载电流。（英文段落将压力开关与电流检查混用，方法映射有歧义，未计入确定参考）
- `MP007:p0012:AUX:004` 排气时避免排出水伤人或损物，热水特别防烫。（人身伤害/物料损害辅助要求；不改成消除泵故障的措施）

## MP007:p0015

| ID | 主体 → 关系 → 客体 | 条件与模态 |
|---|---|---|
| MP007:p0015:V21:001 | motor with a nozzle → maintained_by → lubricate with lubricant or similar high-temperature lithium base grease | 包括11kW以上电机；按原文 nozzle 保留；维护前停机；详见源文 windscreen 说明；required |
| MP007:p0015:V21:002 | motor → maintained_by → lubricate before starting | 季节性运行且停机超过6个月；本段电机润滑适用范围；不得泛化为所有电机日常维护；conditional |
| MP007:p0015:V21:003 | pump → maintained_by → add a proper quantity of antifreezing agent | 安装处可能冻结；数量原文未定量；介质相容性未由本页给出；conditional |
| MP007:p0015:V21:004 | freezing of the liquid conveyed by the pump → causes → damage to the pump | 安装处可能冻结；risk |
| MP007:p0015:V21:005 | pump → maintained_by → drain the liquid inside it | 霜冻期间停用；可经泵头注水口和底部排水口排液；注意冷/热排液安全；conditional |
| MP007:p0015:V21:006 | vent plug and drainage valve → maintained_by → tighten before using the pump again | 前述霜冻停用排液后恢复使用；required |
| MP007:p0015:V21:007 | drainage valve → maintained_by → loosen bypass valve then unscrew drain plug | 需更换排水阀时；步骤顺序固定；前述维护停机条件；conditional |
| MP007:p0015:V21:008 | drainage valve → maintained_by → tighten drain plug then tighten bypass valve | 安装排水阀时；步骤顺序固定；前述维护停机条件；conditional |

辅助/未决项：

- `MP007:p0015:AUX:001` pump bearing：源文规定无需维护。（负向维护要求，禁止编码为正向 maintained_by）
- `MP007:p0015:AUX:002` shaft seal：源文规定无需维护。（负向维护要求，禁止编码为正向 maintained_by）
- `MP007:p0015:AUX:003` motor without a nozzle：源文规定无需维护。（负向维护要求，禁止编码为正向 maintained_by）
- `MP007:p0015:AUX:004` 维护前确认泵停机，以避免事故。（维护前置安全条件，在下面维护动作中继承）
- `MP007:p0015:AUX:005` 机械密封自动调整；动静环接触面由输送液润滑和冷却；滑动轴承由输送液润滑。（源文描述运行机理，不直接等同于操作者正向维护动作）
- `MP007:p0015:AUX:006` 可使用60Hz电机但流量/扬程/功率改变，需咨询制造商。（运行规格辅助信息；本页顶部为前页延续数表，表头不全不猜测）

## MP015:p0039

| ID | 主体 → 关系 → 客体 | 条件与模态 |
|---|---|---|
| MP015:p0039:V21:001 | tolerance ring (1880) → maintained_by → place into shaft recess of pump shaft (2200) | FreFlow；叶轮装配；轴承架1；源文程序步骤顺序1；不得独立视为完整维修程序；required |
| MP015:p0039:V21:002 | tolerance ring → maintained_by → isolate from liquid by applying Loctite 572 on impeller stop face, shaft end and rearmost ring part | FreFlow；叶轮装配；轴承架1；仅青铜和不锈钢泵；源文程序步骤顺序2；不得独立视为完整维修程序；required |
| MP015:p0039:V21:003 | impeller → maintained_by → push over tolerance ring onto shaft; ensure square with shaft | FreFlow；叶轮装配；轴承架1；源文程序步骤顺序3；不得独立视为完整维修程序；required |
| MP015:p0039:V21:004 | impeller bolt and spring washer (1825) → maintained_by → apply Loctite 243 to thread and mount | FreFlow；叶轮装配；轴承架1；紧固力矩须查第10章；本页不给数值；源文程序步骤顺序4；不得独立视为完整维修程序；required |
| MP015:p0039:V21:005 | Back Pull Out-unit → maintained_by → remove | FreFlow；叶轮拆卸；非轴承架1；完整程序见7.5.2，本页只是子程序调用；源文程序步骤顺序1；不得独立视为完整维修程序；required |
| MP015:p0039:V21:006 | locking ring (1825) → maintained_by → tap lips straight | FreFlow；叶轮拆卸；非轴承架1；仅轴承架4；源文程序步骤顺序2；不得独立视为完整维修程序；required |
| MP015:p0039:V21:007 | impeller nut or impeller bolt (1820) → maintained_by → disassemble | FreFlow；叶轮拆卸；非轴承架1；源文程序步骤顺序3；不得独立视为完整维修程序；required |
| MP015:p0039:V21:008 | washer (1830) → maintained_by → remove | FreFlow；叶轮拆卸；非轴承架1；仅轴承架2和3；源文程序步骤顺序4；不得独立视为完整维修程序；required |
| MP015:p0039:V21:009 | impeller (0120) → maintained_by → pull off pump shaft using proper puller | FreFlow；叶轮拆卸；非轴承架1；源文程序步骤顺序5；不得独立视为完整维修程序；required |
| MP015:p0039:V21:010 | impeller nut (1860) → maintained_by → remove from pump shaft | FreFlow；叶轮拆卸；非轴承架1；保留原文部件号，与下节1860名称不同处不自行纠正；源文程序步骤顺序6；不得独立视为完整维修程序；required |
| MP015:p0039:V21:011 | impeller key (1860) → maintained_by → place into keyway of pump shaft (2200) | FreFlow；叶轮装配；非轴承架1；源文程序步骤顺序1；不得独立视为完整维修程序；required |
| MP015:p0039:V21:012 | impeller → maintained_by → slide onto pump shaft | FreFlow；叶轮装配；非轴承架1；源文程序步骤顺序2；不得独立视为完整维修程序；required |
| MP015:p0039:V21:013 | washer (1830) → maintained_by → fit | FreFlow；叶轮装配；非轴承架1；仅轴承架2和3；源文程序步骤顺序3；不得独立视为完整维修程序；required |
| MP015:p0039:V21:014 | locking ring (1825) → maintained_by → fit | FreFlow；叶轮装配；非轴承架1；仅轴承架4；源文程序步骤顺序4；不得独立视为完整维修程序；required |
| MP015:p0039:V21:015 | pump shaft and impeller nut (1820) or bolt (1820) → maintained_by → degrease threads | FreFlow；叶轮装配；非轴承架1；源文程序步骤顺序5；不得独立视为完整维修程序；required |
| MP015:p0039:V21:016 | impeller nut or bolt → maintained_by → apply Loctite 243 to thread and mount | FreFlow；叶轮装配；非轴承架1；紧固力矩须查第10章；本页不给数值；源文程序步骤顺序6；不得独立视为完整维修程序；required |
| MP015:p0039:V21:017 | locking ring (1825) → maintained_by → tap edges into recesses of shaft and impeller nut or bolt | FreFlow；叶轮装配；非轴承架1；仅轴承架4；源文程序步骤顺序7；不得独立视为完整维修程序；required |
| MP015:p0039:V21:018 | screws (0115) → maintained_by → loosen | FreFlow；耐磨板拆卸；Back Pull Out-unit 已拆除；部件号见图55；源文程序步骤顺序1；不得独立视为完整维修程序；required |
| MP015:p0039:V21:019 | wear plate (0125) → maintained_by → remove from casing together with cutting blade (0105) if fitted | FreFlow；耐磨板拆卸；Back Pull Out-unit 已拆除；部件号见图55；切削刀片仅在泵配有切削机构时；源文程序步骤顺序2；不得独立视为完整维修程序；required |
| MP015:p0039:V21:020 | pump casing edge → maintained_by → clean where wear plate is fitted | FreFlow；耐磨板装配；源文程序步骤顺序1；不得独立视为完整维修程序；required |
| MP015:p0039:V21:021 | wear plate → maintained_by → fit aligned in casing with holes correctly positioned and cutting blade if provided | FreFlow；耐磨板装配；切削刀片仅在配有切削机构时；源文程序步骤顺序2；不得独立视为完整维修程序；required |
| MP015:p0039:V21:022 | wear plate screws (0115) → maintained_by → tighten using Loctite 243 to lock screws | FreFlow；耐磨板装配；源文程序步骤顺序3；不得独立视为完整维修程序；required |

辅助/未决项：


## MP018:p0026

| ID | 主体 → 关系 → 客体 | 条件与模态 |
|---|---|---|
| MP018:p0026:V21:001 | Normal fatigue failure → causes → Flaking and cracking | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:002 | Bearing loads in excess of bearing capacity caused by misalignment → causes → Flaking and cracking | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:003 | Flaking and cracking → manifests_as → small cracks on inner and outer races which flake | 本离心泵维护手册轴承；保留泵型/手册适用范围；descriptive |
| MP018:p0026:V21:004 | Flaking and cracking → mitigated_by → Replace bearing if found | 本离心泵维护手册轴承；保留泵型/手册适用范围；发现该轴承缺陷时；按 Failures–Replace if Found 标题；不可套用到适度变色例外；required |
| MP018:p0026:V21:005 | Dirt in the bearings → causes → Indentations | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:006 | Excessive impact loading of the bearing, such as improper mounting or removal → causes → Indentations | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:007 | Indentations → manifests_as → Indentations or cavities in the inner and outer races | 本离心泵维护手册轴承；保留泵型/手册适用范围；descriptive |
| MP018:p0026:V21:008 | Indentations → mitigated_by → Replace bearing if found | 本离心泵维护手册轴承；保留泵型/手册适用范围；发现该轴承缺陷时；按 Failures–Replace if Found 标题；不可套用到适度变色例外；required |
| MP018:p0026:V21:009 | Poor lubrication → causes → Broken Separator (cage) | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:010 | Misalignment of the shaft → causes → Broken Separator (cage) | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:011 | Excessive shaft deflection → causes → Broken Separator (cage) | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:012 | Broken Separator (cage) → manifests_as → Cracked separator or separator in pieces | 本离心泵维护手册轴承；保留泵型/手册适用范围；descriptive |
| MP018:p0026:V21:013 | Broken Separator (cage) → mitigated_by → Replace bearing if found | 本离心泵维护手册轴承；保留泵型/手册适用范围；发现该轴承缺陷时；按 Failures–Replace if Found 标题；不可套用到适度变色例外；required |
| MP018:p0026:V21:014 | Fit on the shaft or in housing too loose → causes → Wear | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:015 | Bearing locked by dirt and turning of shaft or in housing → causes → Wear | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:016 | Wear → manifests_as → Bore and OD of outer ring of bearing galled or braided | 本离心泵维护手册轴承；保留泵型/手册适用范围；descriptive |
| MP018:p0026:V21:017 | Wear → mitigated_by → Replace bearing if found | 本离心泵维护手册轴承；保留泵型/手册适用范围；发现该轴承缺陷时；按 Failures–Replace if Found 标题；不可套用到适度变色例外；required |
| MP018:p0026:V21:018 | Forcing a cocked bearing on or off a shaft → causes → Fractured Ring | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:019 | Too heavy a press fit → causes → Fractured Ring | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:020 | Fractured Ring → manifests_as → Hairline cracks or complete fracture | 本离心泵维护手册轴承；保留泵型/手册适用范围；descriptive |
| MP018:p0026:V21:021 | Fractured Ring → mitigated_by → Replace bearing if found | 本离心泵维护手册轴承；保留泵型/手册适用范围；发现该轴承缺陷时；按 Failures–Replace if Found 标题；不可套用到适度变色例外；required |
| MP018:p0026:V21:022 | Inadequate lubrication → causes → Discoloration | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；源文明确适度滚珠/滚道变色不构成废弃理由；probable |
| MP018:p0026:V21:023 | Discoloration → manifests_as → Balls and races darker than normal appearance of bearing metal | 本离心泵维护手册轴承；保留泵型/手册适用范围；源文明确适度滚珠/滚道变色不构成废弃理由；descriptive |
| MP018:p0026:V21:024 | Water entering the housing → causes → Corrosion | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:025 | Condensation inside the housing → causes → Corrosion | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:026 | Lubricant breaks down into acid (Wrong lubricant) → causes → Corrosion | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:027 | Corrosion → manifests_as → Balls and raceways rusted | 本离心泵维护手册轴承；保留泵型/手册适用范围；descriptive |
| MP018:p0026:V21:028 | Corrosion → mitigated_by → Replace bearing if found | 本离心泵维护手册轴承；保留泵型/手册适用范围；发现该轴承缺陷时；按 Failures–Replace if Found 标题；不可套用到适度变色例外；required |
| MP018:p0026:V21:029 | misalignment → causes → Bearing loads in excess of bearing capacity | 本离心泵维护手册轴承；保留泵型/手册适用范围；PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向；probable |
| MP018:p0026:V21:030 | Flaking and cracking → evolves_to → cracks and flaking over entire race surface | 本离心泵维护手册轴承；保留泵型/手册适用范围；descriptive |

辅助/未决项：

- `MP018:p0026:AUX:001` 滚珠和滚道适度变色不是报废轴承的理由。（负向更换要求；不添加“变色→更换”正向措施）
