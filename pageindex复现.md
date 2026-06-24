# PageIndex 复现

来源：`pageindex_test/log.md`（真实 PageIndex 对 FC-LS 的问答——它把自己的 system prompt / 9 个工具 / 导航决策逻辑 / 降级策略 / 硬规则几乎全交代了）+ V7 代码实读对照。
目的：把"PageIndex 为什么强、怎么工作"写成【可复现蓝图】，并标 V7 现状（已复现 / 还差）。

---

## 0. 一句话 + 核心洞察

PageIndex【不是 embedding RAG】，是 **reasoning-based agentic reading**：用文档结构（目录树 + 摘要）做语义导航 → 按需读页/表/图 → 把散落原文重组成结构化、带页引用的答案。

它自述的核心洞察（最重要的一句）：
> **答案质量 = 信息收集是否全面（覆盖所有相关页） + 整合是否有结构（不是把原文堆一起）。两者缺一不可。**

关键事实（它亲口说的）：**导航【不用向量、不用 embedding】**——是"LLM 读目录里的 title+summary 做语义判断"，和人翻目录找章节一样，只是更快、不翻错页。
→ 所以复现 PageIndex【不需要向量库】，需要的是：好结构+好摘要 + 一套 agent 阅读行为。

---

## 1. 整体架构（两层）

```
离线 processing（建索引，导航的地基）：
   PDF → 结构树(目录 + 页码范围 + 【摘要】) + 内容(页文本，表→Markdown) + 资产(表/图 crop + caption)
在线 agentic reading（回答）：
   问题 → 拆维度 → 用结构摘要语义定位 → 读页/表/图 → coverage 自检 → 结构化输出
口诀："结构工具负责导航，内容工具负责读取。"
```

---

## 2. 离线 processing（索引怎么建 = 导航准不准的地基）

```
· 结构树：每节 = 标题 + 页码范围 + 【摘要】。摘要是导航的【承重】——摘要质量决定能不能命中。
· 摘要必须是【导航索引型】：短、密、【保留具体锚 verbatim】（表号/图号/命令名/字段名/状态名/hex 值）。
   —— 不是"长文压缩描述"。锚保留是 location-inference（靠"看到 Table 150 推 Table 149 在前"）的前提。
· 内容：页文本；PDF 表格 →【Markdown 表格文本】（转换在【工具/处理层】，不是 LLM 现编）。
· 资产：表（cells + crop + caption）、图（crop + caption）。
· 跨页表：表头匹配 + 页相邻 → 拼成一张 logical table；续页标 (Continued)。
```

---

## 3. 工具集（PageIndex 自述 9 个，核心读文档 3 个）

```
库导航：get_folder_structure / browse_documents / search_documents   （单文档场景用不到）
处理  ：process_document / get_document
读文档（核心 3 个）：
   get_document_structure  ← 章节大纲(标题 + 页码 + 摘要)，分 part 分页；用于【定位】
   get_page_content        ← 读页【文字 + 表格 Markdown】，支持【一次多页】(如 "153-156")
   get_document_image      ← 页里的图（先从 page_content 拿路径再调）
管理：remove_document
发现"不存在"前的 persistence：browse → 换 folder → 换同义词 → recursive → search，五步都试过才说"没有"。
```

---

## 4. Agent 行为（复现的灵魂——PageIndex 强的真正原因，不是 summary 像答案，是【行为链】对）

这 6 个行为缺哪个都"不像 PageIndex"：

```
① 先拆维度 decompose（碰工具之前，纯推理）
   问题 → 信息需求列表（如"完整流程+机制+帧结构" → [流程, 帧格式, 响应分支, 完成条件, 相关机制]）
   【它自述：这条 R1 最容易被违反——不拆就抓第一个相关页输出，质量必差】。

② 摘要语义导航 navigate
   读每节 title + summary，把每个需求匹配到最相关的节 → 收集页码。【不是关键词、不是向量，是 LLM 读摘要做判断】。

③ location-inference 降级梯（摘要没直接提到目标时——找具体表/图常遇到）
   1 邻近推断（最可靠）：已知锚（Table 150 在 167）→ 推目标（Table 149）在前几页 → 读邻近
   2 标题推断：标题暗示内容（"…Payload" 节有布局表）
   3 caption 直查（list_assets 按 caption 跳到表/图号）
   4 二分页搜：读中点看编号、收窄、重复
   5 整节读（暴力兜底）

④ 一次读全相关页 + 复用已读
   合并相邻页一次请求（≤10 页/次）；本对话已读过的页直接复用，不重调。

⑤ coverage 自检（读完、输出前）
   · (Continued) → 追下一页（跨页表）
   · "see Table/Figure/§X" → 去 list_assets/structure 查那个位置
   · 第①步每个需求都被读到的内容支撑了吗？没有 → 回去补读。【不全不答】。

⑥ 结构化输出（宏观→微观）
   ① 定位/前提 ② 目的 ③ 结构(最具体) ④ 交互流程(时序+分支表) ⑤ 机制 ⑥ 全景
   条款 → 表/流程图/分层列表（不照抄原文）；补逻辑连接("为什么""然后")；每事实 <cite page>；诚实标边界/不确定。
```

