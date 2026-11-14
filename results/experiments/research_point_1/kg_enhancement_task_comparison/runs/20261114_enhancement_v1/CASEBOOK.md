# 本轮试验增量逐案证据

22条试验Assertion对应19个新增Claim和2条现有Claim的新增证据；同一新增Claim可能有多条来源Assertion。
这是当前AI非盲原文审查后的沙盒结果，不是专家Gold，也不是已通过完整正式发布流程的图谱。
读取规则：先看条件，再看关系；原有文档/页哈希与原始候选保留在JSONL中。

## A-RAW-07520

关系：泵 —maintained_by→ 保持泵尽可能清洁。

来源：[MP021，物理页 3](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Viking_Pump_TSM_1600.pdf>)；Claim `TC-b591fbb5907cdd97daf0ff94`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"scope": "Viking pumps, cleaning maintenance"}`

原文依据：

- MP021 物理页 3：Keep pump as clean as possible.

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-03430

关系：泵无流量或流量过低 —mitigated_by→ 从轴端观察将旋转方向改为顺时针（按箭头方向）。

来源：[MP004，物理页 11](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/DESMI_SA_Self_Priming_Pump_T1345.pdf>)；Claim `TC-3d7696dd74d9ffe10c88cc3a`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"cause": "wrong direction of rotation", "equipment": "DESMI SA", "viewpoint": "shaft end"}`

原文依据：

- MP004 物理页 11：The pump has no or
too low capacity
- MP004 物理页 11：Wrong direction of
rotation
- MP004 物理页 11：Change direction of rotation
to clockwise when viewed
from shaft end (the direction
of the arrow)

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-03881

关系：泵无流量或流量过低 —mitigated_by→ 从轴端观察将旋转方向改为顺时针（按箭头方向）。

来源：[MP005，物理页 60](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf>)；Claim `TC-3d7696dd74d9ffe10c88cc3a`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"cause": "wrong direction of rotation", "equipment": "DESMI NSL", "viewpoint": "shaft end"}`

原文依据：

- MP005 物理页 60：The pump has no or                                                    
            too low capacity
- MP005 物理页 60：Wrong direction of rotation
- MP005 物理页 60：Change direction of rotation to
clockwise when viewed from shaft
end (the direction of the arrow)

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-03441

关系：泵无流量或流量过低 —mitigated_by→ 更换更小V带轮或调整电机转速。

来源：[MP004，物理页 11](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/DESMI_SA_Self_Priming_Pump_T1345.pdf>)；Claim `TC-5e1eb29939ee638d4de35a3c`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"cause": "RPM too low", "equipment": "DESMI SA", "not_unconditional_speed_change_advice": true}`

原文依据：

- MP004 物理页 11：RPM too low
- MP004 物理页 11：Fit smaller V-belt pulley on     
                                                 pump. Change RPM of              
                                                 electric motor

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-03440

关系：转速过低 —causes→ 泵无流量或流量过低。

来源：[MP004，物理页 11](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/DESMI_SA_Self_Priming_Pump_T1345.pdf>)；Claim `TC-f6c2f9de14c732fa69fca841`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "DESMI SA", "modality": "listed_possible_cause"}`

原文依据：

- MP004 物理页 11：The pump has no or
too low capacity
- MP004 物理页 11：RPM too low

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-06102

关系：气隙不均匀 —causes→ 运行噪声大。

来源：[MP019，物理页 20](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf>)；Claim `TC-e0b1eb370a83db10e82edcec`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "ABB low voltage motor, not every pump component", "modality": "listed_possible_cause"}`

原文依据：

- MP019 物理页 20：Noisy operation
- MP019 物理页 20：Air gap not uniform

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-06104

关系：转子不平衡 —causes→ 运行噪声大。

来源：[MP019，物理页 20](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf>)；Claim `TC-bfd68a9ffa93ee3606e7e667`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "ABB low voltage motor", "modality": "listed_possible_cause"}`

原文依据：

- MP019 物理页 20：Noisy operation
- MP019 物理页 20：Rotor unbalance

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-07341

关系：过多管件 —causes→ 滞留空气。

来源：[MP020，物理页 7](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Cornell_General_Purpose_Pumps_Installation_Care.pdf>)；Claim `TC-5c78e13afe3c2466734401b9`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"antecedent": "use of many fittings", "equipment": "Cornell pump suction piping", "modality": "may_cause"}`

