import streamlit as st

# ======================6条正式合同审查规则（法学组定稿）======================
RULE_LIST = [
    {
        "risk_level": "high",
        "label": "🔴高风险：卖方救济条款缺失",
        "desc": "合同全文未出现任何卖方救济相关条款。法定权利仍存在，但买方可能争议转售价格不合理、未给予履约机会等，大幅增加卖方举证难度和诉讼成本。",
        "suggest": "增加条款：如买方无正当理由拒收，卖方有权选择：①请求支付全部价款；②以合理方式转售并索赔差价及费用；③留置后续批次货物直至欠款结清。",
        "law_source": "UCC §2-703；CISG Art.61",
        "keywords": ["remedies", "seller's remedies", "转售", "resale", "留置", "lien", "停运", "stoppage", "价金请求", "price action"]
    },
    {
        "risk_level": "mid",
        "label": "🟡中风险：违约金条款缺失",
        "desc": "合同未约定违约金。违约时只能按实际损失索赔，卖方须自行举证损失金额（利润、附带费用等），举证困难、耗时长、赔偿金额不确定。",
        "suggest": "增加条款：任何一方违约的，应向守约方支付合同金额___%的约定违约金。双方确认该金额系基于违约时预估损害的合理估算。违约金不足以弥补实际损失的，守约方有权继续索赔差额。",
        "law_source": "UCC §2-718；CISG Art.74",
        "keywords": ["liquidated damages", "违约金", "约定损害赔偿", "late payment penalty", "penalty clause"]
    },
    {
        "risk_level": "mid",
        "label": "🟡中风险：检验期与异议期缺失",
        "desc": "合同未约定检验期和异议期，或未约定具体天数。买方可能在收货后任意时间提出质量异议，合理时间认定产生争议，卖方难以主张买方已丧失声称不符的权利。",
        "suggest": "增加条款：买方应在货物到达目的港后___日内完成检验，并在发现瑕疵后___日内向卖方发出书面异议通知，详细说明不符之处。逾期未提出书面异议的，视为货物完全符合合同约定。",
        "law_source": "UCC §2-602；CISG Art.38；CISG Art.39",
        "keywords": ["inspection", "检验", "claim period", "异议期", "notice of defect", "质量异议", "inspection period", "验收期限"]
    },
    {
        "risk_level": "high",
        "label": "🔴高风险：所有权保留条款缺失",
        "desc": "合同未约定所有权保留。货物所有权在交付时即转移给买方，即使买方尚未付款。卖方无法行使取回权或留置权，只能依赖价金请求和损害赔偿追款。",
        "suggest": "增加条款：在买方全额支付货款之前，货物所有权归卖方所有。买方未付清全部款项的，卖方有权取回货物，且买方应承担取回费用。所有权保留不影响风险转移和买方对货物的妥善保管义务。",
        "law_source": "中国《民法典》第641条；UCC Article 2（title retention）",
        "keywords": ["title retention", "所有权保留", "款清前所有权", "ownership reserved", "title does not pass", "所有权归卖方"]
    },
    {
        "risk_level": "mid",
        "label": "🟡中风险：法律适用条款缺失",
        "desc": "合同未约定适用法律。CISG自动适用（中美均为缔约国），对卖方相对有利；但如买方格式合同排除CISG，则适用美国州法UCC，UCC完美交付规则对卖方更不利。",
        "suggest": "增加条款：本合同适用《联合国国际货物销售合同公约》（CISG）。如CISG未规定的事项，适用中华人民共和国法律。或约定争议提交CIETAC/HKIAC仲裁。",
        "law_source": "CISG Art.1；中国《法律适用法》第41条",
        "keywords": ["governing law", "适用法律", "this agreement shall be governed by", "applicable law", "准据法"]
    },
    {
        "risk_level": "mid",
        "label": "🟡中风险：不可抗力条款过于笼统",
        "desc": "仅有force majeure或不可抗力免责等笼统表述，未列明具体情形。港口罢工、海运延误、疫情等是否属于不可抗力产生重大争议，双方可能陷入长期诉讼。",
        "suggest": "增加条款：不可抗力包括但不限于：战争、地震、洪水、火灾、政府禁令、流行病。以下情形不属于不可抗力：港口罢工、海运延误、船期变更、原材料涨价。遭受不可抗力的一方应在___日内书面通知对方，并提供官方证明。",
        "law_source": "CISG Art.79；中国《民法典》第180条",
        "keywords": ["force majeure", "不可抗力", "免责", "excused from performance"]
    }
]

