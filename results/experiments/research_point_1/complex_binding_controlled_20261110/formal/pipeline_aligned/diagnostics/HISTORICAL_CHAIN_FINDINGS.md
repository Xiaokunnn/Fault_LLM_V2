# 17项历史全链路：完整135条响应阅读后补充

仅分析现存原始记录，不修改原8/4/5 AI初审。下列分类是目标字面要素与接口/范围的分析性归因，不是新S/E/U或专家事实标注。已完整检查15页全部135条输出，包括中外文端点与证据，未只搜相关ID。

全部17项原生证据进入历史输入；原提示SHA256均匹配；主提案135→保存候选135，没有该阶段计数丢失；完整解码响应只有triples与空warnings。来源定位、Schema、语义完整性与发布是另外的阶段。

| 靶点 | 主要归因（字面/接口层） | 依据 | 原生规则回放 |
| --- | --- | --- | --- |
| T01 | Schema/范围边界 | 9条输出涉及腐蚀监测、挂片和损伤，没有测试环境一致性与预测准确性陈述；无辅助字段。 | [] |
| T02 | Schema/范围边界 | 3条输出是阀门开闭、推进停机/报警状态；没有共用传感器的许可及例外。 | [] |
| T03 | 目标词句已在输出 | 第8/9条分别含immediately和before returning，动作均存在；不能因无sequence字段称未生成，不据此宣称关系级完整正确。 | [{'id': 'MPT-abc10efaea6b1d67d540', 'included': True, 'flags': [], 'barriers': []}, {'id': 'MPT-19355a857064a9de906b', 'included': True, 'flags': [], 'barriers': []}] |
| T04 | 目标关键要素未见 | 12条完整输出中没有5分钟/80°C闭出口限制；permissible operating range只是泛化范围。 | [{'id': 'MPT-b7fd6a4103cceacea645', 'included': True, 'flags': [], 'barriers': []}] |
| T05 | 目标关键要素未见 | 4条已表达过热风险、法兰保温场景和无阻通风；没有孔/网罩开口不得被保温覆盖的明确禁令。 | [{'id': 'MPT-4dd8c4b90efa21a2b103', 'included': False, 'flags': ['conditional_context_not_explicit'], 'barriers': []}, {'id': 'MPT-b026f6768b45ab7ba01d', 'included': True, 'flags': [], 'barriers': []}] |
| T06 | 目标词句已在输出 | 第9条head为Motor (non drive end)，tail为Vibration trip level >15 mm/s；表格行亦含>10/>15。是否把trip阈值视作InspectionMethod另列类型caveat。 | [{'id': 'MPT-ecb0389e795b06b7027c', 'included': True, 'flags': [], 'barriers': []}] |
| T07 | 目标词句已在输出 | 第23条明确increased or a smaller pump is used；OR没有被模型删掉。该条未准入须看定位/结构判定，不是OR漏生成。 | [{'id': 'MPT-0a76fe80d31fd1d7729d', 'included': False, 'flags': ['unbound_quote'], 'barriers': ['unbound_source_quote']}] |
| T08 | 目标部分要素已见 | 第14/15条检查密封面和弹性体；第16条另有必要时更换机械密封，但没有计划维护替代分支，不能跨项目强行补成完整OR。 | [{'id': 'MPT-7fe70f8ef05b5f27443f', 'included': True, 'flags': [], 'barriers': []}, {'id': 'MPT-31a35c9323459d590e03', 'included': True, 'flags': [], 'barriers': []}] |
| T09 | 目标关键要素未见 | 6条里有检温、排液、泄压和关阀；缺若过热则完全冷却的动作。检温不等于冷却。 | [{'id': 'MPT-0318f6a2d7872f9ffcd9', 'included': True, 'flags': [], 'barriers': []}] |
| T10 | 目标词句已在输出 | 两条均以偏离选型工况为head，evidence含may以及cavitation or shortened life；缺独立modality不自动等于文字消失。 | [{'id': 'MPT-ab84f58a8f81bca73443', 'included': True, 'flags': [], 'barriers': []}, {'id': 'MPT-e21c40f9601ee0d9ef55', 'included': True, 'flags': [], 'barriers': []}] |
| T11 | 目标词句已在输出 | 第6条evidence完整列出Extreme dirt/Dry/负载/速度/0F(-18C)/200F(93C)/Daily flushing；但head是OperatingCondition，mitigated_by类型不合法且绑定需另核，不能计作完整正确关系。 | [{'id': 'MPT-042ed3a0124bd8ac0792', 'included': False, 'flags': ['schema_type_direction', 'unbound_quote'], 'barriers': ['unbound_source_quote']}] |
| T12 | 目标关键要素未见 | 5条有其他润滑脂的质量核实、禁止混脂与补脂动作，没有其他润滑脂可能缩短补脂周期。 | [{'id': 'MPT-1fdfd4d36d8fcfa76cda', 'included': False, 'flags': ['schema_type_direction'], 'barriers': []}] |
| T13 | 目标部分要素已见 | 8条中第2/3条有参考电阻未达、绕组潮湿和烘干动作；没有90°C×12–16h再105°C×6–8h，非仅将已有参数换序即可恢复。 | [{'id': 'MPT-4e9c5cdee2445bafd79a', 'included': False, 'flags': ['schema_type_direction', 'unbound_quote'], 'barriers': ['no_same_column_or_native_cell_binding', 'unbound_source_quote']}, {'id': 'MPT-5557f786a3dc1519779b', 'included': False, 'flags': ['unbound_quote'], 'barriers': ['no_same_column_or_native_cell_binding', 'unbound_source_quote']}] |
| T14 | 目标词句已在输出 | 第4条tail及evidence均保留clear liquids applications only。 | [{'id': 'MPT-1b43eb82b971be6816fc', 'included': True, 'flags': [], 'barriers': []}] |
| T15 | 目标关键要素未见 | 6条有监测压力、维护、泄漏及高温原因；没有四种压力保护选择及反向旋转双侧保护。监测压力不是过压保护。 | [{'id': 'MPT-60931b33087d770f9870', 'included': True, 'flags': [], 'barriers': []}] |
| T16 | Schema/范围边界 | 6条完整响应未表达泄压阀禁止用于调流/调压，且无辅助字段；用途/许可关系边界不能强行转成维护或因果。 | [] |
| T17 | 目标词句已在输出 | 第1条head=impeller，tail与evidence完整包含before operation。 | [{'id': 'MPT-de844399072c122f2cd6', 'included': True, 'flags': [], 'barriers': []}] |

合计：7项目标词句已在输出、2项部分要素已见、5项目标关键要素未见、3项优先属Schema/范围边界。这不把7项升级为7条完整正确关系，也不是相对原图新增量，更不是全语料频率。完整135条清单见historical_complete_inventory.md；原始S/E/U及8/4/5判断保持原样。
