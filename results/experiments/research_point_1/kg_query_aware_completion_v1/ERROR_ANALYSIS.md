# 补全变化案例与错误边界


以下“成功”仅指自动基础目标的排名，不是事实正确率。只在训练和选择封存后回读目标源文。


## query_full / helped / EXC-00e50723917c907550c727e8 / tail

参考：轴封弹簧 → maintained_by → 确保轴封弹簧端部的环位于叶轮凹槽内。预测Top1：('轴封弹簧', 'maintained_by', '确保轴封弹簧端部的环位于叶轮凹槽内')。rank 3.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP005 p109：NOTE: Take care that the ring at the end of the shaft seal spring locates in the recess of the
                   impeller.

上下文：主体：轴封。关系：维护方式为。客体：定期维护轴封。 来源[['MP005', 66]]。

上下文：主体：轴封。关系：维护方式为。客体：轴调整。 来源[['MP022', 39]]。

上下文：主体：轴封。关系：维护方式为。客体：泵/轴封拆卸。 来源[['MP022', 28]]。

## query_full / helped / EXC-067ca165d23b4412f66b388d / tail

参考：叶轮 → inspected_by → 运行前检查叶轮旋转方向。预测Top1：('叶轮', 'inspected_by', '运行前检查叶轮旋转方向')。rank 2.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP022 p18：Check the direction of rotation of the impeller before operation.

上下文：主体：叶轮。关系：检查方法为。客体：拆卸叶轮进行目视检查和磨损迹象检查。 来源[['MP016', 35]]。

上下文：主体：叶轮。关系：检查方法为。客体：拆卸后盖并吊起转子组件以检查叶轮。 来源[['MP005', 93]]。

上下文：主体：叶轮。关系：检查方法为。客体：拆卸叶轮进行目视检查并确认无磨损迹象。 来源[['MP016', 29]]。

## query_full / helped / EXC-57ec62db52363bdbca9a8e5a / head

参考：轴封 → maintained_by → 将完整的轴封安装到短轴(7)上。预测Top1：('轴封', 'maintained_by', '将完整的轴封安装到短轴(7)上')。rank 2.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP022 p32：Fit the complete shaft seal onto the stub shaft (7)

上下文：主体：装配轴封。关系：逆向关系：维护方式为。客体：轴封。 来源[['MP005', 100]]。

上下文：主体：更换轴封。关系：逆向关系：维护方式为。客体：轴封。 来源[['MP015', 33]]。

上下文：主体：定期维护轴封。关系：逆向关系：维护方式为。客体：轴封。 来源[['MP005', 66]]。

## query_full / helped / EXC-703d874eb417b3ae0f0b8ea0 / tail

参考：绝缘电阻 → diagnosed_by → 绝缘电阻测试。预测Top1：('绝缘电阻', 'diagnosed_by', '绝缘电阻测试')。rank 2.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP003 p798：8.7.4 Insulation Resistance Test                                      
                                                                                  
                 One minute after the insulation test, insulation resistance shall be measured by applying a direct
                 voltage of at least 500 V.

上下文：主体：绝缘电阻。关系：诊断方法为。客体：调试前测量绝缘电阻。 来源[['MP019', 97]]。

上下文：主体：绝缘电阻。关系：诊断方法为。客体：使用500或1000V直流电测量。 来源[['MP019', 97]]。

上下文：主体：绝缘电阻。关系：诊断方法为。客体：绝缘电阻测量。 来源[['MP003', 790]]。

## query_full / hurt / EXC-aad22740ae62293f13360e58 / head

参考：产品泄漏 → diagnosed_by → 目视检查所有密封件及产品泄漏迹象。预测Top1：('泄漏', 'diagnosed_by', '目视检查所有密封件及产品泄漏迹象')。rank 1.0→3.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP016 p16：Contrôles visuels de tous les joints et des signes de fuite du
     produit, du liquide de rinçage (le cas échéant).

上下文：主体：目视检查所有连接处确认无介质泄漏迹象。关系：逆向关系：诊断方法为。客体：介质泄漏。 来源[['MP016', 29]]。

上下文：主体：检查泄漏。关系：逆向关系：诊断方法为。客体：泄漏。 来源[['MP016', 5], ['MP016', 47]]。

上下文：主体：检查是否存在泄漏。关系：逆向关系：诊断方法为。客体：泄漏。 来源[['MP016', 28]]。

## query_full / hurt / EXC-5d4dedaa3dae777042ad4803 / tail

参考：唇形密封 → maintained_by → 将唇形密封安装到轴承座中。预测Top1：('唇形密封', 'maintained_by', '检查唇形密封、轴承、衬套和惰轮销并在必要时更换')。rank 1.0→2.0；预测Schema合法=False。

