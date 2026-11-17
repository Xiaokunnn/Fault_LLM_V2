# 路径案例：自动基图参考下的命中、退化和未证实假设

以下是开发验证的事后解释，不是专家事实判定。头预测用inverse遍历；路径箭头不自动具有传递语义。目标引文只在此评价阶段读取。

## 1. 自动参考命中/排名改善，仍需看路径语义

ID `EXC-732489d7a4e0e990ac90d47e`，head，seed 16112026。查询：**爆破试验 — inverse:inspected_by → ?**。自动基图目标：机械接头；过滤后top1：机械接头。

排名：G2=10.0，raw-R3=5.0，full=1.0。

目标来源（不在路径输入中）：MP003 物理p514，`MPT-0149af2cf4600348d693`。

> 5.9.1(d) Burst Testing. Mechanical joints are to be tested to a burst pressure of four (4) times the                  design pressure.

实际路径 `24`（用于filtered top1，节点语义=0.6705，关系序列=1.0000，合分=0.7352，未归一化支持质量=2.3452）：

爆破试验 —[虚拟语义桥]→ 爆破压力试验 —[inverse:inspected_by]→ 抓握式和机械沟槽式接头 —[虚拟语义桥]→ 机械接头

- `RAW-09164ae2bd0c7418c320`，未确认候选边，MP003 p544：Burst pressure test --- CELL --- Y

上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。

实际路径 `26`（用于filtered top1，节点语义=0.6618，关系序列=1.0000，合分=0.7309，未归一化支持质量=2.2461）：

爆破试验 —[虚拟语义桥]→ 爆破压力试验 —[inverse:inspected_by]→ 滑套式接头 —[虚拟语义桥]→ 机械接头

- `RAW-ee7977a8d4474a1c50a5`，未确认候选边，MP003 p544：Burst pressure test --- CELL --- Y

上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。

## 2. 相对匹配raw-R3退化

ID `EXC-e405366981c34875527fff25`，head，seed 16112026。查询：**用螺钉紧固耐磨板并使用Loctite 243锁紧螺钉 — inverse:maintained_by → ?**。自动基图目标：耐磨板；过滤后top1：紧定螺钉。

排名：G2=1.0，raw-R3=1.0，full=4.0。

目标来源（不在路径输入中）：MP015 物理p39，`MPT-d2806c26e3c6b92d24ca`。

> 3 Tighten the wear plate with screws (0115). For this use Loctite 243 to lock the                          screws.

实际路径 `74`（用于filtered top1，节点语义=0.6358，关系序列=1.0000，合分=0.7179，未归一化支持质量=1.9720）：

用螺钉紧固耐磨板并使用Loctite 243锁紧螺钉 —[虚拟语义桥]→ Loctite 243锁固液 —[inverse:maintained_by]→ 短轴紧定螺钉 —[虚拟语义桥]→ 紧定螺钉

- `RAW-90f8b7b5b7e0a8ce6d12`，未确认候选边，MP015 p101：locking of the impeller bolt --- CELL --- Loctite 243

上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。

## 3. 完整原始三跳业务路径

ID `EXC-cdff44d10a49823150e3612c`，tail，seed 16112026。查询：**润滑剂过量 — causes → ?**。自动基图目标：轴承过热；过滤后top1：轴承过热。

排名：G2=5.0，raw-R3=1.0，full=1.0。

目标来源（不在路径输入中）：MP018 物理p15，`MPT-9f5573d9faacb30a6d3e`。

> Do not                       operate pump with excessive amount of lubricant. Such action will cause bearings                       to overheat.

实际路径 `43`（用于filtered top1，节点语义=0.5021，关系序列=0.9762，合分=0.7392，未归一化支持质量=2.4388）：

润滑剂过量 —[causes]→ 轴承温度过高 —[inverse:causes]→ 对中不良 —[causes]→ 轴承过热

- `RAW-35f1b769136e2675dae6`，未确认候选边，MP019 p38：Lagertemperatur zu hoch --- CELL --- Überschüssiges Schmiermittel
- `RAW-0352c40de35399c1729b`，未确认候选边，MP019 p38：Lagertemperatur zu hoch --- CELL --- Schlechte Ausrichtung
- `RAW-ecc1d6eb98a215cf1fd1`，未确认候选边，MP019 p74：Rodamientos sobrecalentados --- CELL --- Mala alineación

