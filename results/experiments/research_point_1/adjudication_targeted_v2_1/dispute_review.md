# 13 条分歧的 v2 技术复核

评审身份：Codex assistant。均为暂定 AI 技术意见；真实独立专家裁定 pending。S/N/U 是历史第一轮和模型第二意见，不作为新准确率标签。

## R021 / MP004:p0010

历史意见：U → S；v2 技术处理：`qualifiers_required`；范围：`primary`。

旧记录：quantity of liquid delivered — diagnosed_by → measuring the current intensity of the connected motor

测电流不能在当前表述中单独替代流量测定；下一句还要求压差读数与泵特性。保留整段联合方法，不把电流单独视为充分方法。

待专家核对：组合方法中电流对应流量还是功率的语法仍可交由专家确认。

原页精确字符区间 [4479, 4839)：
```text
Therefore, after start-up, it is necessary to check either the quantity of liquid delivered or the power
        consumption of the pump e.g. by measuring the current intensity of the connected motor. Together
        with a reading of the differential pressure the quantity of water delivered can be determined against
        the characteristics of the pump.
```

## R087 / MP022:p0028

历史意见：S → N；v2 技术处理：`granularity_repair`；范围：`primary`。

旧记录：shaft seal — maintained_by → Dismantling of pump/shaft seals

维修章节明确包含泵/轴封拆解，不能说源文没有维护依据；但标题不足以成为具体原子动作，需拆成有顺序、部件号和章节范围的步骤。

待专家核对：不得把每一步都无条件作用于轴封；图示部件绑定仍需专家确认。

原页精确字符区间 [771, 3772)：
```text
5.3 Dismantling of pump/shaft seals                                        
                                                                                  
       SSSttteeeppp 111                                                           
       Remove screw (23) and safety guard (22)                                    
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
       SSSttteeeppp 222                                                           
       1. Loosen unions and remove recirculation pipe (56)                        
       2. Remove clamp (57) and front cover (60)                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
                                                                                  
       SSSttteeeppp 333                                                           
       1. Remove air screw (58) with a spanner. Counter hold with a               
         screwdriver on pump shaft (7)                                            
       2. Unscrew cap nuts (24). Remove washers (24a) and pump                    
         casing (29)
```

## R010 / MP002:p0089

历史意见：S → N；v2 技术处理：`background_and_type_mismatch`；范围：`background`。

旧记录：insufficient age-to-failure data — mitigated_by → age exploration tasks are to be designed and implemented

原文确实要求在失效年龄数据不足或使用假设数据时实施寿命探索任务；它是可靠性分析方法，不是泵故障原因及其维修措施。保留背景知识，不发布为主任务 Cause→mitigated_by。

待专家核对：背景知识有用性不等于核心故障知识覆盖。

原页精确字符区间 [4399, 5146)：
```text
17   Age Exploration Tasks                                                 
            When insufficient age-to-failure data are available or assumed data are used during the initial reliability
            based analysis, age exploration tasks are to be designed and implemented. An effective reliability based
            program will necessarily impose frequent changes to an age exploration program, such as adding new
            equipment, deleting completed or unproductive tasks, or adjusting task intervals. The result of the age-
            exploration tasks is a better understanding of the system or equipment’s wear-out region of the failure
            characteristics curve, which can be fed back for use in updating the analysis.
```

## R038 / MP007:p0006

历史意见：N → S；v2 技术处理：`relation_mismatch`；范围：`primary`。

旧记录：nominal current of motor — diagnosed_by → motor nameplate

铭牌提供额定电流参数来源；没有实际检测动作，不能发布为 diagnosed_by。作为参数来源辅助事实保留。

待专家核对：可用于判断额定范围的辅助信息，不由此产生故障诊断真值。

原页精确字符区间 [1587, 1870)：
```text
3.4 RATED CURRENT                                                       
          The allowed nominal current of motor for pump configuration is indicated on the motor
          nameplate. This shows the nominal working scope of motor and can be used to protect the
          motor.
```

## R047 / MP015:p0039

历史意见：S → N；v2 技术处理：`qualifiers_required`；范围：`primary`。

旧记录：tolerance ring — maintained_by → apply Loctite 572 on the impeller stop face (0120), the shaft end and the rearmost part of the tolerance ring

原文支持涂 Loctite 572，但限定在叶轮装配、轴承架1、青铜或不锈钢泵，为隔离容差环与液体。原记录省掉限定，需条件化修复。

待专家核对：不迁移到其他材料、其他轴承架或所有泵。

