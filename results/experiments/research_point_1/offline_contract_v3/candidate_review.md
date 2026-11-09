# 233 条源文技术裁定与修复账本

同一助手、非盲技术编修；不是专家准确率标签。完整字段与原生定位见 `candidate_adjudications.jsonl`。

## VR01:A001 · E0 · MP007:p0015

原始：pump bearing — located_in → pump

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：pump bearing — located_in → pump

条件：[]

证据：

- `page_text[2267:2334]`：Pump bearing and shaft seal require no maintenance.

## VR01:A002 · E0 · MP007:p0015

原始：shaft seal — located_in → pump

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：shaft seal — located_in → pump

条件：[]

证据：

- `page_text[2267:2334]`：Pump bearing and shaft seal require no maintenance.

## VR01:A003 · E0 · MP007:p0015

原始：pump bearing — maintained_by → require no maintenance

裁定：representation_error。原响应已保留 negative，并非极性翻转；无需维护不是维护动作，也不等于禁止维护。

修复：转 `maintenance_requirement` 旁路；要求=not_required。

证据：

- `page_text[2267:2334]`：Pump bearing and shaft seal require no maintenance.

## VR01:A004 · E0 · MP007:p0015

原始：shaft seal — maintained_by → require no maintenance

裁定：representation_error。原响应已保留 negative，并非极性翻转；无需维护不是维护动作，也不等于禁止维护。

修复：转 `maintenance_requirement` 旁路；要求=not_required。

证据：

- `page_text[2267:2334]`：Pump bearing and shaft seal require no maintenance.

## VR01:A005 · E0 · MP007:p0015

原始：motor without a nozzle — maintained_by → requires no maintenance

裁定：representation_error。原响应已保留 negative，并非极性翻转；无需维护不是维护动作，也不等于禁止维护。

修复：转 `maintenance_requirement` 旁路；要求=not_required。

证据：

- `page_text[2543:2594]`：The motor without a nozzle requires no maintenance.

## VR01:A006 · E0 · MP007:p0015

原始：motor with a nozzle — maintained_by → lubricated with lubricant or similar high-temperature lithium base grease

裁定：incomplete。补充维护前停机及 Motor bearing 段的带 nozzle 电机范围；including >11kW 不是仅限 >11kW。

修复：motor with a nozzle — maintained_by → lubricated with lubricant or similar high-temperature lithium base grease

条件：["including motor above 11kW", "Before maintenance: confirm that the pump is shut off", "motor with a nozzle; including motor above 11kW"]

证据：

- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.
- `page_text[2595:2751]`：The motor with a nozzle (including motor above 11kW) shall be lubricated with lubricant or similar high-temperature lithium base grease.
- `page_text[2460:2473]`：Motor bearing

## VR01:A007 · E0 · MP007:p0015

原始：motor with a nozzle — maintained_by → lubricate before starting the motor

裁定：incomplete。补充维护前停机及 Motor bearing 段的带 nozzle 电机范围；including >11kW 不是仅限 >11kW。

修复：motor with a nozzle — maintained_by → lubricate before starting the motor

条件：["seasonal running (motor shutdown for over 6 months)", "Before maintenance: confirm that the pump is shut off", "motor with a nozzle; including motor above 11kW"]

证据：

- `page_text[2811:2921]`：In case of seasonal running (motor shutdown for over 6 months), lubricate before starting the motor.
- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.
- `page_text[2595:2751]`：The motor with a nozzle (including motor above 11kW) shall be lubricated with lubricant or similar high-temperature lithium base grease.
- `page_text[2460:2473]`：Motor bearing

## VR01:A008 · E0 · MP007:p0015

原始：mechanical seal — located_in → pump

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：mechanical seal — located_in → pump

条件：[]

证据：

- `page_text[3028:3219]`：The mechanical seal is adjusted automatically. The contact surface of dynamic ring and static ring in the seal will be lubricated and cooled down by the liquid conveyed by the pump.

## VR01:A009 · E0 · MP007:p0015

原始：dynamic ring — located_in → seal

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：dynamic ring — located_in → seal

条件：[]

证据：

- `page_text[3075:3219]`：The contact surface of dynamic ring and static ring in the seal will be lubricated and cooled down by the liquid conveyed by the pump.

## VR01:A010 · E0 · MP007:p0015

原始：static ring — located_in → seal

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：static ring — located_in → seal

条件：[]

证据：

- `page_text[3075:3219]`：The contact surface of dynamic ring and static ring in the seal will be lubricated and cooled down by the liquid conveyed by the pump.

## VR01:A011 · E0 · MP007:p0015

原始：sliding bearing — located_in → pump

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：sliding bearing — located_in → pump

条件：[]

证据：

- `page_text[3230:3316]`：The sliding bearing in the pump will be lubricated by the liquid conveyed by the pump.

## VR01:A012 · E0 · MP007:p0015

原始：freezing of the liquid conveyed by the pump — causes → damage to the pump

裁定：complete。冻液导致泵损坏，安装处可能冻结的条件已保存。

修复：freezing of the liquid conveyed by the pump — causes → damage to the pump

条件：["pump is installed at a place where it is likely to freeze"]

证据：

- `page_text[3499:3734]`：If the pump is installed at a place where it is likely to freeze, proper quantity of antifreezing agent must be added so as to avoid damage to the pump due to freezing of the liquid conveyed by the pump.

## VR01:A013 · E0 · MP007:p0015

原始：freezing of the liquid conveyed by the pump — prevented_by → proper quantity of antifreezing agent must be added

裁定：incomplete。添加防冻剂为保养要求，补维护停机，保留可能冻结及未定量 proper quantity。

修复：pump — maintained_by → proper quantity of antifreezing agent must be added

条件：["pump is installed at a place where it is likely to freeze", "Before maintenance: confirm that the pump is shut off"]

证据：

- `page_text[3499:3734]`：If the pump is installed at a place where it is likely to freeze, proper quantity of antifreezing agent must be added so as to avoid damage to the pump due to freezing of the liquid conveyed by the pump.
- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.

## VR01:A014 · E0 · MP007:p0015

原始：pump — mitigated_by → drain the liquid inside it

裁定：representation_error。排液是泵保养动作，不是检查液体；补霜冻停用、停机和排液通道，不将危险工况作为被缓解的设备。

修复：pump — maintained_by → drain the liquid via the water injection hole at the pump head and the drainage hole at bottom

条件：["pump out of service during a frost period", "Before maintenance: confirm that the pump is shut off", "Pay attention to safety of persons and objects during water drainage (cold or hot)"]

证据：

- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.
- `page_text[3806:3945]`：If the pump is out of service during a frost period, you should drain the liquid inside it so as to avoid any damage to the pump.
- `page_text[3946:4076]`：The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.
- `page_text[4077:4170]`：Pay attention to safety of persons and objects during water drainage (cold or hot).

## VR01:A015 · E0 · MP007:p0015

原始：water injection hole — located_in → pump head

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：water injection hole — located_in → pump head

条件：[]

证据：

- `page_text[3946:4076]`：The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.

## VR01:A016 · E0 · MP007:p0015

原始：drainage hole — located_in → bottom

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：drainage hole — located_in → bottom

条件：[]

证据：

- `page_text[3946:4076]`：The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.

## VR01:A017 · E0 · MP007:p0015

原始：pump — operates_under → 60hz motor

裁定：complete。结构/运行适用关系可由本页原文支持；与核心诊断量分开。

修复：pump — operates_under → 60hz motor

条件：[]

证据：

- `page_text[1753:1866]`：The pump may run with 60hz motor. The flow, head and power of the pump running at 60hz will be changed.

## VR02:A001 · E1 · MP002:p0089

原始：Trend Analysis — indicates → systems or components that may be in the process of degrading

裁定：representation_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[2253:2359]`：A trend analysis provides an indication for systems or components that may be in the process of degrading.

## VR02:A002 · E1 · MP002:p0089

原始：Equipment downtime — diagnosed_by → Trend Analysis

裁定：representation_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[2372:2478]`：The measurement factors used for trending may be as follows: i) Equipment downtime

## VR02:A003 · E1 · MP002:p0089

原始：Equipment item/component condition monitoring levels (vibration, thermography, tribology, etc.) — diagnosed_by → Trend Analysis

裁定：representation_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[2621:2721]`：ii) Equipment item/component condition monitoring levels (vibration, thermography, tribology, etc.)

## VR02:A004 · E1 · MP002:p0089

原始：Other condition-monitoring parameters related to performance (temperatures, pressures, power, etc.) — diagnosed_by → Trend Analysis

裁定：representation_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[2734:2855]`：iii) Other condition-monitoring parameters related to performance (temperatures, pressures, power, etc.)

## VR02:A005 · E1 · MP002:p0089

原始：The results of chronic root cause failure analyses — diagnosed_by → Trend Analysis

裁定：representation_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[2928:2983]`：iv) The results of chronic root cause failure analyses

## VR02:A006 · E1 · MP002:p0089

原始：Documents containing maintenance requirements for systems, equipment items or components — inspected_by → Maintenance Requirements Document Reviews

裁定：representation_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[3260:3547]`：Documents containing maintenance requirements for systems, equipment items or components are to be reviewed at least annually to identify outdated maintenance processes, techniques or technologies, or to bring attention to obsolete tools and outdated spare parts.
- `page_text[3260:3397]`：Documents containing maintenance requirements for systems, equipment items or components are to be reviewed at least annually

## VR02:A007 · E1 · MP002:p0089

原始：Task packaging — maintained_by → Task packaging reviews

裁定：representation_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[4071:4308]`：Task packaging reviews should be conducted periodically to evaluate the packaged maintenance intervals to verify that as maintenance tasks are added, deleted or modified, optimum packaged intervals are maintained.
- `page_text[4071:4185]`：Task packaging reviews should be conducted periodically to evaluate the packaged maintenance intervals

## VR02:A008 · E1 · MP002:p0089

原始：age exploration tasks — prevented_by → insufficient age-to-failure data are available or assumed data are used during the initial reliability based analysis

裁定：semantic_error。保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。

修复：转 `background_statement` 旁路；要求=见原文及条件。

证据：

- `page_text[4487:4680]`：When insufficient age-to-failure data are available or assumed data are used during the initial reliability based analysis, age exploration tasks are to be designed and implemented.

## VR03:A001 · E1 · MP018:p0026

原始：Flaking and cracking — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Flaking and cracking — occurs_at → bearing

条件：[]

证据：

- `page_text[939:959]`：Flaking and cracking
- `page_text[458:473]`：BEARING DEFECTS

## VR03:A002 · E1 · MP018:p0026

原始：Flaking and cracking — manifests_as → In the early stages the surfaces of the inner and outer races develop small cracks, which flake. The cracks and flaking ultimately spread over the entire race surface.

裁定：representation_error。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。

修复：Flaking and cracking — manifests_as → In the early stages the surfaces of the inner and outer races develop small cracks, which flake. The cracks and flaking ultimately spread over the entire race surface.

条件：[]

证据：

- `page_text[939:959]`：Flaking and cracking
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[799:809]`：APPEARANCE

## VR03:A003 · E1 · MP018:p0026

原始：Normal fatigue failure — causes → Flaking and cracking

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Normal fatigue failure — causes → Flaking and cracking

条件：[]

证据：

- `page_text[939:959]`：Flaking and cracking
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A004 · E1 · MP018:p0026

原始：Bearing loads in excess of bearing capacity caused by misalignment — causes → Flaking and cracking

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Bearing loads in excess of bearing capacity caused by misalignment — causes → Flaking and cracking

条件：[]

证据：

- `page_text[939:959]`：Flaking and cracking
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A005 · E1 · MP018:p0026

原始：Indentations — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Indentations — occurs_at → bearing

条件：[]

证据：

- `page_text[1562:1574]`：Indentations
- `page_text[458:473]`：BEARING DEFECTS

