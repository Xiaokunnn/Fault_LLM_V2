# 待裁定的模型分歧

S=源文支持；N=关系/条件不成立；U=未决。两种 AI 意见均不是真值。

## R021 · MP004 物理页 10

原初审 U；本地第二意见 S；专家裁定 pending。

quantity of liquid delivered → diagnosed_by → measuring the current intensity of the connected motor

初审理由：电流测量直接对应功率消耗；流量还需压差和泵曲线。仅凭当前尾端点是否足以表示流量测定存在缺失条件。

保存的原引用：

```text
check either the quantity of liquid delivered or the power
        consumption of the pump e.g. by measuring the current intensity of the connected motor.
```

## R087 · MP022 物理页 28

原初审 S；本地第二意见 N；专家裁定 pending。

shaft seal → maintained_by → Dismantling of pump/shaft seals

初审理由：轴封拆卸章节标题支持广义维护关系；信息粒度较粗，标题不是全部操作流程。

保存的原引用：

```text
5.3 Dismantling of pump/shaft seals
```

## R010 · MP002 物理页 89

原初审 S；本地第二意见 N；专家裁定 pending。

insufficient age-to-failure data → mitigated_by → age exploration tasks are to be designed and implemented

初审理由：缺乏寿命数据时设计age exploration tasks，整页明确用途；属于维护分析过程，不是物理故障因果。

保存的原引用：

```text
When insufficient age-to-failure data are available or assumed data are used during the initial reliability
            based analysis, age exploration tasks are to be designed and implemented.
```

## R038 · MP007 物理页 6

原初审 N；本地第二意见 S；专家裁定 pending。

nominal current of motor → diagnosed_by → motor nameplate

初审理由：铭牌记载允许额定电流是规格信息，并非用铭牌诊断测量电流；diagnosed_by/InspectionMethod混淆资料来源与检测方法。

保存的原引用：

```text
The allowed nominal current of motor for pump configuration is indicated on the motor
          nameplate.
```

## R047 · MP015 物理页 39

原初审 S；本地第二意见 N；专家裁定 pending。

tolerance ring → maintained_by → apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

初审理由：Loctite 572施用于公差环等明确；须保留青铜/不锈钢泵和轴承组条件。

保存的原引用：

```text
In order to do this apply Loctite 572 on the impeller stop face (0120), the shaft
                         end and the rearmost part of the tolerance ring
```

## R009 · MP002 物理页 53

原初审 U；本地第二意见 S；专家裁定 pending。

rotating equipment → inspected_by → vibration taps

初审理由：vibration taps是测量接入点而非明确InspectionAction；可支持设计安装检测接口，是否等价inspected_by尚不确定。

保存的原引用：

```text
identify maintenance technology
                      requirements that need to be incorporated into the design (e.g., vibration taps on rotating
                      equipment)
```

## R004 · MP001 物理页 112

原初审 S；本地第二意见 N；专家裁定 pending。

unexpected events occurring instantaneously or in a short time period resulting in a total loss of system function → inspected_by → transient analyses

初审理由：transient analyses用于瞬时失效事件，原文直接对应；端点过长影响知识规范化。

保存的原引用：

```text
At times, transient analyses are performed for unexpected events occurring instantaneously or in a short
            time period resulting in a total loss of system function.
```

## R037 · MP007 物理页 15

原初审 N；本地第二意见 S；专家裁定 pending。

The motor without a nozzle → maintained_by → requires no maintenance

初审理由：源文为不需要维护的否定要求；用正向maintained_by连接requires no maintenance并标为MaintenanceAction，无法表达原命题的否定语义。

保存的原引用：

```text
The motor without a nozzle requires no maintenance.
```

## R014 · MP003 物理页 313

原初审 S；本地第二意见 U；专家裁定 pending。

sag and gap → diagnosed_by → verified at all open flanges

初审理由：下垂/间隙验证原文明确，但属于船舶轴系对中语境；不能自动视作泵证据。

保存的原引用：

```text
the sag and gap needs to be simultaneously
                      verified at all open flanges
```

## R039 · MP007 物理页 12

原初审 S；本地第二意见 N；专家裁定 pending。

valves on inlet pipes → inspected_by → If valves on inlet pipes are completely opened or not

初审理由：启动前确认吸入阀全开，原文直接列明。

保存的原引用：

```text
•  If valves on inlet pipes are completely opened or not.
```

## R063 · MP018 物理页 26

原初审 S；本地第二意见 U；专家裁定 pending。

Misalignment of the shaft → causes → Broken Separator (cage)

初审理由：轴承故障表已视觉核对，轴不对中为保持架破裂的可能原因。

保存的原引用：

```text
Broken Separator (cage)
--- CELL ---
1. Poor lubrication.
                                                                                    
                                                        2. Misalignment of the shaft.
                                                                                    
                                                        3. Excessive shaft deflection.
```

## R015 · MP003 物理页 943

原初审 S；本地第二意见 U；专家裁定 pending。

possible flooding → inspected_by → high-level bilge alarm

初审理由：消防泵舱/海底门分舱条件下安装高液位报警以检测进水，关系与泵场景成立。

保存的原引用：

```text
a high-level bilge alarm is to be fitted in the fire pump
                 space, as well as the compartment containing the sea chest, in order to detect possible flooding in
                 each of these spaces
```

## R033 · MP006 物理页 4

原初审 S；本地第二意见 N；专家裁定 pending。

abnormal noises or vibrations → diagnosed_by → Check that the pump rotates in the correct direction and has no abnormal noises or vibrations

初审理由：明确检查噪声/振动；端点包含被检查症状是低信息重复表达，尚非新诊断方法。

保存的原引用：

```text
5. Check that the pump rotates in the correct direction and has no abnormal noises or vibrations
```