目标参考来源（未作检索输入）：MP021 p8：Install the lipseal in the bearing housing (See "Figure 9"
                                             on page 8, "Figure 10" on page 8 or "Figure 11"
                                             on page 8 for lip orientation).

上下文：主体：唇形密封。关系：维护方式为。客体：润滑前后唇形密封。 来源[['MP016', 37]]。

上下文：主体：唇形密封。关系：维护方式为。客体：按需更换。 来源[['MP016', 24]]。

上下文：主体：唇形密封。关系：维护方式为。客体：必要时更换。 来源[['MP016', 6]]。

## query_full / hurt / EXC-6394c654ebef23c6d971bb85 / head

参考：转子转动自如 → diagnosed_by → 手动检查转子是否转动自如。预测Top1：('转子', 'diagnosed_by', '手动检查转子是否转动自如')。rank 1.0→2.0；预测Schema合法=False。

目标参考来源（未作检索输入）：MP018 p24：check that
       the rotor turns freely by hand

上下文：主体：手动盘车检查转动顺畅。关系：逆向关系：诊断方法为。客体：转动无卡滞。 来源[['MP019', 61]]。

上下文：主体：检查电机和驱动是否转动自如，检查轴承和润滑。关系：逆向关系：检查方法为。客体：机械故障。 来源[['MP019', 37]]。

上下文：主体：检查是否存在振动。关系：逆向关系：诊断方法为。客体：振动。 来源[['MP016', 29]]。

## query_full / hurt / EXC-9566c667e1cf2c8ab6cb67a9 / tail

参考：异常噪声 → diagnosed_by → 注意监听异常噪声。预测Top1：('异常噪声', 'diagnosed_by', '听诊异常声音')。rank 1.0→2.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP016 p47：Preste atención para detectar ruidos inesperados.

上下文：主体：异常噪声。关系：诊断方法为。客体：听诊。 来源[['MP016', 15]]。

上下文：主体：异常噪声。关系：诊断方法为。客体：每日检查。 来源[['MP005', 69]]。

上下文：主体：异常噪声。关系：诊断方法为。客体：倾听异常噪声。 来源[['MP016', 5]]。

## transport_R3 / helped / EXC-f39a484bd9245d078f57e7f1 / head

参考：机械接头 → inspected_by → 耐火试验。预测Top1：('机械接头', 'inspected_by', '耐火试验')。rank 3.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP003 p520：In order to establish the capability of the mechanical joints
                           to withstand the effects of fire which may be encountered in service, mechanical
                           joints are to be subjected to a fire endurance test.

上下文：主体：耐火试验。关系：逆向关系：检查方法为。客体：抓握式和机械沟槽式接头。 来源[['MP003', 544]]。

上下文：主体：耐火试验。关系：逆向关系：检查方法为。客体：滑套式接头。 来源[['MP003', 544]]。

上下文：主体：耐火试验(4-6-2/5.7.3(c))。关系：逆向关系：检查方法为。客体：软管。 来源[['MP003', 598]]。

## transport_R3 / helped / EXC-067ca165d23b4412f66b388d / tail

参考：叶轮 → inspected_by → 运行前检查叶轮旋转方向。预测Top1：('叶轮', 'inspected_by', '运行前检查叶轮旋转方向')。rank 2.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP022 p18：Check the direction of rotation of the impeller before operation.

上下文：主体：叶轮。关系：检查方法为。客体：拆卸叶轮进行目视检查和磨损迹象检查。 来源[['MP016', 35]]。

上下文：主体：叶轮。关系：检查方法为。客体：拆卸后盖并吊起转子组件以检查叶轮。 来源[['MP005', 93]]。

上下文：主体：叶轮。关系：检查方法为。客体：拆卸叶轮进行目视检查并确认无磨损迹象。 来源[['MP016', 29]]。

## transport_R3 / helped / EXC-a6b9906e9e642fc24411072f / head

参考：轴承 → maintained_by → 使用拉拔器拆卸并加热或使用专用工具安装。预测Top1：('轴承', 'maintained_by', '使用拉拔器拆卸并加热或使用专用工具安装')。rank 2.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP019 p126：Laakerit                          
     on poistettava käyttäen ulosvetäjää ja asennettava                           
     lämmitettyinä tai tarkoitukseen sopivilla erityistyökaluilla.

上下文：主体：使用拉拔器拆卸并通过加热或专用工具安装。关系：逆向关系：维护方式为。客体：轴承。 来源[['MP019', 18]]。

上下文：主体：使用拉拔器拆卸并热装或使用专用工具安装。关系：逆向关系：维护方式为。客体：轴承。 来源[['MP019', 54]]。

上下文：主体：使用拉拔器拆卸并热装或使用合适工具安装。关系：逆向关系：维护方式为。客体：轴承。 来源[['MP019', 90]]。