# ======================20条法律知识库（法学组定稿）======================
KNOWLEDGE_BASE = [
    {"title": "第1条 买方无正当理由拒收货物，卖方有哪些救济选择？", "content": "根据CISG第61条和UCC §2-703，买方无正当理由拒收货物构成违约。卖方不能强行要求买方收货，而是有三种救济方式可选：请求支付全部价款、合理转售并索赔差价、留置后续货物。建议：先书面通知买方其已违约；评估货物是否易于转售；如不易转售（定制家具），直接要求支付全部货款；如易于转售，尽快寻找新买家，保留转售记录。", "keywords": ["拒收货物", "卖方救济", "CISG 61", "UCC 2-703", "转售权", "价金请求权", "留置权"]},
    {"title": "第2条 买方拖欠货款，卖方的价金请求权与逾期利息怎么算？", "content": "根据CISG第62条，卖方有权要求买方支付货款。根据CISG第78条，拖欠期间卖方有权收取利息。UCC §2-709同样赋予卖方价金之诉权利。建议：先发书面催款通知，限定付款期限；保留所有交货单据、验收记录；如合同约定了利息，按约定利率计算；无约定按法定商业利率。", "keywords": ["拖欠货款", "价金请求权", "CISG 62", "CISG 78", "逾期利息", "UCC 2-709"]},
    {"title": "第3条 货还在运输途中，买方破产或拒收——停运权怎么用？", "content": "根据CISG第71条，买方明显将不履行大部分义务时，卖方可以中止运输。根据UCC §2-705，卖方可以停运（stoppage in transit），只要货物仍在承运人占有下且买方尚未提货。建议：立即书面通知承运人停止交货；确认正本提单仍在手；同时书面通知买方其违约及停运事实。", "keywords": ["停运权", "CISG 71", "UCC 2-705", "买方破产", "承运人", "阻止交货"]},
    {"title": "第4条 上一批货款未付清，能否扣留下一批货？（留置权）", "content": "根据CISG第58条，买方应在卖方交货时付款，卖方享有实质意义上的同时履行抗辩权。根据UCC§2-703，卖方对尚在占有下的货物享有留置权。中国《民法典》第447条也规定了留置权。建议：书面通知买方因上一批货款未付清，暂停发运后续货物；明确告知付清欠款后立即发运。", "keywords": ["留置权", "lien", "扣货", "同时履行抗辩", "CISG 58", "UCC 2-703", "民法典447"]},
    {"title": "第5条 买方不要了，卖方转售货物减少损失，差价和费用由谁承担？", "content": "根据CISG第75条，卖方可以替代交易（cover），向买方索赔原合同价与转售价的差额，以及合理的附带费用。UCC §2-706同样允许合理转售并索赔差价。建议：转售必须是合理的（时间、地点、方式）；保留转售合同、发票、付款记录；书面通知买方转售事实及索赔金额。", "keywords": ["转售", "减损义务", "CISG 75", "UCC 2-706", "差价赔偿", "cover", "附带费用"]},
    {"title": "第6条 买方违约导致原材料/半成品积压，附带损失怎么索赔？", "content": "根据UCC §2-710，卖方可以索赔附带损失（incidental damages），包括仓储费、运输费、保管费等。CISG第74条也允许索赔可预见的损失。建议：保留备料合同、付款凭证、仓储单据；证明备料是专门用于该订单的；计算合理的仓储、资金占用损失。", "keywords": ["附带损失", "UCC 2-710", "备料损失", "仓储费", "CISG 74"]},
    {"title": "第7条 损害赔偿包括利润损失吗？怎么计算？", "content": "根据CISG第74条，损害赔偿包括利润损失（loss of profit），但必须是违约方预见或应预见的损失。UCC §2-708(2)同样允许索赔利润损失。利润计算方式：合同价 - 可变成本；或参考同类订单的历史利润率。", "keywords": ["利润损失", "损害赔偿", "CISG 74", "UCC 2-708", "可预见性", "间接损失"]},
    {"title": "第8条 合同约定的违约金，美国法院认不认？比例多少算合理？", "content": "美国法区分约定违约金（liquidated damages，有效）和惩罚性违约金（penalty，无效）。UCC §2-718要求违约金必须是预估损害的合理约定，而非惩罚。违约金比例一般不超过预估实际损失的20-30%；条款应写明双方确认该金额为预估损害的合理估计，非惩罚。", "keywords": ["违约金", "UCC 2-718", "惩罚性违约金", "预估损失", "合理估计"]},
    {"title": "第9条 买方以轻微瑕疵拒收全部货物，合法吗？", "content": "一般情况下，CISG第25条规定只有根本违约才能解除合同/拒收全部，轻微瑕疵不构成根本违约。UCC §2-608要求撤销接受必须证明实质性损害。例外：CISG第40条，如果卖方发货时明知货物存在瑕疵，则卖方无权以买方未及时检验通知为由抗辩。建议：要求买方具体说明瑕疵性质、程度、数量及照片证据；如属轻微瑕疵，书面反驳其不构成根本违约，提出修补、降价等替代方案。", "keywords": ["根本违约", "轻微瑕疵", "CISG 25", "CISG 40", "明知瑕疵", "减价权", "UCC 2-601", "实质性损害", "拒收全部"]},
    {"title": "第10条 信用证被拒付了，卖方还能找买方要钱吗？", "content": "信用证具有独立性（UCP600第4条），银行拒付不影响买方对卖方的付款义务。根据CISG第54条，买方有义务按合同约定付款。信用证只是付款方式，不是唯一方式。建议：立即要求银行说明拒付的具体不符点；如不符点可补正，尽快补交单据；如无法补正，直接书面要求买方以电汇（T/T）等其他方式付款。", "keywords": ["信用证", "UCP600", "单据不符", "独立性原则", "CISG 54", "电汇", "买方付款义务"]},
    {"title": "第11条 合同没写买方拒收时卖方可转售——缺救济条款的风险", "content": "根据UCC §2-703及细分条文§2-706（转售权）、§2-709（价金请求权）、§2-705（停运权），以及CISG第61条和第75条，卖方在买方拒收时本来享有转售权、价金请求权和停运权。但如果合同里完全没有约定这些救济方式，虽然法定权利仍然存在，实际操作中买方可能争议转售价格不合理、未给予履约机会等，增加卖方举证难度和诉讼成本。", "keywords": ["救济条款", "卖方权利", "合同缺失", "转售权", "举证困难"]},
    {"title": "第12条 合同没写违约金——只能按实际损失索赔，举证困难", "content": "根据UCC §2-718和CISG第74条，合同没有约定违约金时，卖方只能就实际损失索赔。这意味着卖方必须举证证明自己的实际损失金额，包括利润损失、附带费用等，举证难度大、耗时长，且赔偿金额不确定。注意：美国UCC没有规定违约金比例的固定上限，判断标准是该金额是否为签约时对违约损害的合理预估。", "keywords": ["违约金条款", "实际损失", "举证困难", "合同缺失", "约定违约金"]},
    {"title": "第13条 合同没写检验期和异议期——货到多久算默认接受？", "content": "根据UCC §2-606及§2-602，买方必须在合理时间内检验并拒收、通知卖方，否则视为接受。CISG第38条要求买方在尽可能短的时间内检验货物；CISG第39条要求买方在发现或理应发现不符后合理时间内通知卖方。如果合同没有约定具体检验期和异议期，合理时间的认定容易产生争议。重要例外：CISG第40条规定，如卖方已知或不可能不知货物与合同不符而未告知买方，则买方不受检验异议期的限制。", "keywords": ["检验期", "异议期", "UCC 2-606", "CISG 38", "CISG 39", "CISG 40", "默认接受", "书面通知"]},
    {"title": "第14条 合同没写所有权保留——钱没收到，货权已转移", "content": "如果合同没有约定所有权保留条款，货物所有权通常在交付时转移给买方。即使买方还没付款，货物法律上已经属于买方，卖方无法行使取回权或留置权。中国《民法典》第641条明确规定了所有权保留制度，但须经登记才能产生对抗效力。美国UCC下，所有权保留在实质上构成担保权益，须按UCC Article 9的规定提交UCC-1融资声明完成登记，才能对抗第三人。", "keywords": ["所有权保留", "title retention", "货权转移", "民法典641", "登记对抗", "UCC-1", "取回权"]},
    {"title": "第15条 合同没写法律适用——用中国法还是美国法？", "content": "根据CISG第1条，如果中美两国都是缔约国，且合同没有排除CISG，则CISG自动适用。但如果合同明确约定适用美国某州法或排除CISG，则适用该州UCC规则。UCC对卖方的保护通常不如CISG——典型如UCC的完美交付规则（perfect tender rule，UCC §2-601），要求卖方交付的货物必须在各方面严格符合合同约定，否则买方有权拒收全部货物；而CISG下仅在根本违约时买方才能宣告合同无效，对卖方更为宽容。", "keywords": ["法律适用", "governing law", "CISG 1", "完美交付规则", "排除CISG"]},
    {"title": "第16条 不可抗力条款写得笼统——疫情、港口罢工算不算？", "content": "根据CISG第79条，当事人对非其所能控制的障碍免责，但该障碍须满足：订立合同时不能合理考虑到、不能合理避免或克服、且当事人不能防止其后果。CISG第79条本身不列举任何具体不可抗力情形，全部由合同约定。CISG第79条第4款还规定了法定通知义务：遭受障碍的一方必须将障碍及其对履约能力的影响在合理时间内书面通知对方，否则对未通知造成的损失承担赔偿责任。", "keywords": ["不可抗力", "force majeure", "CISG 79", "通知义务", "港口罢工", "海运延误", "民法典180"]},
    {"title": "第17条 FOB vs CIF——交货条件不同，卖方救济权利和风险转移有什么不同？", "content": "根据Incoterms® 2020，FOB（装运港船上交货）和CIF（成本加保险费运费）的风险转移点都是在装运港货物装上船时。但CIF下卖方负责投保和支付运费，FOB下由买方负责。重要提示：Incoterms是国际商会制定的贸易惯例，仅处理货物交付中的风险划分、费用承担和单据义务，不处理货物所有权转移、违约救济、争议解决等法律问题。", "keywords": ["FOB", "CIF", "Incoterms", "风险转移", "救济时机", "运费", "保险"]},
    {"title": "第18条 仲裁赢了美国买方，裁决在美国能强制执行吗？", "content": "中国和美国都是1958年《纽约公约》缔约国。根据《纽约公约》第III条，缔约国应承认和执行外国仲裁裁决。美国联邦仲裁法（FAA）第207条规定，美国联邦法院必须确认仲裁裁决，除非存在公约第V条规定的拒绝情形。美国法院原则上不审查实体对错，只审查程序合法性，成功率很高。", "keywords": ["纽约公约", "FAA", "仲裁执行", "跨境执行", "承认与执行", "香港仲裁"]},
    {"title": "第19条 约定在美国法院起诉，佛山卖家要飞美国打官司吗？", "content": "如果合同约定争议由纽约州法院管辖，一旦发生纠纷，卖方通常需要在美国应诉，这意味着高昂的律师费、差旅费和诉讼成本。美国法院实行长臂管辖，即使卖方在中国，只要合同与美国有足够联系，美国法院就可以管辖。更重要的是，中美之间没有互相承认和执行法院民商事判决的双边条约——这意味着中国法院的判决在美国没有条约义务必须承认，美国法院的判决在中国同样没有条约保障。强烈建议改为仲裁条款。", "keywords": ["管辖权", "jurisdiction", "长臂管辖", "纽约法院", "应诉成本", "判决互认", "仲裁替代"]},
    {"title": "第20条 买方突然违约，72小时证据保全与行动清单", "content": "第1步（0-24小时）：保存所有证据——合同、订单、邮件、聊天记录、发货单、提单、质检报告，全部备份；如货物仍在途中且买方已丧失清偿能力或显然将不履行主要义务，立即书面通知承运人停运，并同步书面通知买方。第2步（24-48小时）：发正式书面违约通知给买方，要求其限期履约或说明理由；咨询律师评估是否需要申请诉前财产保全。第3步（48-72小时）：评估货物状态，决定是否转售；如买方在国内有财产且可能转移，准备材料向有管辖权的法院申请诉前保全。", "keywords": ["72小时", "证据保全", "诉前保全", "行动清单", "停运通知", "insolvency"]}
]

