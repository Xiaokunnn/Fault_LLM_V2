# 真实排名收益与失败案例


固定第一种子，按记录ID选每类最多3例，不改变模型或分母。源文属于自动目标的出处，不自动证明所有替代预测为假。


## cold / recovery / EXC-6ad5fe6000aabc342ca27510 / head

目标：电机可能缺相 → causes → 电机运行过热。G2 rank=2.0，full rank=1.0。G2首选：输送介质含气量过高；full首选：电机可能缺相（Cause）。

原文：MP019物理页20，Motor overheats while
running
--- CELL ---
Motor may have one phase open。适用范围：只用于泵驱动电机可迁移的电气故障与检查维护证据;不得把其他语言重复页计为独立证据。

## cold / negative_transfer / EXC-9566c667e1cf2c8ab6cb67a9 / tail

目标：异常噪声 → diagnosed_by → 注意监听异常噪声。G2 rank=1.0，full rank=2.0。G2首选：注意监听异常噪声；full首选：听诊异常声音（InspectionAction）。

原文：MP016物理页47，Preste atención para detectar ruidos inesperados.。适用范围：仅适用于船用发动机冷却柔性叶轮泵;不得把柔性叶轮机理无条件推广到离心泵。

原文：MP016物理页47，Preste atención para detectar ruidos inusuales。适用范围：仅适用于船用发动机冷却柔性叶轮泵;不得把柔性叶轮机理无条件推广到离心泵。

## cold / negative_transfer / EXC-cae4cafb452459656376a312 / tail

目标：机械密封 → inspected_by → 观察机械密封以确认泄漏是否停止。G2 rank=1.0，full rank=3.0。G2首选：观察机械密封以确认泄漏是否停止；full首选：必要时更换机械密封（MaintenanceAction）。

原文：MP005物理页65，Observe the mechanical seal to see if
        leakage stops, if not it could be enough to dismantle the mechanical seal and clean it properly
        to stop the leakage.。适用范围：优先适用于手册列明的NSL船用离心泵应用。

## cold / schema_violation / EXC-0cc20aa47fb8398088ebbac4 / tail

目标：泵 → inspected_by → 检查泵内介质充注及排气。G2 rank=3.0，full rank=3.0。G2首选：泵机组安装后重新检查对中；full首选：泵机组安装后重新检查对中（MaintenanceAction）。

原文：MP006物理页4，4. Check that the pump is filled with the correct medium and bled。适用范围：安装机理可用于相同结构泵组;不得扩展为所有泵型的故障事实。

## cold / schema_violation / EXC-1106898b754659f14bee10aa / head

目标：阀门 → inspected_by → 设置指示器以显示阀门开启或关闭状态。G2 rank=11.5，full rank=11.5。G2首选：设置指示器以显示阀门开启或关闭状态；full首选：设置指示器以显示阀门开启或关闭状态（InspectionMethod）。

原文：MP003物理页525，Indicators are to be
                 provided to show whether the valves are open or closed.。适用范围：仅保留泵管系及其报警保护章节的原文证据。

## cold / schema_violation / EXC-242444f33d1bd811374175ea / head

目标：燃油及润滑油泵与分离器 → maintained_by → 远程停止装置。G2 rank=11.0，full rank=11.0。G2首选：自动停机；full首选：自动停机（MaintenanceAction）。

原文：MP003物理页769，Fuel oil transfer pumps, fuel oil unit pumps and other similar fuel pumps, lubricating oil service
                 pumps, thermal oil circulating pumps and oil separators (purifiers, but not including oily water
                 separators) are to be fitted with remote means of stopping.。适用范围：仅保留泵管系及其报警保护章节的原文证据。

## structured / schema_violation / EXC-03e3884823f1523525289e58 / tail

目标：半导体组件 → inspected_by → 冲击电压测试。G2 rank=68.0，full rank=76.0。G2首选：试验组件；full首选：试验组件（Component）。

原文：MP003物理页798，8.7.3 Impulse Voltage Test                                            
                 Semiconductor assemblies shall be subject to an Impulse voltage test to simulate the impact of
                 impulse transient over voltages。适用范围：仅保留泵管系及其报警保护章节的原文证据。

## structured / schema_violation / EXC-2145f2e646cda408d1613cd6 / head

目标：绕组过湿 → mitigated_by → 烘箱干燥。G2 rank=29.0，full rank=4.0。G2首选：烘箱干燥；full首选：烘箱干燥（MaintenanceAction）。

原文：MP019物理页115，käämitys on liian kostea ja se on kuivattava uunissa。适用范围：只用于泵驱动电机可迁移的电气故障与检查维护证据;不得把其他语言重复页计为独立证据。

## structured / schema_violation / EXC-2ddd1f8261322e54d43797c5 / tail

目标：泵 → maintained_by → 每次使用后用水或中和剂冲洗。G2 rank=63.0，full rank=53.0。G2首选：确保泵运行平稳；full首选：确保泵运行平稳（InspectionAction）。

原文：MP016物理页3，Pump life will be prolonged if flushed with
                                water or neutralizing agent after each operation.。适用范围：仅适用于船用发动机冷却柔性叶轮泵;不得把柔性叶轮机理无条件推广到离心泵。
