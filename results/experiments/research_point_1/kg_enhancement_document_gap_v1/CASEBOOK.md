# 实际案例：排名恢复、条件类比与负迁移

所有新增分数都来自187项开发验证关系及应用候选；没有重评分224项测试。排名改善只相对既有自动构图事实，不代表现场诊断准确率。源文解释属于Codex助手阅读分析，不是专家Gold。

## transport_win：EXC-f31d99ea4fb68790c420a906

目标：润滑剂迁移 → prevented_by → 定期手动盘车；预测方向=tail。查询可见文档=[]；这里展示的参考文档只用于事后说明，没有作为检索输入。

| 方法 | 三个种子的正确实体排名 |
| --- | --- |
| T0 | 1.0,32.0,1.0 |
| T1 | 7.0,117.0,6.0 |
| T2 | 7.0,117.0,6.0 |
| T3 | 1.0,32.0,1.0 |
| T5 | 5.0,91.0,3.0 |
| text_only | 7.0,117.0,6.0 |

参考：MP019物理p78，原文 `L'albero deve essere ruotato a mano periodicamente per                       
     prevenire migrazioni di lubrificante.`。

迁移片段：润滑脂迁移 → prevented_by → 定期手动盘车，来源[['MP019', 6]]，检索分数=0.844889。

原始证据：It is recommended that shafts are rotated periodically by                    
     hand to prevent grease migration.

迁移片段：润滑脂变质 → prevented_by → 建议定期手动盘车，来源[['MP019', 114]]，检索分数=0.706852。

原始证据：Akselia suositellaan pyöritettävän säännöllisin väliajoin                    
     käsin rasvan muuttumisen estämiseksi.

解释：润滑剂/润滑脂迁移的同族多语言近义记录使目标更接近已出现的盘车措施；它说明检索运输可恢复排序，同时暴露有限别名屏蔽的残留风险。不能作为新故障机理发现或独立跨来源泛化案例。

## transport_loss：EXC-40370a67587645477bdbb834

目标：冷却介质超温 → diagnosed_by → 冷却介质温度监测装置；预测方向=tail。查询可见文档=[]；这里展示的参考文档只用于事后说明，没有作为检索输入。

| 方法 | 三个种子的正确实体排名 |
| --- | --- |
| T0 | 3.0,1.0,1.0 |
| T1 | 1.0,1.0,1.0 |
| T2 | 1.0,1.0,1.0 |
| T3 | 3.0,1.0,1.0 |
| T5 | 2.0,1.0,1.0 |
| text_only | 1.0,1.0,1.0 |

参考：MP003物理p794，原文 `Semiconductor assemblies with forced cooling are to be provided with a means of monitoring the
                 temperature of the cooling medium. Over-temperature of the cooling medium is to be alarmed
                 locally and at a continuously manned location and the equipment shutdown when temperature
                 exceeds the manufacturer specified value.`。

迁移片段：冷却介质温度高 → diagnosed_by → 报警监测，来源[['MP003', 959]]，检索分数=0.896219。

原始证据：Temperature – high
--- CELL ---
x

迁移片段：冷却介质出口温度高 → diagnosed_by → 报警监测，来源[['MP003', 963]]，检索分数=0.865525。

原始证据：Temperature at outlet -
high
--- CELL ---
x

解释：原本纯文本已排第1，迁移到泛化“报警监测”后一个种子退到第3。对冷却介质这一相近词组，目标设备类别/章节范围仍重要。单个种子退化不是所有候选语义错误的证明。

## cross_document_win：EXC-2f17fb8ca5556b483769b051

目标：启动负载过高 → inspected_by → 检查电机启动负载；预测方向=tail。查询可见文档=['MP019']；这里展示的参考文档只用于事后说明，没有作为检索输入。

| 方法 | 三个种子的正确实体排名 |
| --- | --- |
| T0 | 1.0,2.0,2.0 |
| T1 | 1.0,1.0,2.0 |
| T2 | 1.0,2.0,2.0 |
| T3 | 1.0,2.0,2.0 |
| T5 | 2.0,2.0,2.0 |
| text_only | 2.0,3.0,2.0 |

参考：MP019物理p19，原文 `Starting load too high
--- CELL ---
Check the start load of the motor.`。

迁移片段：转速过高 → inspected_by → 核实电机转速、减速比、皮带轮尺寸及其他驱动部件是否适合工况，来源[['MP021', 17]]，检索分数=0.705527。