# ======================功能函数======================
def scan_contract_risk(text):
    """合同风险扫描：6条正式规则，关键词全部未命中则触发风险"""
    hit_result = []
    for rule in RULE_LIST:
        has_keyword = any(kw.lower() in text.lower() for kw in rule["keywords"])
        if not has_keyword:
            hit_result.append(rule)
    return hit_result

def search_kb(query):
    """法律咨询：关键词检索20条知识库"""
    output = []
    for item in KNOWLEDGE_BASE:
        for kw in item["keywords"]:
            if kw.lower() in query.lower():
                output.append(item)
                break
    return output

# ======================会话初始化======================
if "lang" not in st.session_state:
    st.session_state["lang"] = "zh"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

lang_choice = st.radio("", ["中文", "English"], horizontal=True)
st.session_state["lang"] = "zh" if lang_choice == "中文" else "en"
current_lang = st.session_state["lang"]

TEXT_DICT = {
    "zh": {
        "title": "面向对美出口卖方的跨境违约救济AI预审系统",
        "tab_contract": "📄合同预审",
        "tab_chat": "💬智能法律咨询",
        "input_hint": "粘贴合同片段或者描述贸易纠纷事实",
        "submit_btn": "提交预审",
        "chat_placeholder": "请输入你的跨境法律问题",
        "disclaimer_text": "本系统提供的法律信息仅供参考，不构成正式法律意见，不可替代执业律师服务。风险等级仅为初步提示，不代表确定性法律判断。涉及重大法律事项，请咨询执业律师。因使用本系统信息产生的损失，开发团队不承担法律责任。",
        "report_title": "📋合同风险体检报告",
        "risk_stat": "风险统计｜🔴高风险:{h} 🟡中风险:{m}",
        "expand_law": "📖查看法条依据与补正建议",
        "empty_warn": "请输入合同文本！"
    },
    "en": {
        "title": "Cross-border Breach Remedy AI Pre-review System for US-oriented Exporters",
        "tab_contract": "📄Contract Pre-review",
        "tab_chat": "💬Legal Chat",
        "input_hint": "Paste contract text or describe trade dispute facts",
        "submit_btn": "Submit Review",
        "chat_placeholder": "Input your cross-border legal question",
        "disclaimer_text": "Legal information provided by this system is for reference only, does not constitute formal legal advice, and cannot replace licensed lawyer services. Risk levels are preliminary indications only and do not represent definitive legal judgments. For major legal matters, please consult a licensed lawyer. The development team shall not be liable for any losses arising from the use of this system's information.",
        "report_title": "📋Contract Risk Report",
        "risk_stat": "Risk Summary｜🔴High:{h} 🟡Medium:{m}",
        "expand_law": "📖Legal Reference & Suggestion",
        "empty_warn": "Please input contract content!"
    }
}
text = TEXT_DICT[current_lang]

