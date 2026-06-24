# V7 工程进度汇总（新会话先读）

Date: 2026-06-24

## 0. 当前一句话
V7 当前已经从“V6 staged 碎片抽取”转向 **PageIndex 式 agentic reading / SpecIndex 读层优先**：先把 PDF 读准、图表资产接好、输出可审计的自然语言/Markdown 中间体，再从这个中间体结构化成 IR。现在重点不是直接一次性抽 IR，而是先把 **FLOGI 这类长问题的完整阅读质量** 做到接近 PageIndex。

## 1. 关键目录
```text
/Users/zwy/毕设/V7
  src/agent/loop.py                    Agentic RAG 主 loop
  src/agent/prompts/pageindex_reading.txt / pageindex_system.txt
                                        PageIndex 风格阅读 prompt
  src/tools/                           SpecIndex 文档读取工具
  src/ingest/pipeline.py               PDF 处理、summary、chunk 构建入口
  src/web/app.py                       Web API
  src/web/static/index.html            Web UI
  structure_chunker.py                 document structure 分 part
  data/raw/                            当前 V7 内的协议 PDF
  data/out/chunk/FC-LS/                FC-LS 当前结构索引和 parts
  processed_specs/                     page span / table / figure 资产
  pageindex_test/                      PageIndex 对比、live run 记录
```

相关旧工程：
```text
/Users/zwy/毕设/Protocol_V6                 V6 staged 管线、IR/codegen/audit 经验来源
/Users/zwy/毕设/m1-sketch-constrained-extract M1 agentic RAG 原型来源
```

## 2. 架构方向
当前策略已经调整为：

```text
PDF / spec
  -> SpecIndex/PageIndex 式索引和资产层
  -> agentic reading：按问题拆需求、查结构、读页、读表、读图、核 evidence
  -> 自然语言 / Markdown / 表格 / Mermaid 中间体
  -> 再结构化为 IR（message_ir / fsm_ir / state_context / timer 等）
  -> profile -> module contract -> codegen -> audit
```

核心原则：
- 先读准，再结构化；不要让 LLM 在信息还没读完整时直接背 IR schema。
- 语义判断交给 LLM prompt；Python 规则只做结构 wiring、验证、缓存、范围计算。
- summary 是导航元数据，不是事实源；IR grounding 必须指向原始 page span / table cell / figure crop。
- 允许 LLM 重组原文为表格、流程图、分层说明，但具体字段、数值、条件必须来自文档 cite。
- 先验知识只能做背景和连接逻辑；协议细节必须回文档。

## 3. 已完成的 V7 读层工作

### 3.1 M1 Agentic RAG 迁移和 Web
- M1 的 agentic RAG 思路已经迁到 V7。
- V7 有 CLI/Web 入口，Web UI 已迁过来并能打开 PDF、选择文档、发起 QA、查看历史会话。
- 当前 Web 后端入口在 `src/web/app.py`，前端在 `src/web/static/index.html`。

### 3.2 SpecIndex 文档工具
当前读层已有这些核心工具：
- `get_document_structure`：读取文档结构，支持分 part。
- `get_page_content`：读取页内容，已支持混合页码范围，如 `36,166-170,179,203`。
- `list_assets`：列出表格/图片资产。
- `get_table`：读取结构化表格资产。
- `get_image`：读取图片/图表 crop。
- `verify_evidence`：校验证据 ref，已兼容 wrapped ref 归一化。

已暂时不需要：
- `search_nodes`
- `get_prev_node`
- `get_next_node`

### 3.3 Prompt 方向
已把原本偏 IR 抽取的 prompt，调整为 PageIndex 风格阅读 prompt：
- 先拆信息需求，再检索。
- 用 structure 的 title + summary 做语义定位。
- 对具体问题下钻到更具体的子节点，不只读父节点起始页。
- 区分 own page range 和 subtree page range。
- 遇到 `see Table/Figure/section` 这类 cross-reference，应使用已有 structure / asset 工具继续查，不靠猜。
- 输出要宏观到微观，允许表格/流程图重组，事实必须 cite。

## 4. Summary / Index 构建状态
之前问题是 summary 开关没开，导致 structure 没有有效 summary。现在已经补过：
- summary cache 中已有大量 v2 summary。
- summary prompt 已从“长文压缩”改向“导航索引”：短、保留表号/图号/命令名/字段名等 anchor。
- 资产层已纳入 summary 输入：按 node 页范围把 table/figure 的 number、caption、短摘要提供给 summary。
- 已注意到一个正交问题：如果 node 切片不够精确，summary 仍可能重复串节。这不是 prompt 能单独解决的，后续要继续精切 section text。

## 5. Structure Chunk 当前状态
FC-LS 当前结构 chunk 已重建：

