#!/usr/bin/env python3
"""Materialize the recorded, source-read AI judgments; no inference or API calls.

The explicit catalog below is an audit record, not a rule-based quality classifier.
It does not modify the extractor, postprocessor, or frozen reference inventory.
"""
import json
from pathlib import Path
from rp1_offline_contract_v3 import ROOT, rows, sha, object_sha, write, bind, type_valid

BASE = ROOT / 'results/experiments/research_point_1/ai_review_v1'
OUT = BASE / 'holdout_comparison_v1'

# ID ranges are only used for rows that were individually inspected and share
# the same failure/support explanation (e.g. a reversed parts-table relation).
CATALOG = '''
1|E|relation_type|检测方法不能作为manifests_as的故障主语，输出曲线不是故障表现。
2,4,9,11,12,15|E|relation_direction|检测方法与被检测对象/信号颠倒，关系域和值域不符合冻结schema。
3|E|relation_type|原文颗粒扰动传感器场的机理可追溯，但Symptom作为causes主语不符合当前表示。
5,7,13|S|supported|金属碎屑传感器的传感头及励磁/感应线圈由同一表行支持，保留背景范围。
6,8|E|relation_type|疲劳产生的磨粒被标为FaultMode；原文是监测到的磨损颗粒，不是一个名为颗粒的故障模式。
10|E|wrong_source_attachment|不能分析成分和粒径属于金属碎屑传感器局限，错误附着到颜色滴定方法，且indicates方向错误。
14|E|requirement_representation|源文是不适用于深色油的检测方法限制，不是以increases_risk_of替代适用性否定。
16-42|S|supported|船舶机械建议故障模式表的设备行与模式对应，保留example及background，不当作泵故障实例。
43|E|missing_exception|过热器处装汽阀的规定遗漏总过热温度低时允许替代布置的例外。
44-48,50,51|S|supported|锅炉阀件/套筒局部布置由正文支持，保留本条口径中的设备和条件；其他独立阀型要求不自动视为本位置关系的一部分。
49|E|relation_type|缓解措施尾实体是套筒Component而非安装该装置的MaintenanceAction。
52-97|S|supported|原页部件表或拆卸段支持局部部件归属；属于结构知识，不能计作新增诊断或维护动作。
98,103|U|assembly_ambiguity|原文说轴承座连同轴和叶轮整体吊出，单凭此句不能唯一确定轴承座contains部件的结构粒度。
99|E|incomplete_object|整体吊出应包含轴承座、轴、叶轮；原子动作只以轴承座为对象，未保留共同吊出的组成。
100,101|S|supported|拆卸第3步支持螺钉及泵侧联轴器局部归属；只计结构知识。
102,104-108|S|supported|拆卸章节、步骤/局部先后条件及对象保留；检查或拆卸动作与源文一致，不称完整拆卸程序。
109|S|supported|放置法兰支撑后检查孔对齐和密封垫面平行，局部先决动作在conditions保留。
110,112,126,128|E|alternative_lost|改善支撑或安装补偿器是替代措施；单条required未保留alternative，增加重复if条件也不能恢复选择关系。
111,114,115,117,121,123|E|relation_type|条件触发加垫/检查要求被写成causes动作；加if条件不修复causes值域与义务语义。
113|S|supported|垫片处于泵和法兰支撑之间的结构位置明确；不把完整安装操作计入核心维护。
116,118,119,122|E|procedure_context|安装检查的阶段/前序装配状态未进入语义字段；引文中的步骤号仅为来源，不能代替输出中的程序条件。
120,124,125|E|operation_role|初装紧固/装配程序直接标为维护关系，且未完整保留安装顺序；不等同修理或条件调整。
127|S|supported|先固定泵再检查水平的局部条件、对象、安装适用范围保留。
129,132,136,137,140,141|E|relation_type|原表是厂家建议振动设定值，数值本身不是Standard；部件设定值应另存参数记录。
130,131,134,138|S|supported|原页ISO图中的分区说明以背景标准定义保存，不推广为该泵现场故障阈值。
133|E|scope_overstatement|原文仅说行业寿命判断与标准建议一致；不能将孤立的7mm/s数值表述为无条件国际标准规定。
135|S|supported|原文直接说明高于7mm/s振动缩短泵轴承/轴封及电机轴承寿命，保留示例部件而非单一故障判据。
139|E|modality|often resulting被压成asserted高振速因果，未保留经常而非必然的限定。
142|S|supported|工厂测试、垂直泵、测量位置/方向及2.8mm/s限定全部保留，属于测试工况说明。
143-185|E|relation_direction|爆炸图清单被统一写成部件contains整泵，包含方向倒置；不能据此认为部件本身不真实。
186,197,204|U|causal_attachment|入口压力不足→汽蚀→性能/噪声/寿命是链式句，后续分词直接附着按既定争议口径列未决。
187|E|invented_consequence|禁止泵送所列介质的句子没有给出short pump life这一直接后果，不能由附近寿命句补造。
188|E|modality|风险尾语保留may但modality写成required，混淆禁止使用要求与可能爆炸风险，表示内部不一致。
189,190,201|E|relation_direction|收货检查动作被置于inspected_by主语，泵被置于尾部，检查方向颠倒。
191,202,203|E|relation_type|接口识别/所需入口压力变化不能以当前causes值域中的Component或OperatingCondition表示。
192|E|invented_consequence|禁止闭阀运行句未直接说明叶轮损坏；邻近最大压差句不能自动绑定为这条原因的证据，且尾部不是Risk。
193|S|supported|每次运行后用水或中和剂冲洗的动作与局部柔性叶轮泵范围明确；不是灌液启动操作。
194|E|relation_type|Equipment到OperatingCondition的located_in违反当前结构关系模式。
195|S|supported|柔性叶轮泵头进出口的局部结构归属有正文支持。
196|E|relation_direction|超过最大压差导致叶轮损坏，被写成叶轮损坏导致超压运行，因果方向反转。
198|S|supported|柔性叶轮泵可处理夹带固体的工况能力来自正文，不增加故障知识量。
199|S|supported|入口压力不足导致汽蚀是原句明示第一条因果，局部泵型保留。
200|S|supported|Nitrile/Viton叶轮在该类泵的配置和介质用途有原文支持；是配置说明，不是解除邻近禁止要求。
205|E|relation_direction|入口管路建议动作与汽蚀的prevented_by头尾反转。
206,207,209,211,215,217-220,223,224|E|procedure_context|瑞典语拆卸/检查/清洁条目缺少本页统一断电、隔离、泄压、排液前提及相关拆卸阶段；局部必要时或部件名不足以恢复前序条件。
208|E|negative_requirement|正常运行无需调整被放入正向maintained_by动作，未表达无要求。
210,213|E|relation_type|日常/定期检查被写成maintained_by InspectionAction，应按检查关系表示。
212|E|relation_meaning|沿泵体轴线拉出叶轮是方向性拆卸动作，不证明叶轮位于名为泵体轴的实体中。
214|S|supported|原文明示碘/磷清洁剂侵蚀泵并降低性能，因果方向和泵型一致。
216|E|scope_role|保修失效是行政后果，未标背景而进入primary核心causes；不等同泵故障或维护效果。
221|E|procedure_context|定期检查泵头部件的建议存在，但缺少本页检查前隔离等共同前提，不能当作条件完整条目。
222|E|relation_direction|断电泄压等前提与维修检查程序的prevented_by方向/实体类型错误。
225,228-230,233|E|toc_as_instruction|目录标题和页码仅指向其他章节，不能当作本页已给出的具体检查/维护要求。
226|E|scope_role|未读手册的通用责任风险被标为primary核心泵因果；应作为操作说明辅助要求。
227|U|toc_configuration|目录出现自动排气阀章节不足以确认每个型号均包含该部件，配置归属未决。
231|E|condition_logic|原文要求证实未损安全/完整性才可采用未覆盖应用，输出却在该许可条件下声称增加损害风险。
232|S|supported|安装运行应符合适用国家/地方/行业标准的明示通用规范要求；非核心诊断关系。
234,237|E|operation_role|初装断开联轴器/电源的程序前提被直接保存为维护动作；原页安装/隔离说明应单列。
235,236,241,250,251|S|supported|位置、局部结构或布管条件有源文支持，保存为非核心背景/结构/工况信息。
238,242,247|E|relation_meaning|支撑楔块的使用、基础吸振能力或调平螺栓限制被误写为维护该部件的动作。
239,245|E|operation_role|起吊用吊耳/吊环是起吊程序，不是检查泵的方法。
240,244,249|E|relation_direction|防淹/布管减阻/起吊固定的目标与措施表示错误，当前关系域或方向不成立。
243|S|supported|储存环境接近运行环境时保持加热器连接可用，条件保留且已标背景。
246|S|supported|出库或首次启动时给轴承施新润滑剂，局部非堵塞泵范围和触发条件均保留。
248|E|relation_meaning|源文是泵尽量靠近液源的位置要求，不是泵operates_under名为液源的工况。
252|E|procedure_context|调楔块以对中调平的动作缺少基础灌浆/支撑阶段，语义字段未绑定该安装条件。
253,258|S|supported|突然升温可能缺脂/高速应用过度润滑的提示保留possible及局部泵型；被输出标为背景，主图覆盖另计。
254-257,259-261|E|incomplete_maintenance|只给脂种并将材料标MaintenanceAction，缺少同表初始间隔及按油脂状态/温度调整的完整维护条件。
262|E|incomplete_maintenance|每天清除污物缺少该表间隔只是起点、按油脂/温度调整的限定，不能作为条件完整维护条目。
263,272|S|supported|指定ABB变频器下轴承电流及可能影响电机的风险有原文支持，保留probable和型号条件。
264,265,267-271,274,276|E|relation_direction|电机检查/维护/防护的对象、措施或风险关系头尾错误，不能只凭术语正确计支持。
266,273|E|relation_direction|防轴承电流措施被写成动作prevented_by故障，且高功率等级必须联合的两措施拆散。
275|E|modality|原文peuvent仅表达可能，probable提高了证据强度，且变频应用限定不足。
277|E|unknown_relation|required是模态字段，不是冻结schema中的关系，动作与电机方向亦不规范。
278|S|supported|启动前重装联轴器防护罩的预防性维护要求由原图页明确文字支持。
279|U|structural_inference|图文要求重装联轴器罩，但罩located_in联轴器是否表示恰当结构包含关系仍不确定。
280,281|E|relation_direction|直尺/卡尺是检查方法，不能作为被检查对象去inspected_by对中动作。
282|E|relation_direction|应由变形风险指向膨胀补偿措施，当前prevented_by头尾反转且否定故障被当实体。
283,284,286,290,292,293,302,304|S|supported|原页管路/滤器段直接支持相应原因和后果，原有can/may/possible/probable强度及局部泵型保留。
285,288,291,294,298,300|E|relation_direction|检查/维护/预防关系的对象与动作错误或主语不在对应域，不能用相关词出现代替正确关系。
287|E|relation_meaning|管路接头应密封，密封剂只是实现手段；不是对密封剂这个部件实施维护。
289,301|S|supported|轻液吸上工况中两种可选阀的局部位置有原文支持；位置关系本身不宣称两者必须同时安装。
295,299|E|alternative_lost|拖擦提示不对中或管路应力变形，单条asserted丢失替代解释和不唯一性。
296|E|column_splice|两栏串接把左栏suction piping与右栏errors in piping layout or assembly拼成新因果，完整页面不支持该原句。
297|S|supported|升温引起液体膨胀由原文明示；标background并保留回转容积泵范围，不计主图核心覆盖。
303|U|condition_logic|冷液升温与需加热液体是不同举例，conditions并列未定义OR/AND；尚不能确认其表示完整保留热膨胀条件。
305|E|operation_role|运行时保持泵内充液是运行条件，未单列而写成核心MaintenanceAction。
306|S|supported|A/B/C减速器在32°F上下选不同油种的背景规格保留；不补造等于32°F规则。
307,314,322|E|missing_scope|减速器维护/检查缺少A/B/C尺寸范围，换油条目亦未绑定温度油种，不能从相邻独立记录隐式继承。
308,313,315,319,321|E|incomplete_maintenance|材料直接标维护动作，缺少表下注脂间隔、严重工况加密及相容条件；有型号或密封位置仍不完整。
309|E|missing_scope|恶劣工况增加润滑频率未绑定本手册具体泵/润滑脂适用范围与相容限制。
310|E|operation_role|启动前注油是准备运行程序，且仅写左框指代而未保留具体型号/油种，非条件完整维护。
311|E|missing_exception|500小时或六个月先到保留，但恶劣工况更频繁及原脂相容条件遗漏。
312,316,320|S|supported|氨泵油槽归属/出厂无油状态和不锈钢泵腔部件归属有原文支持，仅计非核心信息。
317|E|operation_role|出厂试验液涂覆是已完成的工艺状态，不能作为新维护任务，且并非用户维护动作。
318|E|operation_role|氨泵启动前注油保留了材料条件，但仍是运行准备，不应直接计为核心维护。
323|E|incomplete_maintenance|氨泵油槽换油周期保留，但换油动作未保留轻质制冷油/Neoprene相容性/黏度限制。
324|E|relation_meaning|personal safety是目标不是不良Risk，正文条件性采取防护不能直接变成该风险边。
325-327|S|supported|噪声表型号、原电机罩、BEP、水温和50Hz测试条件齐全；仅规格记录，不是故障阈值。
328|E|relation_type|UltraPure同样适用的说明不是Standard实体，specified_by表示错误。
'''