上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。

实际路径 `44`（用于filtered top1，节点语义=0.4794，关系序列=0.9762，合分=0.7278，未归一化支持质量=2.1777）：

润滑剂过量 —[causes]→ 轴承温度过高 —[inverse:causes]→ 皮带轮直径过小 —[causes]→ 轴承过热

- `RAW-35f1b769136e2675dae6`，未确认候选边，MP019 p38：Lagertemperatur zu hoch --- CELL --- Überschüssiges Schmiermittel
- `RAW-cbeb3049fae2c4440c8f`，未确认候选边，MP019 p38：Lagertemperatur zu hoch --- CELL --- Durchmesser der Riemenscheiben zu klein
- `RAW-b7f545d98ed9464350b2`，未确认候选边，MP019 p110：Överhettade lager --- CELL --- För liten remskivediameter

上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。

## 4. 只有单业务边的桥接目标迁移

ID `EXC-0b82f7efb667148b887514a8`，head，seed 16112026。查询：**在轴承两侧涂抹少量润滑脂 — inverse:maintained_by → ?**。自动基图目标：轴承；过滤后top1：脂润滑轴承。

排名：G2=6.0，raw-R3=2.0，full=2.0。

目标来源（不在路径输入中）：MP015 物理p46，`MPT-b429422eebaf7a2cfc74`。

> Pull the rubber closure rings gently aside and apply a small amount of grease at both                          sides of the bearings. Push the closure rings back in their correct position.

实际路径 `15`（用于reference target, not top1，节点语义=0.7568，关系序列=1.0000，合分=0.7784，未归一化支持质量=3.6107）：

在轴承两侧涂抹少量润滑脂 —[虚拟语义桥]→ 在轴承朝向轴侧涂抹润滑脂珠 —[inverse:maintained_by]→ 重型轴承箱 —[虚拟语义桥]→ 轴承

- `RAW-558ba646a33bad87bb48`，未确认候选边，MP005 p70：Heavy bearing housing (two angular ball bearings): --- CELL --- The bearings are to be relubricated through the lubricator nipple (84) in the bearing cover (15). Fill the bearings with grease and place a grease bead on t

上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。

实际路径 `17`（用于reference target, not top1，节点语义=0.7514，关系序列=1.0000，合分=0.7757，未归一化支持质量=3.5144）：

在轴承两侧涂抹少量润滑脂 —[虚拟语义桥]→ 在轴承朝向轴侧涂抹润滑脂珠 —[inverse:maintained_by]→ 轻型轴承箱 —[虚拟语义桥]→ 轴承

- `RAW-e1abb2b7b80c9fd59a69`，未确认候选边，MP005 p70：Light bearing housing (single-row ball bearing) --- CELL --- The bearing is to be relubricated through the lubricator nipple (84) in the bearing cover (15). In connection with replacement, the bearings are to be mounted

上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。

## 5. 无答案路径，严格回退

ID `EXC-2330d3b4e7c49df8db68b830`，head，seed 16112026。查询：**不停流清洗 — inverse:maintained_by → ?**。自动基图目标：滑油滤器；过滤后top1：双联滤器。

排名：G2=5.0，raw-R3=5.0，full=5.0。

目标来源（不在路径输入中）：MP003 物理p612，`MPT-88a312ad0f639a54a8ae`。

> An oil filter of the duplex type is to be provided or otherwise arranged so                  that it may be cleaned without interrupting the flow of oil

top1与目标均没有可用的两/三跳答案路径；该预测由文本分数或其他答案的重排产生，不能伪造支持路径。

## 6. 最终预测实体类型不合法

ID `EXC-170b10ac24abd85f0bfb7ad3`，tail，seed 16112026。查询：**内置安全阀 — located_in → ?**。自动基图目标：viking泵；过滤后top1：高舱底水位。

排名：G2=299.0，raw-R3=170.0，full=302.0。

目标来源（不在路径输入中）：MP021 物理p13，`MPT-b2419d62be00da425642`。

> Viking pumps can be furnished with either an internal                                pressure relief valve - one which directs the flow from the                          valve back to the suction side of the pump

top1与目标均没有可用的两/三跳答案路径；该预测由文本分数或其他答案的重排产生，不能伪造支持路径。
