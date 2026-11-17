# 实体、关系和来源范围案例

下列为本轮助手阅读分析，非专家Gold。显示折行可压缩；精确原文、原生ID、页哈希和全部候选ID在`SOURCE_UNIT_AUDIT.jsonl`。分类针对固定焦点，并非整个页面所有事实的穷尽标注。

## SU003：MP001物理p67，D

原文：

> hydraulic systems to evaluate the effectiveness of the filtration systems. The cleanliness of oil for
> equipment with components operating with small clearances and high pressures is of utmost importance to
> ensure continued operation. When the particle count exceeds a predetermined maximum, Ferrography
> testing (see 6/2.3) can be used to determine the source of the particles.
> ● Typical P-F interval: Weeks to months
> ● Skill level: Trained skilled worker
> 2.8.1 Advantages

原生单元：`MP001:p0067:blockwindow:0007`；页SHA256 `3bd972edf0dd15483b85ff8b37ab6405b04f5ac323ffb19e06d2a9dc953f66bc`。

初始候选ID：MPT-3c62bfc354272bfe9938、MPT-a62023540efe751bc35b、MPT-adea6779bbc9040706ce、MPT-a267abe4c6e735c1c064、MPT-ed4fd5ccc26d3dc48a8e；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：铁谱用于确定颗粒来源；颗粒计数超限是使用条件。原候选把条件当成诊断对象，目标角色和条件绑定均有问题。

源文代理参考：颗粒来源 → diagnosed_by → 铁谱分析。仅评价/GC使用，不是新修复器或新增正式知识。

## SU010：MP004物理p12，A

原文：

> The pump uses too
> much power
> --- CELL ---
> 1. Counter-pressure too
> low
> 2. The liquid is heavier
> than water
> 3. Foreign body in pump
> 4. Electric motor is
> running on 2 phases
> 5. RPM too high
> 6. Pump and electric
> motor not aligned.
> --- CELL ---
> Insert orifice plate or check
> valve/Contact DESMI
> Contact DESMI
> Dismantle the pump, remove
> the cause
> Check fuses, cable
> connection, and cable
> Fit bigger V-belt pulley on
> pump. Change RPM of
> electric motor.
> Align unit (see para. about
> alignment)

原生单元：`MP004:p0012:t00:r002:native_group`；页SHA256 `524a346bff264fda4398952d157d17e827d155ff79fd49113a64e8c040ce3534`。

初始候选ID：MPT-07f2f973e8e620046604、MPT-0e3e4beb304b3ac128ce、MPT-1a8ca5233e78331ae35e、MPT-20315e8d2e992d920a3a、MPT-2514844b8ed6607279ed、MPT-31790ddbc44abd794be0、MPT-3f8658341bc5f183f17b、MPT-419f8ce90925c6c42578；完整清单见逐单元JSONL。

焦点正式Claim：EXC-8e632613db4245bd8d7cfe67。同页其他Claim不能替代本焦点。

解释：首项背压过低导致泵功耗过大有明确故障表支持，正式图已表达；其余分支和措施并不因此都完整。

源文代理参考：背压过低 → causes → 泵功率消耗过大。仅评价/GC使用，不是新修复器或新增正式知识。

## SU012：MP004物理p4，D

原文：

> The suction branch of the pump is mounted well above impeller inlet. This is an advantage as the
> pump will not - in case of a clack flap leakage - loose all the priming water and consequently the
> priming ability.
> The pump has heavy shaft and bearing design which provide a long life even in case of belt drive
> and diesel engine operation.
> As the pump is self-priming, a foot valve will not be necessary on the suction line, just as the pump,
> contrary to ordinary centrifugal pumps, will resume pumping if, for a short moment, the liquid has

原生单元：`MP004:p0004:blockwindow:0010`；页SHA256 `e6252a76c2d7a101cf4384ed1b2639e69bb87e77b62cdd9c38fe6a02c00565bd`。

初始候选ID：MPT-2d6b04a54c14be0a92cd、MPT-5361eef6f7655f2a4ca1、MPT-375e2c628640c396f6f8、MPT-b003dfd3f751d2292387、MPT-ee0ab6e8ef47f5b1867d；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：SA吸入支管设计使止回阀泄漏时不丧失全部引水；原候选正向causes丢失否定，物理设计也不能伪装成维护动作。

## SU019：MP007物理p18，B

原文：

