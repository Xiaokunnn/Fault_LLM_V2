# 107条逐记录可重构性分析（非新语义标签）

L=有明确局部关系线索，P=有可能但另有语义/结构前提，N=当前任务不重构，U=无法确定。L不代表条件完整或程序已验证。A/B保持原端点及类型；C复用已有可寻址片段；D需要补新的完整实体/动作片段。原始S/E/U保持不变。

## 29页

| ID | 原始关系（源语片段） | 类别 | 依据层级 | 原因／边界 |
| --- | --- | --- | --- | --- |
| MP006:p0006:H29:004 | underlying structure is not level (plane) → causes → it may be necessary to shim under either the pump footplate or under the flange support(s). | U | U | 不平基础触发加垫；原主张causes动作不合法。改为prevented_by会把补偿不平变成防止不平；若改部件维护又涉及初装/维护范围，现有标签不足以唯一裁定。 |
| MP006:p0006:H29:007 | more than a 0.5 mm air gap under the feet → causes → shims must be placed underneath | U | U | 气隙触发加垫同上；不是简单换关系即可保证成立。旧修复仅补if，仍E。 |
| MP006:p0006:H29:008 | flange support(s) → maintained_by → Bolt flange support(s) to underlying structure. | F | N | 初装紧固支撑，不应强制变为维护；现Schema无一般安装步骤关系。 |
| MP006:p0006:H29:009 | pipe system flange(s) and gasket(s) → maintained_by → mount the pipe system flange(s) and gasket(s) against the flange support(s). | F | N | 初装拆临时螺栓/装法兰垫片，缺顺序；不能靠换关系变维护。 |
| MP006:p0006:H29:011 | piping system flange(s) → maintained_by → Bolt the piping system flange(s) together with the pump and flange support(s). | F | N | 初装法兰紧固，现有关系空间不能直接表达安装流程。 |
| MP006:p0006:H29:013 | temperature of the pipe system changes significantly (up or down) after commissioning the  → causes → it should be checked again that the pump shaft still can rotate freely at actual upper/lower tempera | C | L | 已有002/012的pump shaft Component可重配到当前检查动作，原if保留为该检查条件；词面直接出现pump shaft。当前修复仅加if未改头/关系。 |
| MP016:p0042:H29:001 | pumpen → maintained_by → visuell inspektion dagligen | B | L | pumpen Equipment与日常视觉InspectionAction均已有；maintained_by改inspected_by。瑞典语映射未见通用实现。 |
| MP016:p0042:H29:002 | pumpen → maintained_by → regelbundna kontroller vid planerade intervall | B | L | 同页定期检查同理，仅改inspected_by；维修前隔离等公共条件仍须完整保留。 |
| MP016:p0042:H29:003 | Underlåtenhet att underhålla pumpen med utföra ovanstående kontroller → causes → kan göra garantin ogiltig | F | N | 保修失效是行政/背景后果，不属于当前主图故障主张。 |
| MP016:p0042:H29:008 | strömmen till pump och drivmotor brytas, tryckavlastning, dränering och isolering av rörle → prevented_by → Innan reparation eller inspektion påbörjas | D | P | 动作→prevented_by→开始检查不成立；可围绕泵/驱动电机的隔离动作表示，但原现有端点没有完整泵/电机维护对象与分解动作绑定，且前置程序不是被预防事件。 |
| MP016:p0003:H29:001 | damage to the Impeller → causes → operate the pump above the maximum differential pressure shown on the Datasheet, not even for a few  | A | L | 原句as damage to the Impeller will result明确超压→叶轮损坏；原两端及类型交换合法。禁止超压的语境必须保留，不能把禁止操作当建议。 |
| MP016:p0003:H29:008 | High Temperature → causes → Net Inlet Pressure Required or NIPR is higher | F | N | NIPR随温度升高是参数依赖；causes尾OperatingCondition不合法，现Schema无参数依赖关系。 |
| MP016:p0003:H29:009 | High Pump Speeds → causes → Net Inlet Pressure Required or NIPR is higher | F | N | 高转速与NIPR参数依赖同上。 |
| MP016:p0003:H29:010 | inlet pipes are short, large bore and do not collapse under vacuum → prevented_by → cavitate | A | L | 汽蚀←入口短粗且不塌管的建议；交换成FaultMode prevented_by MaintenanceAction。跨句汽蚀上下文必须绑定。 |
| MP016:p0003:H29:015 | Remove packing material from container and check contents against packing list → inspected_by → Flexible Impeller Pumps | U | U | 交换类型虽合法，但检查包装内容对照清单与检查整个泵并非完全同义；目标是否应为包装内容需再辨，不能算只交换即可修好。 |
| MP016:p0003:H29:016 | Check the pump for any physical damage sustained in shipping → inspected_by → Flexible Impeller Pumps | A | L | Check the pump for physical damage与泵Equipment直接对应，交换为泵inspected_by检查。 |
| MP016:p0003:H29:017 | Ensure ports are oriented to give the correct orientation and connection for duty required → inspected_by → Flexible Impeller Pumps | A | L | 检查接口朝向与泵的收货检查上下文对应，交换为泵inspected_by动作；仍需保留收货阶段。 |
| MP016:p0003:H29:020 | direction of shaft rotation → causes → Intake and discharge ports are determined | F | N | 旋转方向决定进出口角色，无当前允许的接口角色/参数决定关系，不是causes Component。 |
| MP017:p0002:H29:007 | Failure to do so → increases_risk_of → personal injury or damage to the pump | F | N | 未读手册责任警告，辅助操作要求；不能为增加核心量改造成泵故障因果。 |
| MP018:p0006:H29:005 | minimum of elbows and fittings in the discharge line → mitigated_by → minimize friction losses | D | P | 减阻措施与目标方向错；须把minimum of elbows实体改为完整布管措施，把minimize friction losses改成摩擦损失风险。原两端原类型不能仅交换，需重新分割/定型。 |
| MP018:p0006:H29:006 | pumping unit → prevented_by → protected against flooding | D | P | 泵不是被预防故障；需要独立flooding风险实体及完整防淹措施。flooding仅嵌在动作中，没有独立已有端点。 |
| MP018:p0006:H29:007 | foundation → maintained_by → absorb vibration and to form a permanent rigid support for the base plate | F | N | 基础吸振/支撑是功能能力，不是维护动作，当前Schema缺功能关系。 |
| MP018:p0006:H29:009 | Coupling halves → maintained_by → disconnected when mounting pumping unit on foundation | F | N | 安装泵时断开联轴器是安装程序前提；不把它重新命名为维护。 |
| MP018:p0006:H29:010 | Wedges → maintained_by → used to support the unit at time of grouting | F | N | 灌浆用楔块的用途不是对楔块的维护，缺用途关系。 |
| MP018:p0006:H29:013 | Leveling bolts → maintained_by → useful when leveling large baseplates, but should not replace shims or blocks for supporting the loa | F | N | 调平螺栓用途及不可代支撑的限制，缺现成用途/程序约束关系。 |
| MP018:p0006:H29:014 | horizontal pump with base and drive equipment → inspected_by → use lugs provided in the base | F | N | 吊装使用吊耳不是检查，当前Schema无一般吊装操作关系。 |
| MP018:p0006:H29:015 | vertical pump → inspected_by → eyebolts may be installed in the tapped holes in the pump casing | F | N | 安装吊环吊装不是检查，同上。 |
| MP018:p0006:H29:016 | pump → prevented_by → secured in a manner that will maintain the pump in a stable, upright position while lifting | F | N | 吊装前固定为操作安全要求；原文未给特定故障实体，不强添倾倒等风险。 |
| MP018:p0006:H29:017 | electrical connections → maintained_by → Disconnect all electrical connections to insure that pump will not start during coupling or intermed | F | N | 安装/对中前断电前提，不能仅换关系便计成该电气接头的维护。 |
| MP019:p0048:H29:003 | Roulement isolé côté non-entraînement → prevented_by → courants de roulement | A | L | 同表中功率段隔离轴承措施与轴承电流可直接反向prevented_by，保留ABB变频器和功率/机座条件。 |
| MP019:p0048:H29:004 | Roulement isolé côté non-entraînement → prevented_by → courants de roulement | D | P | 高功率行是隔离轴承ET共模滤波器联合措施；单条反向仍不完整。须额外形成绑定同一行的联合措施端点/包，不是A。 |
| MP019:p0048:H29:005 | Filtre en mode commun au niveau du convertisseur → prevented_by → courants de roulement | D | P | 与004同一高功率ET措施包，不能将两条各自当充分措施；需要组合动作而非仅交换端点。 |
| MP019:p0048:H29:006 | roulements isolés dotés d'alésages intérieur et/ou extérieur revêtus d'oxyde d'aluminium o → mitigated_by → courants de roulement | D | P | 隔离轴承是Component，反向后仍不满足mitigated_by MaintenanceAction；需要源文utiliser...的完整动作片段并保留防护条件。 |
| MP019:p0048:H29:007 | presse-étoupes appropriés assurant une continuité de masse sur 360° → maintained_by → moteur | D | P | 电缆密封接头Component与电机Equipment交换后仍非MaintenanceAction；需要完整使用/接线动作，而非凭类型改名。 |
| MP019:p0048:H29:009 | conductivité haute fréquence de la connexion fournie par le socle en acier → inspected_by → socle d'acier | D | P | 反向inspected_by只是类型合法；原InspectionAction仅导电性名词，需扩为原文doit être vérifiée完整检查片段，不能算只交换即可修好。 |
| MP019:p0048:H29:010 | mesurant la différence de potentiel entre les composants → diagnosed_by → conductivité haute fréquence de la connexion fournie par le socle en acier | D | P | 导电性不是InspectionAction；需要底座/连接的物理对象与完整测电位差检查组合。原两个InspectionAction不能合法交换成diagnosed_by。 |
| MP019:p0048:H29:011 | câbles symétriques blindés et de presse-étoupe CEM assurant une continuité de masse sur 36 → maintained_by → moteurs d'une puissance supérieure à 30 kW | D | P | 线缆/接头物件不是MaintenanceAction，需完整电机接线动作；功率>30kW及360°连续性须附属动作。 |
| MP019:p0048:H29:012 | câbles symétriques blindés → maintained_by → moteurs de moindre puissance | D | P | 同上，较小功率为推荐而非必须，补完整使用屏蔽线动作。 |
| MP019:p0048:H29:013 | dépassement de la vitesse de rotation la plus élevée autorisée ou de la vitesse critique d → increases_risk_of → vitesses supérieures à la vitesse nominale inscrite sur la plaque signalétique du moteur | E | N | 源文要求额定以上转速时检查临界/最高转速，并未断言额定以上必提高超临界风险；交换也不能证明该风险因果。 |
| MP019:p0048:H29:014 | vérifiez l'absence de dépassement de la vitesse de rotation la plus élevée autorisée ou de → inspected_by → moteur | A | L | vérifiez检查动作与电机反向inspected_by，条件为额定以上转速；目录或铭牌分支仍须保留。 |
| MP020:p0015:H29:003 | STRAIGHT EDGE → inspected_by → ALIGNMENT* | C | P | 已有001尾COUPLING Component可与STRAIGHT EDGE InspectionMethod重新配对为检查对象/方法；但仅图题ALIGNMENT及示意图，唯一对象和完整位置依据尚不足。 |
| MP020:p0015:H29:004 | CALIPER → inspected_by → ALIGNMENT* | C | P | 同上，CALIPER对应联轴器对中；不能只把InspectionAction ALIGNMENT与方法交换就合法。 |
| MP021:p0020:H29:010 | reservoir → maintained_by → fill the reservoir with one pint of Light Refrigeration Oil that is compatible with the Neoprene sea | F | N | 启动前注油是运行准备；旧评价明确不归核心维护。 |
| MP021:p0020:H29:013 | galling → prevented_by → coated with test fluid | F | N | 试验液涂覆是出厂已完成状态，不是用户执行的维护动作。 |
| MP021:p0020:H29:014 | damage to the pump → prevented_by → Be sure the pump is kept full of liquid when in operation | F | N | 运行保持充液为运行工况要求；若重新表达需泵及完整工况端点，当前记录不是现成防护维护措施。 |
| MP021:p0015:H29:014 | Check the alignment of the drive after the piping is hooked up → inspected_by → drive | A | L | 检查传动对中动作与drive Component反向inspected_by；保留管路接好之后。 |
| MP021:p0015:H29:015 | remove the head of the pump and with a feeler gauge determine if there is clearance all th → inspected_by → pump | A | L | 泵Equipment与拆泵头塞尺检查反向inspected_by；机型Q/M/N等限定仍不可遗漏。 |
| MP021:p0015:H29:016 | strainer → mitigated_by → consider a strainer on the suction side of a positive displacement pump | C | L | 同页010已有foreign objects Cause，可与安装入口滤网动作重组prevented_by；源文明确滤网阻异物进入。仍须保持正排量泵/入口等适用范围。 |
| MP021:p0015:H29:017 | pressure relief device → prevented_by → Provide a pressure relief device in any part of a pump and piping system that can be valved off and, | C | L | 同页012已有pump or piping will rupture Risk，可与封闭隔离管段装泄压装置重组prevented_by；须保留热膨胀/闭段条件，不能合并成所有泄压阀均足够。 |
| MP021:p0015:H29:018 | relief valve → mitigated_by → mounting one in the discharge line | C | P | 同页有rupture Risk，但该缺泄压阀时装排出管阀与15条封闭热膨胀风险未直接同一分支；仅潜在可用，不把同页共现当唯一配对。 |
| MP021:p0015:H29:021 | pipe sealer → maintained_by → All joints of the piping system should be tight; pipe sealer will help assure leak-free threaded joi | D | P | 应维护/密封管路接头，当前head仅pipe sealer；已有端点无完整piping joints，需从原句All joints of the piping system新增实体。 |
| MP021:p0015:H29:022 | bypass should be built around the strainer, or two strainers should be put in parallel wit → maintained_by → strainer | A | L | strainer Component与为隔离清洁设置旁通/双滤网措施可反向maintained_by；连续运行条件和两个替代方案均须保留。 |
| MP021:p0015:H29:023 | Loops, expansion joints, or unsecured (this does not mean unsupported) runs should be used → prevented_by → pump casing is not distorted | C | P | 同页006已有casing distortion from piping strain FaultMode，原末尾pump casing is not distorted不可直接当故障；可重配变形事件和补偿措施，但热胀/管应变语境是否等价须裁定，不能只交换否定实体。 |