原始证据：Running too fast. Verify the motor speed, reducer ratio, sheave size, and other drive components are correct for the application?

迁移片段：转速过低 → inspected_by → 检查电机转速正确且接线无误，来源[['MP021', 17]]，检索分数=0.687258。

原始证据：Running too slowly. Check the motor is running at the correct speed and that it is wired correctly.

解释：MP021的转速/驱动核查提供相近InspectionAction形式，对MP019启动负载检查有部分种子排名改善。但该片段不是“转速异常就等于启动负载过高”的事实依据，不能直接发布目标关系。

## cross_document_loss：EXC-6a5a6b7b076fada819c170ef

目标：水锤 → prevented_by → 蒸汽供汽管路安装防止积水；预测方向=tail。查询可见文档=['MP003']；这里展示的参考文档只用于事后说明，没有作为检索输入。

| 方法 | 三个种子的正确实体排名 |
| --- | --- |
| T0 | 2.0,6.0,2.0 |
| T1 | 1.0,3.0,2.0 |
| T2 | 2.0,5.0,2.0 |
| T3 | 2.0,6.0,2.0 |
| T5 | 2.0,3.0,2.0 |
| text_only | 1.0,3.0,2.0 |

参考：MP003物理p625，原文 `Steam supply piping is to be installed such that it will prevent accumulation of water to avoid
                 water hammer.`。

迁移片段：水锤效应 → prevented_by → 先关闭排出阀，来源[['MP018', 14]]，检索分数=0.845919。

原始证据：However, in
       order to prevent water hammer effects, the discharge valve should be closed first.

迁移片段：水锤/液压冲击 → prevented_by → 保证足够降速时间并避免过快关闭阀门，来源[['MP005', 64]]，检索分数=0.814896。

原始证据：1. Have sufficient
ramp down time
and avoid closing
valves too fast.
2. Correct usage of
non-return valves

解释：MP003蒸汽供汽管路防积水与MP018/MP005停泵、阀门控制抑制水锤处于不同设备/阶段。虽然prevented_by及端点类型一致，近义水锤仍会造成负迁移；这是单靠类型与同关系不足的真实例子。T4因查询缺少这些范围字段而没有拦住。

## 同文档条件类比也不是已确认新知识


### GAPREL-e79ed689a457a0aee0ed

机械密封旋转部件 → maintained_by → 将机械密封旋转部件(1220)装到轴上并按图16及对应表调整至距离x1后锁紧紧定螺钉。分数0.610031，全2150目录未过滤排名8.0；都不是事实概率。

三个前提：

- `EXC-b5a88602ceda5f6244300418`，机械密封旋转部件 → maintained_by → 从泵轴上拆除机械密封旋转部件(1220)；MP015物理p41，原文 `Remove the rotating part of the mechanical seal (1220) from the pump shaft.`。

- `EXC-e32422acf46676e6db558797`，机械密封旋转部件(1220) → maintained_by → 从泵轴上拆除机械密封旋转部件(1220)；MP015物理p42，原文 `Remove the rotating part of the mechanical seal (1220) from the pump shaft.`。

- `EXC-93ec7148b5b9083f0febff37`，机械密封旋转部件(1220) → maintained_by → 将机械密封旋转部件(1220)装到轴上并按图16及对应表调整至距离x1后锁紧紧定螺钉；MP015物理p43，原文 `6 Fit the rotating part of the mechanical seal (1220) onto the shaft. Adjust the rotating
                         part of the mechanical seal to distance X1 from figure 16 and corresponding table.
                         Lock it by fixing the set screw.`。


限制：机械密封旋转部件有编号/无编号的端点可能是粒度差异；p42=M7N、p43=MD1，X与X1及组装条件不可混用。共享拆卸动作不能证明所有组装措施通用。

### GAPREL-5b316df91b13a1671219

异常噪音 → diagnosed_by → 倾听任何异常噪声。分数0.644545，全2150目录未过滤排名6.0；都不是事实概率。

三个前提：

- `EXC-3ac8433921d7b07c933d5c26`，异常噪音 → diagnosed_by → 听诊；MP016物理p28，原文 `Ascolta i rumori inaspettati.`。

- `EXC-febfe028efd44fe1c39ca9a7`，异常噪声 → diagnosed_by → 听诊；MP016物理p15，原文 `Écoutez les bruits inattendus.`。