原页精确字符区间 [598, 1063)：
```text
7.6.4 Assembly of the impeller, bearing bracket 1                
                       1 Place the tolerance ring (1880) into the shaft recess of the pump shaft (2200).
                       2 For bronze and stainless steel pumps the tolerance ring must be isolated from the
                         liquid. In order to do this apply Loctite 572 on the impeller stop face (0120), the shaft
                         end and the rearmost part of the tolerance ring
```

## R009 / MP002:p0053

历史意见：U → S；v2 技术处理：`background_and_type_mismatch`；范围：`background`。

旧记录：rotating equipment — inspected_by → vibration taps

vibration taps 是设计中预留的振动测量接口示例，本段没有把接口名称定义成检查动作；一般旋转设备背景不能直接实例化为泵诊断。

待专家核对：不否认该硬件可支持监测；实际方法需另有源文。

原页精确字符区间 [921, 2049)：
```text
v)   Definition of Required Maintenance Tasks. Defining the maintenance tasks for the system
                      during the design phase is beneficial because it helps (1) allocate maintenance resources
                      prior to startup and operation of the process, (2) identify equipment failure modes
                      targeted for maintenance, thus providing the designers with the opportunity to adapt the
                      design (e.g., eliminate the failure mode if possible), (3) identify maintenance technology
                      requirements that need to be incorporated into the design (e.g., vibration taps on rotating
                      equipment), and (4) develop lists of tasks that should be evaluated for maintainability
                      issues. This process should result in a list of applicable and effective planned maintenance
                      tasks for the process. This list is generally developed using reliability analysis tools such
                      as risk derived maintenance, reliability-centered maintenance (RCM), or risk-based
                      inspection.
```

## R004 / MP001:p0112

历史意见：S → N；v2 技术处理：`outside_primary_scope`；范围：`out_of_scope`。

旧记录：unexpected events occurring instantaneously or in a short time period resulting in a total loss of system function — inspected_by → transient analyses

瞬态分析与突发失效事件的关系有明确原文；本段处在发动机/系统监测语境，未说明泵应用。不能据此判为凭空捏造，也不能计入泵主任务覆盖。

待专家核对：可另行保留一般分析知识，泵应用映射未证实。

原页精确字符区间 [4322, 4870)：
```text
At times, transient analyses are performed for unexpected events occurring instantaneously or in a short
            time period resulting in a total loss of system function. The sensors and monitoring equipment selected
            must be suitable to measure any transients and record the data for analysis after the event. Potential causes
            of these events are inadequately designed components or sub-systems, unknown component failure, faulty
            logic in the control system, or operation outside of predetermined parameters.
```

## R037 / MP007:p0015

历史意见：N → S；v2 技术处理：`polarity_mismatch`；范围：`primary`。

旧记录：The motor without a nozzle — maintained_by → requires no maintenance

原文明确为无喷嘴电机无需维护。原 maintained_by 正向维护关系误表极性；保留负向维护要求，不生成维护动作。

待专家核对：nozzle 原文原样保留，不自行修正译名。

原页精确字符区间 [2460, 2921)：
```text
Motor bearing                                                           
          The motor without a nozzle requires no maintenance. The motor with a nozzle (including
          motor above 11kW) shall be lubricated with lubricant or similar high-temperature lithium base
          grease. For more details, refer to instructions on the windscreen. In case of seasonal
          running (motor shutdown for over 6 months), lubricate before starting the motor.
```

## R014 / MP003:p0313

历史意见：S → U；v2 技术处理：`outside_primary_scope`；范围：`out_of_scope`。

旧记录：sag and gap — diagnosed_by → verified at all open flanges

原文有挠度/间隙检查，但属于推进轴系，并且包含临时支撑、同时检查、停坞/下水条件和容差。排除于泵主任务，不宣称原文虚假。

待专家核对：原文 +0.1 mm 按原样留存，不自行改成 ±0.1 mm。

原页精确字符区间 [1509, 2147)：
```text
11.1.2(d) Sag and Gap Verification                               
                                                                                  
                 i)   The sag and gap is to be measured at the drydock or after launching condition, unless
                      agreed to otherwise by ABS.                                 
                 ii)  With assistance of the temporary supports the sag and gap needs to be simultaneously
                      verified at all open flanges until sag and gap values are brought within acceptable
                      tolerances of +0.1 mm from the corresponding calculated values.
```

## R039 / MP007:p0012

历史意见：S → N；v2 技术处理：`qualifiers_required`；范围：`primary`。

