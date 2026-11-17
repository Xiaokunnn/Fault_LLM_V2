# 实际记录案例


本文件是只读AI分析，原始标签、图谱和模型均未改变；相似度和可定位原文不是专家事实真值。


## 1. 原完整图的单Claim双实体分量

EXC-00e50723917c907550c727e8：轴封弹簧 → maintained_by → 确保轴封弹簧端部的环位于叶轮凹槽内；fold=test

完整图中这两个端点有该关系，度不是0；遮蔽该Claim后两端都无剩余关系，属于典型单边分量断开。

- MP005物理页109，家族DESMI，设备centrifugal_pump：NOTE: Take care that the ring at the end of the shaft seal spring locates in the recess of the
                   impeller.

## 2. 事实组共遮蔽

EXC-01175899f4fc41ef1b533e09：电源故障 → diagnosed_by → 自监测机制；fold=test

{"claim_id":"EXC-01175899f4fc41ef1b533e09","entity_id":"EXE-47f83df642b55a38fba79c01","entity_type":"InspectionMethod","full_component_size":8,"full_incident_claims":3,"full_neighbor_degree":3,"label":"自监测机制","masked_neighbor_degree":0,"other_claims_after_own_group_remove":0,"other_claims_after_single_target_remove":2,"reason":"other_full_claims_all_within_own_fact_group","side":"tail","train_neighbor_degree":0}

- MP003物理页894，家族ABS，设备marine_pump_and_piping_systems：The monitoring system is to include a self-monitoring mechanism such that a fault (e.g., power failure,
            sensor failure, etc.) may be detected and alarmed.

## 3. 额外移除验证组

EXC-621f632d7ba9a27029abbce5：防护罩 → maintained_by → 拆除防护罩；fold=test

{"claim_id":"EXC-621f632d7ba9a27029abbce5","entity_id":"EXE-f9ce6aa8f8c842a024fca47e","entity_type":"Component","full_component_size":4,"full_incident_claims":3,"full_neighbor_degree":3,"label":"防护罩","masked_neighbor_degree":1,"other_claims_after_own_group_remove":1,"other_claims_after_single_target_remove":2,"reason":"validation_groups_remove_remaining_incidence","side":"head","train_neighbor_degree":0}

- MP005物理页81，家族DESMI，设备centrifugal_pump：1. Remove guards (28).

- MP005物理页82，家族DESMI，设备centrifugal_pump：1. Remove guards (28).

- MP005物理页80，家族DESMI，设备centrifugal_pump：1. Remove guards (28).

## 4. 同源家族跨文档的相同Claim

已经聚合，不是遗漏；不同文档与不同设备范围不等同独立证据或条件完全一致。

EXC-09da661899903e189f8d6f10

- MP004物理页11，家族DESMI，设备self_priming_centrifugal_pump：The pump has no or
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
electric motor

- MP005物理页60，家族DESMI，设备centrifugal_pump：Find the leakage, repair the fault,
non-return valve not submerged

## 5. 同源家族跨文档的相同Claim

已经聚合，不是遗漏；不同文档与不同设备范围不等同独立证据或条件完全一致。

EXC-487143e301c8547a04eb1c24

- MP004物理页11，家族DESMI，设备self_priming_centrifugal_pump：The pump has no or
too low capacity
--- CELL ---
1. Wrong direction of
rotation
2. Piping system choked
3. The pump is choked
4. Suction line leaks,
pump takes air
5. Suction lift too high
6. Pump and piping
system wrongly
dimensioned
7. RPM too low

- MP005物理页60，家族DESMI，设备centrifugal_pump：7. Pump and piping system
wrongly dimensioned

## 6. 语义相似实体的正反例

SEM-855a016d230d27040cce：轴承损坏 / 损坏轴承，cos=0.9772；同完整分量=False

可能近义但须保留部件/工况范围

- MP005物理页13，家族DESMI，设备centrifugal_pump：Observe the information on maximum flow rates specified in the product literature (to prevent
        overheating, mechanical seal damage, cavitation damage, bearing damage, etc.).

- MP005物理页13，家族DESMI，设备centrifugal_pump：Observe the information on minimum flow rates specified in the product literature (to prevent
        overheating, bearing damage, etc.).

- MP019物理页53，家族ABB，设备low_voltage_induction_motor：Des lubrifiants non miscibles peuvent                                      
       endommager les roulements.

- MP018物理页21，家族PATTERSON_PUMP，设备non_clog_centrifugal_pump：Failure to use this procedure can damage the bearing.

## 7. 语义相似实体的正反例

SEM-9c0c316a36ed0f9a6297：o型圈(21) / o型圈(12)，cos=0.9616；同完整分量=False

编号不同的部件不能凭高相似度合并

- MP005物理页109，家族DESMI，设备centrifugal_pump：Place the O-ring (21) between pump casing and                           
                                                                                  
         rear cover on the rear cover where it can be held                        
         with a little grease.

- MP022物理页29，家族ALFA_LAVAL，设备self_priming_centrifugal_pump：Remove the O-ring (12) from the back plate (25)

## 8. 语义相似实体的正反例

SEM-891f86563eec612618a3：泵和电机轴承 / 泵和电机轴，cos=0.9626；同完整分量=False

轴承与轴并非同一部件，名称近似可误导

- MP006物理页9，家族DESMI，设备centrifugal_pump：Unrestricted ventilation of the motor bracket is therefore necessary to provide sufficient cooling of pump and motor
     bearings

- MP015物理页34，家族SPX_FLOW__JOHNSON_PUMP，设备horizontal_self_priming_centrifugal_pump：Check the alignment of pump and motor shaft, see paragraph 3.4.3 "Alignment of the
                         coupling".

## 9. 相似关系并不自动构成条件等价事实

不自动合并；共享故障/型号差异/动作编号及阶段必须区分。

FACTSIM-b2ced2d4abb2b857b5c1

- MP019物理页20，家族ABB，设备low_voltage_induction_motor：Hot bearings
--- CELL ---
Excess lubricant

- MP018物理页15，家族PATTERSON_PUMP，设备non_clog_centrifugal_pump：Do not
                      operate pump with excessive amount of lubricant. Such action will cause bearings
                      to overheat.

## 10. 相似关系并不自动构成条件等价事实

不自动合并；共享故障/型号差异/动作编号及阶段必须区分。

FACTSIM-36fff44bc224cf38a1b5

- MP015物理页43，家族SPX_FLOW__JOHNSON_PUMP，设备horizontal_self_priming_centrifugal_pump：1 Disassemble the impeller (0120), see paragraph 7.6.3 "Disassembly of the impeller,
                         bearing bracket 1" and paragraph 7.6.5 "Disassembly of the impeller, other bearing
                         brackets".

- MP022物理页29，家族ALFA_LAVAL，设备self_priming_centrifugal_pump：Remove impeller (27)


三个有向三跳路径的所有端点、关系与源文另见directed_three_hop_cases.jsonl。它们跨家族且没有共同设备类型字面签名，不能直接作为三条有效因果链。

事实组共遮蔽和验证组额外删除的全部关联Claim及fold在casebook.jsonl内，不能只靠例图推断原因。
