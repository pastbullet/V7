# V7 重构架构文档

Date: 2026-06-23
作者: 与 Claude 协作整理
目的: 说明 V6 当前实现、遇到的根本问题、以及 V7 应有的新架构。准备据此重构。

---

## 0. 一句话

V6 当年【主动排除了 M1 的 agentic-RAG / PageIndex 路线】，改用"分阶段抽取 + 确定性合并"的 staged 管线；
实测下来 staged 管线【系统性地丢失跨字段/跨页/条件关系】（完整性不足），而被排除的 agentic-RAG 路线反而【读得完整、带引用、可 review】。
**V7 = 把 agentic-RAG 整体读（PageIndex 式）请回来当抽取前端，发现层(orientation)负责"不预设地发现单元"，薄结构化层把完整阅读落成 grounded IR，下游 profile→生成→审计保留。**

---

## 1. V6 当前实现（是什么）

### 1.1 定位（V6 README 原话）
- V6 = "a clean sibling rebuild of the protocol extraction pipeline from m1"。
- 保留 m1 的 orientation / route-mode / review / public-view / deliverable / codegen 架构。
- **明确隔离/排除**（README "Quarantined or excluded"）：`Old RAG/pageindex/context/web/alignment code`、old monolithic pipeline、old agentic repair。
- 现状：**migration-complete, NOT clean-room-complete**。README 承认仍 pending：`Extractor contracts and prompts`、`Reviewed-record to IR materialization`、`Message archetype lowering`。

### 1.2 V6 的 spine（分阶段 staged 管线）
```
orientation（给人读的导航 + context pack）
  → route-mode 抽取（extraction_route_plan + route_mode/* planner/reviewer/checkpoint/shadow-audit）
  → candidate discovery / reviewer（候选发现 + 评审）
  → 各 IR 抽取（message_ir / fsm_ir / state_context / timer）—— 分别抽
  → 大量 lowering_* / merge_* / fsm_* 阶段（合并、归一、拼关系）
  → grounding（accepted_fact_quote_binding / evidence / prior_hypothesis_ledger）
  → implementation_pack → profile → codegen → code2ir / soft audit
```

### 1.3 模块规模（佐证"staged 复杂度"）
`src/extract/` 下数十个模块，其中【拼关系/合并/分阶段】占大头：
- 合并/归一：`merge / fsm_fragment_merge / fsm_semantic_merge / lowering_global_merge / lowering_merge_review / orientation_reconciliation`
- 帧关系拼装：`frame_reference_graph（确定性启发式拼）/ frame_assembler / frame_graph_adapter`
- lowering 层：`lowering_behavior_concepts / lowering_codegen_catalog / lowering_compound_actions / lowering_slot_concept_map / …`（十余个）
- 视觉：`visual_table_sidecar（标题式 continuation 雏形）/ visual_vision_sidecar（按 region、默认 max_pages=1）`

> 观察：大量 merge/lowering/graph 模块 = 把"完整性"交给【确定性规则去拼碎片】。这正是问题根源（见 §2）。

---

## 2. 遇到的问题（为什么要重构）

### 2.1 根本问题：staged 抽取 + 确定性合并 → 系统性丢关系
- 流程是"分阶段碎片抽 → 合并"，**跨字段 / 跨页 / 条件 / 变长关系在碎片化时就丢了，合并阶段拼不回来**。
- 具体证据：
  - `visual_vision_sidecar`：`max_pages_per_region=1` + 按 region 读 → 永远没整体读过一张表 → 出碎片。
  - `frame_reference_graph`：用 page-adjacency / neighborhood / 正则【启发式拼】跨字段关系 → 条件字段（"Word29-30 仅 Payload Bit=1"）、变长、跨表复用拼不全。
  - 审计实测的逻辑错与文档自陈：`图跨行/continuation/variable-length/TLV lowering/sidecar→MessageIR apply` 均未完成（FC codegen-ready 四缺口）。
- **违背自己的原则**："Increase LLM、规则只约束、别堆规则假装泛化、generalization 才是 claim"。staged-merge = 堆规则拼关系。

### 2.2 对照：被排除的 agentic-RAG 路线反而完整
- 实测：问"FLOGI 完整流程 + 帧结构"，agentic RAG（M1）输出【完整 + 准 + 带页级 cite + 抓住所有条件/分支关系】（S_ID 三变体、响应分支全、按 Class 完成条件、SOF 规则、Relogin/R_A_TOV）。
- 即 V6 当年排除的那条线（RAG/pageindex），正是【整体读 → 完整忠实中间体】的可执行形态。**完整性该来自 LLM 整体读，不是确定性拼碎片。**

### 2.3 user-0-prior 风险
- 若抽取【预设单元】（如"去抽 FLOGI"），等于把作者先验偷塞进系统 → 破 user-0-prior claim。
- V6 的 orientation 偏"给人读的导航"，没把"**不预设地发现有哪些 flow/FSM/message**"做成承重的【发现层】。

### 2.4 复杂度债
- 数十个 merge/lowering/graph 模块互相耦合，extractor + IR-materialization 仍未 clean-room 完成（README 自陈）。继续在 staged 上补缺口，是往一个【方向就不对】的结构里加复杂度。

---

## 3. V7 新架构（该怎么做）

### 3.1 核心转变
```
抽取从：【staged 碎片抽 + 确定性 merge 拼关系】
   变为：【发现(orientation) + 逐单元 agentic-RAG 整体读 + 薄结构化 + 两层 verify】
完整性来源从：【确定性规则拼碎片】 → 【LLM 整体读直接拿到】；规则只 verify，不拼、不切。
```

