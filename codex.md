# V7 项目原则（Codex 读这个）

> 完整版见 `CLAUDE.md`；架构见 `V7_REFACTOR_ARCHITECTURE.md`；进度见 `WORK_SUMMARY.md`。

## Codex 的角色
- **codex = binding peer reviewer + implementer**：spec / plan 先过 codex review 再 commit；实现也常交 codex。
- review 时用技术理由 push back，不做 performative agreement；verify 后再实现。
- **绝不自动 commit / git add**，除非明确要求；不碰 .env / secrets；不改 git config；不 skip hooks。

## 承重原则（实现时必须守）

1. **语义 → LLM；规则只 verify 结构。** 不把语义逻辑写进规则、不加 regex 判语义。不堆规则假装泛化——generalization 就是 claim。**完整性来自 LLM 整体读，不是确定性拼碎片。**

2. **先验可用，但必须 gate。** user-0-prior。LLM 用先验帮读，**事实来自 spec 原文 span**；**cite 必须 verify**（prior-leakage gate：引哪页就验那页真支持，抓"引了但页面没说"）。

3. **LLM-propose / rule-verify，每一层都用。** 规则做：结构核验、provenance、schema、coverage；不做：选内容、解析语义、补语义。propose 的变异不破坏可审计。

4. **user-0-prior = 不预设单元。** orientation = 发现层（枚举单元、对 spec 自带目录 ELS 表/状态表 核覆盖）。不能把"FLOGI"这种单元写死进通用代码。

5. **中间体非事实源。** md/mermaid 可审计但派生；IR grounding 指向原文 span/cell/crop。

6. **协议中立（硬约束）。** 通用代码 / prompt 无任何协议 token（BFD/FLOGI/TCP…）；协议 token 只在 test fixture / 用户 goal / 生成 artifact。有 neutrality 扫描，必须过。

7. **vertical-first。** 先把一条端到端 vertical（一个单元：发现→读→IR→生成→审计）跑通，再泛化。别先建通用系统。

8. **verify on real artifact。** 交回结果时附 live run 证据（命令 + 输出）；unit/mock 不算完成。失败如实报。

## 实现红线
- renderer / 确定性层【只 map + verify】，不碰"选什么/语义怎么解析"。
- 任何"该选什么协议内容/字段/单元"的判断 → LLM（propose）+ 规则（verify），不写进规则逻辑。
- 未知 / 不接地 / 信息不足 → 标 unresolved，不静默丢、不硬判。