> The O-ring of the diffuser
> is damaged
> --- CELL ---
> Replace the O-ring
> --- CELL ---

原生单元：`MP007:p0018:t00:r016:native_group`；页SHA256 `9507e7132ce501f2ac37783d1d0cce81f209f4c55116072f9c144f1f91cbda40`。

初始候选ID：MPT-010b75859080402ca028、MPT-033b8f86acb144c60ba9、MPT-03e6e4f5c651fd439174、MPT-06a51c44574e608ff16d、MPT-1d5aa25a01e743fdfc40、MPT-281088fbc28c77d48842、MPT-505c83dd50217b9b6e3f、MPT-544a187cc269f6d395e6；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：导流器O型圈损坏对应更换O型圈，有同表原文和旧候选，但未进入正式图。此为AI源文支持代理，不是专家事实。

源文代理参考：导流器O型圈损坏 → mitigated_by → 更换O型圈。仅评价/GC使用，不是新修复器或新增正式知识。

## SU023：MP015物理p31，D

原文：

> 27, 28, 32
> Pump has lower power consumption than
> 1, 8, 13, 14, 23, 24, 25, 26, 29, 31
> normal
> Mechanical seal have to be replaced to
> 15, 18, 21, 28, 30, 31, 32, 33
> often

原生单元：`MP015:p0031:blockwindow:0040`；页SHA256 `611bb32e3c568794858e680491ef08bcaeebf49ac14d4b34d2c18b78b57a86ef`。

初始候选ID：MPT-a4edb4cb84919b0b9158、MPT-1a9de2c3ee3613632528、MPT-3a4c6f710e4a3aaa4f8d、MPT-4dbde831f65f7c205d7a、MPT-62b2c067b4f533c539f2、MPT-6abed99ff52fba2e9881、MPT-6e5e33934993195f2c69、MPT-813913fa2e5e6e8673f8；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：故障表用原因编号跨页引用；把整串编号当Cause实体并未表达真实原因，需解析手册内引用，不能直接计作新因果事实。

## SU027：MP016物理p5，C

原文：

> replace along with Lip Seals if necessary.
> clamped versions.
> • Impeller should be pulled along the axis of the pump body.
> By ensuring a visual inspection daily and regular checks at
> planned intervals, pumps can be maintained to maximum
> • Twisting the impeller in the direction of pump rotation will
> performance for many years.

原生单元：`MP016:p0005:blockwindow:0103`；页SHA256 `bf496aa04ac9b71e4a6d66fff4bcb28aee3f281d5cd60d77e740764b9ebb3e9e`。

初始候选ID：MPT-5f4b53832101eb06da93、MPT-0ac73fcc9181de770cb0、MPT-dd488c7009477dd5cea7、MPT-19dcc338a778a753cc32、MPT-f870b7d889096551f3e2、MPT-4b872822262f37e88104、MPT-4defeb97309be9cadc39、MPT-673f586d1001a9d6f53c；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：沿泵体轴线拉出叶轮是完整操作；既有同页候选有检查/修换叶轮等相关动作，但未表达这个完整方向性动作。只指留存导出主张，不宣称所有API原文从未包含。

源文代理参考：叶轮 → maintained_by → 沿泵体轴线拉出叶轮。仅评价/GC使用，不是新修复器或新增正式知识。

## SU029：MP017物理p7，D

原文：

> equipped) for cracks, dents, damaged
> threads, and other obvious damage.
> POSITIONING PUMP
> b. Check for and tighten loose attaching hard-
> ware. Since gaskets tend to shrink after dry-
> Lifting
> ing, check for loose hardware at mating sur-

原生单元：`MP017:p0007:blockwindow:0066`；页SHA256 `5941d89b2ec918c9e59f40e4e9a1620205b88c144b129f09a82c605aac1d579c`。

初始候选ID：MPT-28f0c1b796c760a72eb1、MPT-502dd386914123ebbaae、MPT-6df7b76507a8ad01d255、MPT-7f635e56f9773627e420、MPT-a2725f8cb64547450100、MPT-a2a6f026218f857b86ad、MPT-a3e3e6b2af6da53ee0e9；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：检查并紧固松动紧固件同时包含检查和纠正，单标InspectionAction会混合角色；文字出现不等于两个角色均结构化。

源文代理参考：紧固件松动 → mitigated_by → 紧固松动的安装硬件。仅评价/GC使用，不是新修复器或新增正式知识。

