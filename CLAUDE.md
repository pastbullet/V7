# V7 项目原则（Claude / 任何 agent 先读这个）

V7 = 协议抽取管线的 clean rebuild。核心转变：抽取从【staged 碎片抽 + 确定性 merge 拼关系】
改为【发现(orientation) + 逐单元 agentic-RAG 整体读 + 薄结构化 + 两层 verify】，下游 profile→生成→审计保留。
架构细节见同目录 `V7_REFACTOR_ARCHITECTURE.md`；当前进度见 `WORK_SUMMARY.md`。

## 承重原则（最重要，违背就是方向错）

1. **语义决策 → LLM；规则只 verify 结构。**
   - 不把语义逻辑写进规则；不堆规则假装泛化——**generalization 就是 claim**。
   - **完整性来自 LLM 整体读，不是规则拼碎片。** （V6 的根本病：staged 碎片抽+merge 丢跨字段/跨页/条件关系。）

2. **先验可用，但必须 gate。**
   - evidence-gated，非 prior-free。**user-0-prior（用户 0 先验），非 model-0-prior。**
   - LLM 可用先验帮【读 / 理解】，但【事实必须来自 spec 原文 span】。
   - **cite 必须被 verify**（prior-leakage gate：引了哪页，就要验那页【真支持】这条事实，抓"引了但页面没说"）。

3. **LLM-propose / rule-verify，在每一层都用**（发现 / 逐单元读 / 选片）。
   - propose = LLM（语义、可变异）；verify = 规则（结构 / provenance / schema / coverage）。
   - agent 变异不破坏可审计：每个事实带 provenance + 被 verify。

4. **user-0-prior = 不预设单元。**
   - 不能假设"去抽 FLOGI"（那是把作者先验偷塞进系统）。
   - orientation 是【发现层】：导航 spec → 枚举【有哪些 flow / FSM / message】，**不给定列表**；
     发现的单元对照【spec 自带目录】核覆盖（如 FC-LS 的 ELS 命令表 / 状态表），防"静默漏单元"。

5. **中间体（md / mermaid / 表）非事实源。**
   - 它是【整体读的完整忠实呈现 + 可审计中间视图】，但 **IR 的 grounding 指向【原文 span / 表 cell / 图 crop】**。
   - 图 crop / 原文 span = 事实源；中间体可核但不是源。

6. **协议中立。** 通用代码无硬编码协议 token；token 只在 test fixture / 用户 goal / 生成 artifact。

7. **重心 = 可用生成代码。** 审计是 emergent 后续 / 新颖性所在，但**毕设交付物是能跑的代码**。"生成=commodity"只指新颖性不在生成，≠ 不用做出能用的。

8. **vertical-first。** 先把一条端到端 vertical 跑通（一个单元：发现→读→IR→生成→审计），再泛化。**别先建通用系统、零可运行产物。**

9. **verify on real artifact。** live run 是金标准，unit/mock ≠ done。agent 是否可靠当【测量题】（测完整性+一致性），不当【信任题】。

## 工作纪律

- **全程中文回复。**
- **codex = binding peer reviewer**：spec / plan 过 codex review 再 commit。
- **绝不自动 commit / git add**，除非明确要求；不碰 .env / secrets；不改 git config；不 skip hooks。
- 不做 "we beat LLM X" 的 framing；讲 model-agnostic 的可靠性属性（variance / consistency / coverage / provenance / schema）。
- read-before-act：用户已给完整分析时，别再从头翻文件。
