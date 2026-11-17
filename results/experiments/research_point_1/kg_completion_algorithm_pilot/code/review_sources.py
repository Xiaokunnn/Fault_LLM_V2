"""Save the executing assistant's bounded source reading, NOT an automatic judge.

The 24 decisions below were written after reading every saved native unit and
the complete corresponding MP022 page. They are disclosed AI audit judgments;
re-running serialization is not another independent evaluation.
"""
from collections import Counter
from common import RUN, read, save, file_sha


# review_id: grade, local requirements, source-based reasoning.
DECISIONS = {
 'R01': ('C', 'LKH Prime安装预检查、装配次序及前盖O形圈(59)的前置安装', 'p18明确要求fit and align front cover (60)，但这是安装预检查Step4的第3项，不是任意工况的无条件维护指令。'),
 'R02': ('C', '该泵轴封拆卸阶段Step7及相应工具/左旋螺纹提示', 'p29原文Remove the stationary seal ring (11)支持动作对象，阶段及工具提示未进入预测。'),
 'R03': ('C', '先拆完整轴封、再执行Step10第2项；不能混用双机械密封Step8', 'p30区分Step8和Step10，后者明确从drive ring (10)拆spring (13)和rotating seal ring (14)。预测只保留拆弹簧。'),
 'R04': ('C', '安装前旋转方向预检查；禁止叶轮已装而泵壳拆下时启动', 'p17支持Remove impeller (27)，但不能脱离pre-check及启动禁令作为一般运行建议。'),
 'R05': ('C', '安装前方向检查、放气螺钉(58)、扳手并用螺丝刀反向支撑', 'p17第4项含Remove air screw (58) with a spanner及Counter hold with a screwdriver。气塞螺钉仅作该局部源语别称，不能据此确认全局同义；预测漏反向支撑及阶段。'),
 'R06': ('E', '单轴封装配；区分被装配对象与承载位置', 'p32主动作对象是complete shaft seal，stub shaft (7)是安装位置。不能仅因onto共现就认定短轴本身的维护方式为该动作。属于当前证据下的角色不支持，不等于全局事实为假。'),
 'R07': ('C', '污染的盲螺纹孔、分支对象、酸消毒/刷洗后冲洗吹干及后续拭子测试；轴孔分支限Prime10/20', 'p27两个清洗分支均有rinse/blow-dry，但threaded hole泛称未绑定盲孔对象、步骤和适用型号。不能把这一步提升为完整清洁程序。'),
 'R08': ('E', '区分泄漏本体与泄漏液收集/后果控制', 'p14只建议在轴封泄漏时用drip tray收集流出液；没有说它缓解泄漏故障本身。当前FaultMode→mitigated_by缺少这一语义桥接，不能用常识补足。'),
 'R09': ('E', '轴封泄漏后收集，不是防止轴封泄漏发生', 'p14 In case of shaft seal leakage明确是泄漏发生后的收集措施，不支持prevented_by。'),
 'R10': ('U', '需独立源文', '固定检索未提供MP022源文支持。名称自反式检查并非证据，也不能据无命中判为假。'),
 'R11': ('U', '需独立源文及过度润滑判据', '固定检索未提供MP022证据，无法确认通用检查是否针对过润滑有效。'),
 'R12': ('U', '需独立源文、材料角色及适用设备', '固定检索未提供MP022证据；不能从名称相近证明标准绝缘的维护方式。'),
 'R13': ('U', '需独立源文及润滑不足判据', '固定检索未提供MP022证据。不得把检查轴承润滑的合理性作为文档支持。'),
 'R14': ('C', '指定轴封装配Step7的返拆组合、反向支撑及后续扭矩/重装顺序', 'p41明确列出三件同时拆卸，预测保留组合对象，但未保留所处步骤和后续装配联系。'),
 'R15': ('C', '安装前预检查；扳手拆卸时螺丝刀反向支撑', 'p17原文动作和(58)一致，但预测漏Counter hold及阶段。'),
 'R16': ('C', '单轴封装配Step8，先装泵壳/垫圈并按规定扭矩紧固', 'p34第2项是Adjust pump casing (29) to correct position，不能脱离已安装及紧固的前置步骤。'),
 'R17': ('C', '该泵该步骤的screws(6)、均匀紧固、15 Nm、反向支撑', 'p41支持特定螺钉(6)的15 Nm，不支持任意螺钉均用该扭矩。预测head仅螺钉，型号/编号绑定不足。'),
 'R18': ('C', '双机械轴封装配Step12、护罩(22)与螺钉(23)', 'p38原文支持该动作组合；预测无该装配阶段。无冲洗接口时孔由护罩遮挡是说明，不能提升为所有装护罩的前提。'),
 'R19': ('C', '维护矩阵的列对象、单班预防12个月/泄漏后当日/计划维护泄漏后等分支', 'p26矩阵支持更换complete shaft seal，但泛化更换轴封遗漏周期、触发条件及橡胶件/轴承列区分。OCR重复文字不被当成重复事实。'),
 'R20': ('C', '安装前旋转方向检查，Step1第3项；卡箍(57)和前盖(60)联合拆卸', 'p17直接支持联合动作，但预测省略阶段和前置步骤。'),
 'R21': ('C', '单轴封装配Step3、短轴(7)、Connex pin(8)进入drive ring(10)缺口', 'p32直接支持安装完整轴封，且紧接注意Connex pin啮合要求；预测没有此绑定。'),
 'R22': ('S', '保留LKH Prime泵和文档适用范围；after service已在动作中', 'p25明确Check the pump for smooth operation after service。对象、动作与维修后阶段均在预测文字中；不把该检查解释为完整维修程序或安全认证。'),
 'R23': ('E', 'O-ring(44)与O-rings(15)是不同编号/位置', 'p35明确(44)涂润滑后滑至seal housing(40a)，而装入rotating seal rings(14)的是(15)。同页共现不支持预测配对。'),
 'R24': ('S', '保留LKH Prime双机械轴封装配文档范围；before fitting已在动作中', 'p35明确Lubricate the rubber seals before fitting them。当前原子关系及先润滑后安装在预测中均保留；没有声称所有泵所有密封均可同等迁移。'),
}


