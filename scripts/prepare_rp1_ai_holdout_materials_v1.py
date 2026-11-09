#!/usr/bin/env python3
"""Archive source-first AI reference statements and exact frozen E1 payloads.

Statements are authored Codex annotations, not extraction results. No network,
historical candidate access, method tuning, or human validation occurs here.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path

from prepare_rp1_ai_review_v1 import ROOT, BASE, OLD, OUT, rows, sha, save, now, check, validate_witness
from rp1_offline_contract_v3 import bind
from run_rp1_targeted_v2_1 import payload_bytes, digest


# Per-page statements were written only after source text/native rows were read.
# Visual checks are additional evaluator evidence, never injected into E1 inputs.
NOTES = {
 'MP001:p0078':('background','旋转90度油液监测表；PDF目视可读，冻结解析文本为倒序字符。应用明确为柴油/汽油机油、燃气轮机及其轴承，不能实例化为泵故障；方法描述保留背景。'),
 'MP001:p0115':('background','船舶远程监测架构和统计研究展望；未给出本页泵相关原子故障/检查动作。'),
 'MP002:p0104':('background','一般船机阀门、滤器、储罐和压力容器故障枚举；没有本页泵系连接，不因部件名常见于泵而补造泵实例。'),
 'MP002:p0042':('background','向验船师报告维护缺项/振动高于基线的管理要求；本页没有明确泵对象，不能当泵诊断结论。'),
 'MP003:p0266':('out_of_scope','推进齿轮材料强度与ISO引用，不是泵管系及报警保护章节。'),
 'MP003:p0420':('out_of_scope','锅炉蒸汽/给水阀设计；仅有锅炉端约束，缺少泵应用连接，不扩大冻结适用范围。'),
 'MP004:p0030':('noncore_structure','SA-80-220/17零件清单；可保留部件和数量，但不能凭零件名生成故障/维修动作。'),
 'MP004:p0027':('noncore_visual','原PDF为SA-80-160/17爆炸图，解析只留下页脚。目视核实非空白；结构/跨页部件名称无法仅本页完整确定，不伪造维修顺序。'),
 'MP005:p0091':('core','拆卸步骤3–5；保留NSL范围、步骤和前序依赖，步骤1–2未在本页展示，不能将本页当完整维修程序。'),
 'MP005:p0124':('noncore_visual','NSL-330/415/465-02装配图已目视；编号和结构图不等于文字维修步骤，跨页零件映射不猜测。'),
 'MP006:p0007':('core','DESMI泵/电机振动范围、危害及推荐保护值；损伤陈述计核心，报警/跳闸阈值另存配置，不当作故障真值或建议改变。ISO图区域只保留图示，未猜每个组边界。'),
 'MP006:p0006':('core','法兰支撑安装过程，检查/明确调整计核心；紧固装配的通用安装操作单列。反复检查必须保留步骤位置及冷热条件。'),
 'MP007:p0029':('noncore_structure','MVA/MVS10/15/20零件清单；只支持结构和名称，不提供故障/维护动作。'),
 'MP007:p0003':('empty_core','目录末页，只有爆炸图页码，不从章节名制造具体动作。'),
 'MP015:p0086':('noncore_visual','FRE80-210/100-250剖视图已目视；本页无故障或检查/维修动作，部件号不跨页补名。'),
 'MP015:p0008':('empty_core','目录；维修/检查章节标题不是本页具体原子动作。'),
 'MP016:p0042':('core','瑞典语柔性叶轮泵拆卸/清洁说明，重复叶轮检查去重；整体断电、泄压、排液与隔离前提必须保留。末尾壳体步骤跨页，不能说完整。'),
 'MP016:p0003':('core','柔性叶轮泵限制、收货检查及安装；泵型不可推广到离心泵。禁用介质与Nitrile/Viton例外存在上下文边界，辅助说明/未决单列。'),
 'MP017:p0002':('empty_core','引言、手册分工与目录；一般阅读/遵循标准要求保留辅助，不虚构维修步骤。双栏解析有穿插。'),
 'MP018:p0016':('core','轴承再润滑表已经PDF目视核对合并单元；12种工况保留完整行限定，表内空白不是继承前一工况。间隔是维护计划起点，须按润滑脂和温度调整。'),
 'MP018:p0006':('core','储存后轴承润滑和泵组安装；安装/吊装操作和防启动隔离要求另存上下文。基础灌浆间隙的分数字符已损坏，不恢复成猜测值。'),
 'MP019:p0048':('core','法语ABB低压电机说明；仅作可迁移泵驱动电机知识，保留变频器型号、功率/机座阈值及相应例外，不当成新独立设备案例。'),
 'MP019:p0022':('empty_core','德语目录，无本页具体维护/故障断言；不将多语重复章节视为独立证据。'),
 'MP020:p0015':('core','直尺/卡钳对中图已目视，替代条件为不使用双表或激光；不从图示臆造公差数值，启动前装回护罩单列维护要求。'),
 'MP020:p0002':('background','ISO9001认证和版权页；不证明泵故障机理或诊断准确率。'),
 'MP021:p0020':('core','Viking润滑、减速器保养及保修；不同泵/密封/减速器范围分别保留，保修正文不算核心。预启动加油单列运行准备。'),
 'MP021:p0015':('core','回转容积泵吸入/排出管路及对中；双栏第11点续句需按段落复原理解，保留不等同于离心泵的范围。图仅佐证文本。'),
 'MP022:p0044':('noncore_measurement','噪声规格表及BEP/水温/50Hz/原电机护罩条件；不是故障征兆阈值。系统噪声背景另列，不转换成故障诊断。'),
 'MP022:p0052':('empty_core','联系方式与版权，不包含核心目标知识。'),
}

# relation | complete source-relative statement in Chinese | source anchor
SPECS = {
 'MP005:p0091': [
 ('maintained_by','NSL泵组拆卸第3步：松开尖头螺钉73；保留前序拆卸依赖。','Loosen the pointed screw (73)'),
 ('maintained_by','NSL泵组拆卸第3步：松开73后将泵侧联轴器70从轴上拉出。','pull the coupling part pump (70) off the shaft.'),
 ('maintained_by','NSL泵组拆卸第4步：拆下管58，按本段程序顺序。','Dismantle the pipe (58).'),
 ('maintained_by','NSL泵组拆卸第5步：拆下将后盖20固定到泵壳的内六角螺钉22。','Remove Allen screws (22)'),
 ('maintained_by','上述第5步拆下固定螺钉后，使用尖头螺钉86将后盖从泵壳移开。','by means of the pointed screws (86).'),
 ('maintained_by','拆下后盖后，可将轴承座、轴和叶轮作为一个总成从NSL泵中吊出。','The bearing housing with shaft and impeller can now be lifted up from the pump as a unit'),
 ('inspected_by','完成上述拆卸后可检查叶轮；本页没有具体缺陷/容差判据。','the impeller can be inspected.'),
 ],
 'MP006:p0007': [
 ('causes','DESMI泵组语境：高于7 mm/s的振动可缩短泵轴承通常预期寿命；不能当单一诊断阈值。','vibration levels above 7 mm/s are damaging'),
 ('causes','同一高于7 mm/s振动损伤陈述包括泵轴封寿命缩短。','shaft seals in pumps'),
 ('causes','同一高于7 mm/s振动损伤陈述包括电机轴承寿命缩短。','bearings in motors'),
 ('causes','船上主机和/或辅机激振经船体传到泵，经常导致远高于7 mm/s的振速；不是每台泵必然如此。','external excited vibrations from main engine and/or auxiliary machinery'),
 ],
 'MP006:p0006': [
 ('inspected_by','法兰支撑泵安装第1步：固定到底座后检查泵水平。','check that the pump is level.'),
 ('inspected_by','第2步：手动检查泵轴自由旋转、无噪声和异常阻力。','by hand without noise and abnormal resistance.'),
 ('inspected_by','第3步放置法兰支撑后检查螺栓孔对齐。','check that the bolt holes are aligned'),
 ('inspected_by','第3步放置法兰支撑后检查密封垫表面平行。','the gasket surfaces are parallel.'),
 ('maintained_by','底层结构不平时，可能需在泵底板或法兰支撑下加垫；第4步条件性调整，不无条件添加。','it may be necessary to shim'),
 ('inspected_by','第6步检查法兰支撑与底面完全接触。','full contact with the underlying structure'),
 ('maintained_by','第6步支撑脚下空气间隙超过0.5 mm时必须加垫。','if there is more than a 0.5 mm air gap under the feet'),
 ('inspected_by','第8步安装管路法兰后，第9步再检查孔对齐及垫片面平行；与第3步为不同阶段。','9. Check that the bolt holes are aligned'),
 ('inspected_by','第10步紧固管路后，第11步检查轴仍自由转动，声响/阻力与第2步相比不变。','sound and resistance must not have changed according to point 2'),
 ('inspected_by','投运后管温明显升降且热应力/位移可传泵时，第12步在实际温度上下限再次检查轴自由转动。','actual upper/lower temperature limits.'),
 ('maintained_by','所有运行条件下不能自由转动时，第13步改善管路支撑，或在泵与管路之间安装补偿器；两种为替代方案。','If the pump cannot rotate freely under all operating conditions'),
 ],
 'MP016:p0042': [
 ('inspected_by','柔性叶轮泵每日目视检查及按计划间隔检查；本页开头承接前页，不补造前页检查内容。','visuell inspektion dagligen'),
 ('maintained_by','清洁柔性叶轮泵时，应拆卸后作为全系统清洁的一部分手工清洁液体接触面。','rengöring som en del av proceduren'),
 ('causes','碘基或磷基清洁剂会侵蚀该泵并降低性能；禁止使用的要求同时保留为辅助。','jod- eller fosforbaserade rengöringsmedel'),
 ('inspected_by','建议定期检查泵头部件尤其密封和接合处，以便投入使用前清洁或更换；正常运行无需调整不变成正维护。','huvu-dets komponenter'),
 ('maintained_by','维修/检查前须切断泵和驱动电机电源、泄压、排液并隔离管路；是后续全部步骤前提。','Innan reparation eller inspektion påbörjas'),
 ('maintained_by','5.01端盖拆卸：泵/驱动已隔离、冷却至可触碰、液体排净且密封冲洗系统隔离泄压；先松开全部端盖螺栓，卡住时用软锤轻敲侧面，不撬起。','Lossa alla bultar som håller ändlocket mot kroppen.'),
 ('maintained_by','5.01端盖松开后，在支撑重端盖的同时完全拆除螺栓，防止失去支撑。','samtidigt som ändskyddet stöds.'),
 ('maintained_by','5.01拆下端盖置于一旁，必要时清洁；继承断电隔离等前提。','rengör vid behov.'),
 ('inspected_by','5.01取出O形圈并检查磨损；继承端盖拆卸和隔离条件。','Ta bort o-ringen, kontrollera för slitage'),
 ('maintained_by','5.01 O形圈按检查需要更换，不能无条件更换。','byt ut vid behov.'),
 ('maintained_by','5.02使用尺寸合适的Jabsco叶轮拆卸工具移除叶轮；或拆泵体并按相应版本操作，不无条件合并两方案。','Ta bort pumphjulet med rätt storlek'),
 ('maintained_by','5.02叶轮沿泵体轴线拉出，沿泵旋转方向转动可帮助拆卸；注意勿损泵体。','Impellern ska dras längs pumpkroppens axel.'),
 ('inspected_by','5.02检查叶轮磨损或损坏；同页重复句只计一次。','Kontrollera impellern för tecken på slitage eller skador'),
 ('maintained_by','5.02叶轮有磨损/损坏且需要时更换，非所有叶轮必换。','Kontrollera impellern för tecken på slitage eller skador'),
 ('maintained_by','5.03非整体凸轮泵松开泵外凸轮螺钉；继承拆卸前隔离条件。','För pumpar utan integrerad kam'),
 ('maintained_by','5.03凸轮/泵体间可能有密封剂，小心取凸轮并确保凸轮销留在泵体中。','se till att kamstiftet finns i kroppen.'),
 ('maintained_by','5.04凸轮移除后，将耐磨板从轴上滑出；其可能含静密封面或抛光密封面，须谨慎。','Med kammen borttagen, skjut av slitplattan från axeln.'),
 ('inspected_by','5.04检查耐磨板磨损或损坏，保留密封面的注意事项。','Kontrollera slitageplåten för slitage eller skador.'),
 ('maintained_by','5.05单机械密封动面：耐磨板拆下后，取密封挡圈，再将动密封面从轴滑出。','Ta bort tätningshållarringen.'),
 ('inspected_by','5.05单机械密封动面相关部件检查磨损。','Inspektera komponenterna för slitage'),
 ('maintained_by','5.05动面相关部件检查后按需要更换，继承隔离及拆卸顺序。','Inspektera komponenterna för slitage och byt ut dem vid behov.'),
 ('maintained_by','5.05静密封面可小心从泵体凹槽取出；难以取出时按后续拆泵体程序从背面推出，不称本页已有完整后续程序。','Tätningar kan försiktigt dras ut ur kroppens urtag.'),
 ('inspected_by','5.05静密封检查磨损。','tätningen med avseende på slitage'),
 ('maintained_by','5.05静密封按磨损检查需要更换。','tätningen med avseende på slitage och byt ut vid behov.'),
 ('maintained_by','5.05唇形密封使用密封拉拔器或合适钳子取出。','Läpptätningarna kan dras ut'),
 ('inspected_by','5.05检查唇形密封有无损坏。','Kontrollera om läpptätningarna är skadade'),
 ('maintained_by','5.05唇形密封有需要时更换，依赖损坏检查。','Kontrollera om läpptätningarna är skadade'),
 ('maintained_by','5.06螺栓固定版本：松开泵体到底座或适配器的全部螺栓，检查活动；卡住时用软锤轻敲侧面，不撬起。','Lossa alla bultar som håller kroppen på piedestal eller adapter.'),
 ('maintained_by','5.06泵体松开后，支撑泵体同时取下螺栓和垫圈；后续跨页，不称完整拆卸。','När kroppen är lös, ta bort bultar och brickor'),
 ],
 'MP016:p0003': [
 ('causes','柔性叶轮泵超过数据表最大压差运行，即使数秒也会损坏叶轮；最大值本页未给出。','as damage to the Impeller will result.'),
 ('causes','入口压力不足会使柔性叶轮泵汽蚀；高温和高转速需要更高入口压力。','Insufficient inlet pressure will cause the pump to cavitate'),
 ('causes','此入口压力不足导致的汽蚀会造成低性能。','leading to low performance'),
 ('causes','同一汽蚀链条会产生噪声。','low performance, noise and short pump life.'),
 ('causes','同一汽蚀链条会缩短泵寿命。','short pump life.'),
 ('inspected_by','收货时检查泵有无运输物理损坏，发现损失/损坏立即通知承运人和供应商。','Check the pump for any physical damage sustained in'),
 ('inspected_by','收货时确认接口朝向与所需工况连接相适合，不从图推虚构接口型号。','Ensure ports are oriented to give the correct orientation'),
 ('maintained_by','每次操作后用水或中和剂冲洗可延长泵寿命；保留适用介质/材料的咨询限制。','Pump life will be prolonged if flushed with water or neutralizing agent after each operation.'),
 ('increases_risk_of','使用任何Jabsco泵输送汽油、石油产品或闪点低于37°C(98°F)的产品可能爆炸；邻近Nitrile/Viton用途说明不能自动取消该禁止语句。','explosion or death'),
 ],
 'MP018:p0006': [
 ('maintained_by','从储存状态取出设备或首次启动时，必须给轴承施加新鲜润滑剂；限定本泵组。','Fresh lubricant must be applied to bearings'),
 ],
 'MP019:p0048': [
 ('prevented_by','ABB ACS800/ACS550二极管供电变频器：Pn≥100 kW或IEC315–355时，表列非驱动端绝缘轴承用于防止有害轴承电流；不声称仅该措施在更高等级已充分。','Roulement isolé côté non-entraînement'),
 ('prevented_by','同型号变频器：Pn≥350 kW或IEC400–450时，非驱动端绝缘轴承与变频器共模滤波器必须组合。','Filtre en mode commun au niveau du convertisseur'),
 ('maintained_by','为防轴承电流，推荐内/外圈氧化铝涂层或陶瓷滚动体的绝缘轴承；具体类型以电机铭牌为准，不未经ABB同意改变绝缘方法。','éléments de roulement en céramique.'),
 ('inspected_by','IEC机座≥280且电机与被驱动设备共用钢底座时，验证底座连接的高频导电性，例如测组件间电位差；不能当成所有机座的同一条件。','en mesurant la différence de potentiel entre'),
 ('inspected_by','超过铭牌/目录额定转速运行时，检查不超过最高允许转速及整个应用的临界转速。','Pour les vitesses supérieures à la vitesse nominale'),
 ('causes','变频应用负载曲线基于额定供电电压；欠压/过压可能影响应用性能，不推出具体唯一故障。','sous-tension ou de surtension'),
 ],
 'MP020:p0015': [
 ('inspected_by','Cornell泵驱动联轴器可按图用直尺检查对中；仅建议在未用双表或激光时采用，本页无数值公差。','STRAIGHT EDGE'),
 ('inspected_by','同一对中图用卡钳检查两联轴器面间距/对中状态，保留替代方法条件，不推出数值公差。','CALIPER'),
 ('maintained_by','联轴器对中检查后、启动前重新安装联轴器护罩。','Reinstall coupling guard before start-up.'),
 ],
 'MP021:p0020': [
 ('maintained_by','Viking抗摩擦轴承用NLGI2优质多用途聚脲润滑脂；每500运行小时或六个月取先到者，恶劣工况更频繁，与原脂兼容。','anti-friction bearings'),
 ('maintained_by','同一表Viking滑动轴承用上述聚脲脂及同一润滑周期/兼容性条件。','sleeve bearings'),
 ('maintained_by','同一表Viking灯笼环用上述聚脲脂及同一润滑周期/兼容性条件。','lantern rings'),
 ('maintained_by','密封位于转子后时，Viking支架衬套用Petrolatum，需与介质/原脂兼容；继承500h或6个月先到及恶劣工况频率。','when seal is behind rotor'),
 ('maintained_by','Viking O-Pro密封用铝复合食用脂(Chevron FM ALC EP0/1/2)；与介质/原脂兼容，同一周期条件。','O-Pro™ Seal'),
 ('maintained_by','Series4924A氨泵油槽运行首200h后放油重注，此后每1000h；保留轻质制冷油、Neoprene相容性及原文黏度限定，不套到本手册全部型号。','after the first 200 hours of operation'),
 ('maintained_by','Viking A/B/C减速器首次运行100h后排放并更换润滑剂；按温度选SAE30(32°F以上)或SAE10W(32°F以下)，本页未指定恰好32°F。','After first 100 hours of operation'),
 ('inspected_by','上述减速器每2000h或每6个月检查润滑剂液位；原文or不额外推定先到规则。','Check lubricant level every 2000 hours or every six months.'),
 ('maintained_by','上述减速器每年放油重注，保留型号及温度油种条件。','Once each year, drain and refill.'),
 ],
 'MP021:p0015': [
 ('inspected_by','Viking泵管路接入前检查管内清洁。','Be sure the inside of the pipe is clean'),
 ('causes','吸入或排出管线从障碍物上方绕行会形成气袋；水平绕行是原文建议。','it creates an air pocket.'),
 ('causes','吸入管气袋使泵难以灌注。','make it hard for the pump to prime.'),
 ('prevented_by','对于可行的布管位置，通过管路坡度避免气袋/液袋；不能一概指定未给出的坡度值。','slope the piping so no air or liquid'),
 ('prevented_by','热/冷介质与环境温度不同的系统，为管路膨胀收缩留余量(环路、膨胀节或未固定但有支撑的管段)，避免泵壳变形。','casing is not distorted.'),
 ('causes','无吸入滤器时，外来物可能卡住该容积泵。','Without a strainer objects can lock the pump'),
 ('causes','无吸入滤器时，外来物可能损坏泵内部件。','damage the internals and drive.'),
 ('causes','无吸入滤器时，外来物可能损坏驱动。','damage the internals and drive.'),
 ('prevented_by','建议在容积泵吸入侧考虑滤器以拦截外来物；网孔需兼顾压降和保护，尺寸不确定时提供管径/流量/黏度向厂商咨询。','The strainer will keep foreign objects from going into the pump.'),
 ('maintained_by','滤器应有清洗条件；连续运行时用旁通或双滤器并联配适当阀门，使滤器能隔离清洗。','so they can be isolated for cleaning.'),
 ('causes','将管路强行拉至泵连接会引起泵变形；原文第11点续句跨栏，仍是同一段。','cause distortion, possible misalignment, and probable rapid wear of the pump.'),
 ('causes','同一强拉管路条件可能引起不对中。','possible misalignment'),
 ('causes','同一强拉管路条件可能导致泵快速磨损，保留probable。','probable rapid wear of the pump.'),
 ('causes','吸入管泄漏使空气进入时，可能造成泵噪声。','cause a noisy pump or a reduction in capacity.'),
 ('causes','同一吸入漏气条件可能降低流量/输送能力。','cause a noisy pump or a reduction in capacity.'),
 ('causes','在NPT口使用PTFE带作密封可能造成泵开裂，保留原文不推荐而非必然损坏。','This action can result in cracks in the pump.'),
 ('inspected_by','管路连接完成后检查驱动对中。','Check the alignment of the drive after the'),
 ('inspected_by','最终对中检查拆泵头，用塞尺确认转子与壳体周向均有间隙；制造公差可使转子不居中但不能摩擦，Q/M/N尺寸特别建议，非完整拆卸程序。','determine if there is clearance all the way around'),
 ('indicates','上述检查中转子拖擦提示机组不对中或管路应力引起壳体变形；保留两个替代解释，不能当唯一诊断。','indicate unit misalignment or casing distortion'),
 ('causes','介质温度升高会使液体膨胀；本文特别举可升温制冷氨及需加热沥青/糖蜜。','The rise in temperature causes the liquid to expand'),
 ('increases_risk_of','被阀隔离的封闭段无泄压措施时，升温膨胀有泵/管路破裂风险；泵型为本回转容积泵。','there is a chance that the pump or piping will rupture.'),
 ('prevented_by','对泵/管路内能被阀完全隔离的任意部分设置泄压装置以控制上述热膨胀破裂风险；保留冷液升温/热液工况。','Provide a pressure relief device in any part of a pump'),
 ],
}


def main():
    check()
    target=OUT/'heldout_materials'
    target.mkdir(exist_ok=False)
    bundle=OUT/'heldout_sources/source_only.jsonl'
    pages=rows(bundle)
    assert len(pages)==29 and {p['page_key'] for p in pages}==set(NOTES)
    lookup={p['page_key']:p for p in pages}
    references=[]
    for key, specs in SPECS.items():
        for rel, statement, anchor in specs:
            witness=bind(lookup[key],anchor)
            if witness is None:
                raise ValueError('Missing source anchor: '+key+' '+anchor)
            validate_witness(lookup[key],witness)
            references.append(dict(reference_id=f'{key}:AIR:{1+sum(r["page_key"]==key for r in references):03d}',
                page_key=key, relation=rel, statement_zh=statement, source_witnesses=[witness],
                applicability_scope=lookup[key]['applicability_scope'], source_page_sha256=lookup[key]['page_text_sha256'],
                full_page_context_required=True, source_language_preserved=True,
                reference_status='AI_source_first_reference', human_review=False))

    # The twelve visually checked environment/temperature rows are atomic
    # maintenance prescriptions. Preserve merged native rows, not guessed boxes.
    key='MP018:p0016';page=lookup[key];table=page['tables'][0]
    grease_rows=[
      ([1,2],'清洁、干燥、轻中载、低中速，0–120°F(-18–49°C)：2–6个月；高质量NGLI1/2通用轴承脂。'),
      ([1,2,3],'清洁、干燥、轻中载、低中速，120–200°F(49–93°C)：1–2个月；同上通用轴承脂。'),
      ([1,4],'中等至脏、干燥、轻中载、低中速，0–120°F：1–4周；同一通用轴承脂适用合并单元。'),
      ([1,4,5],'中等至脏、干燥、轻中载、低中速，120–200°F：1–7天；同一通用轴承脂。'),
      ([1,6],'极脏、干燥、轻中载、低中速，0–200°F：每天冲出污物；同一通用轴承脂。'),
      ([7],'高湿/直接水溅、轻到重载、低中速，32–200°F：停机时润滑，起始间隔1–4周；锂基或其他防腐脂。'),
      ([8],'重至极重载、低速，0–200°F：1–8周，高黏度润滑；环境空白不继承上行水溅。'),
      ([8,9],'重至极重载、低速，-20–120°F：1–8周，高黏度润滑；环境空白不补填。'),
      ([10],'轻载、高速，100–200°F：1–8周，channeling高速型润滑脂；环境条件原表空白。'),
      ([11],'可能霜冻、轻到重载、低中速，-65–250°F：停机时润滑，1–4周；宽温双酯型等原表油脂。'),
      ([12],'清洁至中等脏、干燥、轻中载、低中速，80–250°F：1–8周；优质高温型润滑脂。'),
      ([13],'清洁至脏、干燥、轻载、低速，80–300°F：1–4周；合成型润滑脂。'),
    ]
    for n,(indexes,statement) in enumerate(grease_rows,1):
        cells=[copy.deepcopy(c) for i in [0]+indexes for c in table['rows'][i]['cells']]
        witness=dict(kind='native_table_cells',table_id=table['table_id'],row_id=table['rows'][indexes[-1]]['row_id'],cells=cells)
        validate_witness(page,witness)
        references.append(dict(reference_id=f'{key}:AIR:{n:03d}',page_key=key,relation='maintained_by',
            statement_zh='本手册脂润滑轴承：'+statement+' 所有间隔只是维护计划起点，应检查油性、污物和运行温度后调整；不是固定安全周期。',
            applicability_scope=page['applicability_scope'],source_page_sha256=page['page_text_sha256'],
            source_witnesses=[witness],visual_evidence='heldout_sources/visual_checks/MP018_p0016.png',
            full_page_context_required=True,reference_status='AI_source_first_reference',human_review=False))
    for n,(rel,statement,quote) in enumerate([
        ('inspected_by','检查润滑脂油性及污物，以据此调整加脂频率。','Check grease conditions for oiliness and dirt'),
        ('maintained_by','根据润滑脂状态调整润滑频率，不机械使用起始间隔。','adjust greasing frequency accordingly.'),
        ('inspected_by','监测轴承运行温度，注意突然升温。','Watch operating temperatures'),
        ('indicates','运行温度突然升高可能提示需补脂，非唯一原因。','sudden rises may show need for grease'),
        ('indicates','较高速应用中突然升温也可能提示过度润滑，不能只解释为缺脂。','over lubrication on higher speed applications.'),
    ],13):
        w=bind(page,quote)
        if w is None:raise ValueError(quote)
        references.append(dict(reference_id=f'{key}:AIR:{n:03d}',page_key=key,relation=rel,
            statement_zh=statement,applicability_scope=page['applicability_scope'],source_page_sha256=page['page_text_sha256'],
            source_witnesses=[w],full_page_context_required=True,reference_status='AI_source_first_reference',human_review=False))
    save(target/'source_first_references.jsonl',references)
    coverage=[]
    for p in pages:
        key=p['page_key'];kind,note=NOTES[key]
        picture=OUT/'heldout_sources/visual_checks'/f'{key.replace(":","_")}.png'
        coverage.append(dict(page_key=key,source_page_sha256=p['page_text_sha256'],category=kind,
            review_note_zh=note,reference_count=sum(r['page_key']==key for r in references),
            page_read_before_new_extraction=True,historical_candidates_read=False,
            visual_checked=picture.exists(),visual_sha256=sha(picture) if picture.exists() else None,
            completeness='AI working inventory; not expert-exhaustive physical-page recall',
            reference_maker='Codex AI assistant; method-aware; no new extraction outputs available',human_review=False))
    save(target/'page_inventory.jsonl',coverage)
    # Record all excluded/uncertain contexts instead of silently calling a
    # graphics/foreign-language page an empty page or replacing its identity.
    save(target/'auxiliary_and_limits.json',dict(
        zero_reference_pages=[r for r in coverage if not r['reference_count']],
        uncertain_content=[
            dict(page_key='MP006:p0007',issue='ISO severity chart group/colour boundaries not separately annotated; table protective settings retained as configuration, not core fault truth.'),
            dict(page_key='MP016:p0003',issue='Medium restrictions and special Nitrile/Viton compatibility require preserving both statements; no external resolution.'),
            dict(page_key='MP018:p0006',issue='Grout clearance fractions corrupted in parsed text; no guessed numerical repair.'),
            dict(page_key='MP021:p0020',issue='Exactly 32 F oil selection unspecified; 4924A ammonia/other reducer scopes stay separate.'),
        ],
        sidecars='Installation/operation, negative requirements, protective settings, structural/parts and legal/background text stay outside core denominator and must be counted separately in output review.',
        no_exhaustive_Gold_claim=True))
    template=json.loads((OLD/'extraction_template.json').read_text())
    requests=[]
    fields=['doc_id','pdf_page_number','title','pump_type','service','applicability_scope','document_sha256','page_text_sha256','page_text','tables']
    for p in pages:
        content=json.dumps({k:p[k] for k in fields},ensure_ascii=False)
        payload={k:copy.deepcopy(v) for k,v in template.items() if k!='system_prompt'}
        payload['messages']=[dict(role='system',content=template['system_prompt']),dict(role='user',content=content)]
        requests.append(dict(request_id='H29_'+p['page_key'].replace(':','_'),page_key=p['page_key'],arm='E1',
            source_page_sha256=p['page_text_sha256'],shared_input_sha256=digest(content.encode()),
            payload=payload,payload_sha256=digest(payload_bytes(payload))))
    save(target/'requests.jsonl',requests)
    files=[target/'source_first_references.jsonl',target/'page_inventory.jsonl',target/'auxiliary_and_limits.json',
        target/'requests.jsonl',bundle,OUT/'ai_method_freeze.json',Path(__file__),
        ROOT/'scripts/run_rp1_targeted_v2_1.py']
    files+=list((OUT/'heldout_sources/visual_checks').glob('*.png'))
    save(target/'reference_and_request_freeze.json',dict(frozen_at=now(),
        sha256={str(p.relative_to(ROOT)):sha(p) for p in files},
        source_first_new_output_blind=True,method_blind=False,human_review=False,
        reference_count=len(references),pages=29,core_reference_pages=sum(bool(r['reference_count']) for r in coverage),
        planned_requests=29,model=template['model'],base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        request_payload_bytes=sum(len(payload_bytes(r['payload'])) for r in requests),
        new_API_calls=0,extraction_status='not_started',
        reference_scope='AI source-first working inventory; no expert or exhaustive physical-page recall claim'))
    print(json.dumps(dict(pages=29,reference_atoms=len(references),core_reference_pages=sum(bool(r['reference_count']) for r in coverage),
        requests=29,visual_checks=6,new_API_calls=0),ensure_ascii=False))


if __name__=='__main__':
    main()