## VR03:A006 · E1 · MP018:p0026

原始：Indentations — manifests_as → Indentations or cavities in the inner and outer races.

裁定：representation_error。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。

修复：Indentations — manifests_as → Indentations or cavities in the inner and outer races.

条件：[]

证据：

- `page_text[1562:1574]`：Indentations
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[799:809]`：APPEARANCE

## VR03:A007 · E1 · MP018:p0026

原始：Dirt in the bearings — causes → Indentations

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Dirt in the bearings — causes → Indentations

条件：[]

证据：

- `page_text[1562:1574]`：Indentations
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A008 · E1 · MP018:p0026

原始：Excessive impact loading of the bearing, such as improper mounting or removal — causes → Indentations

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Excessive impact loading of the bearing, such as improper mounting or removal — causes → Indentations

条件：[]

证据：

- `page_text[1562:1574]`：Indentations
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A009 · E1 · MP018:p0026

原始：Broken Separator (cage) — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Broken Separator (cage) — occurs_at → bearing

条件：[]

证据：

- `page_text[2091:2114]`：Broken Separator (cage)
- `page_text[458:473]`：BEARING DEFECTS

## VR03:A010 · E1 · MP018:p0026

原始：Broken Separator (cage) — manifests_as → Cracked separator or separator in pieces.

裁定：representation_error。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。

修复：Broken Separator (cage) — manifests_as → Cracked separator or separator in pieces.

条件：[]

证据：

- `page_text[2091:2114]`：Broken Separator (cage)
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[799:809]`：APPEARANCE

## VR03:A011 · E1 · MP018:p0026

原始：Poor lubrication — causes → Broken Separator (cage)

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Poor lubrication — causes → Broken Separator (cage)

条件：[]

证据：

- `page_text[2091:2114]`：Broken Separator (cage)
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A012 · E1 · MP018:p0026

原始：Misalignment of the shaft — causes → Broken Separator (cage)

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Misalignment of the shaft — causes → Broken Separator (cage)

条件：[]

证据：

- `page_text[2091:2114]`：Broken Separator (cage)
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A013 · E1 · MP018:p0026

原始：Excessive shaft deflection — causes → Broken Separator (cage)

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Excessive shaft deflection — causes → Broken Separator (cage)

条件：[]

证据：

- `page_text[2091:2114]`：Broken Separator (cage)
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A014 · E1 · MP018:p0026

原始：Wear — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Wear — occurs_at → bearing

条件：[]

证据：

- `page_text[2610:2614]`：Wear
- `page_text[458:473]`：BEARING DEFECTS

## VR03:A015 · E1 · MP018:p0026

原始：Wear — manifests_as → Bore and OD of outer ring of bearing galled or braided.

裁定：representation_error。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。

修复：Wear — manifests_as → Bore and OD of outer ring of bearing galled or braided.

条件：[]

证据：

- `page_text[2610:2614]`：Wear
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[799:809]`：APPEARANCE

## VR03:A016 · E1 · MP018:p0026

原始：Fit on the shaft or in housing too loose — causes → Wear

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Fit on the shaft or in housing too loose — causes → Wear

条件：[]

证据：

- `page_text[2610:2614]`：Wear
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A017 · E1 · MP018:p0026

原始：Bearing locked by dirt and turning of shaft or in housing — causes → Wear

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Bearing locked by dirt and turning of shaft or in housing — causes → Wear

条件：[]

证据：

- `page_text[2610:2614]`：Wear
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A018 · E1 · MP018:p0026

原始：Fractured Ring — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Fractured Ring — occurs_at → bearing

条件：[]

证据：

- `page_text[3235:3249]`：Fractured Ring
- `page_text[458:473]`：BEARING DEFECTS

## VR03:A019 · E1 · MP018:p0026

原始：Fractured Ring — manifests_as → Hairline cracks or complete fracture.

裁定：representation_error。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。

修复：Fractured Ring — manifests_as → Hairline cracks or complete fracture.

条件：[]

证据：

- `page_text[3235:3249]`：Fractured Ring
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[799:809]`：APPEARANCE

## VR03:A020 · E1 · MP018:p0026

原始：Forcing a cocked bearing on or off a shaft — causes → Fractured Ring

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Forcing a cocked bearing on or off a shaft — causes → Fractured Ring

条件：[]

证据：

- `page_text[3235:3249]`：Fractured Ring
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A021 · E1 · MP018:p0026

原始：Too heavy a press fit — causes → Fractured Ring

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Too heavy a press fit — causes → Fractured Ring

条件：[]

证据：

- `page_text[3235:3249]`：Fractured Ring
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A022 · E1 · MP018:p0026

原始：Discoloration — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Discoloration — occurs_at → bearing

条件：[]

证据：

- `page_text[3672:3685]`：Discoloration
- `page_text[458:473]`：BEARING DEFECTS

## VR03:A023 · E1 · MP018:p0026

原始：Discoloration — manifests_as → Balls and races darker than normal appearance of bearing metal.

裁定：representation_error。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。 变色的负向废弃依据以独立要求附存，不冒作原因成立的前提。

修复：Discoloration — manifests_as → Balls and races darker than normal appearance of bearing metal.

条件：[]

证据：

- `page_text[3672:3685]`：Discoloration
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[799:809]`：APPEARANCE
- `page_text[3809:3963]`：(Moderate discoloration of balls and races not a reason for discard).

## VR03:A024 · E1 · MP018:p0026

原始：Inadequate lubrication — causes → Discoloration

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 变色的负向废弃依据以独立要求附存，不冒作原因成立的前提。

修复：Inadequate lubrication — causes → Discoloration

条件：[]

证据：

- `page_text[3672:3685]`：Discoloration
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE
- `page_text[3809:3963]`：(Moderate discoloration of balls and races not a reason for discard).

## VR03:A025 · E1 · MP018:p0026

原始：Corrosion — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Corrosion — occurs_at → bearing

条件：[]

证据：

- `page_text[4099:4108]`：Corrosion
- `page_text[458:473]`：BEARING DEFECTS

## VR03:A026 · E1 · MP018:p0026

原始：Corrosion — manifests_as → Balls and raceways rusted.

裁定：representation_error。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。

修复：Corrosion — manifests_as → Balls and raceways rusted.

条件：[]

证据：

- `page_text[4099:4108]`：Corrosion
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[799:809]`：APPEARANCE

## VR03:A027 · E1 · MP018:p0026

原始：Water entering the housing — causes → Corrosion

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Water entering the housing — causes → Corrosion

条件：[]

证据：

- `page_text[4099:4108]`：Corrosion
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A028 · E1 · MP018:p0026

原始：Condensation inside the housing — causes → Corrosion

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Condensation inside the housing — causes → Corrosion

条件：[]

证据：

- `page_text[4099:4108]`：Corrosion
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR03:A029 · E1 · MP018:p0026

原始：Lubricant breaks down into acid. (Wrong lubricant) — causes → Corrosion

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Lubricant breaks down into acid. (Wrong lubricant) — causes → Corrosion

条件：[]

证据：

- `page_text[4099:4108]`：Corrosion
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR04:A001 · E1 · MP015:p0039

原始：tolerance ring (1880) — located_in → pump shaft (2200)

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：tolerance ring (1880) — maintained_by → Place the tolerance ring (1880) into the shaft recess of the pump shaft (2200).