原文依据：

- MP020 物理页 7：Do not use many fittings. This creates high
- MP020 物理页 7：friction losses and may cause cavitation,
- MP020 物理页 7：trapped air and reduced performance.

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-07947

关系：O形圈(12) —maintained_by→ 将O形圈(12)装到静密封环(11)上并润滑。

来源：[MP022，物理页 35](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf>)；Claim `TC-30f9c96359be68e0fc7e306b`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "LKH Prime, O-ring 12, seal assembly Step 4", "part_number_preserved": 12}`

原文依据：

- MP022 物理页 35：Fit O-ring (12) on stationary seal ring (11) and lubricate

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-07802

关系：空气滞留 —prevented_by→ 吸入管路设计为向泵倾斜下坡。

来源：[MP022，物理页 16](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf>)；Claim `TC-9a38d88e4b75967a6eadbe7a`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "LKH Prime self-priming installation, not a universal suction-pipe rule"}`

原文依据：

- MP022 物理页 16：Design suction line with slope down toward the pump to avoid air entrapments

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-04845

关系：O形圈在轴套上滚动翻转 —prevented_by→ 在o形圈上涂抹甘油或硅喷雾。

来源：[MP015，物理页 42](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf>)；Claim `TC-39a06a8eb9677eeac835bee9`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"alternatives": ["glycerine", "silicon spray"], "phase": "FreFlow mechanical-seal assembly", "pronoun_it": "O-ring"}`

原文依据：

- MP015 物理页 42：Slide the rotating part of the mechanical seal onto the pump shaft.
- MP015 物理页 42：Put some glycerine
                         or silicon spray on the O-ring to prevent it from rolling on the shaft sleeve.

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-07693

关系：供液不足或汽蚀 —mitigated_by→ 增大吸入管径或缩短长度。

来源：[MP021，物理页 17](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Viking_Pump_TSM_1600.pdf>)；Claim `TC-b1d629678ca8c1aa66f7420a`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"action_alternatives": ["increase suction pipe size", "reduce suction pipe length"], "cause_alternatives": ["starving", "cavitating"], "equipment": "Viking pump", "fault": "pump not up to capacity"}`

原文依据：

- MP021 物理页 17：Starving or cavitating. Increase suction pipe size or reduce length.

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-07936

关系：放气螺钉 —maintained_by→ 安装放气螺钉并用扳手拧紧。

来源：[MP022，物理页 34](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf>)；Claim `TC-466459a875828e87f6cb18c2`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "LKH Prime, Step 8, air screw 58", "parameter_binding_basis": "original PDF table visually checked; merged cells not flattened reading order", "parameter_map_Nm": {"LKH Prime 10": 20, "LKH Prime 20": 20, "LKH Prime 40": 40}}`

原文依据：

- MP022 物理页 34：Fit air screw (58) and tighten with a spanner (Torque: see table        
         below)
- MP022 物理页 34：LKH Prime 10:
- MP022 物理页 34：LKH Prime 20:
- MP022 物理页 34：LKH Prime 40:
- MP022 物理页 34：Torque = 20 Nm (15 lbf-ft)
- MP022 物理页 34：Torque = 40 Nm (30 lbf-ft)

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-07663

关系：真空表高读数 —indicates→ 管路尺寸过小。

来源：[MP021，物理页 16](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Viking_Pump_TSM_1600.pdf>)；Claim `TC-939dd46d30d45e9a3b4c757b`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"list_branch": "high reading, item d", "location": "suction port", "modality": "possible_indicator", "sensor": "vacuum gauge"}`

原文依据：

- MP021 物理页 16：VACUUM  GAUGE - SUCTION PORT
- MP021 物理页 16：High reading would indicate:
- MP021 物理页 16：Line is too small.

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-06540

关系：外部损伤 —inspected_by→ 立即检查电机是否存在外部损伤。

