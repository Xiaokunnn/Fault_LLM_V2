"""Read archived records; join explicit analyst attributions; never run repairs.

Attributions are a feasibility interpretation, NOT new S/E/U labels, correct
triples, candidate-generator outputs, or verified recovery measurements.
Run from repository root. All output is confined to this new analysis directory.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'results/experiments/research_point_1'
INPUTS = {}


def read(p):
    p = Path(p)
    raw = p.read_bytes()
    INPUTS[str(p.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return [json.loads(s) for s in raw.decode().splitlines() if s.strip()] if p.suffix == '.jsonl' else json.loads(raw)


def save(name, obj):
    content = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in obj) if name.endswith('.jsonl') else json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    p = OUT / name
    assert p.parent == OUT and '/' not in name
    p.write_text(content)


# Explicit record-by-record interpretation. A/B retain both original surfaces
# and endpoint types. C uses an already addressable local/page endpoint; D must
# introduce at least one new complete endpoint/action span. U is not a refusal
# to recognize an existing E label: it denotes uncertainty about the repair path.
ATTR = {}


def put(prefix, entries):
    for suffix, cls, level, reason in entries:
        key = prefix + suffix
        assert key not in ATTR
        ATTR[key] = dict(primary=cls, basis_level=level, analysis_reason=reason)


# level L: explicit local relation-level evidence and an encodable bounded edit;
# P: conceptual possibility with unresolved semantic/structural prerequisites;
# N: no supported reconstruction within the present task; U: undetermined.
# L does NOT mean complete conditions, validated automatic proof or recovery.
put('MP006:p0006:H29:', [
 ('004','U','U','不平基础触发加垫；原主张causes动作不合法。改为prevented_by会把补偿不平变成防止不平；若改部件维护又涉及初装/维护范围，现有标签不足以唯一裁定。'),
 ('007','U','U','气隙触发加垫同上；不是简单换关系即可保证成立。旧修复仅补if，仍E。'),
 ('008','F','N','初装紧固支撑，不应强制变为维护；现Schema无一般安装步骤关系。'),
 ('009','F','N','初装拆临时螺栓/装法兰垫片，缺顺序；不能靠换关系变维护。'),
 ('011','F','N','初装法兰紧固，现有关系空间不能直接表达安装流程。'),
 ('013','C','L','已有002/012的pump shaft Component可重配到当前检查动作，原if保留为该检查条件；词面直接出现pump shaft。当前修复仅加if未改头/关系。'),
])
put('MP016:p0042:H29:', [
 ('001','B','L','pumpen Equipment与日常视觉InspectionAction均已有；maintained_by改inspected_by。瑞典语映射未见通用实现。'),
 ('002','B','L','同页定期检查同理，仅改inspected_by；维修前隔离等公共条件仍须完整保留。'),
 ('003','F','N','保修失效是行政/背景后果，不属于当前主图故障主张。'),
 ('008','D','P','动作→prevented_by→开始检查不成立；可围绕泵/驱动电机的隔离动作表示，但原现有端点没有完整泵/电机维护对象与分解动作绑定，且前置程序不是被预防事件。'),
])
put('MP016:p0003:H29:', [
 ('001','A','L','原句as damage to the Impeller will result明确超压→叶轮损坏；原两端及类型交换合法。禁止超压的语境必须保留，不能把禁止操作当建议。'),
 ('008','F','N','NIPR随温度升高是参数依赖；causes尾OperatingCondition不合法，现Schema无参数依赖关系。'),
 ('009','F','N','高转速与NIPR参数依赖同上。'),
 ('010','A','L','汽蚀←入口短粗且不塌管的建议；交换成FaultMode prevented_by MaintenanceAction。跨句汽蚀上下文必须绑定。'),
 ('015','U','U','交换类型虽合法，但检查包装内容对照清单与检查整个泵并非完全同义；目标是否应为包装内容需再辨，不能算只交换即可修好。'),
 ('016','A','L','Check the pump for physical damage与泵Equipment直接对应，交换为泵inspected_by检查。'),
 ('017','A','L','检查接口朝向与泵的收货检查上下文对应，交换为泵inspected_by动作；仍需保留收货阶段。'),
 ('020','F','N','旋转方向决定进出口角色，无当前允许的接口角色/参数决定关系，不是causes Component。'),
])
put('MP017:p0002:H29:', [('007','F','N','未读手册责任警告，辅助操作要求；不能为增加核心量改造成泵故障因果。')])
put('MP018:p0006:H29:', [
 ('005','D','P','减阻措施与目标方向错；须把minimum of elbows实体改为完整布管措施，把minimize friction losses改成摩擦损失风险。原两端原类型不能仅交换，需重新分割/定型。'),
 ('006','D','P','泵不是被预防故障；需要独立flooding风险实体及完整防淹措施。flooding仅嵌在动作中，没有独立已有端点。'),
 ('007','F','N','基础吸振/支撑是功能能力，不是维护动作，当前Schema缺功能关系。'),
 ('009','F','N','安装泵时断开联轴器是安装程序前提；不把它重新命名为维护。'),
 ('010','F','N','灌浆用楔块的用途不是对楔块的维护，缺用途关系。'),
 ('013','F','N','调平螺栓用途及不可代支撑的限制，缺现成用途/程序约束关系。'),
 ('014','F','N','吊装使用吊耳不是检查，当前Schema无一般吊装操作关系。'),
 ('015','F','N','安装吊环吊装不是检查，同上。'),
 ('016','F','N','吊装前固定为操作安全要求；原文未给特定故障实体，不强添倾倒等风险。'),
 ('017','F','N','安装/对中前断电前提，不能仅换关系便计成该电气接头的维护。'),
])
put('MP019:p0048:H29:', [
 ('003','A','L','同表中功率段隔离轴承措施与轴承电流可直接反向prevented_by，保留ABB变频器和功率/机座条件。'),
 ('004','D','P','高功率行是隔离轴承ET共模滤波器联合措施；单条反向仍不完整。须额外形成绑定同一行的联合措施端点/包，不是A。'),
 ('005','D','P','与004同一高功率ET措施包，不能将两条各自当充分措施；需要组合动作而非仅交换端点。'),
 ('006','D','P','隔离轴承是Component，反向后仍不满足mitigated_by MaintenanceAction；需要源文utiliser...的完整动作片段并保留防护条件。'),
 ('007','D','P','电缆密封接头Component与电机Equipment交换后仍非MaintenanceAction；需要完整使用/接线动作，而非凭类型改名。'),
 ('009','D','P','反向inspected_by只是类型合法；原InspectionAction仅导电性名词，需扩为原文doit être vérifiée完整检查片段，不能算只交换即可修好。'),
 ('010','D','P','导电性不是InspectionAction；需要底座/连接的物理对象与完整测电位差检查组合。原两个InspectionAction不能合法交换成diagnosed_by。'),
 ('011','D','P','线缆/接头物件不是MaintenanceAction，需完整电机接线动作；功率>30kW及360°连续性须附属动作。'),
 ('012','D','P','同上，较小功率为推荐而非必须，补完整使用屏蔽线动作。'),
 ('013','E','N','源文要求额定以上转速时检查临界/最高转速，并未断言额定以上必提高超临界风险；交换也不能证明该风险因果。'),
 ('014','A','L','vérifiez检查动作与电机反向inspected_by，条件为额定以上转速；目录或铭牌分支仍须保留。'),
])
put('MP020:p0015:H29:', [
 ('003','C','P','已有001尾COUPLING Component可与STRAIGHT EDGE InspectionMethod重新配对为检查对象/方法；但仅图题ALIGNMENT及示意图，唯一对象和完整位置依据尚不足。'),
 ('004','C','P','同上，CALIPER对应联轴器对中；不能只把InspectionAction ALIGNMENT与方法交换就合法。'),
])
put('MP021:p0020:H29:', [
 ('010','F','N','启动前注油是运行准备；旧评价明确不归核心维护。'),
 ('013','F','N','试验液涂覆是出厂已完成状态，不是用户执行的维护动作。'),
 ('014','F','N','运行保持充液为运行工况要求；若重新表达需泵及完整工况端点，当前记录不是现成防护维护措施。'),
])
put('MP021:p0015:H29:', [
 ('014','A','L','检查传动对中动作与drive Component反向inspected_by；保留管路接好之后。'),
 ('015','A','L','泵Equipment与拆泵头塞尺检查反向inspected_by；机型Q/M/N等限定仍不可遗漏。'),
 ('016','C','L','同页010已有foreign objects Cause，可与安装入口滤网动作重组prevented_by；源文明确滤网阻异物进入。仍须保持正排量泵/入口等适用范围。'),
 ('017','C','L','同页012已有pump or piping will rupture Risk，可与封闭隔离管段装泄压装置重组prevented_by；须保留热膨胀/闭段条件，不能合并成所有泄压阀均足够。'),
 ('018','C','P','同页有rupture Risk，但该缺泄压阀时装排出管阀与15条封闭热膨胀风险未直接同一分支；仅潜在可用，不把同页共现当唯一配对。'),
 ('021','D','P','应维护/密封管路接头，当前head仅pipe sealer；已有端点无完整piping joints，需从原句All joints of the piping system新增实体。'),
 ('022','A','L','strainer Component与为隔离清洁设置旁通/双滤网措施可反向maintained_by；连续运行条件和两个替代方案均须保留。'),
 ('023','C','P','同页006已有casing distortion from piping strain FaultMode，原末尾pump casing is not distorted不可直接当故障；可重配变形事件和补偿措施，但热胀/管应变语境是否等价须裁定，不能只交换否定实体。'),
])

put('L01:', [
 ('002','D','P','pump Equipment不能作为causes原因；si-phoning action causing damage是复合片段，没有独立泵损坏端点，单交换仍不合法。须拆虹吸/损坏并绑定Otherwise。'),
 ('008','D','P','源文有reverse rota-tion，但菜单无独立反转ID；原pressure不是反转。须补断行合并后的反转实体。'),
 ('009','E','N','if高扬程是关阀动作条件，不能作为泵适用高扬程的独立事实；拒绝该脱离后件的主张。'),
 ('010','F','N','停泵前关闭阀门是运行操作，当前Schema没有一般运行步骤边，不能硬转维护。'),
 ('011','F','N','不是空气压缩机为类别否定，非operates_under；Schema无is_a/类别排除关系。'),
 ('016','D','P','需从整句独立提取will not prime故障端点，再与条件/泵建立允许关系；现有菜单仅设备和整个失效句。'),
 ('017','U','U','所选尺寸句不是真实Standard，且页尾to续页；完整目标和可行表示尚不确定。'),
])
put('L02:', [('009','D','P','air shaft在原句中，但菜单只有shaft短片段且包含后续另一型号分支；需完整air shaft端点和分支归属，不能仅沿用通用shaft。')])
put('L03:', [
 ('003','F','N','关系和英语检查对象基本成立，错误在seat被译为阀座而非静环座；需要术语修复，不是关系重构收益。'),
 ('005','F','N','波纹管15分钟就位/密封性为安装状态描述，非维护动作，现Schema无一般状态演化计时关系。'),
])
put('L04:', [
 ('003','D','P','u12将整页维护表当整步骤，只有整页动作和无关子动作，无独立橡胶密封随轴封更换动作。需按原列重新切动作及条件，单换已有端点不够。'),
 ('005','D','P','同上，轴承更换/检查动作未独立成正确菜单，整页动作混入轴封列；需恢复列内动作。'),
])
put('L05:', [
 ('001','D','P','head 25为整页statement并非Spike Energy方法实体；即使翻转diagnosed_by仍错，先补独立方法片段。'),
 ('002','D','P','同001：cavitation端点正确，方法是整页，需独立方法。'),
 ('003','D','P','同001且tail 6 bearing wear被中文改成loose fit；缺完整松配合端点，不能只反向。'),
 ('004','D','P','整页方法及bearing wear造成接触的完整目标未原子化；需至少独立方法片段。'),
 ('006','D','P','head 26为整页action，tail 1为Dry running而非磨损/疲劳/应力波；须新建完整目标与TSA片段，并辨识泵适用范围。'),
 ('007','D','P','同上，microwelding不在独立实体菜单，需新增方法及目标。'),
 ('008','D','P','同上，松动/摩擦/拍振没有完整独立端点，需补片段，不能拿Dry running改中文。'),
 ('009','F','N','TSA不适用滚动轴承的技术限制，当前diagnosed_by Component不合法且head仍整页；不能当正向泵诊断关系修复。'),
])
put('L06:', [
 ('001','F','N','油位设定是参数而非Component；改成某物理部件检查需要另定任务对象，不是修原两端关系。'),
 ('002','F','N','油位参数及图纸规范指向，当前物理Component/Standard角色定义不能完整承载。'),
 ('003','F','N','油位相对中心线的数值约束被写成部件工况，现有关系无参数比较/距离定义。'),
 ('004','F','N','图纸油位尺寸定义，当前Schema无参数定义关系。'),
 ('005','F','N','尺寸参考距离不等于located_in物理部件。'),
 ('009','D','P','头是BEARING CHAMBER THROUGH THE BASE OF THE OILER复合片段；需独立BEARING CHAMBER实体，再考虑maintained_by禁止灌注要求，不能只改关系。'),
 ('019','F','N','填料函功能目的不是运行工况；当前关系空间缺功能/用途。'),
 ('022','C','L','同u25 choice 2 stuffing box seal和8完整动作已存在；替换pumped liquid头并改maintained_by，保留通常不使用脏介质/应外供密封液完整要求。'),
 ('024','C','L','同u28已有6 glands与3完整推荐滴漏句，可作为glands operates_under完整工况；与假症状indicates工况区分。需保留原推荐模态。'),
 ('027','E','N','确保不过热仅重述目标，未给具体措施，不凭空造prevented_by。'),
 ('028','D','P','需独立overheating故障端点；u32只有flow rate/temperature stabilizes和此前否定过热片段，没有正向故障实体。阀门动作是另一潜在解释，不预设唯一。'),
 ('031','D','P','u35仅time和整动作，没有packing完整对象；需从原文补packing实体及其同一装填步骤绑定。'),
 ('032','B','L','gland和Never tighten...完整动作均已有，改maintained_by表达负向维护要求，保留Never及后果；编译接口是否容纳该否定要求仍需验证。'),
 ('033','D','P','头尾均为同一完整禁止句，需独立正向过紧原因、overheating及shaft sleeves wear后果；不能靠换causes方向或删除Never。'),
 ('042','D','P','u44仅stuffing box，没有bushing实体；必须补stuffing box bushing并保留if furnished。'),
])
put('L07:', [
 ('001','D','P','temperature→explosion→damage链中explosion缺独立端点，damage ID被译成复合死亡损害；需拆源文新实体。'),
 ('002','E','N','允许启动频率由温升决定不是频率导致温升，单翻转仍causes OperatingCondition，不能改写成源文未声明的因果。'),
 ('003','F','N','功率余量是参数，当前Schema没有它对允许频率的依赖关系。'),
 ('006','F','N','禁止未停稳重启是运行程序，原两端同一动作；不能强塞成维护/故障措施关系。'),
 ('008','D','P','tail pump物理词不是寿命缩短故障，需独立reduce the pump life完整后果及超BEP范围前件。'),
])
put('L08:', [
 ('007','C','P','u11已有8 pumps和21年检完整句，可重组inspected_by；但年度要求限定PMP/RCM设备，必须保留此条件且不把InspectionAction误当维护。'),
 ('008','E','N','劣化漏检说明不支持严重劣化causes总体振动不增的负向因果，不能只换关系挽救原主张。'),
 ('009','D','P','需overall measurement独立InspectionMethod与ISO specification，u22只有ISO/vibration和整句，无独立测量方法。'),
 ('010','F','N','频带外振动未必FaultMode，components产生信号并非当前occurs_at故障部位关系；换向仍不支持故障认定。'),
 ('011','E','N','检测频带盲区不是频带外振动导致总体不变的确定故障因果；不能由negative标签恢复。'),
])
put('L10:', [
 ('001','F','N','手册适用范围整句不是Standard对象；应保留元数据而非用specified_by充量。'),
 ('002','F','N','版本/发货适用规则为手册治理元数据，不是整句Standard实体。'),
 ('003','F','N','旧手册对在用产品适用性同上。'),
 ('009','D','P','u12只有pump suction和整句，没有EU/ASME/ISO/JIS flange standards独立对象；需补原文标准片段，且不能推断具体标准编号。'),
 ('010','F','N','过流材料不是物理Component；当前Schema无材料属性关系。'),
 ('011','F','N','材料等级不是OperatingCondition，不能以运行条件关系表示材质。'),
 ('014','F','N','产品分组说明为元数据，不是整句Standard。'),
 ('015','F','N','叶轮直径是参数，不是Component。'),
 ('017','F','N','两中心线齐平为几何约束，不是物理Component located_in Component。'),
])


def main():
    p29 = BASE/'ai_review_v1/holdout_comparison_v1'
    reg = read(ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json')['relation_registry']
    judgments = {r['review_id']: r for r in read(p29/'source_quality_judgments.jsonl')}
    mapping = {(r['candidate_id'], r['arm']):r['review_id'] for r in read(p29/'private_arm_mapping.jsonl')}
    outputs = read(p29/'outputs.jsonl')
    raw29 = {r['candidate_id']:r for r in outputs if r['arm']=='raw'}
    source29 = {r['page_key']:r for r in read(BASE/'ai_review_v1/heldout_sources/source_only.jsonl')}
    targets=[]
    categories={'relation_direction','relation_type','operation_role','scope_role','relation_meaning','unknown_relation'}
    for cid,r in raw29.items():
        a=r['payload'];j=judgments[mapping[cid,'raw']]
        digest=hashlib.sha256(json.dumps(a,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        assert digest==j['payload_sha256']
        if a.get('scope')!='background' and not a.get('record_kind') and reg.get(a['relation'],{}).get('core_diagnostic_relation') and j['verdict']=='E' and j['error_category'] in categories:
            arms={x['arm']:dict(included=x['included'],review=judgments[mapping[cid,x['arm']]]) for x in outputs if x['candidate_id']==cid}
            inventory=[dict(candidate_id=i,head=v['payload']['head_surface'],head_type=v['payload']['head_type'],tail=v['payload']['tail_surface'],tail_type=v['payload']['tail_type']) for i,v in raw29.items() if v['page_key']==r['page_key']]
            targets.append(dict(dataset='29页',candidate_id=cid,page_key=r['page_key'],original=r,original_review=j,archived_arms=arms,existing_endpoint_inventory=inventory,source_file='results/experiments/research_point_1/ai_review_v1/heldout_sources/source_only.jsonl',**ATTR[cid]))
    assert len(targets)==53
    v10=BASE/'sentence_step_extraction/validation'
    reviews={r['candidate_id']:r for r in read(v10/'source_review.jsonl')}
    sources10={r['page_key']:r for r in read(v10/'sources.jsonl')}
    decisions=read(v10/'decisions.jsonl')
    catalogs={name:read(v10/f'catalogs/{name}.json') for name in sorted({r['candidate_id'].split(':')[0] for r in decisions})}
    for r in decisions:
        cid=r['candidate_id'];j=reviews[cid]
        digest=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert digest==j['decision_sha256']
        if j['primary_target_scope_grade']!='E' and j['core_grade']=='E':
            cat=catalogs[cid.split(':')[0]]
            targets.append(dict(dataset='10页',candidate_id=cid,page_key=r['page_key'],original=r,original_review=j,existing_local_unit=cat['units'][r['unit_id']],source_file='results/experiments/research_point_1/sentence_step_extraction/validation/sources.jsonl',**ATTR[cid]))
    assert len(targets)==107 and {r['candidate_id'] for r in targets}==set(ATTR)
    for r in targets:
        r.update(attribution_status='analyst_feasibility_interpretation_not_new_truth_label',verified_new_recovery=0,new_candidate_generated=False,new_semantic_repair_executed=False)
        # Both original schema and inverse schema legality are diagnostics only.
        a=r['original'].get('payload')
        if a:ht,tt,rel=a['head_type'],a['tail_type'],a['relation']
        else:a=r['original'];ht,tt,rel=a['head']['type'],a['tail']['type'],a['relation']
        rule=reg.get(rel,{})
        r['original_schema_legal']=ht in rule.get('domain',[]) and tt in rule.get('range',[])
        r['swapped_schema_legal']=tt in rule.get('domain',[]) and ht in rule.get('range',[])
        if r['primary']=='A': assert r['swapped_schema_legal'],r['candidate_id']
        if r['primary']=='A' and r['candidate_id']!='MP021:p0015:H29:022':
            r['existing_code_coverage']='normalize_relation_direction already contains this type-level inverse rule; static inspection only, no source completeness or experiment success implied'
        elif r['candidate_id']=='L06:032':
            r['existing_code_coverage']='normalize_relation_direction already maps Component mitigated_by MaintenanceAction to maintained_by; prohibition support still unverified'
        else:
            r['existing_code_coverage']='No general complete repair path established by static inspection; limited related patterns described in REPORT.md. This is not an exhaustive runtime noncoverage proof.'
    save('record_attributions.jsonl',targets)
    summary={}
    for batch,size in [('29页',53),('10页',54)]:
        subset=[r for r in targets if r['dataset']==batch];counts=Counter(r['primary'] for r in subset)
        summary[batch]=dict(n=size,error_pages=len({r['page_key'] for r in subset}),classes={c:dict(count=counts[c],fraction=counts[c]/size,ids=[r['candidate_id'] for r in subset if r['primary']==c]) for c in 'ABCDEFU'},abc_source_local_clue_count=sum(r['primary'] in 'ABC' and r['basis_level']=='L' for r in subset),abc_possible_count=sum(r['primary'] in 'ABC' and r['basis_level']=='P' for r in subset),verified_automatic_complete_repair_count=0,static_existing_normalizer_pattern_count=sum(r['existing_code_coverage'].startswith('normalize_relation_direction') for r in subset))
    # Inventory counts, not candidate generation or semantic selection.
    menus=[]
    for name,cat in catalogs.items():
        for uid,u in cat['units'].items():
            n=len(u['choices'])
            menus.append(dict(catalog=name,unit_id=uid,page_key=f"{cat['doc_id']}:p{cat['target_page']:04d}",choices=n,ordered_pairs=n*(n-1),untyped_relation_pair_upper_bound=n*(n-1)*len(reg),row=u.get('row'),step=u.get('step'),source_characters=len(u['text'])))
    save('catalog_inventory.jsonl',menus)
    # Read prior losses/reference inventories solely as assessment context.
    lossmanifest=read(BASE/'knowledge_loss_summary_20261029/source_manifest.json')
    for p,h in lossmanifest['sha256'].items():
        raw=(ROOT/p).read_bytes();assert hashlib.sha256(raw).hexdigest()==h,p
        INPUTS[p]=h
    for p in ['knowledge_loss_summary_20261029/summary.json','knowledge_loss_summary_20261029/record_and_reference_ledger.jsonl','knowledge_loss_summary_20261029/recovery_targets.jsonl','loss_page_audit_v1/page_candidate_comparison_packets.jsonl','loss_page_audit_v1/pages_source_only.jsonl','ai_review_v1/holdout_comparison_v1/filter_repair_deltas.jsonl']:
        read(BASE/p)
    for p in (ROOT/'src/research_point_1_graph_evidence').rglob('*.py'):
        INPUTS[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ['scripts/aggregate_rp1_knowledge_losses.py','scripts/rp1_offline_contract_v3.py','scripts/review_rp1_holdout_v1.py']:
        INPUTS[p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    summary['limits']=dict(new_model_calls=0,new_extractions=0,new_repairs=0,original_labels_changed=0,interpretations_not_validated_repair_targets=True,counts_not_net_graph_gain=True,abc_l_means_local_relation_clue_not_complete_condition_success=True)
    save('summary.json',summary)
    with (OUT/'class_counts.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['dataset','class','count','denominator','percent'])
        for batch,size in [('29页',53),('10页',54)]:
            for c,r in summary[batch]['classes'].items():w.writerow([batch,c,r['count'],size,f"{r['fraction']*100:.2f}"])
    def esc(s):return str(s).replace('|','／').replace('\n',' ')
    md=['# 107条逐记录可重构性分析（非新语义标签）','', 'L=有明确局部关系线索，P=有可能但另有语义/结构前提，N=当前任务不重构，U=无法确定。L不代表条件完整或程序已验证。A/B保持原端点及类型；C复用已有可寻址片段；D需要补新的完整实体/动作片段。原始S/E/U保持不变。','']
    for batch in ['29页','10页']:
        md += ['## '+batch,'','| ID | 原始关系（源语片段） | 类别 | 依据层级 | 原因／边界 |','| --- | --- | --- | --- | --- |']
        for r in targets:
            if r['dataset']!=batch:continue
            a=r['original'].get('payload')
            if a:h,t,rel=a['head_surface'],a['tail_surface'],a['relation']
            else:a=r['original'];h,t,rel=a['head']['surface'],a['tail']['surface'],a['relation']
            md.append('| '+' | '.join(map(esc,[r['candidate_id'],h[:90]+' → '+rel+' → '+t[:100],r['primary'],r['basis_level'],r['analysis_reason']]))+' |')
        md += ['']
    (OUT/'RECORDS.md').write_text('\n'.join(md)+'\n')
    for p,h in INPUTS.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    save('source_manifest.json',dict(sha256=INPUTS,sources_unchanged=True,original_label_updates=0,analysis_only=True))
    print(json.dumps({k:v for k,v in summary.items() if k!='limits'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
