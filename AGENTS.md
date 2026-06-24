# V7 项目原则（任何 agent 先读）

> 完整版见 `CLAUDE.md`；架构见 `V7_REFACTOR_ARCHITECTURE.md`；进度见 `WORK_SUMMARY.md`。
> 此处是任何 agent 都必须遵守的承重原则浓缩。

V7 = 抽取从【staged 碎片抽 + merge 拼关系】→【发现(orientation) + 逐单元 agentic-RAG 整体读 + 薄结构化 + 两层 verify】→ profile→生成→审计。

## 承重原则

1. **语义 → LLM；规则只 verify 结构。** 不把语义写进规则；不堆规则假装泛化（generalization 就是 claim）。**完整性来自 LLM 整体读，不是规则拼碎片。**

2. **先验可用，但必须 gate。** user-0-prior（用户 0 先验，非 model-0-prior）。LLM 用先验帮【读】，**事实必须来自 spec 原文 span**；**cite 必须 verify（prior-leakage gate：引哪页就验那页真支持）**。

3. **LLM-propose / rule-verify，每一层都用。** propose=LLM（语义、可变异）；verify=规则（结构/provenance/schema/coverage）。变异不破坏可审计：每事实带 provenance + 被验。

4. **user-0-prior = 不预设单元。** 不能假设"去抽 FLOGI"。orientation 是【发现层】：枚举有哪些 flow/FSM/message（不给定），对 spec 自带目录（ELS 表/状态表）核覆盖，防静默漏单元。

5. **中间体（md/mermaid/表）非事实源。** 可审计中间视图，但 **IR grounding 指向原文 span / 表 cell / 图 crop**。crop/span = 源，中间体可核但不是源。

6. **协议中立。** 通用代码无协议 token；token 只在 fixture / goal / artifact。

7. **重心 = 可用生成代码。** 审计是新颖性所在，但交付物是能跑的代码。

8. **vertical-first。** 先一条端到端 vertical 跑通（一个单元），再泛化。别先建通用系统。

9. **verify on real artifact；agent 可靠性当测量题不当信任题。**

## 纪律
- 全程中文。codex review 后才 commit。**绝不自动 commit / git add**；不碰 .env；不改 git config；不 skip hooks。
- 不做 "beat LLM X" framing；讲可靠性属性（variance/consistency/coverage/provenance/schema）。