## SU031：MP018物理p26，B

原文：

> Corrosion
> --- CELL ---
> Balls and raceways rusted.
> --- CELL ---
> 1. Water entering the housing.
> 2. Condensation inside the
> housing.
> 3. Lubricant breaks down into acid.
> (Wrong lubricant).

原生单元：`MP018:p0026:t00:r007:native_group`；页SHA256 `89a562ee89c736033cd7c778da72ecc04a5e7d26312c939c57d0bb3000571cd0`。

初始候选ID：MPT-1e0f2caadfd5370417f8、MPT-26bca26fd703442b7eae、MPT-500e898908d0dffee317、MPT-63076c83417401ece6d0、MPT-75ad0bc57ccbe2790796、MPT-784230fd389efc6081b2、MPT-7b89725b75f463c8c22b、MPT-b5f8706a4c5a5eda7d88；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：腐蚀表现为滚动体/滚道生锈有源文和候选；同表多个腐蚀原因已入图不等于该表现关系也已发布。

源文代理参考：腐蚀 → manifests_as → 滚动体和滚道生锈。仅评价/GC使用，不是新修复器或新增正式知识。

## SU032：MP018物理p28，C

原文：

> Patterson Pump Serial Number
> Assembly Drawing Number
> Name of Part
> Item Number
> WARNING ! ! Do not attempt to substitute with parts manufactured or supplied by any
> concern other than Patterson Pump Company as subsequent damage to the pump may
> occur.

原生单元：`MP018:p0028:blockwindow:0018`；页SHA256 `fb54286ee5dcc2865d90f7f44a7e2d8649e566c118e615109dad4616b1f0a949`。

初始候选ID：MPT-2c09d5e262dc441e9718、MPT-47ec8b6ad5d29cecc5ea、MPT-65100feb589b4a70e085、MPT-a586debf45e96f550b6d、MPT-b937260ad222eb9ba1a2；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：非Patterson来源替代件可能造成泵损坏是明确警告；当前页候选只保留备件储备，留存导出中未见该完整关系。may不能改成必然。

源文代理参考：使用非Patterson公司供应部件 → causes → 泵损坏。仅评价/GC使用，不是新修复器或新增正式知识。

## SU033：MP018物理p15，E

原文：

> Allow only experienced maintenance personnel to lubricate this unit. Before attempting to lubricate
> this unit, refer to your specific assembly drawing to determine the specific type and location of bearings
> that are used. The bearings will accept grease while operating.
> The following steps constitute the procedure for lubricating the bearings:
> 1. Clean the exterior of the unit around the grease and drain plugs.
> 2. Remove the drain plugs and if grease holes are plugged, remove the plugs and install grease
> fittings in their place.

原生单元：`MP018:p0015:blockwindow:0021`；页SHA256 `58eadd527dda4fbe0d4fe7537a5f8456cd90c52a263e5155b1e719a77bfe0a77`。

初始候选ID：MPT-70f7486eb54364cceea7、MPT-82e3c63fca49d4c7ce82、MPT-53b351566afe8697a4ba、MPT-ae8b5a667cee094cc81c、MPT-b87777781d23ca7af0fe、MPT-8103d5279b572355547b、MPT-e9d950d470e221acd967、MPT-8d6a4246e8290b545406；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：本单元明确要求借助本机装配图确定轴承类型和位置；泛化润滑程序不能给出该机具体轴承配置。

## SU036：MP019物理p8，D

原文：

> The degree of protection and diameter are specified in
> Mounting accuracy of coupling half: check that clearance
> the documents relating to the cable gland.
> b is less than 0.05 mm and that the difference a1 to a2 is
> also less than 0.05 mm. See Figure 3.
> WARNING
> Re-check the alignment after final tightening of the bolts

原生单元：`MP019:p0008:blockwindow:0064`；页SHA256 `1c928067af3bbc340abca2a29bb64a59c4a27ed816a24eca86a3214713f554be`。

初始候选ID：MPT-12a2c270269672a77df5、MPT-44a68afb599edb67fa60、MPT-4674e78c314c76528ea7、MPT-5a1e1b9115959f46abb1、MPT-6b838c480b6c1089a541、MPT-7c5048c9bf5532530679、MPT-e4dfa94cbb85a53513d7、MPT-f984be631796003b2580；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：联轴器半体安装间隙b及a1−a2均须小于0.05mm；原候选把量化条件当Standard检查对象，丢掉对象—参数绑定。