# Frozen-reference edges assessed after source quality, independently of which
# arm retains a row. Bundled candidates still receive at most one match.
FULL_MATCHES = {
    102: [7], 104: [5], 105: [2], 106: [3], 107: [4], 108: [1],
    109: [3, 4], 127: [1], 135: [1, 2, 3],
    214: [3], 246: [1], 253: [17], 258: [16], 278: [3],
    283: [6], 284: [14], 286: [12], 290: [11], 292: [13],
    293: [16], 297: [20], 302: [7, 8], 304: [15],
}
PARTIAL_MATCHES = {
    99: ([6], '整体吊出对象未完整保留'),
    116: ([9], '缺少紧固管路之后的检查阶段'),
    118: ([6], '未绑定第6步前序支撑/垫片安装'),
    119: ([8], '未区分第9步与第3步检查阶段'),
    122: ([2], '缺初装阶段绑定'),
    193: ([8], '本条冲洗动作支持，但冻结参考还要求材料/介质咨询限制'),
    199: ([2], '直接汽蚀因果支持，但冻结参考合并了高温/高转速入口压力条件'),
    206: ([13], '缺共同隔离与拆卸条件'),
    207: ([26], '缺共同隔离与拆卸条件'),
    209: ([2], '缺共同隔离条件'),
    211: ([26], '缺共同隔离与拆卸条件'),
    215: ([18], '缺前序凸轮拆除及密封面注意事项'),
    217: ([14], '缺共同隔离与拆卸条件'),
    218: ([21], '缺前序拆卸及明确磨损检查'),
    219: ([9], '缺隔离及取出O圈后检查条件'),
    220: ([27], '缺隔离及检查前提'),
    221: ([4], '缺共同检查前隔离条件'),
    223: ([23], '缺隔离及静面拆卸阶段'),
    224: ([20], '局部拆板条件保留但共同隔离及挡圈步骤不足'),
    254: ([10], '仅脂种及部分工况'), 255: ([1], '仅脂种及部分工况'),
    256: ([11], '仅脂种及部分工况'), 257: ([9], '仅脂种及部分工况'),
    259: ([6], '缺初始间隔及调整要求'), 260: ([7, 8], '合并温区，缺间隔及调整'),
    261: ([12], '缺初始间隔及调整要求'), 262: ([5], '缺可调整起始间隔限定'),
    307: ([7], '缺尺寸和油种'), 308: ([4], '缺周期和相容要求'),
    313: ([3], '缺周期和相容要求'), 314: ([8], '缺A/B/C适用范围'),
    315: ([5], '缺周期和相容要求'), 319: ([1], '缺周期和相容要求'),
    321: ([2], '缺周期和相容要求'), 322: ([9], '缺尺寸及温度油种'),
    323: ([6], '缺换油材料限制'),
}