条件：["7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 1; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[689:768]`：Place the tolerance ring (1880) into the shaft recess of the pump shaft (2200).

## VR04:A002 · E1 · MP015:p0039

原始：tolerance ring — mitigated_by → apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

裁定：representation_error。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：tolerance ring — maintained_by → For bronze and stainless steel pumps the tolerance ring must be isolated from the liquid. In order to do this apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

条件：["For bronze and stainless steel pumps", "7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[794:1063]`：For bronze and stainless steel pumps the tolerance ring must be isolated from the liquid. In order to do this apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

## VR04:A003 · E1 · MP015:p0039

原始：impeller — maintained_by → Push the impeller over the tolerance ring onto the shaft. Make sure its position is square with the shaft!

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller — maintained_by → Push the impeller over the tolerance ring onto the shaft. Make sure its position is square with the shaft!

条件：["7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 3; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[1099:1230]`：Push the impeller over the tolerance ring onto the shaft. Make sure its position is square with the shaft!

## VR04:A004 · E1 · MP015:p0039

原始：impeller bolt and spring washer (1825) — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller bolt and spring washer (1825)

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller bolt and spring washer (1825) — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller bolt and spring washer (1825). See chapter 10 "Technical data" for the correct fastening moment.

条件：["7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 4; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1374:1492]`：Put a drop of Loctite 243 on the thread and mount the impeller bolt and spring washer (1825).
- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[1374:1558]`：Put a drop of Loctite 243 on the thread and mount the impeller bolt and spring washer (1825). See chapter 10 "Technical data" for the correct fastening moment.

## VR04:A005 · E1 · MP015:p0039

原始：fastening moment — specified_by → chapter 10 "Technical data"

裁定：representation_error。chapter 10 是紧固力矩的外部规范引用，Standard 不能作为该关系主体；未编造力矩数值。

修复：impeller bolt and spring washer (1825) — specified_by → chapter 10 "Technical data"

条件：["7.6.4 assembly; torque value must be read from chapter 10"]

证据：

- `page_text[1493:1558]`：See chapter 10 "Technical data" for the correct fastening moment.

## VR04:A006 · E1 · MP015:p0039

原始：Back Pull Out-unit — maintained_by → Remove the Back Pull Out-unit, see paragraph 7.5.2 "Disassembly Back Pull Out-unit".

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：Back Pull Out-unit — maintained_by → Remove the Back Pull Out-unit, see paragraph 7.5.2 "Disassembly Back Pull Out- unit".

条件：["7.6.5 Disassembly of the impeller, other bearing brackets", "source procedure step 1; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1576:1633]`：7.6.5 Disassembly of the impeller, other bearing brackets
- `page_text[1667:1777]`：Remove the Back Pull Out-unit, see paragraph 7.5.2 "Disassembly Back Pull Out- unit".

## VR04:A007 · E1 · MP015:p0039

原始：locking ring (1825) — maintained_by → Tap the lips of the locking ring (1825) straight.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：locking ring (1825) — maintained_by → Bearing bracket 4: Tap the lips of the locking ring (1825) straight.

条件：["Bearing bracket 4", "7.6.5 Disassembly of the impeller, other bearing brackets", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1576:1633]`：7.6.5 Disassembly of the impeller, other bearing brackets
- `page_text[1854:1922]`：Bearing bracket 4: Tap the lips of the locking ring (1825) straight.

## VR04:A008 · E1 · MP015:p0039

原始：impeller nut or the impeller bolt (1820) — maintained_by → Disassemble the impeller nut or the impeller bolt (1820).

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller nut or the impeller bolt (1820) — maintained_by → Disassemble the impeller nut or the impeller bolt (1820).

条件：["7.6.5 Disassembly of the impeller, other bearing brackets", "source procedure step 3; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1576:1633]`：7.6.5 Disassembly of the impeller, other bearing brackets
- `page_text[2031:2088]`：Disassemble the impeller nut or the impeller bolt (1820).

## VR04:A009 · E1 · MP015:p0039

原始：washer (1830) — maintained_by → Remove the washer (1830).

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：washer (1830) — maintained_by → Bearing brackets 2 and 3: Remove the washer (1830).

条件：["Bearing brackets 2 and 3", "7.6.5 Disassembly of the impeller, other bearing brackets", "source procedure step 4; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1576:1633]`：7.6.5 Disassembly of the impeller, other bearing brackets
- `page_text[2114:2165]`：Bearing brackets 2 and 3: Remove the washer (1830).

## VR04:A010 · E1 · MP015:p0039

原始：impeller (0120) — maintained_by → Pull the impeller (0120) off the pump shaft, using a proper puller.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller (0120) — maintained_by → Pull the impeller (0120) off the pump shaft, using a proper puller.

条件：["7.6.5 Disassembly of the impeller, other bearing brackets", "source procedure step 5; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1576:1633]`：7.6.5 Disassembly of the impeller, other bearing brackets
- `page_text[2197:2264]`：Pull the impeller (0120) off the pump shaft, using a proper puller.

## VR04:A011 · E1 · MP015:p0039

原始：impeller nut (1860) — maintained_by → Remove the impeller nut (1860) from the pump shaft.

裁定：unresolved。1860 在相邻程序同时称 nut/key，保留原文不自行改件号/对象；等待部件图或专家裁定。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[2290:2341]`：Remove the impeller nut (1860) from the pump shaft.

## VR04:A012 · E1 · MP015:p0039

原始：impeller key (1860) — located_in → pump shaft (2200)

裁定：unresolved。1860 在相邻程序同时称 nut/key，保留原文不自行改件号/对象；等待部件图或专家裁定。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[2539:2611]`：Place the impeller key (1860) into the key way of the pump shaft (2200).

## VR04:A013 · E1 · MP015:p0039

原始：impeller — maintained_by → Slide the impeller onto the pump shaft.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller — maintained_by → Slide the impeller onto the pump shaft.

条件：["7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[2637:2676]`：Slide the impeller onto the pump shaft.

## VR04:A014 · E1 · MP015:p0039

原始：washer (1830) — maintained_by → Fit the washer (1830).

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：washer (1830) — maintained_by → Bearing brackets 2 and 3: Fit the washer (1830).

条件：["Bearing brackets 2 and 3", "7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 3; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[2803:2851]`：Bearing brackets 2 and 3: Fit the washer (1830).

## VR04:A015 · E1 · MP015:p0039

原始：locking ring (1825) — maintained_by → Fit the locking ring (1825).

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：locking ring (1825) — maintained_by → Bearing bracket 4: Fit the locking ring (1825).

条件：["Bearing bracket 4", "7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 4; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[2886:2933]`：Bearing bracket 4: Fit the locking ring (1825).

## VR04:A016 · E1 · MP015:p0039

原始：thread of the pump shaft and impeller nut (1820) or impeller bolt (1820) — maintained_by → Degrease the thread of the pump shaft and impeller nut (1820) or impeller bolt (1820).

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：thread of the pump shaft and impeller nut (1820) or impeller bolt (1820) — maintained_by → Degrease the thread of the pump shaft and impeller nut (1820) or impeller bolt (1820).

条件：["7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 5; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[2969:3080]`：Degrease the thread of the pump shaft and impeller nut (1820) or impeller bolt (1820).

## VR04:A017 · E1 · MP015:p0039

原始：impeller nut or impeller bolt — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller nut or impeller bolt.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller nut or impeller bolt — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller nut or impeller bolt. See chapter 10 "Technical data" for the correct fastening moment.

条件：["7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 6; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[3156:3240]`：Put a drop of Loctite 243 on the thread and mount the impeller nut or impeller bolt.
- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[3156:3331]`：Put a drop of Loctite 243 on the thread and mount the impeller nut or impeller bolt. See chapter 10 "Technical data" for the correct fastening moment.

## VR04:A018 · E1 · MP015:p0039

原始：fastening moment — specified_by → chapter 10 "Technical data"

裁定：representation_error。chapter 10 是紧固力矩的外部规范引用，Standard 不能作为该关系主体；未编造力矩数值。

修复：impeller nut or impeller bolt (1820) — specified_by → chapter 10 "Technical data"

条件：["7.6.6 assembly; torque value must be read from chapter 10"]

证据：

- `page_text[1493:1558]`：See chapter 10 "Technical data" for the correct fastening moment.

## VR04:A019 · E1 · MP015:p0039

原始：locking ring (1825) — maintained_by → Tap the edges of the locking ring (1825) into the recesses of the pump shaft and the impeller nut or the impeller bolt.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：locking ring (1825) — maintained_by → Bearing bracket 4: Tap the edges of the locking ring (1825) into the recesses of the pump shaft and the impeller nut or the impeller bolt.

条件：["Bearing bracket 4", "7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 7; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[3357:3520]`：Bearing bracket 4: Tap the edges of the locking ring (1825) into the recesses of the pump shaft and the impeller nut or the impeller bolt.

## VR04:A020 · E1 · MP015:p0039

原始：wear plate — maintained_by → After disassembly of the Back Pull Out unit the wear plate can be removed.

裁定：complete。Back Pull Out 拆除后耐磨板可拆的高层前提有原文；不当成已包含所有螺钉/刀片步骤。

修复：wear plate — maintained_by → After disassembly of the Back Pull Out unit the wear plate can be removed.

条件：["After disassembly of the Back Pull Out unit"]

证据：

- `page_text[3714:3788]`：After disassembly of the Back Pull Out unit the wear plate can be removed.

## VR04:A021 · E1 · MP015:p0039

原始：screws (0115) — maintained_by → Loosen the screws (0115).

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：screws (0115) — maintained_by → Loosen the screws (0115).

条件：["7.6.7 Disassembly of the wear plate", "source procedure step 1; previous applicable steps/order retained; this is not a complete procedure", "after disassembly of the Back Pull Out unit; item numbers refer to figure 55"]

证据：

- `page_text[3625:3660]`：7.6.7 Disassembly of the wear plate
- `page_text[3906:3931]`：Loosen the screws (0115).
- `page_text[3714:3848]`：After disassembly of the Back Pull Out unit the wear plate can be removed. The item numbers refer to figure 55.

## VR04:A022 · E1 · MP015:p0039

原始：wear plate (0125) — maintained_by → Remove the wear plate (0125) from the pump casing, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：wear plate (0125) — maintained_by → Remove the wear plate (0125) from the pump casing, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism.

条件：["7.6.7 Disassembly of the wear plate", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure", "after disassembly of the Back Pull Out unit; item numbers refer to figure 55"]

证据：

- `page_text[3625:3660]`：7.6.7 Disassembly of the wear plate
- `page_text[3989:4159]`：Remove the wear plate (0125) from the pump casing, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism.
- `page_text[3714:3848]`：After disassembly of the Back Pull Out unit the wear plate can be removed. The item numbers refer to figure 55.

## VR04:A023 · E1 · MP015:p0039

原始：edge of the pump casing — maintained_by → Clean the edge of the pump casing where the wear plate has to be fitted.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：edge of the pump casing — maintained_by → Clean the edge of the pump casing where the wear plate has to be fitted.

条件：["7.6.8 Assembly of the wear plate", "source procedure step 1; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[4260:4292]`：7.6.8 Assembly of the wear plate
- `page_text[4351:4423]`：Clean the edge of the pump casing where the wear plate has to be fitted.

## VR04:A024 · E1 · MP015:p0039

原始：wear plate — maintained_by → Fit the wear plate, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism, in the pump casing. When doing this, make sure that it is not pushed out of alignment. Pay attention to the position of the holes.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：wear plate — maintained_by → Fit the wear plate, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism, in the pump casing. When doing this, make sure that it is not pushed out of alignment. Pay attention to the position of the holes.

条件：["7.6.8 Assembly of the wear plate", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[4260:4292]`：7.6.8 Assembly of the wear plate
- `page_text[4449:4744]`：Fit the wear plate, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism, in the pump casing. When doing this, make sure that it is not pushed out of alignment. Pay attention to the position of the holes.

## VR04:A025 · E1 · MP015:p0039

原始：wear plate — maintained_by → Tighten the wear plate with screws (0115). For this use Loctite 243 to lock the screws.

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：wear plate — maintained_by → Tighten the wear plate with screws (0115). For this use Loctite 243 to lock the screws.

条件：["7.6.8 Assembly of the wear plate", "source procedure step 3; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[4260:4292]`：7.6.8 Assembly of the wear plate
- `page_text[4770:4882]`：Tighten the wear plate with screws (0115). For this use Loctite 243 to lock the screws.

## VR05:A001 · E0 · MP007:p0012

原始：vacuum valve — located_in → pump

裁定：semantic_error。near 不等于 located_in；one of 表示任一条件，不能暗作三个同时满足。

修复：转 `installation_requirement` 旁路；要求=见原文及条件。

证据：

- `MP007:p0012:t00:r000:c02[0:269]`：If your installation is characterized by one of following features, please install one vacuum valve near the pump. ● The discharge pipe is sloped downwards in the direction of leaving the pump. ● Siphonage may occur. ● It is necessary to stop backflow of unclean water.

## VR05:A002 · E0 · MP007:p0012

原始：dry running — causes → pump bearing and shaft seal will be damaged

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：dry running — causes → pump bearing and shaft seal will be damaged

条件：[]

证据：

- `page_text[1635:2010]`：Caution: Do not start the pump before water is filled and air is discharged. In case of dry running, pump bearing and shaft seal will be damaged. When discharging air, pay attention that water drained shall not injure people or damage objects, especially avoid scalding by sprayed hot water when it is used to convey hot water.

## VR05:A003 · E0 · MP007:p0012

原始：dry running — occurs_at → pump

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：dry running — occurs_at → pump

条件：[]

证据：

- `page_text[1635:1796]`：Caution: Do not start the pump before water is filled and air is discharged. In case of dry running, pump bearing and shaft seal will be damaged.

## VR05:A004 · E0 · MP007:p0012

原始：pump bearing — located_in → pump

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：pump bearing — located_in → pump

条件：[]

证据：

- `page_text[1712:1796]`：In case of dry running, pump bearing and shaft seal will be damaged.

## VR05:A005 · E0 · MP007:p0012

原始：shaft seal — located_in → pump

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：shaft seal — located_in → pump

条件：[]

证据：

- `page_text[1712:1796]`：In case of dry running, pump bearing and shaft seal will be damaged.

## VR05:A006 · E0 · MP007:p0012

原始：Do not start the pump before water is filled and air is discharged — prevented_by → dry running

裁定：semantic_error。禁止未灌水排气启动，不可逆写动作 prevented_by 干运转。

修复：转 `operating_prohibition` 旁路；要求=prohibited_before_filling_and_venting。

证据：

- `page_text[1635:1796]`：Caution: Do not start the pump before water is filled and air is discharged. In case of dry running, pump bearing and shaft seal will be damaged.

## VR05:A007 · E0 · MP007:p0012

原始：motor — contains → heat protector

裁定：complete。单相电机有内部热保护器，原条件已存。

修复：motor — contains → heat protector

条件：["One-phase motor"]

证据：

- `page_text[2416:2581]`：One-phase motor is provided with a heat protector inside while three-phase motor shall be provided with a three-phase protector before installation.

## VR05:A008 · E0 · MP007:p0012

原始：three-phase motor — maintained_by → shall be provided with a three-phase protector before installation

裁定：representation_error。电气安装配置与接地要求单列，不强写为检修保养。

修复：转 `electrical_requirement` 旁路；要求=见原文及条件。

证据：

- `page_text[2479:2581]`：three-phase motor shall be provided with a three-phase protector before installation.

## VR05:A009 · E0 · MP007:p0012

原始：motor — maintained_by → reliable earthing

裁定：representation_error。电气安装配置与接地要求单列，不强写为检修保养。

修复：转 `electrical_requirement` 旁路；要求=见原文及条件。

证据：

- `page_text[2141:2192]`：The motor shall be provided with reliable earthing.

## VR05:A010 · E0 · MP007:p0012

原始：Check if foot bolts are tightened — inspected_by → pump

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：foot bolts — inspected_by → check foot bolts are tightened

条件：["before pump startup"]

证据：

- `page_text[2774:2811]`：• Check if foot bolts are tightened.
- `page_text[2691:2720]`：7.2 CHECK BEFORE PUMP STARTUP

## VR05:A011 · E0 · MP007:p0012

原始：If the pump is full of water or not — inspected_by → pump

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：pump — inspected_by → check full of water

条件：["before pump startup"]

证据：

- `page_text[2857:2896]`：• If the pump is full of water or not.
- `page_text[2691:2720]`：7.2 CHECK BEFORE PUMP STARTUP

## VR05:A012 · E0 · MP007:p0012

原始：If the rotating direction is correct or not — inspected_by → pump

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：pump — inspected_by → check direction of rotation

条件：["before pump startup"]

证据：

- `page_text[3023:3070]`：• If the rotating direction is correct or not.
- `page_text[2691:2720]`：7.2 CHECK BEFORE PUMP STARTUP

## VR05:A013 · E0 · MP007:p0012

原始：If valves on inlet pipes are completely opened or not — inspected_by → inlet pipes

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：valves on inlet pipes — inspected_by → check completely opened

条件：["before pump startup"]

证据：

- `page_text[3272:3412]`：• If valves on inlet pipes are completely opened or not. The outlet valve shall be opened slowly after the pump is started up.
- `page_text[2691:2720]`：7.2 CHECK BEFORE PUMP STARTUP

## VR05:A014 · E0 · MP007:p0012

原始：Check working pressure if a pressure meter is installed — inspected_by → pressure meter

裁定：semantic_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：working pressure — diagnosed_by → check working pressure using an installed pressure meter

条件：["before pump startup", "if a pressure meter is installed"]

证据：

- `page_text[3456:3515]`：• Check working pressure if a pressure meter is installed.
- `page_text[2691:2720]`：7.2 CHECK BEFORE PUMP STARTUP

## VR05:A015 · E0 · MP007:p0012

原始：outlet valve — maintained_by → shall be opened slowly after the pump is started up

裁定：representation_error。启动后慢开出口阀是运行操作，保留 after 覆盖章节 before 的局部时序。

修复：转 `operating_procedure` 旁路；要求=见原文及条件。

证据：

- `page_text[3330:3412]`：The outlet valve shall be opened slowly after the pump is started up.

## VR05:A016 · E0 · MP007:p0012

原始：scalding by sprayed hot water — increases_risk_of → convey hot water

裁定：semantic_error。烫伤/物料受损与热水工况方向倒置，保留排气安全警示，不补造设备故障边。

修复：转 `safety_requirement` 旁路；要求=见原文及条件。

证据：

- `page_text[1911:2010]`：especially avoid scalding by sprayed hot water when it is used to convey hot water.

## VR05:A017 · E0 · MP007:p0012

原始：damage to materials at the outlet caused by the liquid flowing at a high speed — increases_risk_of → convey hot water

裁定：semantic_error。烫伤/物料受损与热水工况方向倒置，保留排气安全警示，不补造设备故障边。

修复：转 `safety_requirement` 旁路；要求=见原文及条件。

证据：

- `page_text[4670:4822]`：especially avoid damage to materials at the outlet caused by the liquid flowing at a high speed when it is used to convey hot water.

## VR06:A001 · E1 · MP004:p0010

原始：self-priming centrifugal pump — operates_under → pump casing has been filled with liquid

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：self-priming centrifugal pump — operates_under → pump casing has been filled with liquid

条件：[]

证据：

- `page_text[604:737]`：A self-priming centrifugal pump will not function until the pump casing has been filled with liquid.

## VR06:A002 · E1 · MP004:p0010

原始：plug at the top of the pump casing — located_in → pump casing

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：plug at the top of the pump casing — located_in → pump casing

条件：[]

证据：

- `page_text[738:933]`：Remove the plug at the top of the pump casing and fill the pump with cold liquid. Fit the plug and the pump is ready for service.

## VR06:A003 · E1 · MP004:p0010

原始：liquid — causes → coolant for the shaft seal

裁定：representation_error。液体用作冷却介质，不是 liquid causes coolant 的因果关系。

修复：转 `operating_mechanism` 旁路；要求=见原文及条件。

证据：

- `page_text[972:1025]`：The liquid also serves as coolant for the shaft seal.

## VR06:A004 · E1 · MP004:p0010

原始：shaft seal — contains → coolant

裁定：semantic_error。作为冷却介质不证明轴封结构包含 coolant；保留功能原文。

修复：转 `operating_mechanism` 旁路；要求=见原文及条件。

证据：

- `page_text[972:1025]`：The liquid also serves as coolant for the shaft seal.

## VR06:A005 · E1 · MP004:p0010

原始：started before it has been primed with liquid — increases_risk_of → damage to the shaft seal

裁定：unresolved。本页明确禁止未灌液/干转，具体 shaft seal/pump 损伤端点未直接给出，不以常识补真值。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[1026:1358]`：Consequently, the pump must under no circumstances be started before it has been primed with liquid. Furthermore, the pump must never run dry.

## VR06:A006 · E1 · MP004:p0010

原始：run dry — increases_risk_of → damage to the pump

裁定：unresolved。本页明确禁止未灌液/干转，具体 shaft seal/pump 损伤端点未直接给出，不以常识补真值。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[1223:1358]`：Furthermore, the pump must never run dry.

## VR06:A007 · E1 · MP004:p0010

原始：operate against closed discharge valve — increases_risk_of → damage to the pump

裁定：incomplete。最大允许值不是危险发生条件；补 otherwise 的超限逻辑，5分钟或80°C任一越界，不改成AND。

修复：operate against closed discharge valve — increases_risk_of → damage to the pump

条件：["closed discharge valve operation", "duration exceeds 5 minutes OR liquid temperature exceeds 80°C (standard pumps)"]

证据：

- `page_text[1668:1942]`：For safety reasons the pump is only allowed to operate against closed discharge valve for a short time (max. 5 minutes and at a max. temperature of 80°C for standard pumps). Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.

## VR06:A008 · E1 · MP004:p0010

原始：operate against closed discharge valve — increases_risk_of → steam explosion

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：operate against closed discharge valve — increases_risk_of → steam explosion

条件：["exceeds max. 5 minutes or max. temperature of 80°C for standard pumps"]

证据：

- `page_text[1850:1942]`：Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.

## VR06:A009 · E1 · MP004:p0010

原始：pump is not monitored — mitigated_by → installation of a safety device

裁定：representation_error。安全装置安装用于降低前述损坏/蒸汽爆炸风险；保留无人监控与 recommended，不声称确定消除风险。

修复：damage or steam-explosion risk during closed-discharge operation — prevented_by → installation of a safety device

条件：["pump is not monitored", "closed discharge valve operation"]

证据：

- `page_text[1668:1942]`：For safety reasons the pump is only allowed to operate against closed discharge valve for a short time (max. 5 minutes and at a max. temperature of 80°C for standard pumps). Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.
- `page_text[1943:2032]`：If the pump is not monitored, the installation of a safety device is recommended.

## VR06:A010 · E1 · MP004:p0010

原始：relief valve — located_in → pump

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：relief valve — located_in → pump

条件：[]

证据：

- `page_text[2151:2280]`：To protect the pump against unintentional operation it is equipped with a relief valve which opens at a pre-set pressure.

## VR06:A011 · E1 · MP004:p0010

原始：unintentional operation — mitigated_by → relief valve which opens at a pre-set pressure

裁定：representation_error。泄压阀装置及预设压力保护功能不是维护动作，保留功能与阈值未给定。

修复：转 `protective_function` 旁路；要求=见原文及条件。

证据：

- `page_text[2151:2280]`：To protect the pump against unintentional operation it is equipped with a relief valve which opens at a pre-set pressure.

## VR06:A012 · E1 · MP004:p0010

原始：relief valve — maintained_by → see paragraph 10

裁定：representation_error。仅有维护章节交叉引用，尚无具体维护动作。

修复：转 `cross_reference` 旁路；要求=见原文及条件。

证据：

- `page_text[2507:2569]`：As regards maintenance of the relief valve - see paragraph 10.

## VR06:A013 · E1 · MP004:p0010

原始：removed or re-adjusted — mitigated_by → must in no circumstances be removed or re-adjusted

裁定：semantic_error。禁止拆除/重调应为 prohibited 要求，不是缓解动作本身。

修复：转 `maintenance_requirement` 旁路；要求=prohibited。

证据：

- `page_text[2424:2493]`：The relief valve must in no circumstances be removed or re-adjusted !

## VR06:A014 · E1 · MP004:p0010

原始：shaft rotates freely without jarring sounds — inspected_by → check that the shaft rotates freely without jarring sounds

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：shaft — inspected_by → check that the shaft rotates freely without jarring sounds

条件：["Before starting the pump"]

证据：

- `page_text[2839:3057]`：Before starting the pump check that - the shaft rotates freely without jarring sounds.

## VR06:A015 · E1 · MP004:p0010

原始：pump casing is filled with liquid — inspected_by → check that the pump casing is filled with liquid

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：pump casing — inspected_by → check that the pump casing is filled with liquid

条件：["Before starting the pump"]

证据：

- `page_text[2839:2874]`：Before starting the pump check that
- `page_text[3090:3130]`：- the pump casing is filled with liquid.

## VR06:A016 · E1 · MP004:p0010

原始：direction of rotation — diagnosed_by → Start the pump for a moment to check the direction of rotation

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：pump — inspected_by → start briefly to check direction of rotation

条件：["brief check before continued startup", "continue only when direction agrees with arrow"]

证据：

- `page_text[3171:3333]`：Start the pump for a moment to check the direction of rotation. If the direction is correct (i.e. in the direction of the arrow), the pump may be started.

## VR06:A017 · E1 · MP004:p0010

原始：considerably smaller delivery head than expected — causes → increase the quantity of liquid delivered

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：considerably smaller delivery head than expected — causes → increase the quantity of liquid delivered

条件：[]

证据：

- `page_text[3974:4159]`：A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.

## VR06:A018 · E1 · MP004:p0010

原始：considerably smaller delivery head than expected — causes → increased power consumption

裁定：representation_error。原文为低扬程→流量增加→功耗/可能汽蚀；保存相邻因果边，不将传递路径冒作直接边。

修复：increased quantity of liquid delivered — causes → increased power consumption

条件：["considerably smaller delivery head than expected"]

证据：

- `page_text[3974:4159]`：A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.

## VR06:A019 · E1 · MP004:p0010

原始：considerably smaller delivery head than expected — causes → cavitation in pump and piping

裁定：representation_error。原文为低扬程→流量增加→功耗/可能汽蚀；保存相邻因果边，不将传递路径冒作直接边。

修复：increased quantity of liquid delivered — causes → cavitation in pump and piping

条件：["considerably smaller delivery head than expected"]

证据：

- `page_text[3974:4159]`：A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.

## VR06:A020 · E1 · MP004:p0010

原始：cavitation — occurs_at → pump

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：cavitation — occurs_at → pump

条件：[]

证据：

- `page_text[4121:4159]`：perhaps cavitation in pump and piping.

## VR06:A021 · E1 · MP004:p0010

原始：cavitation — occurs_at → piping

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：cavitation — occurs_at → piping

条件：[]

证据：

- `page_text[4121:4159]`：perhaps cavitation in pump and piping.

## VR06:A022 · E1 · MP004:p0010

原始：cavitation (corrosion) — manifests_as → heavy erosion

裁定：representation_error。源文明说 erosion caused by cavitation；保留 impeller 和 may，不当必然，也不把表现关系当因果边。

修复：cavitation (corrosion) — causes → heavy erosion of the impeller

条件：["in the pump impeller"]

证据：

- `page_text[4160:4339]`：In the pump the impeller may show signs of heavy erosion caused by cavitation (corrosion) which may at times render an impeller unfit for use in a very short time.

## VR06:A023 · E1 · MP004:p0010

原始：cavitation (corrosion) — occurs_at → impeller

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：cavitation (corrosion) — occurs_at → impeller

条件：[]

证据：

- `page_text[4160:4339]`：In the pump the impeller may show signs of heavy erosion caused by cavitation (corrosion) which may at times render an impeller unfit for use in a very short time.

## VR06:A024 · E1 · MP004:p0010

原始：heavy erosion caused by cavitation (corrosion) — evolves_to → render an impeller unfit for use

裁定：complete。对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。

修复：heavy erosion caused by cavitation (corrosion) — evolves_to → render an impeller unfit for use

条件：["at times", "in a very short time"]

证据：

- `page_text[4258:4339]`：which may at times render an impeller unfit for use in a very short time.

## VR06:A025 · E1 · MP004:p0010

原始：similar erosions — occurs_at → pipe bends and valves elsewhere in the piping system

裁定：representation_error。侵蚀发生于弯管和阀门有支持；发生位置关系的主体需为故障/机理而非 Symptom。

修复：similar erosions — occurs_at → pipe bends and valves elsewhere in the piping system

条件：[]

证据：

- `page_text[4340:4444]`：Not unusually do similar erosions occur in pipe bends and valves elsewhere in the piping system.

## VR06:A026 · E1 · MP004:p0010

原始：quantity of liquid delivered or the power consumption of the pump — inspected_by → check either the quantity of liquid delivered or the power consumption of the pump e.g. by measuring the current intensity of the connected motor

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：power consumption of the pump — diagnosed_by → measuring current intensity of the connected motor

条件：["after start-up; example method, not accuracy guarantee"]

证据：

- `page_text[4479:4679]`：Therefore, after start-up, it is necessary to check either the quantity of liquid delivered or the power consumption of the pump e.g. by measuring the current intensity of the connected motor.

## VR06:A027 · E1 · MP004:p0010

原始：quantity of water delivered — diagnosed_by → reading of the differential pressure

裁定：unresolved。流量、功率、电流、压差和泵曲线的联合测定句法尚未裁定；不把缺失测量链强行补全。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[4680:4839]`：Together with a reading of the differential pressure the quantity of water delivered can be determined against the characteristics of the pump.

## VR06:A028 · E1 · MP004:p0010

原始：pump not function as intended — diagnosed_by → proceed according to the fault-finding list

裁定：representation_error。仅指向未在本页给出的 fault-finding list；保持交叉引用，不充作具体诊断方法。

修复：转 `cross_reference` 旁路；要求=见原文及条件。

证据：

- `page_text[4890:4983]`：Should the pump not function as intended, please proceed according to the fault-finding list.

## VR07:A001 · E0 · MP018:p0026

原始：Flaking and cracking — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Flaking and cracking — occurs_at → bearing

条件：[]

证据：

- `page_text[939:959]`：Flaking and cracking
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A002 · E0 · MP018:p0026

原始：Flaking and cracking — manifests_as → In the early stages the surfaces of the inner and outer races develop small cracks, which flake. The cracks and flaking ultimately spread over the entire race surface.

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Flaking and cracking — manifests_as → In the early stages the surfaces of the inner and outer races develop small cracks, which flake. The cracks and flaking ultimately spread over the entire race surface.

条件：[]

证据：

- `MP018:p0026:t00:r001:c01[0:167]`：In the early stages the surfaces of the inner and outer races develop small cracks, which flake. The cracks and flaking ultimately spread over the entire race surface.
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A003 · E0 · MP018:p0026

原始：Normal fatigue failure — causes → Flaking and cracking

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Normal fatigue failure — causes → Flaking and cracking

条件：[]

证据：

- `page_text[1006:1032]`：1. Normal fatigue failure.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A004 · E0 · MP018:p0026

原始：Bearing loads in excess of bearing capacity caused by misalignment — causes → Flaking and cracking

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Bearing loads in excess of bearing capacity caused by misalignment — causes → Flaking and cracking

条件：[]

证据：

- `MP018:p0026:t00:r001:c02[27:97]`：2. Bearing loads in excess of bearing capacity caused by misalignment.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A005 · E0 · MP018:p0026

原始：Indentations — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Indentations — occurs_at → bearing

条件：[]

证据：

- `page_text[1562:1574]`：Indentations
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A006 · E0 · MP018:p0026

原始：Indentations — manifests_as → Indentations or cavities in the inner and outer races.

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Indentations — manifests_as → Indentations or cavities in the inner and outer races.

条件：[]

证据：

- `MP018:p0026:t00:r002:c01[0:54]`：Indentations or cavities in the inner and outer races.
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A007 · E0 · MP018:p0026

原始：Dirt in the bearings — causes → Indentations

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Dirt in the bearings — causes → Indentations

条件：[]

证据：

- `page_text[1631:1655]`：1. Dirt in the bearings.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A008 · E0 · MP018:p0026

原始：Excessive impact loading of the bearing, such as improper mounting or removal — causes → Indentations

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Excessive impact loading of the bearing, such as improper mounting or removal — causes → Indentations

条件：[]

证据：

- `page_text[1797:1993]`：2. Excessive impact loading of the bearing, such as improper mounting or removal.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A009 · E0 · MP018:p0026

原始：Broken Separator (cage) — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Broken Separator (cage) — occurs_at → bearing

条件：[]

证据：

- `page_text[2091:2114]`：Broken Separator (cage)
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A010 · E0 · MP018:p0026

原始：Broken Separator (cage) — manifests_as → Cracked separator or separator in pieces.

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Broken Separator (cage) — manifests_as → Cracked separator or separator in pieces.

条件：[]

证据：

- `page_text[2115:2156]`：Cracked separator or separator in pieces.
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A011 · E0 · MP018:p0026

原始：Poor lubrication — causes → Broken Separator (cage)

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Poor lubrication — causes → Broken Separator (cage)

条件：[]

证据：

- `page_text[2157:2177]`：1. Poor lubrication.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A012 · E0 · MP018:p0026

原始：Misalignment of the shaft — causes → Broken Separator (cage)

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Misalignment of the shaft — causes → Broken Separator (cage)

条件：[]

证据：

- `page_text[2319:2348]`：2. Misalignment of the shaft.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A013 · E0 · MP018:p0026

原始：Excessive shaft deflection — causes → Broken Separator (cage)

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Excessive shaft deflection — causes → Broken Separator (cage)

条件：[]

证据：

- `page_text[2490:2520]`：3. Excessive shaft deflection.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A014 · E0 · MP018:p0026

原始：Wear — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Wear — occurs_at → bearing

条件：[]

证据：

- `page_text[2610:2614]`：Wear
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A015 · E0 · MP018:p0026

原始：Wear — manifests_as → Bore and OD of outer ring of bearing galled or braided.

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Wear — manifests_as → Bore and OD of outer ring of bearing galled or braided.

条件：[]

证据：

- `MP018:p0026:t00:r004:c01[0:55]`：Bore and OD of outer ring of bearing galled or braided.
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A016 · E0 · MP018:p0026

原始：Fit on the shaft or in housing too loose — causes → Wear

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Fit on the shaft or in housing too loose — causes → Wear

条件：[]

证据：

- `MP018:p0026:t00:r004:c02[0:44]`：1. Fit on the shaft or in housing too loose.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A017 · E0 · MP018:p0026

原始：Bearing locked by dirt and turning of shaft or in housing — causes → Wear

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Bearing locked by dirt and turning of shaft or in housing — causes → Wear

条件：[]

证据：

- `page_text[2942:3060]`：2. Bearing locked by dirt and turning of shaft or in housing.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A018 · E0 · MP018:p0026

原始：Fractured Ring — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Fractured Ring — occurs_at → bearing

条件：[]

证据：

- `page_text[3235:3249]`：Fractured Ring
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A019 · E0 · MP018:p0026

原始：Fractured Ring — manifests_as → Hairline cracks or complete fracture.

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Fractured Ring — manifests_as → Hairline cracks or complete fracture.

条件：[]

证据：

- `page_text[3256:3293]`：Hairline cracks or complete fracture.
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A020 · E0 · MP018:p0026

原始：Forcing a cocked bearing on or off a shaft — causes → Fractured Ring

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Forcing a cocked bearing on or off a shaft — causes → Fractured Ring

条件：[]

证据：

- `page_text[3294:3398]`：1. Forcing a cocked bearing on or off a shaft.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A021 · E0 · MP018:p0026

原始：Too heavy a press fit — causes → Fractured Ring

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Too heavy a press fit — causes → Fractured Ring

条件：[]

证据：

- `page_text[3554:3579]`：2. Too heavy a press fit.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A022 · E0 · MP018:p0026

原始：Discoloration — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Discoloration — occurs_at → bearing

条件：[]

证据：

- `page_text[3672:3685]`：Discoloration
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A023 · E0 · MP018:p0026

原始：Discoloration — manifests_as → Balls and races darker than normal appearance of bearing metal. (Moderate discoloration of balls and races not a reason for discard).

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 变色的负向废弃依据以独立要求附存，不冒作原因成立的前提。

修复：Discoloration — manifests_as → Balls and races darker than normal appearance of bearing metal. (Moderate discoloration of balls and races not a reason for discard).

条件：[]

证据：

- `MP018:p0026:t00:r006:c01[0:133]`：Balls and races darker than normal appearance of bearing metal. (Moderate discoloration of balls and races not a reason for discard).
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[3809:3963]`：(Moderate discoloration of balls and races not a reason for discard).

## VR07:A024 · E0 · MP018:p0026

原始：Inadequate lubrication — causes → Discoloration

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 变色的负向废弃依据以独立要求附存，不冒作原因成立的前提。

修复：Inadequate lubrication — causes → Discoloration

条件：[]

证据：

- `page_text[3728:3754]`：1. Inadequate lubrication.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE
- `page_text[3809:3963]`：(Moderate discoloration of balls and races not a reason for discard).

## VR07:A025 · E0 · MP018:p0026

原始：Corrosion — occurs_at → bearing

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Corrosion — occurs_at → bearing

条件：[]

证据：

- `page_text[4099:4108]`：Corrosion
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A026 · E0 · MP018:p0026

原始：Corrosion — manifests_as → Balls and raceways rusted.

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Corrosion — manifests_as → Balls and raceways rusted.

条件：[]

证据：

- `page_text[4120:4146]`：Balls and raceways rusted.
- `page_text[458:473]`：BEARING DEFECTS

## VR07:A027 · E0 · MP018:p0026

原始：Water entering the housing — causes → Corrosion

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Water entering the housing — causes → Corrosion

条件：[]

证据：

- `page_text[4151:4181]`：1. Water entering the housing.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A028 · E0 · MP018:p0026

原始：Condensation inside the housing — causes → Corrosion

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Condensation inside the housing — causes → Corrosion

条件：[]

证据：

- `page_text[4323:4418]`：2. Condensation inside the housing.
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A029 · E0 · MP018:p0026

原始：Lubricant breaks down into acid. (Wrong lubricant). — causes → Corrosion

裁定：complete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。

修复：Lubricant breaks down into acid. (Wrong lubricant). — causes → Corrosion

条件：[]

证据：

- `page_text[4578:4690]`：3. Lubricant breaks down into acid. (Wrong lubricant).
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[826:840]`：PROBABLE CAUSE

## VR07:A030 · E0 · MP018:p0026

原始：BEARING DEFECTS — mitigated_by → Replace if Found

裁定：incomplete。依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。 全局更换标题保留例外；不从此条扩生成六条已匹配的具体更换边。

修复：BEARING DEFECTS — mitigated_by → Replace if Found

条件：["bearing defect found", "moderate discoloration of balls and races alone is not a reason for discard"]

证据：

- `page_text[458:655]`：BEARING DEFECTS (Failures – Replace if Found)
- `page_text[458:473]`：BEARING DEFECTS
- `page_text[3809:3963]`：(Moderate discoloration of balls and races not a reason for discard).

## VR08:A001 · E0 · MP004:p0010

原始：pump casing — contains → plug

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：pump casing — contains → plug

条件：[]

证据：

- `page_text[738:852]`：Remove the plug at the top of the pump casing and fill the pump with cold liquid.

## VR08:A002 · E0 · MP004:p0010

原始：shaft seal — located_in → self-priming centrifugal pump

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：shaft seal — located_in → self-priming centrifugal pump

条件：[]

证据：

- `page_text[972:1025]`：The liquid also serves as coolant for the shaft seal.

## VR08:A003 · E0 · MP004:p0010

原始：liquid — causes → coolant for the shaft seal

裁定：representation_error。液体用作冷却介质，不是 liquid causes coolant 的因果关系。

修复：转 `operating_mechanism` 旁路；要求=见原文及条件。

证据：

- `page_text[972:1025]`：The liquid also serves as coolant for the shaft seal.

## VR08:A004 · E0 · MP004:p0010

原始：started before it has been primed with liquid — increases_risk_of → damage to the shaft seal

裁定：unresolved。不得未灌液启动的警告未直接指明 damage to shaft seal，具体损伤目标是推断；保留未决。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[1026:1358]`：Consequently, the pump must under no circumstances be started before it has been primed with liquid. Furthermore, the pump must never run dry.

## VR08:A005 · E0 · MP004:p0010

原始：run dry — occurs_at → self-priming centrifugal pump

裁定：representation_error。negative occurs_at 不能表示不得干转；这是禁止运行要求。

修复：转 `operating_prohibition` 旁路；要求=prohibited。

证据：

- `page_text[1223:1358]`：Furthermore, the pump must never run dry.

## VR08:A006 · E0 · MP004:p0010

原始：operate against closed discharge valve — increases_risk_of → damage to the pump

裁定：incomplete。最大允许值不是危险发生条件；补 otherwise 的超限逻辑，5分钟或80°C任一越界，不改成AND。

修复：operate against closed discharge valve — increases_risk_of → damage to the pump

条件：["closed discharge valve operation", "duration exceeds 5 minutes OR liquid temperature exceeds 80°C (standard pumps)"]

证据：

- `page_text[1668:1942]`：For safety reasons the pump is only allowed to operate against closed discharge valve for a short time (max. 5 minutes and at a max. temperature of 80°C for standard pumps). Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.

## VR08:A007 · E0 · MP004:p0010

原始：operate against closed discharge valve — increases_risk_of → steam explosion

裁定：incomplete。最大允许值不是危险发生条件；补 otherwise 的超限逻辑，5分钟或80°C任一越界，不改成AND。

修复：operate against closed discharge valve — increases_risk_of → steam explosion

条件：["closed discharge valve operation", "duration exceeds 5 minutes OR liquid temperature exceeds 80°C (standard pumps)"]

证据：

- `page_text[1850:1942]`：Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.
- `page_text[1668:1942]`：For safety reasons the pump is only allowed to operate against closed discharge valve for a short time (max. 5 minutes and at a max. temperature of 80°C for standard pumps). Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.

## VR08:A008 · E0 · MP004:p0010

原始：safety device — mitigated_by → installation of a safety device

裁定：representation_error。安全装置安装用于降低前述损坏/蒸汽爆炸风险；保留无人监控与 recommended，不声称确定消除风险。

修复：damage or steam-explosion risk during closed-discharge operation — prevented_by → installation of a safety device

条件：["pump is not monitored", "closed discharge valve operation"]

证据：

- `page_text[1668:1942]`：For safety reasons the pump is only allowed to operate against closed discharge valve for a short time (max. 5 minutes and at a max. temperature of 80°C for standard pumps). Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.
- `page_text[1943:2032]`：If the pump is not monitored, the installation of a safety device is recommended.

## VR08:A009 · E0 · MP004:p0010

原始：relief valve — located_in → self-priming centrifugal pump

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：relief valve — located_in → self-priming centrifugal pump

条件：[]

证据：

- `page_text[2151:2280]`：To protect the pump against unintentional operation it is equipped with a relief valve which opens at a pre-set pressure.

## VR08:A010 · E0 · MP004:p0010

原始：unintentional operation — mitigated_by → relief valve

裁定：representation_error。泄压阀装置及预设压力保护功能不是维护动作，保留功能与阈值未给定。

修复：转 `protective_function` 旁路；要求=见原文及条件。

证据：

- `page_text[2151:2280]`：To protect the pump against unintentional operation it is equipped with a relief valve which opens at a pre-set pressure.

## VR08:A011 · E0 · MP004:p0010

原始：relief valve — maintained_by → maintenance of the relief valve - see paragraph 10

裁定：representation_error。仅有维护章节交叉引用，尚无具体维护动作。

修复：转 `cross_reference` 旁路；要求=见原文及条件。

证据：

- `page_text[2507:2569]`：As regards maintenance of the relief valve - see paragraph 10.

## VR08:A012 · E0 · MP004:p0010

原始：relief valve — inspected_by → check that the shaft rotates freely without jarring sounds

裁定：semantic_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：shaft — inspected_by → check that the shaft rotates freely without jarring sounds

条件：["Before starting the pump"]

证据：

- `page_text[2839:3130]`：Before starting the pump check that - the shaft rotates freely without jarring sounds. - the pump casing is filled with liquid.

## VR08:A013 · E0 · MP004:p0010

原始：pump casing — inspected_by → check that the pump casing is filled with liquid

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：pump casing — inspected_by → check that the pump casing is filled with liquid

条件：["Before starting the pump"]

证据：

- `page_text[2839:3130]`：Before starting the pump check that - the shaft rotates freely without jarring sounds. - the pump casing is filled with liquid.

## VR08:A014 · E0 · MP004:p0010

原始：direction of rotation — inspected_by → Start the pump for a moment to check the direction of rotation

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：pump — inspected_by → start briefly to check direction of rotation

条件：["brief check before continued startup", "continue only when direction agrees with arrow"]

证据：

- `page_text[3171:3333]`：Start the pump for a moment to check the direction of rotation. If the direction is correct (i.e. in the direction of the arrow), the pump may be started.

## VR08:A015 · E0 · MP004:p0010

原始：considerably smaller delivery head than expected — causes → increased power consumption

裁定：representation_error。原文为低扬程→流量增加→功耗/可能汽蚀；保存相邻因果边，不将传递路径冒作直接边。

修复：increased quantity of liquid delivered — causes → increased power consumption

条件：["considerably smaller delivery head than expected"]

证据：

- `page_text[3974:4159]`：A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.

## VR08:A016 · E0 · MP004:p0010

原始：considerably smaller delivery head than expected — causes → cavitation

裁定：representation_error。原文为低扬程→流量增加→功耗/可能汽蚀；保存相邻因果边，不将传递路径冒作直接边。

修复：increased quantity of liquid delivered — causes → cavitation

条件：["considerably smaller delivery head than expected"]

证据：

- `page_text[3974:4159]`：A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.

## VR08:A017 · E0 · MP004:p0010

原始：cavitation — occurs_at → pump

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：cavitation — occurs_at → pump

条件：[]

证据：

- `page_text[4121:4159]`：perhaps cavitation in pump and piping.

## VR08:A018 · E0 · MP004:p0010

原始：cavitation — occurs_at → piping

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：cavitation — occurs_at → piping

条件：[]

证据：

- `page_text[4121:4159]`：perhaps cavitation in pump and piping.

## VR08:A019 · E0 · MP004:p0010

原始：cavitation — causes → heavy erosion

裁定：incomplete。源文明说 erosion caused by cavitation；保留 impeller 和 may，不当必然，也不把表现关系当因果边。

修复：cavitation — causes → heavy erosion of the impeller

条件：["in the pump impeller"]

证据：

- `page_text[4160:4339]`：In the pump the impeller may show signs of heavy erosion caused by cavitation (corrosion) which may at times render an impeller unfit for use in a very short time.

## VR08:A020 · E0 · MP004:p0010

原始：heavy erosion — occurs_at → impeller

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：heavy erosion — occurs_at → impeller

条件：[]

证据：

- `page_text[4160:4257]`：In the pump the impeller may show signs of heavy erosion caused by cavitation (corrosion)

## VR08:A021 · E0 · MP004:p0010

原始：heavy erosion — evolves_to → impeller unfit for use

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：heavy erosion — evolves_to → impeller unfit for use

条件：[]

证据：

- `page_text[4258:4339]`：which may at times render an impeller unfit for use in a very short time.

## VR08:A022 · E0 · MP004:p0010

原始：erosions — occurs_at → pipe bends

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：erosions — occurs_at → pipe bends

条件：[]

证据：

- `page_text[4340:4444]`：Not unusually do similar erosions occur in pipe bends and valves elsewhere in the piping system.

## VR08:A023 · E0 · MP004:p0010

原始：erosions — occurs_at → valves

裁定：complete。结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。

修复：erosions — occurs_at → valves

条件：[]

证据：

- `page_text[4340:4444]`：Not unusually do similar erosions occur in pipe bends and valves elsewhere in the piping system.

## VR08:A024 · E0 · MP004:p0010

原始：quantity of liquid delivered — inspected_by → check either the quantity of liquid delivered or the power consumption of the pump e.g. by measuring the current intensity of the connected motor

裁定：unresolved。流量、功率、电流、压差和泵曲线的联合测定句法尚未裁定；不把缺失测量链强行补全。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[4479:4679]`：Therefore, after start-up, it is necessary to check either the quantity of liquid delivered or the power consumption of the pump e.g. by measuring the current intensity of the connected motor.

## VR08:A025 · E0 · MP004:p0010

原始：power consumption — inspected_by → measuring the current intensity of the connected motor

裁定：representation_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：power consumption of the pump — diagnosed_by → measuring current intensity of the connected motor

条件：["after start-up; example method, not accuracy guarantee"]

证据：

- `page_text[4525:4679]`：check either the quantity of liquid delivered or the power consumption of the pump e.g. by measuring the current intensity of the connected motor.
- `page_text[4479:4679]`：Therefore, after start-up, it is necessary to check either the quantity of liquid delivered or the power consumption of the pump e.g. by measuring the current intensity of the connected motor.

## VR08:A026 · E0 · MP004:p0010

原始：quantity of water delivered — inspected_by → reading of the differential pressure

裁定：unresolved。流量、功率、电流、压差和泵曲线的联合测定句法尚未裁定；不把缺失测量链强行补全。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[4680:4839]`：Together with a reading of the differential pressure the quantity of water delivered can be determined against the characteristics of the pump.

## VR08:A027 · E0 · MP004:p0010

原始：pump not function as intended — diagnosed_by → fault-finding list

裁定：representation_error。仅指向未在本页给出的 fault-finding list；保持交叉引用，不充作具体诊断方法。

修复：转 `cross_reference` 旁路；要求=见原文及条件。

证据：

- `page_text[4890:4983]`：Should the pump not function as intended, please proceed according to the fault-finding list.

## VR10:A001 · E1 · MP007:p0015

原始：pump — operates_under → 60hz motor

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：pump — operates_under → 60hz motor

条件：[]

证据：

- `page_text[1753:1866]`：The pump may run with 60hz motor. The flow, head and power of the pump running at 60hz will be changed.

## VR10:A002 · E1 · MP007:p0015

原始：60hz — causes → flow, head and power of the pump running at 60hz will be changed

裁定：representation_error。60Hz 下性能改变属于运行规格，不能仅用 Symptom 标签变成故障。

修复：转 `operating_mechanism` 旁路；要求=见原文及条件。

证据：

- `page_text[1787:1866]`：The flow, head and power of the pump running at 60hz will be changed.

## VR10:A003 · E1 · MP007:p0015

原始：pump — inspected_by → confirm that the pump is shut off

裁定：complete。检查停机或霜冻风险有明确源文/前提；这些是额外受支持条目，不从参考缺席推为错误。

修复：pump — inspected_by → confirm that the pump is shut off

条件：["Before maintenance"]

证据：

- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.

## VR10:A004 · E1 · MP007:p0015

原始：Pump bearing — maintained_by → require no maintenance

裁定：representation_error。原响应已保留 negative，并非极性翻转；无需维护不是维护动作，也不等于禁止维护。

修复：转 `maintenance_requirement` 旁路；要求=not_required。

证据：

- `page_text[2267:2334]`：Pump bearing and shaft seal require no maintenance.

## VR10:A005 · E1 · MP007:p0015

原始：shaft seal — maintained_by → require no maintenance

裁定：representation_error。原响应已保留 negative，并非极性翻转；无需维护不是维护动作，也不等于禁止维护。

修复：转 `maintenance_requirement` 旁路；要求=not_required。

证据：

- `page_text[2267:2334]`：Pump bearing and shaft seal require no maintenance.

## VR10:A006 · E1 · MP007:p0015

原始：Motor bearing — located_in → motor without a nozzle

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：Motor bearing — located_in → motor without a nozzle

条件：[]

证据：

- `page_text[2543:2594]`：The motor without a nozzle requires no maintenance.

## VR10:A007 · E1 · MP007:p0015

原始：Motor bearing — maintained_by → requires no maintenance

裁定：representation_error。原响应已保留 negative，并非极性翻转；无需维护不是维护动作，也不等于禁止维护。

修复：转 `maintenance_requirement` 旁路；要求=not_required。

证据：

- `page_text[2543:2594]`：The motor without a nozzle requires no maintenance.

## VR10:A008 · E1 · MP007:p0015

原始：Motor bearing — located_in → motor with a nozzle (including motor above 11kW)

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：Motor bearing — located_in → motor with a nozzle (including motor above 11kW)

条件：[]

证据：

- `page_text[2595:2751]`：The motor with a nozzle (including motor above 11kW) shall be lubricated with lubricant or similar high-temperature lithium base grease.

## VR10:A009 · E1 · MP007:p0015

原始：Motor bearing — maintained_by → lubricated with lubricant or similar high-temperature lithium base grease

裁定：incomplete。补充维护前停机及 Motor bearing 段的带 nozzle 电机范围；including >11kW 不是仅限 >11kW。

修复：Motor bearing — maintained_by → lubricated with lubricant or similar high-temperature lithium base grease

条件：["The motor with a nozzle (including motor above 11kW)", "Before maintenance: confirm that the pump is shut off", "motor with a nozzle; including motor above 11kW"]

证据：

- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.
- `page_text[2595:2751]`：The motor with a nozzle (including motor above 11kW) shall be lubricated with lubricant or similar high-temperature lithium base grease.
- `page_text[2460:2473]`：Motor bearing

## VR10:A010 · E1 · MP007:p0015

原始：Motor bearing — maintained_by → lubricate before starting the motor

裁定：incomplete。补充维护前停机及 Motor bearing 段的带 nozzle 电机范围；including >11kW 不是仅限 >11kW。

修复：Motor bearing — maintained_by → lubricate before starting the motor

条件：["seasonal running (motor shutdown for over 6 months)", "Before maintenance: confirm that the pump is shut off", "motor with a nozzle; including motor above 11kW"]

证据：

- `page_text[2811:2921]`：In case of seasonal running (motor shutdown for over 6 months), lubricate before starting the motor.
- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.
- `page_text[2595:2751]`：The motor with a nozzle (including motor above 11kW) shall be lubricated with lubricant or similar high-temperature lithium base grease.
- `page_text[2460:2473]`：Motor bearing

## VR10:A011 · E1 · MP007:p0015

原始：mechanical seal — located_in → pump

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：mechanical seal — located_in → pump

条件：[]

证据：

- `page_text[3028:3219]`：The mechanical seal is adjusted automatically. The contact surface of dynamic ring and static ring in the seal will be lubricated and cooled down by the liquid conveyed by the pump.

## VR10:A012 · E1 · MP007:p0015

原始：dynamic ring — located_in → seal

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：dynamic ring — located_in → seal

条件：[]

证据：

- `page_text[3075:3219]`：The contact surface of dynamic ring and static ring in the seal will be lubricated and cooled down by the liquid conveyed by the pump.

## VR10:A013 · E1 · MP007:p0015

原始：static ring — located_in → seal

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：static ring — located_in → seal

条件：[]

证据：

- `page_text[3075:3219]`：The contact surface of dynamic ring and static ring in the seal will be lubricated and cooled down by the liquid conveyed by the pump.

## VR10:A014 · E1 · MP007:p0015

原始：contact surface of dynamic ring and static ring — maintained_by → lubricated and cooled down by the liquid conveyed by the pump

裁定：representation_error。输送液自动润滑/冷却是机理，不是操作者维护步骤。

修复：转 `operating_mechanism` 旁路；要求=见原文及条件。

证据：

- `page_text[3075:3219]`：The contact surface of dynamic ring and static ring in the seal will be lubricated and cooled down by the liquid conveyed by the pump.

## VR10:A015 · E1 · MP007:p0015

原始：sliding bearing — located_in → pump

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：sliding bearing — located_in → pump

条件：[]

证据：

- `page_text[3230:3316]`：The sliding bearing in the pump will be lubricated by the liquid conveyed by the pump.

## VR10:A016 · E1 · MP007:p0015

原始：sliding bearing — maintained_by → lubricated by the liquid conveyed by the pump

裁定：representation_error。输送液自动润滑/冷却是机理，不是操作者维护步骤。

修复：转 `operating_mechanism` 旁路；要求=见原文及条件。

证据：

- `page_text[3230:3316]`：The sliding bearing in the pump will be lubricated by the liquid conveyed by the pump.

## VR10:A017 · E1 · MP007:p0015

原始：freezing of the liquid conveyed by the pump — increases_risk_of → damage to the pump

裁定：complete。检查停机或霜冻风险有明确源文/前提；这些是额外受支持条目，不从参考缺席推为错误。

修复：freezing of the liquid conveyed by the pump — increases_risk_of → damage to the pump

条件：["If the pump is installed at a place where it is likely to freeze"]

证据：

- `page_text[3499:3734]`：If the pump is installed at a place where it is likely to freeze, proper quantity of antifreezing agent must be added so as to avoid damage to the pump due to freezing of the liquid conveyed by the pump.

## VR10:A018 · E1 · MP007:p0015

原始：freezing of the liquid conveyed by the pump — prevented_by → proper quantity of antifreezing agent must be added

裁定：incomplete。添加防冻剂为保养要求，补维护停机，保留可能冻结及未定量 proper quantity。

修复：pump — maintained_by → proper quantity of antifreezing agent must be added

条件：["If the pump is installed at a place where it is likely to freeze", "Before maintenance: confirm that the pump is shut off"]

证据：

- `page_text[3499:3734]`：If the pump is installed at a place where it is likely to freeze, proper quantity of antifreezing agent must be added so as to avoid damage to the pump due to freezing of the liquid conveyed by the pump.
- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.

## VR10:A019 · E1 · MP007:p0015

原始：pump out of service during a frost period — increases_risk_of → damage to the pump

裁定：complete。检查停机或霜冻风险有明确源文/前提；这些是额外受支持条目，不从参考缺席推为错误。

修复：pump out of service during a frost period — increases_risk_of → damage to the pump

条件：[]

证据：

- `page_text[3806:3945]`：If the pump is out of service during a frost period, you should drain the liquid inside it so as to avoid any damage to the pump.

## VR10:A020 · E1 · MP007:p0015

原始：pump out of service during a frost period — mitigated_by → drain the liquid inside it

裁定：representation_error。排液是泵保养动作，不是检查液体；补霜冻停用、停机和排液通道，不将危险工况作为被缓解的设备。

修复：pump — maintained_by → drain the liquid via the water injection hole at the pump head and the drainage hole at bottom

条件：["pump out of service during a frost period", "Before maintenance: confirm that the pump is shut off", "Pay attention to safety of persons and objects during water drainage (cold or hot)"]

证据：

- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.
- `page_text[3806:3945]`：If the pump is out of service during a frost period, you should drain the liquid inside it so as to avoid any damage to the pump.
- `page_text[3946:4076]`：The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.
- `page_text[4077:4170]`：Pay attention to safety of persons and objects during water drainage (cold or hot).

## VR10:A021 · E1 · MP007:p0015

原始：liquid inside the pump — inspected_by → drained via the water injection hole at the pump head and the drainage hole at bottom

裁定：semantic_error。排液是泵保养动作，不是检查液体；补霜冻停用、停机和排液通道，不将危险工况作为被缓解的设备。

修复：pump — maintained_by → drain the liquid via the water injection hole at the pump head and the drainage hole at bottom

条件：["pump out of service during a frost period", "Before maintenance: confirm that the pump is shut off", "Pay attention to safety of persons and objects during water drainage (cold or hot)"]

证据：

- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.
- `page_text[3806:3945]`：If the pump is out of service during a frost period, you should drain the liquid inside it so as to avoid any damage to the pump.
- `page_text[3946:4076]`：The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.
- `page_text[4077:4170]`：Pay attention to safety of persons and objects during water drainage (cold or hot).

## VR10:A022 · E1 · MP007:p0015

原始：water injection hole — located_in → pump head

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：water injection hole — located_in → pump head

条件：[]

证据：

- `page_text[3946:4076]`：The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.

## VR10:A023 · E1 · MP007:p0015

原始：drainage hole — located_in → bottom

裁定：complete。本页结构/运行关系；不计为核心诊断增量。

修复：drainage hole — located_in → bottom

条件：[]

证据：

- `page_text[3946:4076]`：The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.

## VR10:A024 · E1 · MP007:p0015

原始：using the pump once again — prevented_by → firstly tighten the vent plug and drainage valve

裁定：semantic_error。再次使用是操作目的，不是要预防的事件；保留为排液后恢复运行程序。

修复：转 `operating_procedure` 旁路；要求=见原文及条件。

证据：

- `page_text[3806:3945]`：If the pump is out of service during a frost period, you should drain the liquid inside it so as to avoid any damage to the pump.
- `page_text[4171:4262]`：When using the pump once again, firstly tighten the vent plug and drainage valve.

## VR10:A025 · E1 · MP007:p0015

原始：replace the drainage valve — prevented_by → loosen the bypass valve, then unscrew the drain plug

裁定：semantic_error。更换/安装的目的不得当作被预防事件；改为排水阀检修程序，then 顺序及停机前提保留。

修复：drainage valve — maintained_by → loosen the bypass valve, then unscrew the drain plug

条件：["when replacing the drainage valve", "Before maintenance: confirm that the pump is shut off"]

证据：

- `page_text[4263:4405]`：When it is necessary to replace the drainage valve, you must loosen the bypass valve, then unscrew the drain plug (refer to Fig. 5).
- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.

## VR10:A026 · E1 · MP007:p0015

原始：install the drainage valve — prevented_by → firstly tighten the drain plug, then tighten the bypass valve

裁定：semantic_error。更换/安装的目的不得当作被预防事件；改为排水阀检修程序，then 顺序及停机前提保留。

修复：drainage valve — maintained_by → firstly tighten the drain plug, then tighten the bypass valve

条件：["when installing the drainage valve", "Before maintenance: confirm that the pump is shut off"]

证据：

- `page_text[4406:4521]`：If you want to install the drainage valve, firstly tighten the drain plug, then tighten the bypass valve.
- `page_text[2188:2266]`：Before maintenance, confirm that the pump is shut off so as to avoid accident.

## VR11:A001 · E1 · MP007:p0012

原始：vacuum valve — located_in → pump

裁定：semantic_error。near 不等于 located_in；one of 表示任一条件，不能暗作三个同时满足。

修复：转 `installation_requirement` 旁路；要求=见原文及条件。

证据：

- `MP007:p0012:t00:r000:c02[0:269]`：If your installation is characterized by one of following features, please install one vacuum valve near the pump. ● The discharge pipe is sloped downwards in the direction of leaving the pump. ● Siphonage may occur. ● It is necessary to stop backflow of unclean water.

## VR11:A002 · E1 · MP007:p0012

原始：dry running — causes → pump bearing and shaft seal will be damaged

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：dry running — causes → pump bearing and shaft seal will be damaged

条件：[]

证据：

- `page_text[1635:1796]`：Caution: Do not start the pump before water is filled and air is discharged. In case of dry running, pump bearing and shaft seal will be damaged.

## VR11:A003 · E1 · MP007:p0012

原始：dry running — occurs_at → pump

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：dry running — occurs_at → pump

条件：[]

证据：

- `page_text[1644:1796]`：Do not start the pump before water is filled and air is discharged. In case of dry running, pump bearing and shaft seal will be damaged.

## VR11:A004 · E1 · MP007:p0012

原始：pump bearing — located_in → pump

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：pump bearing — located_in → pump

条件：[]

证据：

- `page_text[1752:1795]`：pump bearing and shaft seal will be damaged

## VR11:A005 · E1 · MP007:p0012

原始：shaft seal — located_in → pump

裁定：complete。干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。

修复：shaft seal — located_in → pump

条件：[]

证据：

- `page_text[1752:1795]`：pump bearing and shaft seal will be damaged

## VR11:A006 · E1 · MP007:p0012

原始：heat protector — located_in → One-phase motor

裁定：complete。类型、检查对象及 before startup 条件已在 applicability 中，不因 conditions 空而误判遗漏。

修复：heat protector — located_in → One-phase motor

条件：[]

证据：

- `page_text[2416:2581]`：One-phase motor is provided with a heat protector inside while three-phase motor shall be provided with a three-phase protector before installation.

## VR11:A007 · E1 · MP007:p0012

原始：three-phase protector — located_in → three-phase motor

裁定：representation_error。provided with 三相保护器不证明一定装在电机内部；保留安装前配置要求。

修复：转 `electrical_requirement` 旁路；要求=见原文及条件。

证据：

- `page_text[2479:2581]`：three-phase motor shall be provided with a three-phase protector before installation.

## VR11:A008 · E1 · MP007:p0012

原始：foot bolts — inspected_by → Check if foot bolts are tightened

裁定：complete。类型、检查对象及 before startup 条件已在 applicability 中，不因 conditions 空而误判遗漏。

修复：foot bolts — inspected_by → Check if foot bolts are tightened

条件：[]

证据：

- `page_text[2774:2811]`：• Check if foot bolts are tightened.

## VR11:A009 · E1 · MP007:p0012

原始：pump — inspected_by → If the pump is full of water or not

裁定：complete。类型、检查对象及 before startup 条件已在 applicability 中，不因 conditions 空而误判遗漏。

修复：pump — inspected_by → If the pump is full of water or not

条件：[]

证据：

- `page_text[2857:2896]`：• If the pump is full of water or not.

## VR11:A010 · E1 · MP007:p0012

原始：pump — inspected_by → If the rotating direction is correct or not

裁定：complete。类型、检查对象及 before startup 条件已在 applicability 中，不因 conditions 空而误判遗漏。

修复：pump — inspected_by → If the rotating direction is correct or not

条件：[]

证据：

- `page_text[3023:3070]`：• If the rotating direction is correct or not.

## VR11:A011 · E1 · MP007:p0012

原始：pipes — inspected_by → If all pipes are tightly connected or not, if pipes can provide water normally or not

裁定：complete。类型、检查对象及 before startup 条件已在 applicability 中，不因 conditions 空而误判遗漏。

修复：pipes — inspected_by → If all pipes are tightly connected or not, if pipes can provide water normally or not

条件：[]

证据：

- `page_text[3106:3222]`：• If all pipes are tightly connected or not, if pipes can • provide water normally or not.

## VR11:A012 · E1 · MP007:p0012

原始：valves on inlet pipes — inspected_by → If valves on inlet pipes are completely opened or not

裁定：complete。类型、检查对象及 before startup 条件已在 applicability 中，不因 conditions 空而误判遗漏。

修复：valves on inlet pipes — inspected_by → If valves on inlet pipes are completely opened or not

条件：[]

证据：

- `page_text[3272:3329]`：• If valves on inlet pipes are completely opened or not.

## VR11:A013 · E1 · MP007:p0012

原始：pressure meter — inspected_by → Check working pressure if a pressure meter is installed

裁定：semantic_error。根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。

修复：working pressure — diagnosed_by → check working pressure using an installed pressure meter

条件：["before pump startup", "if a pressure meter is installed"]

证据：

- `page_text[3456:3515]`：• Check working pressure if a pressure meter is installed.
- `page_text[2691:2720]`：7.2 CHECK BEFORE PUMP STARTUP

## VR11:A014 · E1 · MP007:p0012

原始：full-load current of the motor — inspected_by → Check if the full-load current of the motor exceeds the maximum allowable current via the pressure switch

裁定：unresolved。源文通过 pressure switch 检查电流的方法有歧义；不凭工程常识代改。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[3705:3931]`：If the pump is controlled by the pressure switch, check, adjust, start and disconnect the pressure. Check if the full-load current of the motor exceeds the maximum allowable current via the pressure switch.

## VR12:A001 · E0 · MP015:p0039

原始：tolerance ring (1880) — located_in → pump shaft (2200)

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：tolerance ring (1880) — maintained_by → Place the tolerance ring (1880) into the shaft recess of the pump shaft (2200).

条件：["7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 1; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[689:768]`：Place the tolerance ring (1880) into the shaft recess of the pump shaft (2200).

## VR12:A002 · E0 · MP015:p0039

原始：impeller (0120) — located_in → pump shaft (2200)

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller (0120) — maintained_by → Push the impeller over the tolerance ring onto the shaft. Make sure its position is square with the shaft!

条件：["7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 3; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1099:1156]`：Push the impeller over the tolerance ring onto the shaft.
- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[1099:1230]`：Push the impeller over the tolerance ring onto the shaft. Make sure its position is square with the shaft!

## VR12:A003 · E0 · MP015:p0039

原始：tolerance ring — maintained_by → apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：tolerance ring — maintained_by → For bronze and stainless steel pumps the tolerance ring must be isolated from the liquid. In order to do this apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

条件：["For bronze and stainless steel pumps", "7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[794:1063]`：For bronze and stainless steel pumps the tolerance ring must be isolated from the liquid. In order to do this apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

## VR12:A004 · E0 · MP015:p0039

原始：impeller bolt and spring washer (1825) — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller bolt and spring washer (1825)

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller bolt and spring washer (1825) — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller bolt and spring washer (1825). See chapter 10 "Technical data" for the correct fastening moment.

条件：["7.6.4 Assembly of the impeller, bearing bracket 1", "source procedure step 4; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[598:647]`：7.6.4 Assembly of the impeller, bearing bracket 1
- `page_text[1374:1558]`：Put a drop of Loctite 243 on the thread and mount the impeller bolt and spring washer (1825). See chapter 10 "Technical data" for the correct fastening moment.

## VR12:A005 · E0 · MP015:p0039

原始：impeller (0120) — maintained_by → Pull the impeller (0120) off the pump shaft, using a proper puller

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller (0120) — maintained_by → Pull the impeller (0120) off the pump shaft, using a proper puller.

条件：["7.6.5 Disassembly of the impeller, other bearing brackets", "source procedure step 5; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[1576:1633]`：7.6.5 Disassembly of the impeller, other bearing brackets
- `page_text[2197:2264]`：Pull the impeller (0120) off the pump shaft, using a proper puller.

## VR12:A006 · E0 · MP015:p0039

原始：impeller key (1860) — located_in → pump shaft (2200)

裁定：unresolved。1860 在相邻程序同时称 nut/key，保留原文不自行改件号/对象；等待部件图或专家裁定。

修复：未决隔离；原文和记录保留。

证据：

- `page_text[2539:2611]`：Place the impeller key (1860) into the key way of the pump shaft (2200).

## VR12:A007 · E0 · MP015:p0039

原始：thread of the pump shaft and impeller nut (1820) or impeller bolt (1820) — maintained_by → Degrease the thread of the pump shaft and impeller nut (1820) or impeller bolt (1820)

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：thread of the pump shaft and impeller nut (1820) or impeller bolt (1820) — maintained_by → Degrease the thread of the pump shaft and impeller nut (1820) or impeller bolt (1820).

条件：["7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 5; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[2969:3080]`：Degrease the thread of the pump shaft and impeller nut (1820) or impeller bolt (1820).

## VR12:A008 · E0 · MP015:p0039

原始：impeller nut or impeller bolt — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller nut or impeller bolt

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：impeller nut or impeller bolt — maintained_by → Put a drop of Loctite 243 on the thread and mount the impeller nut or impeller bolt. See chapter 10 "Technical data" for the correct fastening moment.

条件：["7.6.6 Assembly of the impeller, other bearing brackets", "source procedure step 6; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[2448:2502]`：7.6.6 Assembly of the impeller, other bearing brackets
- `page_text[3156:3331]`：Put a drop of Loctite 243 on the thread and mount the impeller nut or impeller bolt. See chapter 10 "Technical data" for the correct fastening moment.

## VR12:A009 · E0 · MP015:p0039

原始：wear plate (0125) — located_in → pump casing

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：wear plate (0125) — maintained_by → Remove the wear plate (0125) from the pump casing, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism.

条件：["7.6.7 Disassembly of the wear plate", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure", "after disassembly of the Back Pull Out unit; item numbers refer to figure 55"]

证据：

- `page_text[3625:3660]`：7.6.7 Disassembly of the wear plate
- `page_text[3989:4159]`：Remove the wear plate (0125) from the pump casing, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism.
- `page_text[3714:3848]`：After disassembly of the Back Pull Out unit the wear plate can be removed. The item numbers refer to figure 55.

## VR12:A010 · E0 · MP015:p0039

原始：cutting blade (0105) — located_in → pump casing

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：cutting blade (0105) — maintained_by → Remove the wear plate (0125) from the pump casing, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism.

条件：["if the pump is provided with a cutting mechanism", "7.6.7 Disassembly of the wear plate", "source procedure step 2; previous applicable steps/order retained; this is not a complete procedure", "after disassembly of the Back Pull Out unit; item numbers refer to figure 55"]

证据：

- `page_text[3625:3660]`：7.6.7 Disassembly of the wear plate
- `page_text[3989:4159]`：Remove the wear plate (0125) from the pump casing, including the possible cutting blade (0105), if the pump is provided with a cutting mechanism.
- `page_text[3714:3848]`：After disassembly of the Back Pull Out unit the wear plate can be removed. The item numbers refer to figure 55.

## VR12:A011 · E0 · MP015:p0039

原始：edge of the pump casing — maintained_by → Clean the edge of the pump casing where the wear plate has to be fitted

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：edge of the pump casing — maintained_by → Clean the edge of the pump casing where the wear plate has to be fitted.

条件：["7.6.8 Assembly of the wear plate", "source procedure step 1; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[4260:4292]`：7.6.8 Assembly of the wear plate
- `page_text[4351:4423]`：Clean the edge of the pump casing where the wear plate has to be fitted.

## VR12:A012 · E0 · MP015:p0039

原始：screws (0115) — maintained_by → use Loctite 243 to lock the screws

裁定：incomplete。从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。

修复：screws (0115) — maintained_by → Tighten the wear plate with screws (0115). For this use Loctite 243 to lock the screws.

条件：["7.6.8 Assembly of the wear plate", "source procedure step 3; previous applicable steps/order retained; this is not a complete procedure"]

证据：

- `page_text[4260:4292]`：7.6.8 Assembly of the wear plate
- `page_text[4770:4882]`：Tighten the wear plate with screws (0115). For this use Loctite 243 to lock the screws.