- `EXC-679f3646ee8d88e9f6f48e78`，异常噪声 → diagnosed_by → 倾听任何异常噪声；MP016物理p5，原文 `Listen for any unusual noises`。


限制：异常噪音/异常噪声及多个倾听动词来自同一柔性叶轮泵手册的多语言重复。先核实别名与证据去重；不可把五条组合计为五个新诊断事实。

### GAPREL-14d14f0c219ea9145116

表面/近表面裂纹及不连续缺陷 → diagnosed_by → 液体染料渗透检测。分数0.540477，全2150目录未过滤排名8.0；都不是事实概率。

三个前提：

- `EXC-64664e7bb8dcacc363341717`，磨损 → causes → 表面/近表面裂纹及不连续缺陷；MP001物理p94，原文 `surface/near-surface cracks and discontinuities
            caused by problems such as fatigue, wear, inclusions, laminations, heat treatment, hydrogen embrittlement,
            seams, and corrosion`。

- `EXC-f42ab5ba5f1f19c6d6eeb450`，磨损 → causes → 表面不连续或裂纹；MP001物理p93，原文 `surface discontinuities or cracks due to problems such as
            fatigue, wear, surface shrinkage, and grinding`。

- `EXC-8036fea8572cd6d13a15ddbf`，表面不连续或裂纹 → diagnosed_by → 液体染料渗透检测；MP001物理p93，原文 `The use of liquid dye penetrants can help detect surface discontinuities or cracks due to problems such as
            fatigue, wear, surface shrinkage, and grinding.`。


限制：p93液体渗透仅限表面开口缺陷且不适用高孔隙材料；p94-95磁粉检测有材料和表面/近表面限制。共享磨损原因不能证明检测方法可无条件互换。

## 跨文档暂缓线索：SCOPE-e839883e937d0dac41

泵流量不稳定 → inspected_by → 核对数据表Q/H曲线和NPSH或联系DESMI。原关系模式来自MP004, MP005，同角色共享泵吸入空气。源文前提如下；不同pump_type字符串不直接当作冲突，也不默认为可互换。


- `EXC-26e8ddc22abd5b9fa372b2d0`：泵吸入空气 → causes → 泵流量不稳定；MP004物理p12，`The pump capacity is
unstable
--- CELL ---
1. Suction line leaks
2. Air pockets in suction
line
3. The pump takes air`。

- `EXC-2d132130b508b2d34cb46441`：泵吸入空气 → causes → 泵无流量或流量过低；MP005物理p60，`5. Pump takes air`。

- `EXC-0219d14db2cf2588c37a5645`：泵无流量或流量过低 → inspected_by → 核对数据表Q/H曲线和NPSH或联系DESMI；MP004物理p11，`The pump has no or
too low capacity
--- CELL ---
Change direction of rotation
to clockwise when viewed
from shaft end (the direction
of the arrow)
Clean or replace
Clean the pump
Find the leakage, repair the
fault, non-return valve not
submerged
Check data sheet Q/H curve
and NPSH or contact DESMI
As 5
Fit smaller V-belt pulley on
pump. Change RPM of
electric motor`。


判定：需要核实共享原因是否确属同一机制、Q/H/NPSH核查是否适用SA/NSL双方、源段是否仅限特定泵配置；目前只保留前提，不称新增正确事实。其余16条见同一JSONL。

## 原始候选已有与具体方向问题


- `GAPREL-246d27d7c7df9ce9e49f`，过载 → causes → 电机过载：D，MP022 p22的“Motor overloaded”是故障表的现象，列出的原因是黏液/高密度液、低出口压力等，不能从该词条推出“过载导致电机过载”。这是同义重述/角色混淆风险，未见页也不能作为支持。。来源与原预测ID均在JSONL保留。

- `GAPREL-c35ede7cbd68eecc5762`，故障 → manifests_as → 报警：A，Initial record already expresses this relation under finite aliases; not a new algorithm discovery.。来源与原预测ID均在JSONL保留。

- `GAPREL-aad2ea44b81d4a79263b`，功能故障 → evolves_to → 故障模式：D，MP002 p62描述functional failure是failure mode对系统的影响，p14也说failure mode可能导致functional failure；不支持“功能故障 evolves_to 故障模式”，更不能把概念定义自动变成时序演化。。来源与原预测ID均在JSONL保留。


A不算算法新发现；D的两项沿用已有AI源文分析，不能改称独立专家核验。所有C保持未知。