# ======================页面主体======================
st.title(text["title"])
tab_contract, tab_chat = st.tabs([text["tab_contract"], text["tab_chat"]])

# Tab1：合同预审
with tab_contract:
    contract_input = st.text_area(label=text["input_hint"], height=260)
    click_submit = st.button(text["submit_btn"])
    if click_submit:
        if not contract_input.strip():
            st.warning(text["empty_warn"])
        else:
            risk_items = scan_contract_risk(contract_input)
            st.subheader(text["report_title"])
            count_high = sum(1 for r in risk_items if r["risk_level"] == "high")
            count_mid = sum(1 for r in risk_items if r["risk_level"] == "mid")
            st.info(text["risk_stat"].format(h=count_high, m=count_mid))
            for risk in risk_items:
                st.markdown(f"**{risk['label']}**")
                st.write(risk["desc"])
                with st.expander(text["expand_law"]):
                    st.markdown("**法律依据：**")
                    st.write(risk["law_source"])
                    st.markdown("**建议补正条款：**")
                    st.write(risk["suggest"])

# Tab2：智能法律咨询
with tab_chat:
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    user_question = st.chat_input(text["chat_placeholder"])
    if user_question:
        st.session_state["chat_history"].append({"role": "user", "content": user_question})
        kb_result = search_kb(user_question)
        if kb_result:
            answer_text = "\n\n".join([f"**{k['title']}**\n{k['content']}" for k in kb_result])
        else:
            answer_text = "未匹配到对应知识库条文，请换一种描述。"
        st.session_state["chat_history"].append({"role": "assistant", "content": answer_text})
        st.rerun()

# 底部正式免责声明
st.divider()
st.caption(text["disclaimer_text"])