---

## 5. 复现版 System Prompt（中立，可直接用）

V7 已落在 `src/agent/prompts/pageindex_reading.txt`，要点（去掉任何协议专有词，用抽象例）：

```
CORE：不从训练知识答文档问题；总是检索+引用；完整性=覆盖所有相关页+结构化整合；找不到就明说不猜。
      先验只做 framing/连接，绝不用于具体数值/字段/状态/分支/定时器/响应/完成条件。重组只改呈现、不改事实。
工具规则：参数不许编（id/页码逐字复制工具返回）；失败别用同参重试；独立调用并行；get_table/get_image 只用工具返回的 id。
阅读流程：拆维度 → 读 title+summary 匹配 → 合并相邻一次读 → 表走 get_table/图走 get_image → coverage 自检 → 不全不答。
location-inference：邻近/标题/caption/二分/整节，按序降级。
输出：宏观→微观；条款转表/流程图/分层列表；每事实一页一个 <cite>；图内容标 figure-derived；不输出 base64。
```

---

## 6. 硬规则（PageIndex 自述，分级）

```
绝对（不可破）：参数逐字真实、失败不同参重试、每实质声明带 cite、不用训练知识替文档、不输出 base64、不声明没读过的页。
强约束：大文档先结构后内容、发现漏斗不跳步、"返回了结果≠找对了"、已读复用、页范围精准(≤10)、(Continued) 必追页、cross-ref 必跟踪。
最易违反 top3（它自述）：C5 不用训练知识替文档 / D3 返回≠找对 / R1 先拆维度再读。
```

---

## 7. 为什么"完整"（完整性配方，复现的本质）

```
完整 = 【收集全】(① 拆维度 + ② 导航 + ④ 一次读全 + ⑤ coverage 自检)  ×  【整合有结构】(⑥ 宏观→微观 + 重组 + cite)
不是 summary 写得像答案，是【这条行为链】对。
PageIndex 自己的话："工具取数据，LLM 理解+重组；质量取决于收集是否全面 + 整合是否有结构。"
```

---

## 8. V7 现状对照（grounded，基于实读代码）

```
[已复现 ✓]
· 离线：结构树+摘要(page_index.py，PageIndex 开源) + 内容DB + 资产层(pdfplumber 表 cells/crop/caption、图 crop、spans 带 bbox) + 跨页表确定性 stitch
· 摘要：已改成 v2 导航索引型(短+保留锚)，444/444 干净（早期的 0/444、re-expansion 1665、SSE/think 污染都修了）
· 工具：get_document_structure / get_page_content(spans+asset_refs) / list_assets / get_table / get_image / verify_evidence
   —— V7 在 PageIndex 基础上【多加了】get_table(结构化 cells，比 markdown 准)、verify_evidence(结构 prior-gate)
· Agent 行为：pageindex_reading.txt 已编入 拆维度/摘要导航/location-inference/coverage/own-vs-subtree-range/cross-ref/结构化输出

[还差 / 风险]
· 图是视觉盲区：get_image 返回 caption+crop+【空 vision_summary】，vision 从没应用 → 图/状态图内容读不到（PageIndex 至少能把图喂多模态）。文本表 OK，图密集协议是缺口。
· 切片重复串节：node text 切片粗 → 同页多节点吃重叠文本 → summary 重复（6.2/6.2.2/6.2.2.2 几乎一样）。正交于上面所有修复，仍在。
· live-QA 精度：FLOGI 覆盖到位但有【过度读】(152-161 vs 153-156，费钱不伤准)、偶发【覆盖漏】(VF/EVFP 没稳定补到 203-206，伤准)。
· verify_evidence 还不是回答前的硬 gate。
· structure part 70k 偏大：part 少但单 part 重，agent 读 structure 有压力（导航成本 vs 碎片的天平）。
```

---

## 9. 复现验收（怎么知道复现到位了——别靠眼睛）

```
导航：问一个【摘要没直接提的具体表/图】，看 agent 能否靠【邻近推断】定位（验"摘要保留锚"+"location-inference"真生效）。
完整：拿一个大问题（多维度），建【ground-truth 维度+事实 checklist】，自动打分：每维度覆盖到没 + cite 页对没。
   —— 这是把"做准"从眼睛看变成有分数的关键，目前最缺。
结构：输出是【宏观→微观分块 + 表/流程图 + 每事实 cite】，不是堆原文。
效率：不过度读（范围贴需求）、复用已读、≤10 页/次。
诚实：找不到明说、图内容标 figure-derived、不用训练知识补具体事实。
```

---

## 10. 一句话

**PageIndex = reasoning-based agentic reading（不用向量）：好结构+导航索引型摘要(保留锚) 当地基，6 个 agent 行为(拆维度/摘要导航/location-inference/一次读全/coverage 自检/结构化输出)当灵魂；完整性 = 收集全 × 整合有结构。V7 已复现架构+工具+多数行为，且在 PageIndex 之上加了 get_table/verify_evidence；还差：图视觉盲区、切片重复、live-QA 精度/覆盖、verify 硬 gate。复现是否到位，用"摘要没提的表能否邻近定位 + 大问题的 ground-truth 打分"来验，别靠感觉。**