### 3.2 分层架构
```
① 发现层（orientation-as-discovery）  ← user-0-prior 的承重
   导航 spec → 枚举【有哪些 flow / FSM / message / 表】，【不预设列表】
   覆盖 verify：发现的单元对照【spec 自带目录】核（FC-LS 的 ELS 命令表 / 状态表 / 帧格式表清单）
   → 发现的单元数 vs 目录条目数对不上 → 报漏（防"静默漏单元"）

② 读层（agentic RAG，复用 M1）       ← commodity、已实证完整
   对每个发现的单元【聚焦整体读】→ 完整忠实中间体（md/表/mermaid + 页级 cite）
   注意聚焦 per-unit 读（广问粒度 < 专问；为 message_ir 专门读对应表）

③ 结构化层（薄、新写）               ← 你的贡献之一
   完整阅读 → 结构化 IR（message_ir/fsm_ir/…，schema 对）+ 字段级 provenance（细化页级→span/cell）

④ verify 层（两层 propose-verify）   ← 你的贡献之二
   发现层：orientation 提议单元 → 规则验覆盖（对 ELS 表/状态表）
   单元层：RAG 提议读+cite → 规则验 cite 真支持（prior-leakage gate）+ schema + cross-ref
   → "可审计 despite agent 变异"：variance 在检索路径，不破坏可审计（每事实带 provenance + 被验）

⑤ profile → 生成 → 审计（V6 保留）   ← 你的贡献之三
   executable_profile（LLM 选片 + rule 验 refs，已实现）→ module-contract renderer → codegen → code2ir / soft audit
```

### 3.3 两种完整性（V7 必须都管）
```
发现完整性：orientation 找全所有单元 —— 新风险（staged 至少遍历所有 node，发现式可能静默漏单元）
   → 缓解：对 spec 自带目录核覆盖（§3.2 ①）
每单元完整性：agentic RAG 把每个单元读全 —— 已实证（FLOGI 输出）
```

### 3.4 中间体纪律
```
md/mermaid/表 = 【可审计中间视图】（整体读的完整忠实呈现 + provenance）
   = 审计检查点 + 显示/orientation + 抽取中间体（从它结构化成 IR）
红线：它【派生、可有损】→ 绝不当事实源、绝不当 IR 的 evidence；IR 的 grounding 指向【原文 span / 表 cell / 图 crop】。
   图 crop / 原文 span = 事实源；中间体可核但不是源。
```

### 3.5 agent 变异怎么处理（你纠结的点）
```
不把"该不该用 agent"当信任题，当【测量题】：
   在已知目标（如 FC-LS Table 149，字段已知）上跑 N 次，量【完整性 + 一致性】
   可靠 → 用；变异大 → verify 层兜（漏了重查）。
模型变强是【锦上添花】不是【前提】：现在就靠 provenance + verify 兜底，不拿可靠性赌"模型会更好"。
```

---

## 4. 迁移清单（keep / shed / bring-back / new）

```
KEEP（V6 已有、保留）：
  · IR schema（message_ir / fsm_ir / state_context / timer 的目标结构）
  · grounding 纪律 + prior-leakage gate（prior_hypothesis_ledger / accepted_fact_quote_binding）
  · executable_profile（LLM 选片 + rule 验）+ module_contract_renderer + codegen + code2ir + code_semantic_audit
  · orientation 的"导航/context"基建（但要扩成发现导向，见 NEW）

SHED（退役 / 大幅简化——staged 拼关系那套）：
  · 分阶段碎片抽 + 大量 merge/lowering：merge / fsm_fragment_merge / fsm_semantic_merge / lowering_global_merge / lowering_*（拼关系部分）
  · frame_reference_graph 的【启发式拼跨字段关系】（关系改由整体读直接拿到）
  · visual_vision_sidecar 的【按 region、max_pages=1】碎片读（改整体读整张表）

BRING-BACK（V6 当年排除的、要请回来）：
  · M1 的 agentic RAG（src/agent/loop.py agentic_rag）当【读层】—— 复现 PageIndex 的整体读+引用

NEW（薄、要新写）：
  · orientation-as-discovery：枚举单元 + 对 spec 自带目录核覆盖
  · 完整阅读 → 结构化 IR + 字段级 provenance 的【薄结构化层】
```

---

## 5. 红线 / 非目标

```
红线：
  · 不预设单元（去抽 FLOGI 是先验）—— 必须发现层发现。user-0-prior。
  · md/中间体非事实源；IR grounding 指向原文 span/cell/crop。
  · cite 必须 verify（prior-leakage gate）；发现必须 coverage-verify（对 ELS 表/状态表）。
  · 完整性来自 LLM 整体读；规则只 verify（schema/provenance/coverage），不拼关系、不切阅读。
非目标：
  · 把 thesis 变成"带引用的阅读 chat"（PageIndex 已存在、不新颖）。
    你的新颖性在【发现→grounded IR→可运行生成→可验证审计】这条，PageIndex/RAG 只是 commodity 读前端。
  · 继续在 staged 上补缺口（方向问题，不是补丁问题）。
```

---

## 6. 重构第一步建议

```
1. 测：在 FC-LS Table 149 上跑 M1 agentic RAG，量【完整性 + 一致性 + cite 是否真支持】→ 决定读层就用它。
2. 立发现层：orientation 出"单元清单"，对 FC-LS 的 ELS 命令表核覆盖（先证明"不预设也能发现全"）。
3. 接结构化薄层：拿一个单元（如 FLOGI message）的完整阅读 → message_ir + 字段级 provenance + prior-gate 验。
4. 串到已有下游：该单元 → profile → 生成 → 审计，跑出【一个发现驱动、整体读、可审计、能生成】的端到端样本。
→ 先把【发现→整体读→IR→生成→审计】一条 vertical 跑通（一个单元），再铺全协议。vertical-first。
```
