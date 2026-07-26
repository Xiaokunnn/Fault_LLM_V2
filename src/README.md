# Research Points

`src/` 按论文的三个研究点划分。任何实现代码都必须归入对应研究点目录，不在 `src/` 根目录直接堆放业务模块。

```text
src/
├── research_point_1_graph_evidence/  低时延图谱证据检索与自适应剪枝
├── research_point_2/                 图谱证据蒸馏与原型记忆边缘轻量模型
└── research_point_3/                 置信度校准与选择性回退
```

三个研究点之间可共享通用数据结构和基础工具，但只有出现稳定的跨研究点复用需求后，才新增独立的 `src/shared/`；当前阶段不提前抽象。
