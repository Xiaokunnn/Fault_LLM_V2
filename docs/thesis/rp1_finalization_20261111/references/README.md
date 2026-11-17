# 章节参考与证据出处

`rp1_chapter3_selected.bib`从既有ICSMD最终稿书目中原样选出4项：EDC、PROV-O、nanopublication和ProVe。2026-11-11核对了对应原始出版/标准页面：

- EDC：[ACL Anthology](https://aclanthology.org/2024.emnlp-main.548/)。
- PROV-O：[W3C Recommendation](https://www.w3.org/TR/prov-o/)。
- Nanopublication：[原出版DOI](https://doi.org/10.3233/ISU-2010-0613)。
- ProVe：[原出版DOI](https://journals.sagepub.com/doi/10.3233/SW-233467)。

这些来源仅支撑已有技术定位和书目，不支撑本仓库的实验数值；实验数值以本地记录为依据。没有重跑这些外部方法，因此不作同数据性能比较或穷尽查新结论。

`supplementary_source_manifest.json`补充8个与模型核验、20页协议、扩图及历史RP2有关的代码/文献/配置哈希。它补充主`source_manifest.json`的109个输入，不改历史清单。原始数据、代码和论文中的历史术语保留，新的正文统一使用自动证据准入等表述。

部分旧结果文件的状态字段是生成时的中间快照，例如扩图`counts.json`曾记“质量检查待完成”，而后续`quality_summary.json`及`completion.json`已记完成。论文按完整时间链读取，不能仅凭单个早期状态字段把已完成实验说成未执行；同样，未进行的专家事实评价、新图CQ或下游迁移不能被“完成”状态覆盖。
