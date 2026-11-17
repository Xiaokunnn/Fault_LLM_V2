# 排名与文档核验失败案例


固定模型由验证集选择；以下按已冻结排序规则挑出4个大排名失败及4个rank1恢复。选择案例不会改变训练。排名失败不等于预测事实为假。


## 1. high_rank_failure / EXC-30d926e6812c0db1866a7b56

目标：将无支撑泵悬挂在管路上 → causes → 加速磨损。任务head，rank=1626.0，端点both_cold。首选实体：磨合过程（OperatingCondition）。

源文：MP020物理页7，hang an unsupported pump on piping → causes → accelerated wear。证据：Do not hang an unsupported pump on                     
                             piping. This is a source of bearing problems,          
                             accelerated wear, motor overloads, and leaks.。范围：非船舶专用;仅迁移通用离心泵组机理并保留Cornell泵适用范围。

## 2. high_rank_failure / EXC-78f4a6fdefbbfd8f55ee507b

目标：将无支撑泵悬挂在管路上 → causes → 轴承故障。任务head，rank=1518.0，端点both_cold。首选实体：轴封泄漏液或蒸汽被迫进入轴承单元（FailureMechanism）。

源文：MP020物理页7，hang an unsupported pump on piping → causes → bearing problems。证据：Do not hang an unsupported pump on                     
                             piping. This is a source of bearing problems,          
                             accelerated wear, motor overloads, and leaks.。范围：非船舶专用;仅迁移通用离心泵组机理并保留Cornell泵适用范围。

## 3. high_rank_failure / EXC-089d8313656453b9544f420c

目标：将无支撑泵悬挂在管路上 → causes → 电机过载。任务head，rank=1382.0，端点one_cold。首选实体：电机缺相运行（Cause）。

源文：MP020物理页7，hang an unsupported pump on piping → causes → motor overloads。证据：Do not hang an unsupported pump on                     
                             piping. This is a source of bearing problems,          
                             accelerated wear, motor overloads, and leaks.。范围：非船舶专用;仅迁移通用离心泵组机理并保留Cornell泵适用范围。

## 4. high_rank_failure / EXC-e0216a990fb426ee14a9b810

目标：自动控制装置 → inspected_by → 航行或靠泊测试。任务head，rank=1214.0，端点both_cold。首选实体：舱底水系统（Equipment）。

源文：MP003物理页14，automatic controls → inspected_by → tested underway or alongside the pier。证据：All automatic controls, including tripping of all safety protective devices that
            affect the vessel's propulsion system, are to be tested underway or alongside the pier, to the satisfaction of
            the Surveyor。范围：仅保留泵管系及其报警保护章节的原文证据。

## 5. rank1_recovery / EXC-0bd8e0338fb2e41caf3f31df

目标：机械密封静环 → maintained_by → 将机械密封静环垂直压入密封腔。任务head，rank=1.0，端点one_cold。首选实体：机械密封静环（Component）。

源文：MP015物理页42，counter ring of the mechanical seal → maintained_by → press the counter ring of the mechanical seal straight into it。证据：press the counter ring of the mechanical
                         seal straight into it。范围：通用泵厂商资料;用于补充可迁移泵机理但不得自动声称船舶现场特异性。

## 6. rank1_recovery / EXC-0bd8e0338fb2e41caf3f31df

目标：机械密封静环 → maintained_by → 将机械密封静环垂直压入密封腔。任务tail，rank=1.0，端点one_cold。首选实体：将机械密封静环垂直压入密封腔（MaintenanceAction）。

源文：MP015物理页42，counter ring of the mechanical seal → maintained_by → press the counter ring of the mechanical seal straight into it。证据：press the counter ring of the mechanical
                         seal straight into it。范围：通用泵厂商资料;用于补充可迁移泵机理但不得自动声称船舶现场特异性。

## 7. rank1_recovery / EXC-0cc20aa47fb8398088ebbac4

目标：泵 → inspected_by → 检查泵内介质充注及排气。任务head，rank=1.0，端点one_cold。首选实体：泵（Equipment）。

源文：MP006物理页4，pump → inspected_by → Check that the pump is filled with the correct medium and bled。证据：4. Check that the pump is filled with the correct medium and bled。范围：安装机理可用于相同结构泵组;不得扩展为所有泵型的故障事实。

## 8. rank1_recovery / EXC-0cc20aa47fb8398088ebbac4

目标：泵 → inspected_by → 检查泵内介质充注及排气。任务tail，rank=1.0，端点one_cold。首选实体：检查泵内介质充注及排气（InspectionAction）。

源文：MP006物理页4，pump → inspected_by → Check that the pump is filled with the correct medium and bled。证据：4. Check that the pump is filled with the correct medium and bled。范围：安装机理可用于相同结构泵组;不得扩展为所有泵型的故障事实。

## 文档核验揭示的具体机制问题

R09：MP022 p14的接液盘是泄漏后的收集措施，prevented_by错误改变了作用时点。R23：p35的O-ring(44)与(15)编号不同，模型按“同类密封+装配”相近语义错配。R06把安装位置短轴误当被维护对象。R08把收集泄漏液等同缓解泄漏本体，当前证据不足。

R07和R19则显示有源文支持的动作仍须保留清洗步骤/型号或维护矩阵周期。R10—R13无检索支持，只能U，不能当错误事实。R22/R24有局部原子支持，但均为基础图已知知识；不算新发现。

24例是定向诊断，不能外推26,328条预测的准确率。完整记录与证据见 ../discovery/SOURCE_REVIEW.md。
