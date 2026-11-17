# expanded1456到RP2/RP3：接口及版本迁移说明

状态：**规划与数据说明，不是已执行迁移**。新默认知识源为`data/kg/marine_pump/versions/expanded_v1_20261012/`。现有strict208索引、40项查询参考、教师缓存、训练、模型、ONNX、校准和结果均保留；不改路径、不改名、不复用为新图结果。

## 1. 必须统一的读取语义

| 需要提供的信息 | expanded现有位置 | 注意事项 |
| --- | --- | --- |
| 图版本及哈希 | 图目录 + 本包`future_default_graph.json` | 文档策略指针，不是已激活的运行配置 |
| 稳定实体ID、中文名、类型 | `entities.jsonl`: entity_id / label_zh / entity_type | 字段不同于旧图canonical_label_zh；不按标签字符串临时重建ID |
| 稳定Claim及有向关系 | `claims.jsonl`: claim_id / head_entity_id / relation / tail_entity_id | 使用EXC/EXE；relation机器码从JSONL读取，不以GraphML中文显示名替代 |
| 稳定证据断言ID | `evidence_assertions.jsonl`: assertion_id | 使用EXA；Claim为主张族，断言携带具体来源 |
| 源语端点及中文规范名 | `source_records.jsonl`: head/tail_surface、head/tail_canonical_zh | 两套表述都保留，中文不是原文证据 |
| 物理页、URL、文档/页哈希 | 断言文件与完整source_records | pdf_page_number不同于printed_page |
| 来源族 | **需要从source_records按expanded_assertion_id连接** | 现有expanded断言文件没有source_family_id字段，不能假设可直接读取 |
| 新恢复位置 | source_witnesses / expansion_source_witnesses | 保留单元ID、原生偏移、bbox；不造页连续偏移 |
| 基线位置 | source_records中的原evidence_validation/evidence_units等 | 1326条baseline的source_witnesses为null不表示无来源；须走旧定位分支 |
| 条件、模态 | conditions_source、modality | 新130条显式；旧1326条null/legacy_unspecified，不能填为无条件确定 |
| 极性 | 没有全图统一显式字段 | 作为未知传递，证据文本保留；不能默认positive |
| 有效质量状态 | expansion_layer、expansion_validation或历史准入契约 | 新恢复与旧准入使用不同契约 |
| 不确定性与缺陷旁注 | 原始验证结果、80条quality_review、未定/拒绝原因 | AI初审不是Gold；旁注不得覆盖原始状态 |

1326条复用记录的根级`claim_id`仍为旧MPC，而`expanded_claim_id`为EXC。统一用`expanded_head_entity_id`、`expanded_tail_entity_id`、`expanded_claim_id`、`expanded_assertion_id`连接主图。新增130条根级ID已是新命名空间，两类混读会造成部分记录“能加载”、大部分记录丢链接的隐蔽错误。

## 2. 建议的适配视图（仅定义，本轮不导入运行系统）

```json
{
  "graph_version": "expanded_v1_20261012",
  "graph_manifest_sha256": "由文件清单计算，不手填常量",
  "entity": {"id": "实际EXE", "label_zh": "已有中文名", "type": "已有实体类型", "source_surfaces": []},
  "claim": {"id": "实际EXC", "head_id": "实际EXE", "relation": "稳定机器码", "tail_id": "实际EXE", "meaning": "evidence_linked_claim_family"},
  "assertion": {
    "id": "实际EXA", "claim_id": "实际EXC", "parent_record_id": "历史父记录ID",
    "contract_id": "historical_gate_or_native_role_contract",
    "source_family_id": "从完整记录连接",
    "conditions_status": "explicit_or_legacy_unspecified",
    "polarity": null, "polarity_status": "not_explicit_in_artifact",
    "quality_score": null, "quality_score_status": "not_comparable_across_contracts",
    "source_witnesses": [], "source_record_reference": "保留完整旧字段入口"
  }
}
```

