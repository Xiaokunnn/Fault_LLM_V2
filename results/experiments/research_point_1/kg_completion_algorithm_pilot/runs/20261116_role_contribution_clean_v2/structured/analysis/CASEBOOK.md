# 来源角色与贡献对照的真实样本


以下是强对照的源文实例，不是专家标注或真实错误清单；N+是有证据的关系原型而不是待预测答案，N-是受控代理。


## RP-b274b3653bb7cd75738c / source_object_swap

查询头：轴承损坏。监督尾集合：['遵守产品文献中规定的最大流量信息']。N+：遵守产品文献中规定的最小流量信息；N-：在泵壳与后盖之间的o型圈槽中放置o型圈并用少量润滑脂固定。边/关系方向编号13→13。冻结贡献：+0.001279/-0.001214。

参考源：MP005物理页13：Observe the information on minimum flow rates specified in the product literature (to prevent
        overheating, bearing damage, etc.).。原生单元[]；范围优先适用于手册列明的NSL船用离心泵应用。

扰动对象源：MP005物理页101：Place the O-ring (21) between pump casing and                           
         rear cover (or motor bracket in ø215/265) in the                         
                                                                                  
         O-ring groove and hold it with a little grease.。原生单元[]；范围优先适用于手册列明的NSL船用离心泵应用。

## RP-f4d869897a7b02db2fbe / type_legal_relation_swap

查询头：轴承损坏。监督尾集合：['遵守产品文献中规定的最大流量信息']。N+：遵守产品文献中规定的最小流量信息；N-：遵守产品文献中规定的最小流量信息。边/关系方向编号13→10。冻结贡献：+0.001279/-0.000108。

参考源：MP005物理页13：Observe the information on minimum flow rates specified in the product literature (to prevent
        overheating, bearing damage, etc.).。原生单元[]；范围优先适用于手册列明的NSL船用离心泵应用。

## RP-698728b690a82af877d3 / direction_swap

查询头：泵损坏。监督尾集合：['潮湿、污染或损坏的开口及连接件']。N+：泵内温升或蒸汽形成；N-：泵内温升或蒸汽形成。边/关系方向编号15→0。冻结贡献：+0.000133/-0.003256。

参考源：MP005物理页46：rise in temperature / formation
          of steam in the pump which may cause damage to the pump。原生单元[]；范围优先适用于手册列明的NSL船用离心泵应用。

## RP-198a16be2cd407a91fa0 / different_table_row_object

查询头：过载。监督尾集合：['电机堵转']。N+：电机加速时间过长或电流过高；N-：电机振动。边/关系方向编号0→0。冻结贡献：+0.000017/-0.000363。

参考源：MP019物理页20：Motor takes too long to
accelerate and/or draws
high current
--- CELL ---
Excessive load。原生单元['MP019:p0020:t00:r001:c01', 'MP019:p0020:t00:r001:c02']；范围只用于泵驱动电机可迁移的电气故障与检查维护证据;不得把其他语言重复页计为独立证据。

扰动对象源：MP019物理页20：Motor vibrates
--- CELL ---
Bearings not in line。原生单元['MP019:p0020:t00:r011:c01', 'MP019:p0020:t00:r016:c02']；范围只用于泵驱动电机可迁移的电气故障与检查维护证据;不得把其他语言重复页计为独立证据。

## 假负例与不可辨识限制

同一故障可有多种有效措施，其他表行的动作并非世界中必然错误。例如“过载—电机振动”可能是未记录的真实机理，仅当前表行不对应；本实验负utility也只表示旧模型下对已知训练尾的不利影响。原型不能因此充当事实真假裁判。

同义答案副本的疑似样本在clean_v2被排除，不改变原事实标签；最大/最小、数值编号和否定不同者不按相似字符串直接合并。仍可能漏掉远距离语义转述，不宣称完美语义去重。

纯条件归属/型号交换若不改变输入，任何新损失都无法区分；该类控制不训练。需要输入可观察性改进时，应独立做输入消融，而不是说本轮已学会条件绑定。
