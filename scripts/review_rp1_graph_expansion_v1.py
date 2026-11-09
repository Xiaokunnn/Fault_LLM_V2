#!/usr/bin/env python3
"""Archive the assistant's source-page judgments; calculate, never infer, labels.

No API calls. This is an unblinded single-AI audit, not independent human truth.
The graph and sample were fixed before these judgments. No sample exclusions.
"""
from collections import Counter
from build_rp1_graph_expansion_v1 import OUT, GRAPH, ROOT, rows, write, sha

# ID | source support | context-qualified usable | paired original usable | reason
JUDGMENTS = '''
B01|S|U|-|原文有预防功能故障的泛指action，但没有具体动作，独立知识用途未确定。
B02|S|S|-|皮带传动段明确要求垂直传动比其他配置更紧，比较条件保留。
B03|S|S|-|圆锥滚子轴承装配原句保留Q/QS尺寸与内圈大端相对条件。
B04|S|E|-|因果原句存在，但this procedure未解析；实际指从内圈施力压出径向轴承。
B05|U|U|-|正文称Ø215/265应按表再润滑，紧邻表格又说明该轻型轴承终身润滑；需区分配置，不能直接认定正确。
B06|E|E|-|Do not operate without liquid被转成正向operates_under无液充注，否定反转。
B07|S|S|-|干转导致泵磨损增加，原句与中文方向一致。
B08|S|S|-|叶轮键、垫圈及不同直径对应螺母/紧定螺钉保留在引用中。
B09|S|E|-|关系符合推进轴割绳器段原文，但该段不在声明的泵管系适用范围内。
B10|S|S|-|ABB电机故障表把皮带拉力过大列为轴承发热原因，保留电机来源。
B11|S|E|-|压入静环动作有支持，但遗漏紧邻的定位销对孔要求及否则破裂警示。
B12|S|S|-|电机不启动表中，过载跳闸对应检查并复位启动器过载保护。
B13|S|U|-|薄膜RTD结构表述正确，但本页未明确泵或可迁移旋转机械适用性，作为泵核心知识未定。
B14|S|S|-|共模滤波器减少轴承电流，安装变频器的条件在引用内。
B15|S|S|-|精密信号发生器用于检查信号处理设备频率测量准确度，源段支持。
B16|S|S|-|管道安装防止气锁的关系由原文直接支持，引用含尤其泵入口侧。
B17|S|S|-|磨损板磨损/损伤检查直接对应，未与邻栏轴承语句混合。
B18|S|S|-|X射线发现表面/亚表面缺陷，源段明确包括泵的金属磨损部件。
B19|S|S|-|角度和平行不对中用移动电机及增减垫片纠正，原文支持；不是完整对中操作规程。
B20|E|E|-|直线度是检查属性却被标为FaultMode；源段还是推进轴而非泵管系。
B21|S|S|-|叶轮拆卸与有耐磨环时避免损伤的限定在原句内。
B22|S|S|-|机械接头抗轴向脱离能力用拉拔试验，作为检查方法关联成立。
B23|S|S|-|轴封泄漏表现为适配器底部槽口滴液，方向与原文一致。
B24|S|E|-|损坏时更换衬套成立，但紧邻的Ø330/415/418/465/525配置标题未绑定。
B25|S|S|-|源句明确讨论泵额定工况；关系信息量较低但未反转含义。
B26|S|S|-|堵塞可能导致电机欠载/过载或轴弯曲，原句保留并列替代结果及can。
B27|S|E|-|O形圈装入旋转环成立，但双机械密封配置及页首装配前润滑条件未附着。
B28|S|S|-|瑞典文端盖拆卸段明确取出O形圈并检查磨损，检查对象一致。
B29|S|E|-|防止耐磨环损伤有支持，但截取的引用丢失重新装配转子时的局部条件。
B30|S|E|-|舱底水报警与积水关系成立，但无风雨密垫片的集装箱货舱这一来源限定未保留。
B31|S|S|-|机械接头用耐火试验检查，方法关联成立；不把关联当作完整试验参数。
B32|S|S|-|工作完成后恢复防护装置的时序条件保留在引用内。
B33|S|E|-|静环压入动作有支持，但it指代、M7N型号及定位销对孔要求未完整绑定。
B34|S|S|-|防护罩22与螺钉23安装紧固直接对应源文维护步骤。
B35|S|E|-|储存柜装高液位报警有支持，但燃油共用通气/溢流总管的前提不在记录内。
B36|S|E|-|观察机械密封泄漏是否停止有支持，但首次启动少量初始泄漏的前提缺失；不能推广为任意泄漏等待。
B37|S|S|-|中文明确排水管进入轴承箱处密封，防止水尘进入的方向有源文支持。
B38|E|E|-|火灾遥控停泵装置属于报警保护配置，被当成维护动作，关系角色不成立。
B39|S|U|-|每台量产泵需按指定条款试验有支持，但记录只存条款号，未解析具体方法，完整可用性未定。
B40|S|S|-|润滑O形圈50并装入静环51及密封壳体，对象与先后顺序保留。
A01|S|S|E|项目diagnosed_by允许SignalFeature；检查满载电流有源文支持，新增上下文补回压力开关控制前提；不保证源手册技术表达本身正确。
A02|S|S|S|表格同一故障单元下列出吸入管路存气，因果方向正确；原表示已有两个端点。
A03|S|S|S|联轴器安装不当对应检查并重新安装，新增上下文还绑定振动噪声故障。
A04|S|S|E|电机故障的过载子行对应检查电流，新上下文补齐故障及原因；原引用只有过载与动作。
A05|S|U|U|拆卸后盖动作和目标一致；记录未保留具体泵组合标题，本页又是续页，型号完整性未定。
A06|S|U|U|后盖紧定螺钉拆卸直接支持；本页上半为续页且下半切换组合，当前记录配置归属未定。
A07|S|S|E|新记录把核对Q/H与NPSH绑定到吸上高度过高造成流量不足；原引用只有动作，缺少目标及条件。
A08|S|E|E|功率过大表中确有孔板/止回阀措施，但一个大单元含六项原因和多项动作，未显式绑定到低背压子项。
A09|S|E|E|正常疲劳导致剥落裂纹有支持；保留的单元未包含BEARING DEFECTS及内外圈限定，不能泛化到整泵任意剥落。
A10|S|U|U|不当起吊的风险原句成立，但局部上下文混入对中栏，未保留不许用单部件吊点吊整机的完整指代。
A11|S|S|E|表格把轴承失效列为电机故障原因；新定位补回电机故障合并单元，原引用仅有轴承和更换动作。
A12|S|S|E|检查电机方向有支持；新增上下文含STARTUP STEPS与注水先后，原记录无启动语境。
A13|S|S|S|O形圈损坏对应泵支架顶部/泵底泄漏，表格同一行绑定明确。
A14|E|E|E|换机械密封是干转导致轴泄漏后的维修，不能用causes槽的干转作mitigated_by头实体；换密封不消除无水运行。
A15|S|E|E|拆螺母、叶轮和平键步骤有支持，但Ø215/265-12组合标题没有进入上下文。
A16|S|S|S|压力过高列为轴泄漏原因，表格位置和方向正确。
A17|S|S|S|叶轮27拆卸有支持，新上下文补充必要时轻敲叶片；不声称独立完整拆卸规程。
A18|S|E|E|拆平键有支持，原句含先拆紧定螺钉和叶轮；Ø330/415/418/465/525配置未绑定。
A19|S|S|S|检查运输物理损伤，原动作已含运输语境，新上下文明确收货。
A20|S|S|S|O形圈不耐介质用适配介质的O形圈替换，目标和条件一致。
A21|S|E|E|水进入壳体造成腐蚀符合轴承故障表；未保留轴承滚道/滚珠的腐蚀对象，壳体与腐蚀指向不完整。
A22|S|S|S|检查工作压力且装有压力表的前提完整；按现有SignalFeature诊断目标定义成立。
A23|S|S|S|不在指定工况范围对应泵振动噪声，保留具体泵来源及可能原因模态。
A24|E|E|E|检查驱动对中有原句，但对中状态被标成Component；类型角色错误没有修复。
A25|S|S|E|轴弯曲导致振动过大由表格支持，新定位补回故障单元；原引用只有弯轴及更换轴。
A26|S|S|E|吸上高度过高导致无/低流量由表格支持，新定位补回故障；原引用只有原因。
A27|S|S|S|机械密封安装不当对应轴泄漏，表格行与方向一致。
A28|S|S|S|泵脚应力使泵体变形对应顶部/底部泄漏，中文保留中间机制。
A29|S|S|E|泵内异物是功率过大原因，新定位补回故障单元；原引用只有原因。
A30|S|E|E|污物卡滞轴承并在轴/壳体内转动造成磨损有支持；只附故障/原因，未保留appearance中配合表面对象。
A31|S|S|E|流量不足用清洁/更换管路缓解，新增原因单元限定管路堵塞；原引用只存动作。
A32|S|E|E|拆防护罩是拆泵步骤，但新增上下文仍只有单句，缺少拆卸阶段及Ø215/265-12配置。
A33|S|E|E|电机支架紧固件拆卸有支持，但Ø215/265-02组合标题未绑定。
A34|S|S|E|水/污染物进入轴承对应过早失效，新定位补回故障单元；原引用只有原因及环境保护动作。
A35|S|E|E|拆密封旋转件有支持，前后步骤保留，但MG12型号标题未进入上下文。
A36|S|S|E|异物卡叶轮导致噪声过大，新定位补回故障单元；原引用只有异物和清除动作。
A37|S|S|S|泵内无介质对应振动噪声，表格同组因果方向正确。
A38|S|S|S|两相运行对应检查熔断器、电缆及连接，诊断对象本身明确，旧inspected_by也在项目允许范围内。
A39|S|S|S|检查电机接线对应正确转向，源页启动检查清单支持。
A40|S|S|S|运行时检查噪声/振动，条件原本即保留；新增上下文补入异常时停机。
'''