## transport_R3 / helped / EXC-a7798e93cfc1d0c73fe6b50e / head

参考：驱动对中 → inspected_by → 管路连接后检查驱动对中。预测Top1：('驱动对中', 'inspected_by', '管路连接后检查驱动对中')。rank 2.0→1.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP021 p15：Check the alignment of the drive after the piping is hooked up.

上下文：主体：安装后及启动前检查泵与驱动装置的对中。关系：逆向关系：检查方法为。客体：联轴器对中。 来源[['MP016', 21], ['MP016', 46]]。

上下文：主体：安装后及启动前检查对中。关系：逆向关系：检查方法为。客体：泵对中。 来源[['MP016', 34]]。

上下文：主体：安装后及启动前检查泵与驱动装置对中。关系：逆向关系：检查方法为。客体：泵与驱动装置对中。 来源[['MP016', 27]]。

## transport_R3 / hurt / EXC-aad22740ae62293f13360e58 / head

参考：产品泄漏 → diagnosed_by → 目视检查所有密封件及产品泄漏迹象。预测Top1：('泄漏', 'diagnosed_by', '目视检查所有密封件及产品泄漏迹象')。rank 1.0→3.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP016 p16：Contrôles visuels de tous les joints et des signes de fuite du
     produit, du liquide de rinçage (le cas échéant).

上下文：主体：目视检查所有连接处确认无介质泄漏迹象。关系：逆向关系：诊断方法为。客体：介质泄漏。 来源[['MP016', 29]]。

上下文：主体：检查泄漏。关系：逆向关系：诊断方法为。客体：泄漏。 来源[['MP016', 5], ['MP016', 47]]。

上下文：主体：检查是否存在泄漏。关系：逆向关系：诊断方法为。客体：泄漏。 来源[['MP016', 28]]。

## transport_R3 / hurt / EXC-7af41bad50b0b51d38715365 / head

参考：标准绝缘 → specified_by → 电压峰值1300v。预测Top1：('特殊绝缘', 'specified_by', '电压峰值1300v')。rank 3.0→5.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP019 p29：Standardisolierung Spannungsspitze 1300 V

上下文：主体：电压峰值1800v。关系：逆向关系：由规范规定。客体：专用绝缘。 来源[['MP019', 29]]。

上下文：主体：峰值1800v。关系：逆向关系：由规范规定。客体：特殊绝缘。 来源[['MP019', 83]]。

上下文：主体：压力温度等级≤ASME B16.5 Class 1500且公称尺寸≤65mm或等效国家标准。关系：逆向关系：由规范规定。客体：G型法兰。 来源[['MP003', 536]]。

## transport_R3 / hurt / EXC-b89dabbeda179831ccc111f6 / tail

参考：汽蚀(吸程过高) → causes → 噪声过大。预测Top1：('汽蚀(吸程过高)', 'causes', '汽蚀损坏')。rank 6.0→14.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP020 p26：Cavitation (excessive suction lift)
--- CELL ---
Consult Cornell factory

上下文：主体：吸上高度过高。关系：导致。客体：泵汽蚀。 来源[['MP018', 27]]。

上下文：主体：吸上高度过高。关系：导致。客体：泵内汽蚀。 来源[['MP004', 12]]。

上下文：主体：汽蚀。关系：导致。客体：压力表指针抖动、跳动或读数不稳定。 来源[['MP021', 17]]。

## transport_R3 / hurt / EXC-62cb279ce553aec4f936d41c / head

参考：静电荷 → prevented_by → 使用防静电材料。预测Top1：('静电荷危险积聚', 'prevented_by', '使用防静电材料')。rank 3.0→4.0；预测Schema合法=True。

目标参考来源（未作检索输入）：MP003 p804：Electrostatic charges both in the rotating body and the casing are to be prevented by the use of
                 anti-static materials.

上下文：主体：使用防冷凝加热器。关系：逆向关系：预防措施为。客体：电机内部冷凝水积聚。 来源[['MP019', 114]]。

上下文：主体：使用不燃且最好不吸油材料隔热。关系：逆向关系：预防措施为。客体：燃油着火。 来源[['MP003', 591]]。

上下文：主体：采用不燃且优选不吸油材料隔热。关系：逆向关系：预防措施为。客体：润滑油着火。 来源[['MP003', 601]]。


角色/型号风险见retrieval/role_mismatch_cases.jsonl。不同作用对象、型号、条件的近似文字可能排到前列；Schema合法仍不保证关系正确。发生MRR改善但Top1仍错误者不计新增正确知识。

固定迁移和神经残差均有负向实例，全部保留。候选相关性只有自动合同、原生地址和类型等代理检查；没有开展事实级大模型裁判或专家评价。