## 10页

| ID | 原始关系（源语片段） | 类别 | 依据层级 | 原因／边界 |
| --- | --- | --- | --- | --- |
| L01:002 | pump → causes → si- phoning action causing damage | D | P | pump Equipment不能作为causes原因；si-phoning action causing damage是复合片段，没有独立泵损坏端点，单交换仍不合法。须拆虹吸/损坏并绑定Otherwise。 |
| L01:008 | pressure → mitigated_by → Withhighdischargeheads,itisrecommendedthat a throttling valve and a system check valve be in- stalle | D | P | 源文有reverse rota-tion，但菜单无独立反转ID；原pressure不是反转。须补断行合并后的反转实体。 |
| L01:009 | pump → operates_under → application involves a high discharge head | E | N | if高扬程是关阀动作条件，不能作为泵适用高扬程的独立事实；拒绝该脱离后件的主张。 |
| L01:010 | pump → maintained_by → If the application involves a high discharge head, gradually close the discharge throttling valve be | F | N | 停泵前关闭阀门是运行操作，当前Schema没有一般运行步骤边，不能硬转维护。 |
| L01:011 | Bypass Lines Self-priming pumps → operates_under → Bypass Lines Self-priming pumps are not air compressors. | F | N | 不是空气压缩机为类别否定，非operates_under；Schema无is_a/类别排除关系。 |
| L01:016 | A self-priming centrifugal pump → operates_under → A self-priming centrifugal pump will not prime if there is sufficient static liquid head to hold the | D | P | 需从整句独立提取will not prime故障端点，再与条件/泵建立允许关系；现有菜单仅设备和整个失效句。 |
| L01:017 | The bypass line → specified_by → The bypass line should be sized so that it does not affect pump discharge capacity; however, the by- | U | U | 所选尺寸句不是真实Standard，且页尾to续页；完整目标和可行表示尚不确定。 |
| L02:009 | shaft → maintained_by →  Should swab testing continue to fail, or time is of the essence, install a new (spare) air shaft. | D | P | air shaft在原句中，但菜单只有shaft短片段且包含后续另一型号分支；需完整air shaft端点和分支归属，不能仅沿用通用shaft。 |
| L03:003 | carbon ring → inspected_by → If the carbon ring is not fixed, it is important to check that it is fitted correctly, i.e. the cham | F | N | 关系和英语检查对象基本成立，错误在seat被译为阀座而非静环座；需要术语修复，不是关系重构收益。 |
| L03:005 | bellows → maintained_by → NOTE: When using silicone grease on the shaft, the bellows will settle and seat in about 15 minutes, | F | N | 波纹管15分钟就位/密封性为安装状态描述，非维护动作，现Schema无一般状态演化计时关系。 |
| L04:003 | rubber seals → maintained_by →  RRRuuubbbbbbeeerrr ssseeeaaalllsss SSShhhaaafffttt ssseeeaaalll Motor bearings RRReeeppplllaaacccee | D | P | u12将整页维护表当整步骤，只有整页动作和无关子动作，无独立橡胶密封随轴封更换动作。需按原列重新切动作及条件，单换已有端点不够。 |
| L04:005 | bearings → maintained_by →  RRRuuubbbbbbeeerrr ssseeeaaalllsss SSShhhaaafffttt ssseeeaaalll Motor bearings RRReeeppplllaaacccee | D | P | 同上，轴承更换/检查动作未独立成正确菜单，整页动作混入轴封列；需恢复列内动作。 |
| L05:001 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → Dry running | D | P | head 25为整页statement并非Spike Energy方法实体；即使翻转diagnosed_by仍错，先补独立方法片段。 |
| L05:002 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → cavitation | D | P | 同001：cavitation端点正确，方法是整页，需独立方法。 |
| L05:003 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → bearing wear | D | P | 同001且tail 6 bearing wear被中文改成loose fit；缺完整松配合端点，不能只反向。 |
| L05:004 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → bearing wear | D | P | 整页方法及bearing wear造成接触的完整目标未原子化；需至少独立方法片段。 |
| L05:006 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → Dry running | D | P | head 26为整页action，tail 1为Dry running而非磨损/疲劳/应力波；须新建完整目标与TSA片段，并辨识泵适用范围。 |
| L05:007 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → Dry running | D | P | 同上，microwelding不在独立实体菜单，需新增方法及目标。 |
| L05:008 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → Dry running | D | P | 同上，松动/摩擦/拍振没有完整独立端点，需补片段，不能拿Dry running改中文。 |
| L05:009 | 5 Dynamic Monitoring 5 Dynamic Typical P- Monitoring Conditions Monitored Skill Level Adva → diagnosed_by → bearings | F | N | TSA不适用滚动轴承的技术限制，当前diagnosed_by Component不合法且head仍整页；不能当正向泵诊断关系修复。 |
| L06:001 | oil level setting → inspected_by → It is extremely important that the oil level setting be checked and properly set if required. | F | N | 油位设定是参数而非Component；改成某物理部件检查需要另定任务对象，不是修原两端关系。 |
| L06:002 | proper oil level → specified_by → pump assembly section drawing | F | N | 油位参数及图纸规范指向，当前物理Component/Standard角色定义不能完整承载。 |
| L06:003 | The minimum oil level setting → operates_under → centerline of the side outlet of the oiler | F | N | 油位相对中心线的数值约束被写成部件工况，现有关系无参数比较/距离定义。 |
| L06:004 | oil level setting → specified_by → assembly section drawing | F | N | 图纸油位尺寸定义，当前Schema无参数定义关系。 |
| L06:005 | dimension given → located_in → top of the slant tube | F | N | 尺寸参考距离不等于located_in物理部件。 |
| L06:009 | BEARING CHAMBER THROUGH THE BASE OF THE OILER → mitigated_by → NEVER FILL THE BEARING CHAMBER THROUGH THE BASE OF THE OILER. | D | P | 头是BEARING CHAMBER THROUGH THE BASE OF THE OILER复合片段；需独立BEARING CHAMBER实体，再考虑maintained_by禁止灌注要求，不能只改关系。 |
| L06:019 | Stuffing Box → operates_under → purpose of a stuffing box | F | N | 填料函功能目的不是运行工况；当前关系空间缺功能/用途。 |
| L06:022 | pumped liquid → mitigated_by → Normally, the pumped liquid is not used to lubricate the stuffing box seal, as the liquid is usually | C | L | 同u25 choice 2 stuffing box seal和8完整动作已存在；替换pumped liquid头并改maintained_by，保留通常不使用脏介质/应外供密封液完整要求。 |
| L06:024 | steady dripping of liquid through the gland → indicates → The amount of the leakage is hard to define, but a steady dripping of liquid through the gland is re | C | L | 同u28已有6 glands与3完整推荐滴漏句，可作为glands operates_under完整工况；与假症状indicates工况区分。需保留原推荐模态。 |
| L06:027 | stuffing box doesn't over heat → prevented_by → Be sure the stuffing box doesn't over heat. | E | N | 确保不过热仅重述目标，未给具体措施，不凭空造prevented_by。 |
| L06:028 | flow rate → maintained_by → If overheating does occur, increase the flow rate until the temperature stabilizes. | D | P | 需独立overheating故障端点；u32只有flow rate/temperature stabilizes和此前否定过热片段，没有正向故障实体。阀门动作是另一潜在解释，不预设唯一。 |
| L06:031 | Allow some time for packing to adjust to new position. → mitigated_by → Allow some time for packing to adjust to new position. | D | P | u35仅time和整动作，没有packing完整对象；需从原文补packing实体及其同一装填步骤绑定。 |
| L06:032 | gland → mitigated_by → Never tighten gland to be leakproof as this will cause overheating and undue wear on shaft sleeves. | B | L | gland和Never tighten...完整动作均已有，改maintained_by表达负向维护要求，保留Never及后果；编译接口是否容纳该否定要求仍需验证。 |
| L06:033 | Never tighten gland to be leakproof as this will cause overheating and undue wear on shaft → causes → Never tighten gland to be leakproof as this will cause overheating and undue wear on shaft sleeves. | D | P | 头尾均为同一完整禁止句，需独立正向过紧原因、overheating及shaft sleeves wear后果；不能靠换causes方向或删除Never。 |
| L06:042 | stuffing box → maintained_by → 7. Make sure the stuffing box bushing (if furnished), is set at the bottom of the box. | D | P | u44仅stuffing box，没有bushing实体；必须补stuffing box bushing并保留if furnished。 |
| L07:001 | Too high temperature of the motor surface → causes → damage | D | P | temperature→explosion→damage链中explosion缺独立端点，damage ID被译成复合死亡损害；需拆源文新实体。 |
| L07:002 | The frequency of starts → causes → maximum temperature increase of the motor | E | N | 允许启动频率由温升决定不是频率导致温升，单翻转仍causes OperatingCondition，不能改写成源文未声明的因果。 |
| L07:003 | power reserves of the motor → causes → The frequency of starts | F | N | 功率余量是参数，当前Schema没有它对允许频率的依赖关系。 |
| L07:006 | Do not re-start the pump set before the pump motor is fully stopped. → mitigated_by → Do not re-start the pump set before the pump motor is fully stopped. | F | N | 禁止未停稳重启是运行程序，原两端同一动作；不能强塞成维护/故障措施关系。 |
| L07:008 | Recommend operate pump at 70 to 120% of BEP flow for hihg efficiency, operation outside th → causes → pump | D | P | tail pump物理词不是寿命缩短故障，需独立reduce the pump life完整后果及超BEP范围前件。 |
| L08:007 | spectrum analysis → mitigated_by →  For equipment enrolled in the Preventative Maintenance Program or RCM Program, when applying this t | C | P | u11已有8 pumps和21年检完整句，可重组inspected_by；但年度要求限定PMP/RCM设备，必须保留此条件且不把InspectionAction误当维护。 |
| L08:008 | advanced state of deterioration → causes → overall vibration | E | N | 劣化漏检说明不支持严重劣化causes总体振动不增的负向因果，不能只换关系挽救原主张。 |
| L08:009 | ISO specification → specified_by → vibration | D | P | 需overall measurement独立InspectionMethod与ISO specification，u22只有ISO/vibration和整句，无独立测量方法。 |
| L08:010 | components → occurs_at → vibration | F | N | 频带外振动未必FaultMode，components产生信号并非当前occurs_at故障部位关系；换向仍不支持故障认定。 |
| L08:011 | vibration → causes → overall vibration amplitude | E | N | 检测频带盲区不是频带外振动导致总体不变的确定故障因果；不能由negative标签恢复。 |
| L10:001 | DESMI NSL pumps → specified_by → These operation and maintenance instructions apply to both DESMI NSL pumps in Monobloc and Spacer de | F | N | 手册适用范围整句不是Standard对象；应保留元数据而非用specified_by充量。 |
| L10:002 | DESMI NSL pumps → specified_by → After the publish of this manual, the original manual will no longer apply to the products for subse | F | N | 版本/发货适用规则为手册治理元数据，不是整句Standard实体。 |
| L10:003 | DESMI NSL pumps → specified_by → But the original manual still applies to the past or in-use products. | F | N | 旧手册对在用产品适用性同上。 |
| L10:009 | pump suction → specified_by → The pump suction and discharge ports are casted flanges which comply with European Union flange stan | D | P | u12只有pump suction和整句，没有EU/ASME/ISO/JIS flange standards独立对象；需补原文标准片段，且不能推断具体标准编号。 |
| L10:010 | The pump → contains → wet part material | F | N | 过流材料不是物理Component；当前Schema无材料属性关系。 |
| L10:011 | wet part material → operates_under → The options and combinations include cast iron, copper alloy and stainless steel in different grades | F | N | 材料等级不是OperatingCondition，不能以运行条件关系表示材质。 |
| L10:014 | The pump → specified_by → The operation and maintenance instructions include descriptions for two product groups based on thei | F | N | 产品分组说明为元数据，不是整句Standard。 |
| L10:015 | The pump → contains → standard impeller diameter of the pump | F | N | 叶轮直径是参数，不是Component。 |
| L10:017 | line through inlet → located_in → center line of the shaft | F | N | 两中心线齐平为几何约束，不是物理Component located_in Component。 |