```text
data/out/chunk/FC-LS/manifest.json
total_parts = 7
files = part_0001.json ... part_0007.json
```

本次调整：
- 默认 `structure_max_limit` 已从 `30000` 调到 `70000` 左右。
- Web API 默认值、pipeline 默认值、前端默认设置都已同步。
- 前端 localStorage key 从 `kiro.process.settings.v1` 升到 `kiro.process.settings.v2`，避免浏览器继续沿用旧的 `30000`。
- `subtree_start_index/subtree_end_index` 没有删，仍保留导航范围。

已验证的关键例子：
```text
node_id = 0292
own range     = 153-153
subtree range = 153-156
```
这正好对应 FC-LS FLOGI 父节点自己只在 153 页，但子孙内容覆盖到 156 页的问题。

## 6. FLOGI Live QA 现状
最近一次 FLOGI live run：
```text
pageindex_test/flogi_live_run_20260624_145140.json
pageindex_test/flogi_live_run_20260624_145140.md
```

已改善：
- 能读到 `155-156`，修复了之前只读父节点 start page 导致漏掉 completion/relogin/SOF 的问题。
- 回答已覆盖：
  - FLOGI 的定位和功能
  - 请求/响应流程
  - LS_ACC / F_BSY / P_BSY / F_RJT / P_RJT / LS_RJT / no response 等分支
  - SOF/Class 选择和 retry
  - Relogin / implicit logout / R_A_TOV
  - Originator / Responder completion 条件
  - Table 149/150 附近的 payload / service parameter 结构

仍有问题：
- 有过度读取：例如读 `152-161`，比理想的 `153-156` 宽。
- VF/EVFP 相关细节在某次 run 中没有稳定补到 `203-206`。
- `verify_evidence` 还不是最终严格 gate：目前能校验，但还没强制作为最终回答前的硬验收。
- 输出和 PageIndex 相比仍需要继续优化长文组织、表格呈现和 trace 里的导航行为。

### 6.1 FLOGI / Table149 客观验收尺
已补第一版 machine-readable checklist + scorer，把“看起来覆盖了”改成可重复打分：

```text
checklists/fc_ls_flogi_table149.json
src/evaluation/checklist.py
tests/test_checklist_evaluation.py
audits/flogi_table149_checklist_145140.json
```

使用方式：
```bash
PYTHONPATH=. python -m src.evaluation.checklist \
  --checklist checklists/fc_ls_flogi_table149.json \
  --run pageindex_test/flogi_live_run_20260624_145140.json \
  --out audits/flogi_table149_checklist_145140.json
```

当前旧 run `flogi_live_run_20260624_145140.json` 打分：
```text
48 / 50 = 0.96
```

失败项正好是两个真实缺口：
- `table149_class6_uses_class1`：答案覆盖了 Class6 复用 Class1，但没读/引支持该事实的 page 165。
- `vf_evfp_support_pages`：没补读/引用 `203-206` 的 VF/EVFP 依赖。

### 6.2 Subtree 实验结论
`subtree_start_index/subtree_end_index` 加入后，`145140` 的 FLOGI 本地页召回明显变好：

```text
141740 pages: 36-40,151-154,166-170,179,203-210
145140 pages: 36-37,152-161,166-170,179
```

这不是“全局页召回更多”，而是召回重心从外部相关章节回到了 FLOGI 本地子树：
- 收益：读到了 `155-156`，补上 response branches、SOF/relogin、completion 条件，checklist 从 `33/50` 提升到 `48/50`。
- 代价：agent 把 `6 Login and Service Parameters` / `6.2 Fabric Login` 的局部 subtree 当成完成边界，没有继续补读第 8 章 `Virtual Fabrics N_Port Support` 的 `203-206`。
- 触发原因：`list_assets` 被限制在 `page_range=152-196`，且 coverage check 只确认了 `message_format / overview_mechanisms / implementation_flow`，没有把 source summary 里“FLOGI enables Virtual Fabrics / EVFP”这种跨章节依赖提升成独立信息需求。

已更新 `src/agent/prompts/pageindex_reading.txt`：
- Step 1：把 source 明确命名的 related mechanisms 纳入信息需求，即使它们在本地 section 外。
- Step 2：本地 section 映射后，扫描 fetched structure 里 outside-subtree 的 cross-section dependencies。
- Step 4：为跨章节依赖找 asset 时，不要先用本地 `page_range` 锁死搜索范围。
- Step 5：如果结构摘要或已读页面说目标会 enable/trigger/depend/negotiate/followed-by 某机制，长问题必须读该机制 own section；一句本地提及只能证明“存在”，不能证明“机制细节已覆盖”。
- Page range strategy：parent subtree 只当 boundary map，不默认读大父区间；优先读最小 child ranges。

