# KG_v1 标准化约束报告

- 报告版本：`marine_pump_graph_constraint_report_v1`
- 生成时间：`2026-07-30T10:12:12.335448+00:00`
- 校验器：`custom_python_graph_constraint_profile`
- 结论：**未发现发布阻断错误**
- 失败检查：1
- 发布阻断检查：0
- 人工专家审核：否
- 标签政策：Silver only; never Gold

> 本报告是项目专用Python约束配置的可执行结果，不是完整JSON Schema验证、RDF验证或SHACL验证。

## 图谱包统计

| 图谱 | 源记录 | 实体 | Claim | Evidence | 链接 |
|---|---:|---:|---:|---:|---:|
| KG_v1_raw | 8003 | 9149 | 7651 | 8003 | 8003 |
| KG_v1_validated | 208 | 281 | 203 | 208 | 208 |

## 约束结果

| 规则 | 范围 | 状态 | 严重度 | 检查数 | 违规数 | 发布阻断 |
|---|---|---|---|---:|---:|---|
| `PKG001_REQUIRED_LAYER_FILES` 五个分层JSONL文件均存在 | KG_v1_raw | pass | info | 5 | 0 | 否 |
| `PKG002_UNIQUE_STABLE_IDENTIFIERS` 分层记录ID唯一且非空 | KG_v1_raw | pass | info | 32806 | 0 | 否 |
| `PKG003_LINK_TARGETS_AND_UNIQUENESS` Claim—Evidence链接稳定且目标存在 | KG_v1_raw | pass | info | 8003 | 0 | 否 |
| `PKG004_CLAIM_HAS_EVIDENCE` 每个Claim至少关联一条Evidence | KG_v1_raw | pass | info | 7651 | 0 | 否 |
| `PKG005_EVIDENCE_HAS_CLAIM_LINK` 每条Evidence至少被一个Claim引用 | KG_v1_raw | pass | info | 8003 | 0 | 否 |
| `PKG006_SOURCE_RECORD_LINK_COVERAGE` 源记录与Claim—Evidence链接双向覆盖 | KG_v1_raw | pass | info | 16006 | 0 | 否 |
| `GOV001_ALLOWED_GOVERNANCE_STATUS` 治理状态属于冻结枚举 | KG_v1_raw | pass | info | 8003 | 0 | 否 |
| `SPLIT001_PRIMARY_GRAPH_BUILD_ONLY` 主图谱不含开发集或保留测试集 | KG_v1_raw | pass | info | 8003 | 0 | 否 |
| `GOV003_RAW_STATUS_DISTRIBUTION` 审计图治理状态分布 | KG_v1_raw | info | info | 8003 | 0 | 否 |
| `PROV001_CORE_FIELDS_PRESENT` Silver/发布记录具有核心溯源字段 | KG_v1_raw | pass | info | 1698 | 0 | 否 |
| `PROV002_PAGE_URL_HASH_FORMAT` 物理页、URL和哈希格式有效 | KG_v1_raw | pass | info | 1698 | 0 | 否 |
| `PROV003_NONRELEASE_EVIDENCE_GAPS` 非发布记录的原文缺失审计 | KG_v1_raw | fail | warning | 6305 | 40 | 否 |
| `EVID001_RELEASE_E1_E2_NONINFERRED_ENTAILED` Silver/发布记录为有效E1/E2且非推断 | KG_v1_raw | pass | info | 1698 | 0 | 否 |
| `REL001_REGISTRY_DOMAIN_RANGE` Silver/发布关系符合注册表与Domain/Range | KG_v1_raw | pass | info | 1698 | 0 | 否 |
| `ID001_STABLE_SOURCE_IDENTIFIERS` Silver/发布源记录稳定ID可重算 | KG_v1_raw | pass | info | 1698 | 0 | 否 |
| `REL002_RAW_NONRELEASE_INVALID_RELATIONS` 审计图非发布记录中的关系违规分布 | KG_v1_raw | info | info | 1292 | 0 | 否 |
| `PKG007_LAYER_PROJECTION_CONSISTENCY` 源记录与实体/Claim/Evidence投影一致 | KG_v1_raw | pass | info | 8003 | 0 | 否 |
| `PKG001_REQUIRED_LAYER_FILES` 五个分层JSONL文件均存在 | KG_v1_validated | pass | info | 5 | 0 | 否 |
| `PKG002_UNIQUE_STABLE_IDENTIFIERS` 分层记录ID唯一且非空 | KG_v1_validated | pass | info | 900 | 0 | 否 |
| `PKG003_LINK_TARGETS_AND_UNIQUENESS` Claim—Evidence链接稳定且目标存在 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `PKG004_CLAIM_HAS_EVIDENCE` 每个Claim至少关联一条Evidence | KG_v1_validated | pass | info | 203 | 0 | 否 |
| `PKG005_EVIDENCE_HAS_CLAIM_LINK` 每条Evidence至少被一个Claim引用 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `PKG006_SOURCE_RECORD_LINK_COVERAGE` 源记录与Claim—Evidence链接双向覆盖 | KG_v1_validated | pass | info | 416 | 0 | 否 |
| `GOV001_ALLOWED_GOVERNANCE_STATUS` 治理状态属于冻结枚举 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `SPLIT001_PRIMARY_GRAPH_BUILD_ONLY` 主图谱不含开发集或保留测试集 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `GOV002_VALIDATED_ONLY_SILVER` 发布图只包含Silver记录 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `PROV001_CORE_FIELDS_PRESENT` Silver/发布记录具有核心溯源字段 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `PROV002_PAGE_URL_HASH_FORMAT` 物理页、URL和哈希格式有效 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `PROV003_NONRELEASE_EVIDENCE_GAPS` 非发布记录的原文缺失审计 | KG_v1_validated | pass | info | 0 | 0 | 否 |
| `EVID001_RELEASE_E1_E2_NONINFERRED_ENTAILED` Silver/发布记录为有效E1/E2且非推断 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `REL001_REGISTRY_DOMAIN_RANGE` Silver/发布关系符合注册表与Domain/Range | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `ID001_STABLE_SOURCE_IDENTIFIERS` Silver/发布源记录稳定ID可重算 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `PKG007_LAYER_PROJECTION_CONSISTENCY` 源记录与实体/Claim/Evidence投影一致 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `ZH001_RELEASE_ENDPOINT_GOVERNANCE` 发布端点满足中文术语门控 | KG_v1_validated | pass | info | 208 | 0 | 否 |
| `ZH002_RELEASE_ENTITY_PROJECTION` 发布实体具有中文规范名和术语ID | KG_v1_validated | pass | info | 281 | 0 | 否 |
| `RELEASE001_VALIDATED_SUBSET_WITH_IMMUTABLE_EVIDENCE` 发布记录可回溯到Raw且原文溯源未变 | KG_v1_raw -> KG_v1_validated | pass | info | 208 | 0 | 否 |

## 失败与警告明细

### `PROV003_NONRELEASE_EVIDENCE_GAPS` 非发布记录的原文缺失审计

拒绝项允许因证据缺失而存在于审计图；此项作为warning记录，不阻止已经合格的发布子集。

- 严重度：warning
- 违规数：40
- 发布阻断：否
- 示例：

  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-137c56bd0e93b9430080"}`
  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-218938f7da5ee89f8a26"}`
  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-25de13f7c2347a2bf52a"}`
  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-2c59246962bfd3d4f338"}`
  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-399ee638a1ce309f6dcd"}`
  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-3a529725e95e8c884520"}`
  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-3c7481214481d4b5b9d5"}`
  - `{"reason": "nonrelease_record_missing_evidence_text", "record": "MPT-3e4bad767a6ea0bd268e"}`

## 解释边界

- `error`表示当前发布约束的硬失败，并令`release_blocked=true`。
- `warning`记录审计质量缺口，但不自动否定已通过门槛的发布子集。
- `info`包括通过项和只作分布统计的审计项。
- 该结果验证结构、溯源和治理状态的一致性，不等价于领域专家确认事实正确。