def main():
    samples={s['review_id']:s for s in rows(OUT/'quality_sample.jsonl')}
    review=[]
    for line in JUDGMENTS.strip().splitlines():
        rid,support,usable,original,reason=line.split('|',4);s=samples[rid];r=s['record']
        review.append(dict(review_id=rid,cohort=s['cohort'],triple_id=r['triple_id'],
            doc_id=r['doc_id'],pdf_page_number=r['pdf_page_number'],source_support=support,
            context_qualified_usable=usable,paired_original_usable=None if original=='-' else original,
            paired_original_source_support=support if original!='-' else None,reason_zh=reason,
            source_page_sha256=r['page_text_sha256'],reviewer='current Codex assistant; unblinded single-AI source audit',
            inspected='full archived source page, candidate quotation, Chinese triple, native table context where applicable',
            sample_sha256=sha(OUT/'quality_sample.jsonl')))
    assert {r['review_id'] for r in review}==set(samples) and len(review)==80
    write(OUT/'quality_review.jsonl',review)
    result={'status':'completed_offline_expansion_and_AI_sample_comparison','sample_n':80,
        'labels':{'S':'source-supported / context-qualified usable under the indicated column',
                  'E':'observed representation, scope or binding defect','U':'unresolved from attached evidence'},
        'rubric':'Support checks endpoints, direction, polarity, Chinese meaning and semantic types against full source page. Usable also requires local applicability/critical action conditions in attached evidence/context; a page pointer alone is insufficient. Atomic method associations need not reproduce a full procedure.',
        'limitations':['unblinded single-AI judgments; not expert accuracy or independent evaluation',
                      'build-corpus record samples, correlated within pages; not external generalization',
                      'no page reference inventory; no recall claim',
                      'only a sample is adjudicated; none removed or repaired after review'],
        'sample_sha256':sha(OUT/'quality_sample.jsonl'),'graph_freeze_sha256':sha(OUT/'graph_freeze.json')}
    for cohort in ['baseline','added']:
        group=[r for r in review if r['cohort']==cohort]
        result[cohort]={k:dict(Counter(r[k] for r in group)) for k in ['source_support','context_qualified_usable']}
        result[cohort]['n']=len(group)
    added=[r for r in review if r['cohort']=='added']
    result['paired_original']={k:dict(Counter(r['paired_original_'+k] for r in added)) for k in ['source_support','usable']}
    result['paired_usable_transitions']=dict(Counter(r['paired_original_usable']+'->'+r['context_qualified_usable'] for r in added))
    for metric in ['source_support','context_qualified_usable']:
        result['weighted_expanded_'+metric+'_S_fraction']=(1326*result['baseline'][metric].get('S',0)/40+130*result['added'][metric].get('S',0)/40)/1456
    result['estimated_added_context_qualified_records']=130*result['added']['context_qualified_usable'].get('S',0)/40
    result['estimated_added_note']='Sample-weighted estimate, not a count of verified records; no claim-level estimate.'
    write(OUT/'quality_summary.json',result)
    print(__import__('json').dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