这是接口模板，不是含已验证值的正式结果。实际版本与SHA256见本包JSON指针和来源清单。不要用模板中的文字占位符创建运行时实体。

来源家族可连接补齐，但新增130条没有与历史1698同口径的重新模型核验分数。旧`final_confidence`、旧`relation_entailment_validation`是历史状态，不可直接排序为新契约的0分或满分。现有`source_family_support.filter_eligible_assertions`使用历史准入标签及E1/E2状态，会排除新恢复记录；不能只把目录换成expanded就声称来源族治理已完成迁移。未来适配须显式选择契约、保留未知、另定可比较评分，不能改写原始字段来骗过旧过滤器。

## 3. RP2的必要迁移项目

1. **冻结输入。** 明确图目录、实体/Claim/断言/source记录哈希、Schema、术语和质量旁注；同一批结果不混读standard或strict。
2. **建立适配视图。** EXA连接来源族和条件，EXC连接全部断言；不只读取无条件GraphML裸边。源语别名从完整记录按实际EXE聚合，不能假设entities已带旧source_surfaces。
3. **重建索引。** 为新Claim及证据生成独立词法、向量与图邻接索引，记录编码模型、维度、版本及对象数。旧203项Claim/281实体的索引不可当作1400/2150版本索引。
4. **重新定义合法证据路径。** 以语义关系边定义“hop”，不把旧GraphML中Entity—Claim—Evidence的物理连线和新GraphML中直接Claim边混作同样跳数。查询需要断言级适用范围与来源去重约束。
5. **重建查询参考。** 可保留原40问题文本用于连续性分析，但原参考关系ID、可答/不可答、候选池、排序和答案数不得沿用。应在新图上形成新路径集合并进行独立源文检查，明确AI身份及未决项。旧自动fault_class_ids可以作为检索候选标签，不直接充当新图参考答案。
6. **固定公平比较。** 在新图内部重新确定构建/开发/评价分工，冻结预算、候选上限、模型、验证及弃答口径；新旧图性能比较须区分图谱变化与选择方法变化，不能把规模增量归于算法改进。
7. **记录已知问题。** B06/A14/A24等旁注应可回查；不把未经源文支持的边或缺失极性默认为教师正例。新教师要能拒绝图中有问题的主张，不因它在研究主图内就强制回答。

上述项目是接口说明，未在本轮建立新索引、生成新答案或运行新RP2基线。主图研究定位不等于RP2结果已经转移。

## 4. RP3的必要迁移项目

RP3的蒸馏对象应是**新版RP2的证据选择/核验输出及其合同**。输入空间将从历史208证据/203Claim变为新版内存，候选ID、可用性、教师正负标签、非空比例、K值和成本分布可能改变。

应另立TeacherGraph与任务版本，冻结图哈希、RP2选择器、验证器、渲染/弃答合同及输出缓存；再形成分组划分和独立开发/校准流程。旧strict208训练集、40个原问题的标签、特征缓存、ONNX和阈值不能直接标作expanded1456结果。旧外部评估集不能拿来设计新本体、提示、分组或路由。

本轮不执行上述教师重建、训练、校准或模型导出，不宣称原RP3失败已经被扩图解决。三章研究主线已统一，实证链是否贯通须在后续真实新版结果出现后再写为完成。

## 5. 可交接的已有资产和验收边界

- 三版规模及父记录链接已核实，本包`tables/version_record_id_crosswalk.csv`为1456条记录提供ID对照。
- `future_default_graph.json`只提供新版规划指针及实际文件哈希；`runtime_default_changed=false`。
- 源文、中文名、来源家族及位置按实际字段提供，不补造bbox、offset、分数或极性。
- expanded的完整CQ答案集、1400 Claim检索索引、新RP2参考、新RP3教师/训练均为**未执行**，不以文档生成替代实验完成。