当前取舍：不强求“够用就停”。现阶段宁可 controlled over-coverage，也不要静默漏证据。`pageindex_reading.txt` 已强调：
- coverage 优先于 minimal retrieval；
- 不确定小范围相关页/表/图是否必要时，先补读；
- 收窄页数排在 coverage 之后，不为了省页数冒漏 branch/field/condition/table continuation/cross-section dependency 的风险。

### 6.3 FLOGI 拆分读计划 / focused tasks
先不做 RepoIndex 和完整 ProtocolIR，已先补一层 **protocol-neutral reading planner**，把“发现出的 unit + proposed task candidates”物化成可审计、可逐任务执行的 reading plan：

```text
src/reading/planner.py
src/reading/from_plan.py
tests/test_reading_planner.py
```

这层只做机械事：
- normalize unit/task；
- 校验 page range、asset id、预算、必填字段；
- 写 `unit_meta.json` / `reading_plan.json` / `tasks/*/task_input.json` / `unresolved.json` / `verify_report.json`；
- 可从 `reading_plan.json` 逐 task 调 `run_reading_claim_agent`。

保持协议中立：
- 通用代码里没有 FC/FLOGI token；
- FLOGI/FC-LS 只出现在 fixture / artifact；
- task 边界由外部 proposal 给，planner 不用规则推协议语义。

FLOGI seed artifact 已落地：

```text
pageindex_test/fc_ls_flogi_reading_plan_input.json
processed_specs/local/FC-LS/reading/units/unit_fc_ls_flogi/reading_plan.json
processed_specs/local/FC-LS/reading/units/unit_fc_ls_flogi/verify_report.json
```

物化结果：

```text
accepted_count = 7
unresolved_count = 0
invalid_count = 0
```

7 个 focused tasks：
- `flogi_els_envelope`：36-37
- `flogi_procedure_branches`：153-156
- `flogi_payload_table149`：165-166 + `table_0157`
- `flogi_common_service_parameters`：167-170 + `table_0158/table_0160/table_0161/table_0163`
- `flogi_class_service_parameters`：179 + `table_0168/table_0170`
- `flogi_relogin_logout_side_effects`：155, 162-164 + `table_0155`
- `flogi_virtual_fabrics_evfp`：203-206 + `table_0192`

这正是对“FLOGI 一个 query 太大”的工程化回应：不继续靠单次长 QA 里 prompt 硬撑，而是把 broad query 拆成 IR-oriented 小读任务，后面再做 claim aggregation / thin IR。

本次还修了两个通用边界：
- `max_tables/max_figures = 0` 对纯文本任务合法；`max_pages/max_tool_calls` 仍需为正数。
- `from_plan` 生成 reader prompt 时必须带上 task 的真实 `reading_goal`，不能只带标题、页码和 completion criteria。

### 6.4 Focused reading 初跑结论
已用 FLOGI plan 先跑两个代表性 task，结论是：**拆小 query 有效，但批处理 runner 还要补 progress / resume / timeout 控制**。

成功输出：

```text
processed_specs/local/FC-LS/reading/units/unit_fc_ls_flogi/tasks/flogi_els_envelope/reading/
processed_specs/local/FC-LS/reading/units/unit_fc_ls_flogi/tasks/flogi_els_envelope/reading_single/
processed_specs/local/FC-LS/reading/units/unit_fc_ls_flogi/tasks/flogi_payload_table149/reading_single/
```

`flogi_els_envelope`：
- 单 task 成功，`6` accepted / `0` unresolved / `0` invalid，`6` turns。
- 证据只来自原文页 `36-38` + `table_0002/table_0003`。
- 覆盖 ELS_Command 位置、FLOGI code `04h`、TYPE `01h`、R_CTL request/reply、single Exchange。

`flogi_payload_table149`：
- 单 task 成功，`21` accepted / `0` unresolved / `0` invalid，`5` turns。
- 只读页 `165-166` + `table_0157`。
- 明显优于长 QA：Word 0、1-4、5-6、7-8、9-12、13-16、17-20、21-24、25-28、29-30、31、32-61、62-63、64-n 都单独成 claim；Payload Bit=0/1、Class6 复用 Class1、256+ byte login 过程也有证据。
- 暴露一个 schema 小问题：`Words 64-n` claim 的 `kind=variable_length_fields` 不是 canonical kind。已在 `src/reading/claims.py` 增加 `schema_warnings`，并收紧 `reading_claim_system.txt` 要求只能用 canonical kind，暂不硬拦，因为现有测试仍把 `kind` 当开放标签使用。

