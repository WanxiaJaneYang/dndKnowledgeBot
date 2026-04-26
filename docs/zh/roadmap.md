# 路线图

> [English](../roadmap.md) | **中文**

## Phase 0 - 设计（已完成）

- [x] 定义产品范围
- [x] 定义 source bootstrap 计划与准入契约
- [x] 设计语料 ingestion 流水线
- [x] 设计 chunking 与 retrieval 流水线
- [x] 定义 citation policy
- [x] 定义模型策略（角色与选择标准）
- [x] 定义评测计划
- [x] 冻结 bootstrap source slice（`srd_35`）
- [x] 构建该 slice 的 20-30 题 gold set
- [x] 对齐 `source_ref` / `locator` / `answer_segments` 轻契约
- [x] 在该 slice 上验证 provisional schema

## Phase 1 - 核心实现（当前）

**Sources：** 先以 `srd_35` 为基线，随后在契约稳定后逐步扩展到 PHB / DMG / MM 与官方 errata / FAQ。

- [x] 实现 ingestion pipeline（extraction + normalization）— `scripts/ingest_srd35/`
- [x] 加入 fixture corpus + golden outputs + preview evidence 标准 — `tests/fixtures/`、`docs/standards/pr_evidence.md`
- [x] 实现 chunker — baseline section-passthrough strategy，`scripts/chunker/`、`tests/test_chunker.py`
- [x] 实现 lexical-first baseline retrieval pipeline（hard filters → normalization → BM25/FTS retrieval → evidence pack）— `scripts/retrieval/`（PR #49）
  - [x] 领域感知打分中的 chunk-type prior（PR #52）
  - [x] 在 chunk index 中索引 structure metadata（PR #61）
  - [x] 基于 `(document_id, section_root)` 的 section-aware 候选聚合层（PR #64）
  - [x] 将 chunk adjacency 字段（`parent_chunk_id`、`previous_chunk_id`、`next_chunk_id`）贯穿到 `LexicalCandidate` 与 `search_chunk_index`（PR #67、#69）
  - [x] 扩展 recall-coverage 回归测试（PR #53）
- [x] retrieval 输出的 evidence-pack 契约 + 调试用 retrieval CLI — `scripts/retrieve_debug.py`（PR #66）
- [x] 实现 v1 answer generation（基于规则的摘录式组合器，带 grounding 约束）、citation 渲染与 abstain 行为 — `scripts/answer/`、`scripts/answer_question.py`（PR #74，issue #23）
- [ ] 实现 v2 answer generation（基于 LLM 的散文合成器，复用同一 `EvidencePack` 契约）
- [x] Phase 1 gold-set 评测 harness 与首次运行 — `scripts/eval/`、`scripts/run_phase1_eval.py`（PR #81）；报告见 `evals/reports/phase1_gold_latest.{md,json}`

## Phase 2 - 质量提升

- [ ] 增加 vector / semantic retrieval，用于模糊表达与 paraphrase
- [ ] 合并并重排 lexical + semantic 两路候选
- [ ] 引入 reranker
- [ ] 扩展语料（官方补充来源）
- [ ] 改进复杂版式（表格、多栏）chunking
- [ ] 增加 errata / FAQ 覆盖层
- [ ] 扩展评测集

## Phase 3 - 接口

- [ ] 定义目标接口（CLI / Discord / Web UI）
- [ ] 实现选定接口
- [ ] 增加查询日志用于离线分析

## 延后 / 超出范围

- 多版本支持
- homebrew 内容集成
- 公共部署或多用户访问
- 实时联网检索