def main():
    packets=read(RUN/'discovery/review_packets.jsonl')
    mapping={r['review_id']:r for r in read(RUN/'discovery/review_private_mapping.jsonl')}
    assert {r['review_id'] for r in packets}==set(DECISIONS)
    reviewed=[];layers={k:[] for k in ['source_explicit','source_conditional','source_supported_non_independent','source_mismatch','inference_only']}
    for packet in packets:
        rid=packet['review_id'];grade,required,reason=DECISIONS[rid];m=mapping[rid];ind=m['independence']
        independent_text=bool(packet['source_units']) and ind['document_withheld'] and not ind['possible_training_text_duplicates']
        row=dict(review_id=rid,prediction_id=m['prediction']['prediction_id'],head=packet['head'],relation=packet['relation'],tail=packet['tail'],
            grade=grade,reviewer='Executing Codex assistant; AI source reading, not human/expert or independent-model Gold',
            blind_limit='Packets omit method/score; executing assistant also knows aggregate results and private mapping. No double-blind claim.',
            source_doc=packet['document'],source_page=packet['source_page'],source_unit_ids=[u['unit_id'] for u in packet['source_units']],
            evidence_texts=[u['text'] for u in packet['source_units']],reason=reason,required_context=required,
            document_scope=packet.get('source_metadata',{}).get('applicability_scope'),
            source_document_text_independent=independent_text,strict_warm_endpoint_evidence_eligible=ind['strict_independent_evidence_eligible'],
            novelty_class=m['prediction']['novelty_class'],trained_on_review_text=False,publication=False,
            new_complete_fact_confirmed=False)
        # S retains explicit document applicability in this audit sidecar only.
        if grade in ['S','C'] and not independent_text:layer='source_supported_non_independent'
        else:layer={'S':'source_explicit','C':'source_conditional','E':'source_mismatch','U':'inference_only'}[grade]
        row['layer']=layer;reviewed.append(row);layers[layer].append(row)
    save(RUN/'discovery/AI_source_review.jsonl',reviewed)
    for name,rows in layers.items():save(RUN/'discovery/layers'/(name+'.jsonl'),rows)
    save(RUN/'discovery/source_review_summary.json',dict(n=len(reviewed),grades=dict(Counter(r['grade'] for r in reviewed)),
        layers={k:len(v) for k,v in layers.items()},source_document_text_independent=sum(r['source_document_text_independent'] for r in reviewed),
        strict_warm_endpoint_independent=sum(r['strict_warm_endpoint_evidence_eligible'] for r in reviewed),
        conditional_new_pair_leads=[r['review_id'] for r in reviewed if r['grade']=='C' and r['novelty_class']=='beyond_both_pools'],
        new_complete_verified_facts=0,formal_graph_changes=0,
        packets_sha256=file_sha(RUN/'discovery/review_packets.jsonl'),
        limitations='Purposive 24-case diagnostic sample, one withheld manual, same executing AI reviewer; no accuracy estimate, expert Gold, cross-model agreement or global novelty certificate. S is local source support with scope attached here, not an extraction accuracy label.'))
    lines=['# 24条预测的AI源文核查\n','实际阅读固定MP022原生片段及完整页后逐条判断。S=在文档范围内支持该原子关系且关键局部时序在动作中；C=有局部依据但必须补条件/编号/步骤；E=当前证据不支持该角色/关系；U=当前检索证据不足。不是盲态独立模型或专家评价，也不估计全体预测准确率。\n',
           '| ID | 预测 | 物理页 | 判定 | 证据与限制 |','| --- | --- | --- | --- | --- |']
    for r in reviewed:lines.append(f"| {r['review_id']} | {r['head']} → {r['relation']} → {r['tail']} | {r['source_page']} | {r['grade']} | {r['reason']} 必须保留：{r['required_context']}。 |")
    save(RUN/'discovery/SOURCE_REVIEW.md','\n'.join(lines)+'\n')
    print('Saved actual AI source reading:',Counter(r['grade'] for r in reviewed))


if __name__=='__main__':main()