来源：[MP019，物理页 60](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf>)；Claim `TC-19879bf3cd62a0ff4e0f6143`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "ABB low voltage motor", "phase": "upon receipt", "same_family_translations_not_independent_facts": true}`

原文依据：

- MP019 物理页 60：A su recepción, verifique inmediatamente si el motor presenta daños externos

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-RAW-03392

关系：泵轴 —inspected_by→ 检查轴转动是否灵活。

来源：[MP004，物理页 8](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/DESMI_SA_Self_Priming_Pump_T1345.pdf>)；Claim `EXC-a3d68208696d47c416efaf3c`。

计数：现有Claim新增来源，不计新Claim。

适用条件：`{"equipment": "DESMI SA", "phase": "after pump assembly"}`

原文依据：

- MP004 物理页 8：When the pump has been assembled, check that the shaft rotates freely.

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## A-FLUSH-70C

关系：外置单端面或双端面机械密封 —operates_under→ 冲洗介质最高温度70°C。

来源：[MP022，物理页 42](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf>)；Claim `TC-d2df960f8fb67b410fcd760f`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"equipment": "LKH Prime shaft-seal specification", "limit_type": "maximum flush-medium temperature", "value_C": 70}`

原文依据：

- MP022 物理页 42：Seal types
- MP022 物理页 42：External single or double mechanical seal
- MP022 物理页 42：Max. temperature flush medium 70oC

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## ET-2d101065dd39d1f0a16243ee

关系：泵越曲线运行或系统不当 —causes→ 驱动机过载。

来源：[MP020，物理页 26](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/Cornell_General_Purpose_Pumps_Installation_Care.pdf>)；Claim `TC-6768181f6d42a4c4dbafba35`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"cause_is_disjunctive": true, "equipment": "Cornell pump driver", "modality": "listed_possible_cause"}`

原文依据：

- MP020 物理页 26：Pump runs out on curve/ system incorrect
- MP020 物理页 26：Driver overloaded

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## EJ-33160299828692fc0d50d36b

关系：有效汽蚀余量过低 —causes→ 泵流量不稳定。

来源：[MP015，物理页 31](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf>)；Claim `TC-d0d2cdbc63b98f52aa03fb3e`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"cause_index": 4, "equipment": "SPX FreFlow", "explicit_reference": "Table 4 -> Table 5", "modality": "possible_cause"}`

原文依据：

- MP015 物理页 31：Irregular delivery
- MP015 物理页 31：4, 7, 9, 14
- MP015 物理页 31：Possible causes, see Table 5.
- MP015 物理页 32：NPSH available too low

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## EJ-471057fef1c44a86727c3ba2

关系：吸入管路泄漏 —causes→ 泵流量不稳定。

来源：[MP015，物理页 31](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf>)；Claim `EXC-8d969856ab7a0feda939bad2`。

计数：现有Claim新增来源，不计新Claim。

适用条件：`{"cause_index": 7, "equipment": "SPX FreFlow", "explicit_reference": "Table 4 -> Table 5", "modality": "possible_cause"}`

原文依据：

- MP015 物理页 31：Irregular delivery
- MP015 物理页 31：4, 7, 9, 14
- MP015 物理页 31：Possible causes, see Table 5.
- MP015 物理页 32：Air leak in the suction pipe

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## EJ-6d9718dffd572f0a32c6ed57

关系：液体析出气体或空气 —causes→ 泵流量不稳定。

来源：[MP015，物理页 31](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf>)；Claim `TC-b9ccb9d62119e8baa96dadda`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"cause_index": 9, "equipment": "SPX FreFlow", "explicit_reference": "Table 4 -> Table 5", "modality": "possible_cause"}`

原文依据：

- MP015 物理页 31：Irregular delivery
- MP015 物理页 31：4, 7, 9, 14
- MP015 物理页 31：Possible causes, see Table 5.
- MP015 物理页 32：Gas or air coming from the liquid

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。

## EJ-0ec2cda58be382eb81b9d631

关系：管路堵塞 —causes→ 泵流量不稳定。

来源：[MP015，物理页 31](<E:/704/2026年春季研究生中期考核工作材料包/Fault_llm_v2/data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf>)；Claim `TC-6cc2d2c47f057d3bfcf8ff8c`。

计数：新增试验Claim的来源Assertion。

适用条件：`{"cause_index": 14, "equipment": "SPX FreFlow", "explicit_reference": "Table 4 -> Table 5", "modality": "possible_cause"}`

原文依据：

- MP015 物理页 31：Irregular delivery
- MP015 物理页 31：4, 7, 9, 14
- MP015 物理页 31：Possible causes, see Table 5.
- MP015 物理页 32：Obstruction in the piping

程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。