批跑观察：
- `python -m src.reading.from_plan ...` 第一次在第一个 task 后遇到空 final JSON，已修：`src/agent/loop.py` 对 empty final 做 retry；`src/reading/runner.py` 对 JSON parse failure 写 `raw_answer.txt/runner_error.json`；`src/reading/from_plan.py` 单 task 失败会写 `task_error.json` 并继续。
- 第二次批跑被手动中断，但它已经完成了第一个 task；说明不是 task 本身不可读，而是批处理缺少 progress/resume，长时间静默不利于实验。
- 下一步不建议直接盲跑 7 个 task；先给 `from_plan` 加 `--task-id` / skip-completed / progress callback，再逐个或断点跑。

## 7. 和 PageIndex 对比得到的结论
PageIndex 强的地方不是 embedding，而是 agentic reading 行为：
- 先拆需求。
- 用 summary 做语义导航。
- 对父节点命中不急着读父节点 start page，而是看子节点/子树范围。
- 对表号、图号、章节号做邻近推断。
- 读完后做 coverage 自检，不全就补读。
- 输出时主动重组原文为表格、流程和分层说明。

V7 当前管线的主问题曾经不是“有没有向量检索”，而是：
- prompt 写成了 IR 抽取器，不像 PageIndex reader。
- page content 曾有截断风险。
- coverage 曾有硬编码倾向，应回到 LLM prompt。
- summary 曾没开，且 prompt 不够像导航索引。
- structure part 太碎，已通过 70k chunk limit 缓解。

## 8. V6 中仍可复用的部分
V7 不等于全盘丢掉 V6。可复用：
- IR schema：`message_ir` / `fsm_ir` / `state_context` / `timer`
- prior-leakage gate 思路
- executable_profile：BFD 上跑过 LLM 选片 + rule verify refs
- module-contract renderer plan
- codegen / code2ir / code_semantic_audit
- BFD 已抽取出的 IR 和 session-up profile 经验

准备退役或大幅简化：
- staged 碎片抽取
- 规则式 merge/lowering 拼跨页/跨字段关系
- frame_reference_graph 这类启发式补关系
- 过早直接从碎片降 IR

## 9. 当前风险
- Summary 质量会直接影响 navigation；如果 summary 漏表号/图号，后续查表会变差。
- 大 part 降低 part 数，但单次 `get_document_structure` 响应变大，可能给 LLM 带来阅读压力。
- 图表 vision 目前仍主要是资产和 caption 层；真正需要读图内部时，还要接多模态总结。
- Single-QA 做准还没等于 IR 做准；IR 前还需要一层“完整阅读结果 -> 结构化 IR”的薄转换和 provenance 细化。

## 10. 下一步建议
优先级从近到远：

1. 用 `processed_specs/local/FC-LS/reading/units/unit_fc_ls_flogi/reading_plan.json` 跑 7 个 focused reading task，先看逐任务 claim 质量：
   - 重点观察 Table149 是否不再压缩 Word ranges；
   - VF/EVFP `203-206` 是否稳定覆盖；
   - procedure branches 是否保持完整，不因拆分丢上下文。

2. 先补 `from_plan` 工程控制：
   - `--task-id` 单 task 运行；
   - skip completed / resume；
   - progress callback 或每 task 结束即刷新 manifest；
   - per-task timeout / budget 记录。

3. 对 task outputs 做最小 aggregation：同一 unit 下合并 claims / unresolved / evidence，先不要急着上完整 ProtocolIR。

4. 用 `checklists/fc_ls_flogi_table149.json` 跑拆分后结果的客观回归；优先把分数从 `48/50` 推到 `50/50`：
   - 先补 `VF/EVFP` 到 `203-206` 的覆盖；
   - 再补 Table149 Class6 复用 Class1 的 page 165 cite；
   - 最后才收敛 `152-161` 这类过度读取。

5. 修 section text 精切，减少 summary 重复串节。

6. 把 `verify_evidence` 做成回答前的更严格 gate：最终答案里的关键事实必须能被 page span/table cell/figure crop 支持。

7. 为图表资产补多模态 summary：caption 足够导航，但不够理解复杂图内部结构。

8. 在 FLOGI 上产出稳定的“自然语言/Markdown 中间体”，再做第一版 `message_ir` 结构化实验。

9. 串一个最小 vertical：
   ```text
   FC-LS FLOGI 阅读中间体
     -> message_ir / state_context
     -> profile
     -> module contract
     -> codegen / audit
   ```

## 11. 最近验证
截至 2026-06-24，最近一次全量测试结果：

```text
65 passed, 6 warnings
```

最近一次 FC-LS chunk 验证：
```text
manifest total_parts = 7
part files = 7
node 0292 subtree range = 153-156
```
