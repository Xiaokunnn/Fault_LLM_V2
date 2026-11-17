# 来源角色与贡献对照的真实样本


以下是强对照的源文实例，不是专家标注或真实错误清单；N+是有证据的关系原型而不是待预测答案，N-是受控代理。


## RP-f4d869897a7b02db2fbe / type_legal_relation_swap

查询头：轴承损坏。监督尾集合：['遵守产品文献中规定的最大流量信息']。N+：遵守产品文献中规定的最小流量信息；N-：遵守产品文献中规定的最小流量信息。边/关系方向编号13→10。冻结贡献：+0.001989/-0.000809。

参考源：MP005物理页13：Observe the information on minimum flow rates specified in the product literature (to prevent
        overheating, bearing damage, etc.).。原生单元[]；范围优先适用于手册列明的NSL船用离心泵应用。

## RP-9cd7ca691b5ebd469c65 / source_object_swap

查询头：凸轮。监督尾集合：['穿过泵体固定凸轮螺钉并拧紧']。N+：穿过本体固定凸轮螺钉并拧紧；N-：润滑密封橡胶并将密封件压入泵体孔中。边/关系方向编号8→8。冻结贡献：+0.000016/-0.000020。

参考源：MP016物理页50：Fije el tornillo de leva a través del cuerpo y apriételo。原生单元[]；范围仅适用于船用发动机冷却柔性叶轮泵;不得把柔性叶轮机理无条件推广到离心泵。

扰动对象源：MP016物理页31：Lubrificare la gomma della guarnizione e premere la
     guarnizione nel foro del corpo.。原生单元[]；范围仅适用于船用发动机冷却柔性叶轮泵;不得把柔性叶轮机理无条件推广到离心泵。

## RP-698728b690a82af877d3 / direction_swap

查询头：泵损坏。监督尾集合：['潮湿、污染或损坏的开口及连接件']。N+：泵内温升或蒸汽形成；N-：泵内温升或蒸汽形成。边/关系方向编号15→0。冻结贡献：+0.000376/-0.000123。

参考源：MP005物理页46：rise in temperature / formation
          of steam in the pump which may cause damage to the pump。原生单元[]；范围优先适用于手册列明的NSL船用离心泵应用。

## 假负例与不可辨识限制

同一故障可有多种有效措施，其他表行的动作并非世界中必然错误。例如“过载—电机振动”可能是未记录的真实机理，仅当前表行不对应；本实验负utility也只表示旧模型下对已知训练尾的不利影响。原型不能因此充当事实真假裁判。

同义答案副本的疑似样本在clean_v2被排除，不改变原事实标签；最大/最小、数值编号和否定不同者不按相似字符串直接合并。仍可能漏掉远距离语义转述，不宣称完美语义去重。

纯条件归属/型号交换若不改变输入，任何新损失都无法区分；该类控制不训练。需要输入可观察性改进时，应独立做输入消融，而不是说本轮已学会条件绑定。