源文代理参考：联轴器半体 → inspected_by → 检查联轴器半体安装精度。仅评价/GC使用，不是新修复器或新增正式知识。

## SU039：MP020物理p23，D

原文：

> Bearing temperatures to 160°F (71°C) are normal. Temperatures over 200°F (93°C) are too high. The human
> hand can not estimate high temperatures. Use a thermometer or other device for temperature measurement.
> IMPORTANT
> A. Oil level must be correct before unit is started.
> B. Oil lubricated frames must be installed horizontally and level.
> C. Grease lubricated motors and frames must be maintained per instructions accompanying
> the pump. Grease code EP-2 is recommended for most applications. Added grease must

原生单元：`MP020:p0023:blockwindow:0003`；页SHA256 `56058a7b375f3393caa5880d20399cd618c2ad809f3ec172d45f2ef53ba9f9cc`。

初始候选ID：MPT-22c7d05910c5d7bd0104、MPT-ddecb636f6702833b867、MPT-6b9dd8c31340f762101c、MPT-6eb5b5b715333202e6a5、MPT-d7b3a2315cbc6dfe5d07、MPT-d2fc837ed9c802a198da、MPT-e3a809f40ce973d9b91c、MPT-22055af58693a6beefab；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：轴承正常温度和过高阈值是不同数值判断，160°F和200°F间不能自行填结论；测温方法已入图不等于阈值被结构化保存。

## SU040：MP021物理p20，D

原文：

> Grease used for
> O-Pro™ Seal
> --- CELL ---
> Edible Grease,
> aluminum complex
> --- CELL ---
> Chevron FM ALC
> EP 0, 1, 2

原生单元：`MP021:p0020:t01:r003:native_group`；页SHA256 `b12b1c44bfe0eee05393ab6636e807869ec6c6e82a567c4505146409ec0ca35f`。

初始候选ID：MPT-03e6fe0a8152ba05a237、MPT-4a01238ae1c04916de41、MPT-60560bd4539d8c817a36、MPT-68d6b18fa3d9b4fc27dd、MPT-6fe78be9f30c16feda07、MPT-793110ede8d6134ea970、MPT-b4674c0a45ee405d404f、MPT-c87fccd69921802e8929；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：O-Pro密封使用食用级复合铝基脂，材料名不能直接伪装为MaintenanceAction；用脂动作与产品/适用密封需分开。

源文代理参考：O-Pro™密封 → maintained_by → 使用食用级复合铝基润滑脂。仅评价/GC使用，不是新修复器或新增正式知识。

## SU042：MP021物理p14，D

原文：