旧记录：valves on inlet pipes — inspected_by → If valves on inlet pipes are completely opened or not

启动前检查标题赋予后续项目检查动作语义。If ... or not 是“是否”的嵌入问句，不是条件前提；规范为“启动前检查进口阀是否全开”。

待专家核对：旧关键词筛查可能误报，尚未据此统计总体误拒率或修改旧规则。

原页精确字符区间 [2691, 3412)：
```text
7.2 CHECK BEFORE PUMP STARTUP                                           
          •  Check if foot bolts are tightened.                                   
          •  If the pump is full of water or not.                                 
          •  If the voltage of power grid is correct or not.                      
          •  If the rotating direction is correct or not.                         
          •  If all pipes are tightly connected or not, if pipes can              
          •  provide water normally or not.                                       
          •  If valves on inlet pipes are completely opened or not. The outlet valve shall be opened
             slowly after the pump is started up.
```

## R063 / MP018:p0026

历史意见：S → U；v2 技术处理：`qualifiers_required`；范围：`primary`。

旧记录：Misalignment of the shaft — causes → Broken Separator (cage)

同一行明确把轴不对中列为保持架破裂的可能原因；需保存 PROBABLE CAUSE 表头与轴承/泵型范围。既不能升级为必然原因，也不能从表头缺失的短引用断定没有因果支持。

待专家核对：需要同时复核表头和行；不能只靠端点共现。

原生表头与同行单元：

- `MP018:p0026:t00:r000:c00`：DEFECT (Failure)
- `MP018:p0026:t00:r000:c01`：APPEARANCE
- `MP018:p0026:t00:r000:c02`：PROBABLE CAUSE
- `MP018:p0026:t00:r003:c00`：Broken Separator (cage)
- `MP018:p0026:t00:r003:c01`：Cracked separator or separator in pieces.
- `MP018:p0026:t00:r003:c02`：1. Poor lubrication. / 2. Misalignment of the shaft. / 3. Excessive shaft deflection.

## R015 / MP003:p0943

历史意见：S → U；v2 技术处理：`qualifiers_required`；范围：`primary`。

旧记录：possible flooding — inspected_by → high-level bilge alarm

高位舱底报警检测可能进水有原文支持，且直接关联消防泵/海底门舱保护，应按 v2 的直接关联保护范围保留；不是把所有消防系统知识纳入。必须保留消防泵在机舱外及舱室配置条件。

待专家核对：区分同舱且海底门阀锁开、不同舱两种配置，不泛化为全船通用报警规则。

原页精确字符区间 [4576, 5726)：
```text
ix)  Starting of a fire pump located outside of the propulsion machinery space, including operation of
                 all necessary valves, to pressurize the fire main. However, valves located near the pump need not
                 be provided with remote operation from the firefighting station, if they are kept locked open (LO),
                 or closed (LC), as appropriate, to provide immediate water supply to the fire main. The position of
                 the valves (open or closed) is to be clearly marked. Where the sea chest valve is located in the
                 same compartment as the fire pump and the sea chest valve is kept locked open, a high-level bilge
                 alarm is to be fitted in the fire pump space. If the sea chest is located in a different space than the
                 compartment containing the fire pump, then a high-level bilge alarm is to be fitted in the fire pump
                 space, as well as the compartment containing the sea chest, in order to detect possible flooding in
                 each of these spaces. The high-level bilge alarm is to sound in the centralized control station.
```

## R033 / MP006:p0004

历史意见：S → N；v2 技术处理：`granularity_repair`；范围：`primary`。

旧记录：abnormal noises or vibrations — diagnosed_by → Check that the pump rotates in the correct direction and has no abnormal noises or vibrations

启动检查确实要求确认旋转方向及无异常声振；这是检查动作，不足以推断唯一故障原因。原尾实体合并两个目标，拆为泵旋向检查及异常声振检查，保留启动阶段。

待专家核对：不把检查是否有异常声振误说成诊断异常的原因；不是无源文支持。

原页精确字符区间 [3897, 4815)：
```text
Before startup                                                               
                                                                                  
                                                                                  
     1. Check that the pump can rotate by turning it by hand                      
     2. Check alignment of pipe system                                            
     3. Check bearings are lubricated before startup or no later than immediately afterwards
     4. Check that the pump is filled with the correct medium and bled            
                                                                                  
     5. Check that the pump rotates in the correct direction and has no abnormal noises or vibrations
     6. Check differential pressure (discharge pressure - suction pressure) and compare with calculated operating point for
       the installation
```
