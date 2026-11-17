# RP1构图数据可行性：可回查案例簿

日期：2026-11-13。以下19例为本次助手定向阅读的分析性案例，不是新专家Gold或独立评价样本；不把案例比例外推全图。引文和图状态从文件读取。候选源键未映射不等于最终知识不存在。

完整逐条载荷和精确页内上下文见`casebook_records.jsonl`；相似性集合见`clusters/`及`entities/`。

## A01 跨家族关系级重叠正例：润滑剂过量与轴承过热

ABB电机和Flowserve泵手册均有过量润滑与轴承过热的关系线索；中文“过多/过量”造成拆分。可作为关系族对齐候选，但设备范围不同，应保留各自证据。西语候选虽定位合法，原决策仍是拒绝，不能自动改成融合正例。它是1个可回查机制案例，不是3份已确认独立事实。

- `MPT-0a7c947864ba00fc6bfc`，MP019物理p20，族`ABB`；原状态`silver_candidate`；**已发布**。
  候选：润滑剂过多 [Cause] → causes → 轴承过热 [Symptom]。
  证据：Hot bearings --- CELL --- Excess lubricant
  审计链：[{"triple_id": "MPT-0a7c947864ba00fc6bfc", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-0a7c947864ba00fc6bfc", "claim_id": "EXC-bc6296cea7fb4a2d0017ad06", "assertion_id": "EXA-2748c061a7ce5286c7335fc1", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-391c11af546f98d98eb0`：轴承过热 [Symptom] → causes → 润滑剂过多 [Cause]；完整原载荷保留在案例JSONL。
- `MPT-9f5573d9faacb30a6d3e`，MP018物理p15，族`PATTERSON_PUMP`；原状态`silver_candidate`；**已发布**。
  候选：润滑剂过量 [Cause] → causes → 轴承过热 [Symptom]。
  证据：Do not operate pump with excessive amount of lubricant. Such action will cause bearings to overheat.
  审计链：[{"triple_id": "MPT-9f5573d9faacb30a6d3e", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-9f5573d9faacb30a6d3e", "claim_id": "EXC-cdff44d10a49823150e3612c", "assertion_id": "EXA-9ed558fcf3207edae0c18cc4", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-4a49307fa2a931d108bd`：润滑剂过量 [Cause] → causes → 轴承过热 [Symptom]；完整原载荷保留在案例JSONL。
- `MPT-da874a4cb007069f3880`，MP019物理p74，族`ABB`；原状态`rejected`；**未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在**。
  候选：润滑剂过量 [Cause] → causes → 轴承过热 [Symptom]。
  证据：Rodamientos sobrecalentados --- CELL --- Exceso de lubricante
  审计链：[{"triple_id": "MPT-da874a4cb007069f3880", "decision": "rejected", "rejection_reasons": ["evidence_invalid"], "review_reasons": ["relation_entailment_undetermined", "evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[]
  原始抽取`MPT-385352fceb848d429642`：润滑剂过量 [Cause] → causes → 轴承过热 [Symptom]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/Patterson_Non_Clog_Pump_OM.pdf`，物理p15；页哈希`58eadd527dda4fbe0d4fe7537a5f8456cd90c52a263e5155b1e719a77bfe0a77`。

源页：`data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf`，物理p20；页哈希`4bf37fb94e77813b712ff4c11e5a9b6bbb8070d88896c6770f5ca0d322d4ecf3`。

源页：`data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf`，物理p74；页哈希`f78cb6b34dce86ad3c3ff89107fd91f63606910695411de66e4ff92325077544`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## A02 跨文档但同族：过高吸上高度与低流量

两份DESMI手册形成同一规范主张族，已在expanded中聚合。SA与NSL适用范围不同，不能删除断言；这不是两个独立来源家族。

- `MPT-1f927e2bdf5ab942b510`，MP004物理p11，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：吸上高度过高 [Cause] → causes → 泵无流量或流量过低 [FaultMode]。
  证据：The pump has no or too low capacity --- CELL --- 1. Wrong direction of rotation 2. Piping system choked 3. The pump is choked 4. Suction line leaks, pump takes air 5. Suction lift too high 6. Pump and piping system wrongly dimensioned 7. RPM too low
  审计链：[{"triple_id": "MPT-1f927e2bdf5ab942b510", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-1f927e2bdf5ab942b510", "claim_id": "EXC-ee0bc9b82a255f67206978eb", "assertion_id": "EXA-ebecb0889690628dfbb06317", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-1a45762a1b6de53eed65`：泵无流量或流量过低 [FaultMode] → causes → 吸上高度过高 [Cause]；完整原载荷保留在案例JSONL。
- `EXP-e3fd7141139855017fe8fae6`，MP005物理p60，族`DESMI`；原状态`automatically_evidence_qualified_expansion`；**已发布**。
  候选：吸上高度过高 [Cause] → causes → 泵无流量或流量过低 [FaultMode]。
  证据：6. Suction lift is too high
  审计链：[{"triple_id": "MPT-bd63adfea668dbfc963c", "decision": "rejected", "rejection_reasons": ["evidence_invalid", "relation_not_entailed"], "review_reasons": ["evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[{"triple_id": "EXP-e3fd7141139855017fe8fae6", "claim_id": "EXC-ee0bc9b82a255f67206978eb", "assertion_id": "EXA-9b96aea735aa1b92f2695a39", "conditions_source": [{"role": "fault", "cell_id": "MP005:p0060:t00:r001:c00", "text": "The pump has no or\ntoo low capacity"}, {"role": "cause", "cell_id": "MP005:p0060:t00:r006:c01", "text": "6. Suction lift is too high"}, {"role": "remedy", "cell_id": "MP005:p0060:t00:r006:c02", "text": "Check data sheet Q/H curve and\nNPSH or contact DESMI"}], "modality": "possible", "match_basis": "exact_source_key"}]
  原始抽取`MPT-69b145f5be29259f7e69`：泵无流量或流量过低 [FaultMode] → causes → 吸上高度过高 [Cause]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_SA_Self_Priming_Pump_T1345.pdf`，物理p11；页哈希`a7c857d531dd662344684cbd4e613f09c96c45eb8b3f92bc4146696bd606d33a`。

源页：`data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf`，物理p60；页哈希`c29925aa48cc183b307a04fb591b6976ea5b650c1959d45fdfc11d2f73e2096a`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## A03 同一文档的多语言重复：泵头O形圈/垫片更换

同一MP016手册的英语、荷兰语、意大利语和瑞典语页已聚合为主张族。源语言元数据可能均为en，应以实际引文识别语言；译本不能视为独立家族。现有去重与来源族规则已经覆盖这类重复。

- `MPT-f870b7d889096551f3e2`，MP016物理p5，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：泵头o型圈和/或垫片 [Component] → maintained_by → 更换泵头o型圈和/或垫片 [MaintenanceAction]。
  证据：Change O-rings and/or gaskets on pump head.
  审计链：[{"triple_id": "MPT-1c0210442890f469be74", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-f870b7d889096551f3e2", "claim_id": "EXC-299dbba39fb4fa173202aea2", "assertion_id": "EXA-42bb24c06e4447c816700dd9", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-39777ddeaf5d6b6cc673`：泵头O型圈和/或垫片 [Component] → maintained_by → 更换泵头O型圈和/或垫片 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-0fef92ad5035a651a7dc`，MP016物理p35，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：泵头o型圈和/或垫片 [Component] → maintained_by → 更换泵头o型圈和/或垫片 [MaintenanceAction]。
  证据：Vervang O-ringen en/of pakkingen op de pompkop.
  审计链：[{"triple_id": "MPT-5e6f519bd25fc17a58a1", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-0fef92ad5035a651a7dc", "claim_id": "EXC-299dbba39fb4fa173202aea2", "assertion_id": "EXA-24c3d888ee276945cdfbdb88", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-99f9a4e85be20221b865`：泵头O型圈和/或垫片 [Component] → maintained_by → 更换泵头O型圈和/或垫片 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-3d4b36a65dcd3b791e82`，MP016物理p29，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：泵头o型圈和/或垫片 [Component] → maintained_by → 更换泵头o型圈和/或垫片 [MaintenanceAction]。
  证据：Sostituire gli o-ring e/o le guarnizioni sulla testa della pompa.
  审计链：[{"triple_id": "MPT-a9a3bf9370a7db0122df", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-3d4b36a65dcd3b791e82", "claim_id": "EXC-299dbba39fb4fa173202aea2", "assertion_id": "EXA-1428d94902b2d1f73c03bca9", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-3712ca79f417c6328ded`：泵头O型圈和/或垫片 [Component] → maintained_by → 更换泵头O型圈和/或垫片 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-22c8286a1c34dc14503f`，MP016物理p41，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：泵头o型圈和/或垫片 [Component] → maintained_by → 更换泵头o型圈和/或垫片 [MaintenanceAction]。
  证据：Byt pumphuvudets O-ringar och/eller packningar.
  审计链：[{"triple_id": "MPT-c575a5c7453e514a4088", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-22c8286a1c34dc14503f", "claim_id": "EXC-299dbba39fb4fa173202aea2", "assertion_id": "EXA-723c2b420a066fe441ac5510", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-d40da9ea0258fdc99cd7`：泵头O型圈和/或垫片 [Component] → maintained_by → 更换泵头O型圈和/或垫片 [MaintenanceAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p5；页哈希`bf496aa04ac9b71e4a6d66fff4bcb28aee3f281d5cd60d77e740764b9ebb3e9e`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p29；页哈希`dafd114ab9cd319013c1b5bcca256e71dddc18562727fd2c4093288789c2172e`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p35；页哈希`d3d4f950f5cf3718a7c7c2a549526050149e665f4b8f5ff4d7da4d7ce2ee1920`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p41；页哈希`82a5b881fd74a5b4bb60b1e2b2bc1aefadf6b48eb8e3b1d8e23c2a5d03c3c4c4`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## A04 相似但不能合并：轴承过早失效与轴承过热

同一“不对中”原因可对应不同后果。名称和关系相似并不意味着两个后果等价，也不是冲突。需检查新增记录的完整table source_witnesses，不能仅用短引文判断全部后果。

- `EXP-7553c787a9008478f53d438b`，MP020物理p26，族`INDICOR__CORNELL_PUMP`；原状态`automatically_evidence_qualified_expansion`；**已发布**。
  候选：不对中 [Cause] → causes → 轴承过早失效 [Symptom]。
  证据：Misalignment --- CELL --- Align all rotating parts
  审计链：[{"triple_id": "MPT-c8a9920575101076cd86", "decision": "rejected", "rejection_reasons": ["evidence_invalid", "relation_not_entailed"], "review_reasons": ["evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[{"triple_id": "EXP-7553c787a9008478f53d438b", "claim_id": "EXC-89c1405ae6f436a601c662b5", "assertion_id": "EXA-2fd40cf2ee54cc37dc28aa8b", "conditions_source": [{"role": "fault", "cell_id": "MP020:p0026:t00:r034:c00", "text": "Premature bearing\nfailure"}, {"role": "cause", "cell_id": "MP020:p0026:t00:r036:c01", "text": "Misalignment"}, {"role": "remedy", "cell_id": "MP020:p0026:t00:r036:c02", "text": "Align all rotating parts"}], "modality": "possible", "match_basis": "exact_source_key"}]
  原始抽取`MPT-b649b9fffceb9ef8c35a`：轴承过早失效 [Symptom] → causes → 不对中 [Cause]；完整原载荷保留在案例JSONL。
- `MPT-4db3cce871d96a3bedaa`，MP019物理p20，族`ABB`；原状态`silver_candidate`；**已发布**。
  候选：不对中 [Cause] → causes → 轴承过热 [Symptom]。
  证据：Hot bearings --- CELL --- Misalignment
  审计链：[{"triple_id": "MPT-4db3cce871d96a3bedaa", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-4db3cce871d96a3bedaa", "claim_id": "EXC-f0e5133c335853be8e089076", "assertion_id": "EXA-40221762acd5fa3b2a577e64", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-af4258a90f76343f1deb`：轴承过热 [Symptom] → causes → 不对中 [Cause]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf`，物理p20；页哈希`4bf37fb94e77813b712ff4c11e5a9b6bbb8070d88896c6770f5ca0d322d4ecf3`。

源页：`data/source_docs/marine_pump/raw/Cornell_General_Purpose_Pumps_Installation_Care.pdf`，物理p26；页哈希`a7ff2e54e6284c39e6aedc976644b6c7ba03e48d5263ea1c7fd5095a60f7549b`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## A05 安装与拆卸并存：阶段不同，不是真冲突

Fit the guard与Dismantle guard来自不同维护阶段及文档。应保留动作差异和阶段，不能因相同部件把动作合并，也不能算相同工况下相互矛盾。

- `MPT-b0e376ff1333acff24dd`，MP015物理p23，族`SPX_FLOW__JOHNSON_PUMP`；原状态`silver_candidate`；**已发布**。
  候选：防护罩 [Component] → maintained_by → 安装防护罩 [MaintenanceAction]。
  证据：4 Fit the guard.
  审计链：[{"triple_id": "MPT-04e14c6220e212e683ed", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-b0e376ff1333acff24dd", "claim_id": "EXC-fc63afbcfd753c0a07017622", "assertion_id": "EXA-3e74c2022bbc5a606392ff4c", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-205408c9de76235dba43`：防护罩 [Component] → maintained_by → 安装防护罩 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-e5f5c6c6558df05e6197`，MP005物理p90，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：防护罩 [Component] → maintained_by → 拆卸防护罩 [MaintenanceAction]。
  证据：1. Dismantle guard(69).
  审计链：[{"triple_id": "MPT-b4ccf403bf09eda91e03", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-e5f5c6c6558df05e6197", "claim_id": "EXC-d27f18b1a083430d468cb324", "assertion_id": "EXA-8b0143528c5a6b7544c105d2", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-5a5a96d043ad8a0911fc`：防护罩 [Component] → maintained_by → 拆卸防护罩 [MaintenanceAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf`，物理p90；页哈希`4da013bfe43460be919efb5775c8de9dd773afff741b6a821e9f421aafc17691`。

源页：`data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf`，物理p23；页哈希`e21a5f4c4f45afc9811f88690894afbed43c9a9b6d0e93ccde00eea8a5e02435`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## A06 一个Claim承载七页证据，不代表七条独立事实

橡胶密封安装前润滑的7条断言被同一Claim聚合，均来自MP022。Claim作为主张族的聚合本身并非错误；若消费程序只取裸边、丢弃装配配置和before时机，就会损失上下文。

- `MPT-eb18872408609cfe2aaf`，MP022物理p35，族`ALFA_LAVAL`；原状态`silver_candidate`；**已发布**。
  候选：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]。
  证据：Lubricate the rubber seals before fitting them.
  审计链：[{"triple_id": "MPT-3c1ccda5e82629a60ff8", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-eb18872408609cfe2aaf", "claim_id": "EXC-874176dee893d47cf1cfcd2e", "assertion_id": "EXA-4da360a7ba45468380093bf5", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-d6f6863d66fc23727eb4`：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-12134125fd63e368c610`，MP022物理p37，族`ALFA_LAVAL`；原状态`silver_candidate`；**已发布**。
  候选：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]。
  证据：Lubricate the rubber seals before fitting them.
  审计链：[{"triple_id": "MPT-59d151df6ab7e612f6c6", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-12134125fd63e368c610", "claim_id": "EXC-874176dee893d47cf1cfcd2e", "assertion_id": "EXA-71bf6c9a362b2976f311ee2a", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-f2621a568f731a70c501`：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-7dfcfdb861d258c7d402`，MP022物理p41，族`ALFA_LAVAL`；原状态`silver_candidate`；**已发布**。
  候选：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]。
  证据：Lubricate the rubber seals before fitting them.
  审计链：[{"triple_id": "MPT-5e7f74bbc29779911889", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-7dfcfdb861d258c7d402", "claim_id": "EXC-874176dee893d47cf1cfcd2e", "assertion_id": "EXA-be64fcbfcacbf72f0189df40", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-d90b062644f0a19ffafb`：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-da46130fce5be6a97597`，MP022物理p39，族`ALFA_LAVAL`；原状态`silver_candidate`；**已发布**。
  候选：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]。
  证据：Lubricate the rubber seals before fitting them.
  审计链：[{"triple_id": "MPT-693fe709d40fcbe536b6", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-da46130fce5be6a97597", "claim_id": "EXC-874176dee893d47cf1cfcd2e", "assertion_id": "EXA-6a72bace21a9ec10a9d2708b", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-1fd8c85e707b29354a0f`：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-cb265ceae3a581bba491`，MP022物理p36，族`ALFA_LAVAL`；原状态`silver_candidate`；**已发布**。
  候选：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]。
  证据：Lubricate the rubber seals before fitting them.
  审计链：[{"triple_id": "MPT-da2970ea427c6f6b5943", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-cb265ceae3a581bba491", "claim_id": "EXC-874176dee893d47cf1cfcd2e", "assertion_id": "EXA-05df5b67dc78d9f7a7086c70", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-4a738bf11d6e41a8cceb`：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-b360fcd981012dcf620a`，MP022物理p38，族`ALFA_LAVAL`；原状态`silver_candidate`；**已发布**。
  候选：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]。
  证据：Lubricate the rubber seals before fitting them.
  审计链：[{"triple_id": "MPT-e6b5541eefa7cd521f6c", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-b360fcd981012dcf620a", "claim_id": "EXC-874176dee893d47cf1cfcd2e", "assertion_id": "EXA-3342e0d032a7cee527233225", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-f491f6c66f4df1323faf`：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-5a461a48e0656995afc2`，MP022物理p40，族`ALFA_LAVAL`；原状态`silver_candidate`；**已发布**。
  候选：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]。
  证据：Lubricate the rubber seals before fitting them.
  审计链：[{"triple_id": "MPT-fa392cd2ea348496d368", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-5a461a48e0656995afc2", "claim_id": "EXC-874176dee893d47cf1cfcd2e", "assertion_id": "EXA-85b0f1deb8b33dd39a330613", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-8d5059d7888fdafd0e79`：橡胶密封件 [Component] → maintained_by → 安装前润滑橡胶密封件 [MaintenanceAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf`，物理p35；页哈希`0f11a5e1a750b97c1678032adfa8f44a2391178fb497b1a3352765df09c7b26c`。

源页：`data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf`，物理p36；页哈希`ea95d7d47ed4094a6fae168b4a4562d0bbbce1dfbf87c1e19e7a40483421db30`。

源页：`data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf`，物理p37；页哈希`1cddf7b5f19aaa24094f0193b6afcfa3fd288a732475e25d8c7826f671118117`。

源页：`data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf`，物理p38；页哈希`ca8245980bd179102830c14ae68e241e1e2b42edf009432fec307786207c7b37`。

源页：`data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf`，物理p39；页哈希`b2ebb3acbd61e7670bb6c363d07f459e4a82565fce5e954dfeab22162e1058a4`。

源页：`data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf`，物理p40；页哈希`0f368522a0249419e4ba588f5842e7475229ef33db6a60ba5ff2f7db8171ac2d`。

源页：`data/source_docs/marine_pump/raw/Alfa_Laval_LKH_Prime_Instruction_Manual.pdf`，物理p41；页哈希`5f2cb980c5aeda1235124cedf565150e64e8ec4d68eb59e8d4f9ace25cbf1a7d`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## B01 可在候选层关联的步骤：停机—消因—恢复

两项原子动作和before returning字面信息已存在，是构图阶段局部步骤关联的正向可行性线索。当前没有独立、完整的重启前置边，不能把可能恢复写成已成功恢复，也不能由这1例证明通用事件图融合必要。

既有靶点：T03；范围`core`；旧AI状态`literal_partial`。
原文证据（多单元分隔，非伪造连续偏移）：Stop the pump (set) immediately. | 原生片段分隔 | Eliminate the causes before returning the pump set to service.

- `MPT-abc10efaea6b1d67d540`，MP005物理p53，族`DESMI`；原状态`原始缓存未判定`；**未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在**。
  候选：泵损坏 [FaultMode] → mitigated_by → 立即停泵 [MaintenanceAction]。
  证据：Abnormal noises, vibrations, temperatures or leakage could cause damage to the pump. Stop the pump (set) immediately.
  审计链：[{"triple_id": "MPT-5671a8cdcf1c22d8c487", "decision": "candidate_needs_review", "rejection_reasons": [], "review_reasons": ["relation_entailment_undetermined", "entailment_not_automatic_silver"]}]
  图谱：[]
- `MPT-19355a857064a9de906b`，MP005物理p53，族`DESMI`；原状态`原始缓存未判定`；**未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在**。
  候选：泵损坏 [FaultMode] → mitigated_by → 恢复运行前消除故障原因 [MaintenanceAction]。
  证据：Eliminate the causes before returning the pump set to service.
  审计链：[{"triple_id": "MPT-38016b5e085f916f88d3", "decision": "rejected", "rejection_reasons": ["evidence_invalid", "relation_not_entailed"], "review_reasons": ["evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[]

源页：`data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf`，物理p53；页哈希`48699dd2599181e21fbeb35aaf791777f90e88456a566b9b40cca77369b5b2ef`。

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## B02 型号条件未绑定：损坏衬套更换

既有B24 AI评价为源文S、条件E。源页存在组合型号标题，候选短引文不足以独立给出范围。若构图可读取原生章节元数据，存在局部补绑定可能；仅用候选三元组不能凭空知道型号。此处不是已执行修复。

- `MPT-b60af75fc3a32754dfb0`，MP005物理p114，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：联轴器衬套(74) [Component] → maintained_by → 如有损坏则更换 [MaintenanceAction]。
  证据：Check Allen screws (76) and coupling bushes (74) for damage and clean these with a cloth. Replace them in case of damage.
  审计链：[{"triple_id": "MPT-6f52b5a1efcae1a99a31", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-b60af75fc3a32754dfb0", "claim_id": "EXC-8d6c610f0a8d0f79aa50bbdb", "assertion_id": "EXA-a3f92fe444b9372185f05be5", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-1bb140e2edb10d09fa1d`：联轴器衬套(74) [Component] → maintained_by → 如有损坏则更换 [MaintenanceAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf`，物理p114；页哈希`c08c4cfc98f428784f2b2eebd9f773f58284e94610ed2d7a9fb4ea1387b8342c`。
页内位置2482—3002：2 6 mm Ø330/415/418/465/525 1. Check Allen screws (76) and coupling bushes 

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## B03 否定语义被正向裸边遮蔽

既有B06 AI评价已指出Do not operate without liquid被表示为正向operates_under无液充注。禁止文字仍保留在证据中，属于关系表示/消费风险，而非原文彻底丢失。不能把一个新极性字段缺失与全图否定错误数量画等号。

- `MPT-0927c8970e1124c5c738`，MP005物理p67，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：泵组 [Equipment] → operates_under → 无液体充注 [OperatingCondition]。
  证据：Do not operate the pump set without liquid fill.
  审计链：[{"triple_id": "MPT-0927c8970e1124c5c738", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-0927c8970e1124c5c738", "claim_id": "EXC-a5ad2169c39bf636b88d7308", "assertion_id": "EXA-635a40aea27f56c635c90125", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-aad144f9c894e547641f`：泵组 [Equipment] → operates_under → 无液体充注 [OperatingCondition]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf`，物理p67；页哈希`bd85a44a86149ec0bbab07f7f07451e5971422bf8ad1abe420c270999803d815`。

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## B04 纯候选构图无法补齐的数值时序

原文有90°C 12–16小时后105°C 6–8小时；已有候选涉及绕组受潮和烘干，但不含完整有序参数。若仅允许候选及其现有引文，无法恢复数值；重读完整页面发现参数是额外源文信息提取，应单列，不能算融合算法免费收益。

既有靶点：T13；范围`core`；旧AI状态`literal_partial`。
原文证据（多单元分隔，非伪造连续偏移）：Om referensresistansen inte kan uppnås är lindningen | 原生片段分隔 | för fuktig och måste torkas i ugn. | 原生片段分隔 | 90°C under 12-16 timmar, följt av 105 °C under 6-8 | 原生片段分隔 | timmar.

- `MPT-4e9c5cdee2445bafd79a`，MP019物理p97，族`ABB`；原状态`原始缓存未判定`；**未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在**。
  候选：绕组受潮 [FaultMode] → diagnosed_by → 无法达到参考电阻值 [Symptom]。
  证据：Om referensresistansen inte kan uppnås är lindningen fuktig och måste torkas i ugn.
  审计链：[{"triple_id": "MPT-ed3fada9f943fe761555", "decision": "rejected", "rejection_reasons": ["relation_type_invalid", "evidence_invalid", "relation_not_entailed"], "review_reasons": ["evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[]
- `MPT-5557f786a3dc1519779b`，MP019物理p97，族`ABB`；原状态`原始缓存未判定`；**未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在**。
  候选：绕组受潮 [FaultMode] → mitigated_by → 烘箱干燥 [MaintenanceAction]。
  证据：Om referensresistansen inte kan uppnås är lindningen fuktig och måste torkas i ugn.
  审计链：[{"triple_id": "MPT-b241030331c24f5d31e1", "decision": "rejected", "rejection_reasons": ["evidence_invalid", "relation_not_entailed"], "review_reasons": ["evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[]

源页：`data/source_docs/marine_pump/raw/ABB_Low_Voltage_Motors_Manual.pdf`，物理p97；页哈希`3c6ce578b0cabc3066e44a39d3ce59ca64c4d962b7c81b32c69d0d7aea8b939d`。
页内位置4542—5062： uppåt för fuktig och måste torkas i ugn. Ugnstemperaturen skall och vätska kan förväntas rinna ned utefter vara 90°C under 12-16 timmar, följt av 105 °C under 6-8 axeln måste användaren vidta åtgärder för att timmar. förhindra detta. Om det finns pluggar i dräneringshålen måste dessa tas ur och stängningsventiler, om sådana finns, 

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## B05 反例：清液限制已经字面保留

clear liquids applications only已在候选/引文及已发布记录保留。conditions_source为空不等于条件丢失；可查询字段不齐与语义缺失需分开。

既有靶点：T14；范围`core`；旧AI状态`literal_complete`。
原文证据（多单元分隔，非伪造连续偏移）：Flow straigheners are for clear liquids applications only.

- `MPT-1b43eb82b971be6816fc`，MP020物理p6，族`INDICOR__CORNELL_PUMP`；原状态`原始缓存未判定`；**显式legacy ID或精确源键映射到已发布**。
  候选：整流器 [Component] → operates_under → 仅适用于清洁液体工况 [OperatingCondition]。
  证据：*Flow straigheners are for clear liquids applications only.
  审计链：[{"triple_id": "MPT-45bfda56249f45f77d08", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-44efe0d48a0eeff3fb91", "claim_id": "EXC-c6fe31771b50bb7f50b2c2aa", "assertion_id": "EXA-b13dd50f34bb95e90ff24837", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "explicit_legacy_id"}]

源页：`data/source_docs/marine_pump/raw/Cornell_General_Purpose_Pumps_Installation_Care.pdf`，物理p6；页哈希`81eabacab09a20941dcf844228ea0794116fb39e86f7a4ee60ab1ee31c7e9675`。

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## B06 反例：OR已经在完整动作中，主要瓶颈是定位

增加流量或改用小泵的OR仍在动作尾端。旧原生链拒绝引用不等于模型未生成OR，也不能把它当需要专门替代方案算法的证明。最终页级记录与相关原始候选分列，避免用ID变动断言知识缺失。

既有靶点：T07；范围`core`；旧AI状态`literal_complete`。
原文证据（多单元分隔，非伪造连续偏移）：Water flow is very low, the
bubble pump is blocked | 原生片段分隔 | Make sure that flow is
increased or a smaller
pump is used

- `MPT-0a76fe80d31fd1d7729d`，MP007物理p18，族`DESMI`；原状态`原始缓存未判定`；**未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在**。
  候选：水流量极低导致气泡泵堵塞 [Cause] → mitigated_by → 确保增加流量或选用更小泵 [MaintenanceAction]。
  证据：Water flow is very low, the bubble pump is blocked Make sure that flow is increased or a smaller pump is used
  审计链：[{"triple_id": "MPT-5784e7d148be33952c6c", "decision": "rejected", "rejection_reasons": ["evidence_invalid"], "review_reasons": ["relation_entailment_undetermined", "evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[]

源页：`data/source_docs/marine_pump/raw/DESMI_Vertical_Multistage_T1536.pdf`，物理p18；页哈希`9507e7132ce501f2ac37783d1d0cce81f209f4c55116072f9c144f1f91cbda40`。

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## B07 首次启动泄漏前提：上下文仍可回查

既有B36为源文S、条件E：观察泄漏是否停止的建议属于首次启动尚未跑合的少量初始泄漏。直接推广为任何泄漏都等待不成立。源文邻句仍存在，但尚未证明自动选择正确作用对象。

- `MPT-f7412885a38d453e7a6d`，MP005物理p65，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：机械密封 [Component] → inspected_by → 观察机械密封以确认泄漏是否停止 [InspectionAction]。
  证据：Observe the mechanical seal to see if leakage stops, if not it could be enough to dismantle the mechanical seal and clean it properly to stop the leakage.
  审计链：[{"triple_id": "MPT-f7412885a38d453e7a6d", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-f7412885a38d453e7a6d", "claim_id": "EXC-cae4cafb452459656376a312", "assertion_id": "EXA-40b809b177723ec95010efb8", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-b5729cf42d3f37c12527`：机械密封 [Component] → inspected_by → 观察机械密封以确认泄漏是否停止 [InspectionAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf`，物理p65；页哈希`e40b79a44c27bf515776a458d1df83aa6a16461ea57db58c3b947afc0725bb7e`。
页内位置2759—3279： - A mechanical seal might have some initial leakage like drops or a small trickle during first start- up as it has not yet fully settled and become tight. Observe the mechanical seal to see if leakage stops, if not it could be enough to dismantle the mechanical seal and clean it properly to stop the leakage. 

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## B08 表格工况组合不是独立关键词

一行共同规定污物、湿度、负载、速度、温度及每日冲洗。旧候选虽保留多项字面线索，却存在单位字形/类型与引用问题，不能归为纯构图条件错。需要先分清原子关系是否已合法存在。

既有靶点：T11；范围`core`；旧AI状态`literal_partial`。
原文证据（多单元分隔，非伪造连续偏移）：Extreme dirt | 原生片段分隔 | Dry | 原生片段分隔 | Light to
medium | 原生片段分隔 | Slow to
medium | 原生片段分隔 | Daily flushing out dirt

- `MPT-042ed3a0124bd8ac0792`，MP018物理p16，族`PATTERSON_PUMP`；原状态`原始缓存未判定`；**未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在**。
  候选：极度脏污环境 [OperatingCondition] → mitigated_by → 每日冲洗污垢 [MaintenanceAction]。
  证据：Extreme dirt Dry Light to medium Slow to medium 0F (-18C) 200F (93C) Daily flushing out dirt
  审计链：[{"triple_id": "MPT-995c280ec5efa7fc15ab", "decision": "rejected", "rejection_reasons": ["relation_type_invalid", "evidence_invalid"], "review_reasons": ["relation_entailment_undetermined", "evidence_not_automatic_silver", "entailment_not_automatic_silver"]}]
  图谱：[]

源页：`data/source_docs/marine_pump/raw/Patterson_Non_Clog_Pump_OM.pdf`，物理p16；页哈希`f7dab72d68cb3bd90f6b470eab2af0db44670e66d4288fddbafc22974246e99e`。
页内位置2976—3496： Light to Slow to 0F 200F Extreme dirt Dry Daily flushing out dirt medium medium (-18C) (93C) High humidity Light to Slow to 32F 200F 1 to 4 weeks grea

判断边界：仅支持局部构图恢复的可能性；未执行修复。

## C01 潜在同义拆分：耐磨板磨损检查

中文仅有“的/是否”等表述差异，多语言源语均指同一检查，并共享受检部件。是明显的对齐候选；多数这类差异可能用短语规范化或词典解决，不能据此证明实体—关系联合模型必要。

- `MPT-a7a5a5858f953f8c8c70`，MP016物理p36，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：耐磨板 [Component] → inspected_by → 检查耐磨板的磨损或损坏 [InspectionAction]。
  证据：Controleer de slijtplaat op slijtage of schade.
  审计链：[{"triple_id": "MPT-8badb98ffb59d84a9a11", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-a7a5a5858f953f8c8c70", "claim_id": "EXC-2517d7de59d7a89b27fd2afa", "assertion_id": "EXA-13c091db02827ba67c8f6880", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-2003f16daaf95165994d`：耐磨板 [Component] → inspected_by → 检查耐磨板的磨损或损坏 [InspectionAction]；完整原载荷保留在案例JSONL。
- `MPT-ef255e6e2f3c6ca97fe9`，MP016物理p23，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]。
  证据：Überprüfen Sie die Verschleißplatte auf Verschleiß oder Beschädigung.
  审计链：[{"triple_id": "MPT-13d33fb48b08021c7a7d", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-ef255e6e2f3c6ca97fe9", "claim_id": "EXC-76ac842a2334b413f82ecaa7", "assertion_id": "EXA-d033beffcfc74b89c912c28b", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-05bf513dca3e4de11d7d`：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]；完整原载荷保留在案例JSONL。
- `MPT-da9266d579828e38c001`，MP016物理p30，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]。
  证据：Controllare la piastra antiusura per usura o danni.
  审计链：[{"triple_id": "MPT-19a719de499c2b4db79b", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-da9266d579828e38c001", "claim_id": "EXC-76ac842a2334b413f82ecaa7", "assertion_id": "EXA-b810eccdecad9322869b47ad", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-601dfcabf51f247231c0`：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]；完整原载荷保留在案例JSONL。
- `MPT-12a1f47c5d1925b13102`，MP016物理p42，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]。
  证据：Kontrollera slitageplåten för slitage eller skador. Slitplattan kan innehålla statisk tätningsyta eller ha polerad yta för försegling,
  审计链：[{"triple_id": "MPT-26b61d50ded124d5c171", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-12a1f47c5d1925b13102", "claim_id": "EXC-76ac842a2334b413f82ecaa7", "assertion_id": "EXA-0e2d8c24e128bd335e54b4b1", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-c4fd2955eef47af11085`：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]；完整原载荷保留在案例JSONL。
- `MPT-2e410e27e3921335a8b2`，MP016物理p6，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]。
  证据：Check wearplate for wear or damage.
  审计链：[{"triple_id": "MPT-a588d48b3a58985f37f8", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-2e410e27e3921335a8b2", "claim_id": "EXC-76ac842a2334b413f82ecaa7", "assertion_id": "EXA-f61e75c1a36bff383b95290a", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-2ec6308b8be888e9fed2`：耐磨板 [Component] → inspected_by → 检查耐磨板磨损或损坏 [InspectionAction]；完整原载荷保留在案例JSONL。
- `MPT-1798292dc04a3e13def3`，MP016物理p17，族`XYLEM__JABSCO`；原状态`silver_candidate`；**已发布**。
  候选：耐磨板 [Component] → inspected_by → 检查耐磨板是否磨损或损坏 [InspectionAction]。
  证据：Vérifiez que la plaque d’usure n’est pas usée ou endommagée.
  审计链：[{"triple_id": "MPT-49c0986e4da9c8e08a16", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-1798292dc04a3e13def3", "claim_id": "EXC-bd5c226e4b424b73bd8376de", "assertion_id": "EXA-577aa8fb9f1595864f2632a5", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-f44af60afb6e868495c6`：耐磨板 [Component] → inspected_by → 检查耐磨板是否磨损或损坏 [InspectionAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p6；页哈希`a72cd91a89601806bc559e061449afcbdaa0bd1abb016e90287e20944144b365`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p17；页哈希`e1742d1bd7318c779f6951afca0409c2e2374f5082cc39b1c2496a49e8588cbf`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p23；页哈希`0317e4853febc2e7254dcf05ad8aee49f26a2168b0fb50f77b55f95a114c71e7`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p30；页哈希`64fdceee7f9d325b0c89048d633ed48f1a62d378607662b71c2cad6d04d26e2b`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p36；页哈希`e3a77b43ffeda086d54ac421ab3224a9d42ded25b1e743f2358e2e3e30477503`。

源页：`data/source_docs/marine_pump/raw/Xylem_Jabsco_Engine_Cooling_Flexible_Impeller_Pump_IOM.pdf`，物理p42；页哈希`c69c560f618078cff4d8583bb36479d38530327da120983e98cbe8eb129bd2d9`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## C02 名称和邻域都相近仍不能合并：最大/最小流量

名称相似度0.9375且共享2项关系邻居，但maximum与minimum规定不同边界。共同邻域不保证同义；合并后会抹去一项约束。

- `MPT-c15836dc96527f5038de`，MP005物理p13，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：汽蚀损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]。
  证据：Observe the information on maximum flow rates specified in the product literature (to prevent overheating, mechanical seal damage, cavitation damage, bearing damage, etc.).
  审计链：[{"triple_id": "MPT-c15836dc96527f5038de", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-c15836dc96527f5038de", "claim_id": "EXC-9b135159c2d82a6ec11dad1d", "assertion_id": "EXA-14db669c5d66c2050fde8f7b", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-7d9ce12c9508a035b6a4`：汽蚀损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-484a272c6a3059198814`，MP005物理p13，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：轴承损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]。
  证据：Observe the information on maximum flow rates specified in the product literature (to prevent overheating, mechanical seal damage, cavitation damage, bearing damage, etc.).
  审计链：[{"triple_id": "MPT-484a272c6a3059198814", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-484a272c6a3059198814", "claim_id": "EXC-00d60a14759953d4a1c48667", "assertion_id": "EXA-9043620a8b40d66413c3e2ac", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-08d3800f107a5b148aa1`：轴承损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-642aeb051f63d5960074`，MP005物理p13，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：机械密封损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]。
  证据：Observe the information on maximum flow rates specified in the product literature (to prevent overheating, mechanical seal damage, cavitation damage, bearing damage, etc.).
  审计链：[{"triple_id": "MPT-642aeb051f63d5960074", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-642aeb051f63d5960074", "claim_id": "EXC-19d3f0a57569812c027bb5d2", "assertion_id": "EXA-43bdb88ab1df62312bba8007", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-b9a55299b4d1bda77779`：机械密封损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-c44997553e0e8160c622`，MP005物理p13，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：过热 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]。
  证据：Observe the information on maximum flow rates specified in the product literature (to prevent overheating, mechanical seal damage, cavitation damage, bearing damage, etc.).
  审计链：[{"triple_id": "MPT-c44997553e0e8160c622", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-c44997553e0e8160c622", "claim_id": "EXC-7254620330d4a8082500290b", "assertion_id": "EXA-8885894f1877a84ddbcccffc", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-5054433f4a6585780d51`：过热 [FaultMode] → prevented_by → 遵守产品文献中规定的最大流量信息 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-e62c605c9a35521c0f65`，MP005物理p13，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：轴承损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最小流量信息 [MaintenanceAction]。
  证据：Observe the information on minimum flow rates specified in the product literature (to prevent overheating, bearing damage, etc.).
  审计链：[{"triple_id": "MPT-e62c605c9a35521c0f65", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-e62c605c9a35521c0f65", "claim_id": "EXC-7b4971af0aef074057ab5083", "assertion_id": "EXA-85d5a13eae67b0c346cd36a7", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-fdbfedaddd9fab0ee6b7`：轴承损坏 [FaultMode] → prevented_by → 遵守产品文献中规定的最小流量信息 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-b9d0575b1e59edc49c4e`，MP005物理p13，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：过热 [FaultMode] → prevented_by → 遵守产品文献中规定的最小流量信息 [MaintenanceAction]。
  证据：Observe the information on minimum flow rates specified in the product literature (to prevent overheating, bearing damage, etc.).
  审计链：[{"triple_id": "MPT-b9d0575b1e59edc49c4e", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-b9d0575b1e59edc49c4e", "claim_id": "EXC-28679a55dafd4ff8ccc5c675", "assertion_id": "EXA-39b71096263693ad324dbb62", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-3df2815d6637863b6b28`：过热 [FaultMode] → prevented_by → 遵守产品文献中规定的最小流量信息 [MaintenanceAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_NSL_Pump_T1542.pdf`，物理p13；页哈希`93eeb30c8e0845d6d11983113f8be903092ad34c8995c067fb150c93108bae1f`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## C03 高液位与高高液位：级别应保留

同一来源页分别命名high level alarm和high-high level alarm，名称相似并共享邻居；它们可能对应不同报警阈级，不能以字面或结构相似直接合并。

- `MPT-63bbed608d16271435a3`，MP003物理p586，族`ABS`；原状态`silver_candidate`；**已发布**。
  候选：溢流柜 [Equipment] → contains → 高液位报警 [Component]。
  证据：The overflow tank is to be provided with a high level alarm, see 4-6-4/13.5.4.
  审计链：[{"triple_id": "MPT-373dd13fb07245597e6e", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-63bbed608d16271435a3", "claim_id": "EXC-cd182325dbed134e79c488a1", "assertion_id": "EXA-f41297e3ed6a6967e68380ae", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-bc52ab14d58ae9e24efc`：溢流柜 [Equipment] → contains → 高液位报警 [Component]；完整原载荷保留在案例JSONL。
- `MPT-5a3efc5dcb4450f78418`，MP003物理p586，族`ABS`；原状态`silver_candidate`；**已发布**。
  候选：储存柜 [Equipment] → contains → 高液位报警 [Component]。
  证据：Each storage tank is to be fitted with a high level alarm and a high-high level alarm.
  审计链：[{"triple_id": "MPT-9b1b1e8b8d5aa1f18b78", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-5a3efc5dcb4450f78418", "claim_id": "EXC-7b1c8c9df134187f1847a753", "assertion_id": "EXA-ba65b46158c08c52a1430f5a", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-f45c2862a0be03146e16`：储存柜 [Equipment] → contains → 高液位报警 [Component]；完整原载荷保留在案例JSONL。
- `MPT-929b6f7b78798c3bfeeb`，MP003物理p586，族`ABS`；原状态`silver_candidate`；**已发布**。
  候选：储存柜 [Equipment] → contains → 高高液位报警 [Component]。
  证据：Each storage tank is to be fitted with a high level alarm and a high-high level alarm.
  审计链：[{"triple_id": "MPT-3add766916118de40a26", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-929b6f7b78798c3bfeeb", "claim_id": "EXC-2e883afe41b28aa0cd3b8f14", "assertion_id": "EXA-b7e73b4ac43f5b71e0a50227", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-1270debb1c0ba828b700`：储存柜 [Equipment] → contains → 高高液位报警 [Component]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/ABS_Marine_Vessel_Rules_Part4_2021.pdf`，物理p586；页哈希`8d9eeeca7d2d63b7fd2c70d233508438698f6e50e820b96e30a7a6a3985dc14a`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## C04 部件与层级差异：泵和电机轴承/泵和电机轴

bearings与shaft不同，中文长公共前缀使相似度高；这不是同一部件。名称相似检索只能提议，不能给出对齐真值。

- `MPT-90caf20c8a592b776c16`，MP006物理p9，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：泵和电机轴承 [Component] → maintained_by → 电机支架无阻碍通风 [MaintenanceAction]。
  证据：Unrestricted ventilation of the motor bracket is therefore necessary to provide sufficient cooling of pump and motor bearings
  审计链：[{"triple_id": "MPT-9eab053f78b4bbac0c9f", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-90caf20c8a592b776c16", "claim_id": "EXC-66299119a6466336ff73c7bc", "assertion_id": "EXA-efb918f7e241d6c821c00308", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-66bc18256fddbe289476`：泵和电机轴承 [Component] → maintained_by → 电机支架无阻碍通风 [MaintenanceAction]；完整原载荷保留在案例JSONL。
- `MPT-714e18efe8c209dcde01`，MP015物理p34，族`SPX_FLOW__JOHNSON_PUMP`；原状态`silver_candidate`；**已发布**。
  候选：泵和电机轴 [Component] → inspected_by → 检查泵和电机轴的对中 [InspectionAction]。
  证据：Check the alignment of pump and motor shaft, see paragraph 3.4.3 "Alignment of the coupling".
  审计链：[{"triple_id": "MPT-f4e2afbb30782f49112c", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-714e18efe8c209dcde01", "claim_id": "EXC-ef1c041ed00ee274e0a9370f", "assertion_id": "EXA-d709c591723e51dea3ce7f18", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-6c8fd874d166943a1a55`：泵和电机轴 [Component] → inspected_by → 检查泵和电机轴的对中 [InspectionAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_Pump_Installation_Guidelines.pdf`，物理p9；页哈希`bfa7edc85de85b2fa3d43ea2e447b5a2cae6c89a65217973404bd709b490d231`。

源页：`data/source_docs/marine_pump/raw/SPX_Johnson_Pump_FreFlow_Instruction_Manual.pdf`，物理p34；页哈希`2c686360538d587bc5dfea9ae5274a9f85a25b2f0c582475ef902f6b9db5f110`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。

## C05 检查润滑剂与检查已润滑：对象/前置条件不同

一个检查bearing lubricant，另一个要求轴承启动前或紧接启动后已润滑；不能在未检查动作对象和时机时当完全同义。这也说明动作短语不是简单命名实体。

- `MPT-7464ffc484131d0a0cca`，MP018物理p13，族`PATTERSON_PUMP`；原状态`silver_candidate`；**已发布**。
  候选：轴承润滑剂 [Component] → inspected_by → 检查轴承润滑剂 [InspectionAction]。
  证据：Check the bearing lubricant.
  审计链：[{"triple_id": "MPT-387a462b00a5f61f1bcc", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-7464ffc484131d0a0cca", "claim_id": "EXC-42bcc8c745d7d3f8535a5035", "assertion_id": "EXA-397835ebb3c91425cb9becf2", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-e9a0d8125342e82619dc`：轴承润滑剂 [Component] → inspected_by → 检查轴承润滑剂 [InspectionAction]；完整原载荷保留在案例JSONL。
- `MPT-b5f69b6d4ffec2334a9a`，MP006物理p4，族`DESMI`；原状态`silver_candidate`；**已发布**。
  候选：轴承 [Component] → inspected_by → 检查轴承润滑 [InspectionAction]。
  证据：3. Check bearings are lubricated before startup or no later than immediately afterwards
  审计链：[{"triple_id": "MPT-0a4be2ebab8e85fba771", "decision": "silver_candidate", "rejection_reasons": [], "review_reasons": []}]
  图谱：[{"triple_id": "MPT-b5f69b6d4ffec2334a9a", "claim_id": "EXC-c592faa48908ef16bc773490", "assertion_id": "EXA-4d7cb4a7ff3553222ede8041", "conditions_source": null, "modality": "legacy_unspecified", "match_basis": "exact_source_key"}]
  原始抽取`MPT-5f1a30f71bc8bde47d21`：轴承 [Component] → inspected_by → 检查轴承润滑 [InspectionAction]；完整原载荷保留在案例JSONL。

源页：`data/source_docs/marine_pump/raw/DESMI_Pump_Installation_Guidelines.pdf`，物理p4；页哈希`702d936770bc14812917a95ce50dcd1dcbaf8bddca0c5818095fbf31bc73a47e`。

源页：`data/source_docs/marine_pump/raw/Patterson_Non_Clog_Pump_OM.pdf`，物理p13；页哈希`e5727e9047d6733f44abd85492036c456de2c66bd2124b6af5fd89adc0d864bf`。

判断边界：关系/实体层级的分析解释；未执行合并或改写。