def materialize():
    packets = rows(OUT / 'quality_review_packets.jsonl')
    pages = {p['page_key']: p for p in rows(BASE / 'heldout_sources/source_only.jsonl')}
    references = {r['reference_id']: r for r in rows(BASE / 'heldout_materials/source_first_references.jsonl')}
    notes = {}
    for line in CATALOG.strip().splitlines():
        ids, verdict, category, reason = line.split('|', 3)
        for group in ids.split(','):
            limits = list(map(int, group.split('-')))
            for n in range(limits[0], limits[-1] + 1):
                if n in notes:
                    raise ValueError(('Duplicate judgment', n))
                notes[n] = (verdict, category, reason)
    assert set(notes) == set(range(1, len(packets) + 1))
    result = []
    for packet in packets:
        n = int(packet['review_id'][3:])
        verdict, category, reason = notes[n]
        payload = packet['payload']
        page = pages[packet['page_key']]
        full = [f'{packet["page_key"]}:AIR:{i:03d}' for i in FULL_MATCHES.get(n, [])]
        partial, partial_reason = PARTIAL_MATCHES.get(n, ([], None))
        partial = [f'{packet["page_key"]}:AIR:{i:03d}' for i in partial]
        assert all(i in references for i in full + partial)
        if full:
            assert verdict == 'S'
        if verdict == 'S':
            assert type_valid(payload), packet['review_id']
        witnesses = []
        for field in ['evidence_text', 'head_surface', 'tail_surface']:
            witness = bind(page, payload[field])
            if witness and witness not in witnesses:
                witnesses.append(witness)
        result.append(dict(review_id=packet['review_id'], page_key=packet['page_key'],
            payload_sha256=packet['payload_sha256'], source_page_sha256=packet['source_page_sha256'],
            verdict=verdict, error_category=category, reason_zh=reason,
            source_witnesses=witnesses,
            context_source='heldout_sources/source_only.jsonl#' + packet['page_key'],
            context_read='full_page_and_native_table',
            locator_note='Witnesses are verbatim locating anchors, not automatic proof of the whole assertion.',
            reference_matches=full, partial_reference_matches=partial, partial_reason_zh=partial_reason,
            reviewer='Codex AI assistant', human_review=False,
            blind_to_method=False, annotation_unit='unique_page_payload'))
    write(OUT / 'source_quality_judgments.jsonl', result)
    write(OUT / 'review_freeze.json', dict(
        status='source_judgments_recorded_before_arm_aggregation',
        reviewed_unique_payloads=len(result), frozen_reference_count=len(references),
        reference_inventory_changed=False, API_calls=0,
        source_quality_separate_from_mechanical_locator_flags=True,
        matching_note='Full match only; partial matches are disclosed, never counted. Background output matches are audited separately from retained core coverage.',
        sha256={str(p.relative_to(ROOT)): sha(p) for p in [
            Path(__file__), OUT / 'source_quality_judgments.jsonl',
            OUT / 'quality_review_packets.jsonl', OUT / 'outputs.jsonl',
            BASE / 'heldout_materials/source_first_references.jsonl',
            BASE / 'heldout_sources/source_only.jsonl']},
    ))
    return {'reviewed': len(result), 'references': len(references), 'API_calls': 0}


if __name__ == '__main__':
    print(json.dumps(materialize(), ensure_ascii=False))
