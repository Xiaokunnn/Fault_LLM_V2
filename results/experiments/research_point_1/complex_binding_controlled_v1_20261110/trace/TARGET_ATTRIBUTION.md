# T01–T17全链路归因（开发性AI分析，非Gold）

原17项及其编号不变。提示为经过原缓存SHA256验证的重建，不冒充历史保存的请求字节。完整解码响应及主候选逐页计数一致；没有auxiliary字段、warnings为空，不靠搜索主候选推断全响应。5页merged_chunks均逐part确认stop。

| 靶点 | 文档物理页 | 范围 | 原AI初审 | 相关缓存 | 完整响应锚点 | 原生回放准入 | 必保留内容/归因 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | MP001:p0088 | auxiliary_only | cached_core_absent | 无原相关ID | [False] | [] | 环境在整个测试期一致；准确预测为条件性陈述。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T02 | MP003:p0891 | auxiliary_only | cached_core_absent | 无原相关ID | [False] | [] | 许可排除停机功能及所列必需泵自动启动/切换，保持例外作用域。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T03 | MP005:p0053 | core | literal_partial | MPT-abc10efaea6b1d67d540,MPT-19355a857064a9de906b | [True, True] | [True, True] | 异常/损坏语境；立即停泵；消除原因在重新投运之前；不得添加强制重启。 两动作、immediately及before returning均已出现。跨边动作链是否足够可由源文读者判断，不能仅因没有sequence字段称信息全丢。 |
| T04 | MP005:p0053 | core | cached_core_absent | MPT-b7fd6a4103cceacea645 | [False] | [True] | 标准泵；闭出口；最长5分钟 AND 最高80°C；不构成现场操作许可。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T05 | MP006:p0009 | core | cached_core_absent | MPT-4dd8c4b90efa21a2b103,MPT-b026f6768b45ab7ba01d | [False] | [False, True] | 电机支架孔/网罩开口；保温场景；不得覆盖。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T06 | MP006:p0007 | core_with_type_caveat | literal_complete | MPT-ecb0389e795b06b7027c | [True, True] | [True] | 电机非驱动端；建议跳机而非报警；严格>15 mm/s；DESMI局部范围。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T07 | MP007:p0018 | core | literal_complete | MPT-0a76fe80d31fd1d7729d | [True, True] | [False] | 对应低流量/堵塞表格分支；增加流量 OR 使用较小泵，不能变成AND。 OR已在动作文字中；未准入是证据/规则问题，不是OR未生成。 |
| T08 | MP016:p0029 | core | literal_partial | MPT-7fe70f8ef05b5f27443f,MPT-31a35c9323459d590e03 | [False] | [True, True] | 密封面磨损、弹性体状态检查；必要时替换 OR 记录待计划维护；指代对象一致。 相关检查和其他更换动作存在，但计划维护的替代分支未见；不能把其他条目的更换强配为此分支。 |
| T09 | MP017:p0004 | core | cached_core_absent | MPT-0318f6a2d7872f9ffcd9 | [True, False] | [True] | 开泵/检修之前；IF 已过热 THEN 完全冷却，不能无条件化。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T10 | MP018:p0002 | core | literal_complete | MPT-ab84f58a8f81bca73443,MPT-e21c40f9601ee0d9ef55 | [True] | [True, True] | 偏离选型工况；may；汽蚀或轴承/密封/填料/轴寿命缩短；非必然后果。 工况在head，may在evidence；无独立modality字段只表示不可直接按字段查询。 |
| T11 | MP018:p0016 | core | literal_partial | MPT-042ed3a0124bd8ac0792 | [True, True, True, True, True] | [False] | 同一行：极脏、干、轻至中负载、低至中速、0–200°F→每日冲排污物；不能跨行。 全部工况及每日冲排已在原evidence，0F/200F仍保留F量纲；度符号缺失不直接等于单位语义丢失。需分开记录literal保留、未绑定字段、类型/定位拒绝。 |
| T12 | MP019:p0107 | core | cached_core_absent | MPT-1fdfd4d36d8fcfa76cda | [False] | [False] | 使用其他润滑脂时，周期可能缩短；非确定强制缩短。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T13 | MP019:p0097 | core | literal_partial | MPT-4e9c5cdee2445bafd79a,MPT-5557f786a3dc1519779b | [False, False] | [False, False] | 参考电阻未达到；先90°C×12–16h，后105°C×6–8h；温度/时长必须成对且有序。 潮湿诊断及烘干动作已生成；有序温度—时长片段未在保存响应中出现。 |
| T14 | MP020:p0006 | core | literal_complete | MPT-1b43eb82b971be6816fc | [True] | [True] | 整流器仅清液适用；only不可删除。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T15 | MP021:p0002 | core | cached_core_absent | MPT-60931b33087d770f9870 | [False, False] | [True] | 四种压力保护替代：泵上阀/管路阀/扭矩限制/爆破盘；可能反转时双侧保护。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T16 | MP021:p0002 | auxiliary_only | cached_core_absent | 无原相关ID | [False] | [] | 不可用于流量控制，也不可用于出口压力调节；在辅助要求中完整保留。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |
| T17 | MP022:p0019 | core | literal_complete | MPT-de844399072c122f2cd6 | [True] | [True] | 运行前；叶轮旋向检查。 字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。 |

范围外/无现有关系可表达的T01/T02/T16不进入核心关系保留分母，另评价辅助要求保留；T06标为类型解释需核验。字段缺失、类型拒绝、发布阻断及文字仍在分别保留，不能合并成LLM未生成。

逐项原文、输入、原始解码输出、全部候选和验证记录见full_input_output_packets.jsonl；这些材料不进入新生成提示或盲审的期望答案。