> 1. Check pump ports to be sure they are square and in the
> proper position; shim or move the pump as required. Do
> not force piping to line up with the ports.
> 2. If the pump is driven by a flexible coupling(s) either directly
> connected to the motor or through a reducer, remove any
> coupling guards or covers and check alignment of the
> coupling halves. At a minimum, a straightedge (such as a

原生单元：`MP021:p0014:blockwindow:0011`；页SHA256 `e9638a5c3f1b597598d412dcb3cd34398bed96f748a0b263e7a4a86a99b514cf`。

初始候选ID：MPT-06328e953e9ee3ae21a9、MPT-47a69fbeb04e00f1e909、MPT-6202ca1229d0d73ef4ce、MPT-86f186f55267605f1fa6、MPT-03a8f99e5d4f5292c6fe、MPT-b332f4e2f7f87f92a3e5、MPT-d8ff99b0e51aff3df592、MPT-ec0d7eef0f4bea228221；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：首个检查对象是泵口，不是“对中”工况；原候选对象类型/角色错配。现有inspected_by本可表达，无需新增关系。

源文代理参考：泵口 → inspected_by → 检查泵口是否方正且位置正确。仅评价/GC使用，不是新修复器或新增正式知识。

## SU043：MP022物理p42，D

原文：

> Product wetted steel parts AISI 316L
> Other steel parts Stainless steel
> Finish Standard blasted
> Product wetted seals EPDM (standard)
> Other O-rings EPDM (standard)
> Alternative seals Nitrile (NBR) and fluorinated rubber (FPM)

原生单元：`MP022:p0042:t00:r003:native_group`；页SHA256 `b85d838afa36669c2c0161435a10490f493afa3dbe39e2799c115deab33e283c`。

初始候选ID：MPT-0f6855a201495ea8fda9、MPT-2103a27e5079655a1897、MPT-82937c4971ec18600d0f、MPT-3d3f8826fe7af13df9b2、MPT-6e8ec0f7b11714d33244、MPT-979290f44478820da12f、MPT-9c10a3e5910d3464044d、MPT-c6c30a1109c9fd4ab806；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：过流钢材、密封材料和替代密封需要对象—属性—替代范围关联；平铺三元组或任意Standard映射不能保证完整表达。

## SU045：MP022物理p7，D

原文：

> AAAlllwwwaaayyysss read the technical data carefully. (See chapter 6.1 Technical data)
> AAAlllwwwaaayyysss use a lifting crane when handling the pump.
> AAAlllwwwaaayyysss remove the air screw and impeller before checking the direction of rotation.
> NNNeeevvveeerrr start the pump if the impeller and air screw are fitted and the pump casing is removed.
> OOOpppeeerrraaatttiiiooonnn:::
> AAAlllwwwaaayyysss read the technical data carefully. (See chapter 6.1 Technical data)
> NNNeeevvveeerrr touch the pump or the pipelines when pumping hot liquids or when sterilising.

原生单元：`MP022:p0007:blockwindow:0006`；页SHA256 `276b602937f42abeef8e3aa0967e2a1db10773bfabe911d5eb60ba2d2b514291`。

初始候选ID：MPT-146bec48307b3067775e、MPT-64ba740999bb4f5af5d3、MPT-8163b67f7833b8b9656b、MPT-87b774b5f3b16d46e325、MPT-a48bf7457219fec5bbe9、MPT-af64a0b55a6ef51c1571、MPT-d0e5b5031e61f5e4754f、MPT-e284f88bd950e6f0e863；完整清单见逐单元JSONL。

焦点正式Claim：未发现焦点的同类型五元签名。同页其他Claim不能替代本焦点。

解释：检查转向前拆除空气螺钉及叶轮、特定拆装状态禁止启动，包含前提/时序/禁止；当前Equipment prevented_by等伪三元组不能替代。

## GA直接桥的源文复查

结构上连接旧组件并不等于语义上可用于同一泵实例。5条直接桥全保留，不按结果挑选：

- `AQC-e80377f7fc73fe96418eba64`：压力容器 → inspected_by → 水压试验；MP003物理p417，原文 `The Surveyor is to witness hydrostatic tests on all pressure vessels.`。一般压力容器水压见证检验，源文本身清楚；但不证明与当前泵本体具有同一设备实例或试验条件。

- `AQC-477bb46e29b8cc423aa190f8`：泵 → inspected_by → 液压试验；MP003物理p500，原文 `7.3.2(a) Hydrostatic tests. The pumps are to be hydrostatically tested to a pressure of at least 1.5P`。泵水压试验及至少1.5P有直接原文；仍需保留具体章节设备范围和试验压力，不能只有泛化泵—液压试验。

- `AQC-4daba054bba2b0068ecebbb7`：轴套 → inspected_by → 水压试验；MP003物理p312，原文 `Shaft liners are to prove tight under hydrostatic test of 1.0 bar (1 kgf/cm2, 15 psi).`。shaft liners与中文轴套的类名可能相同，源页为推进轴系规则语境；不能自动当成另一手册泵轴套的同一实例。

- `AQC-e14f234b1537eb10bdb362a4`：长期停机期间液体冻结 → causes → 泵损坏；MP005物理p56，原文 `Liquids may freeze during long-term shutdown periods, which could damage the pump.`。长期停机时液体冻结可能损坏泵有直接原句；条件部分在头实体文字中，may/could不能解释为必然因果。

- `AQC-91e30ab8cc9d99a2adf21a8b`：故障 → prevented_by → 处置措施；MP001物理p9，原文 `A condition-monitoring task is a scheduled task used to detect the potential onset of a failure so that action
            can be taken to prevent such failure.`。通用状态监测定义说采取action防故障，语义非常抽象；即使连接了实体，也没有提供一个具体可执行维修措施。


同一中文“轴套”若代表部件类别，可组织推进轴套与泵轴套；若解释为同一个物理实例则越界。MP003 p312明确是Propulsion Shafting，不是泵手册。这说明问题在于身份层与适用范围，而非水压试验这个关系本身一定错误。
