# D&D 3.5 知识问答助手

> [English](README.md) | **中文**

一个私有、个人使用的 RAG 项目，用于回答 **Dungeons & Dragons 3.5e** 规则问题，并返回带 **来源引用** 的答案。

## 项目状态

当前处于 **Phase 1 — 核心实现阶段**。Phase 0 设计已完成。

核心检索链路已落地：ingestion（`scripts/ingest_srd35/`）、chunker（`scripts/chunker/`）、带领域感知打分与 match-signal 重排的 lexical-first retrieval（`scripts/retrieval/`）、section-aware 的候选聚合、structure metadata 索引，以及 evidence-pack 契约与 retrieval debug CLI（`scripts/retrieve_debug.py`）。

Phase 1 仍待完成：带 grounding 约束的 answer generation、citation 渲染、abstain 行为，以及在 gold set 上的首次评测运行。

设计文档仍是契约的主约束；实现通过 fixture corpus、golden test 与 recall-coverage 回归加以对齐。

## 愿景

目标是构建一个规则助手，能够：

- 依赖检索到的规则文本回答问题，而不是模型“记忆”
- 为关键结论提供可验证引用
- 严格遵守版本边界
- 在证据不足时明确 abstain

Phase 1 仅支持 **D&D 3.5e**。

## 核心原则

### 1. 有据优先
答案必须能追溯到检索证据。

### 2. 引用是核心功能
引用不是 UI 装饰，必须有稳定 provenance 支撑。

### 3. 版本边界严格
Phase 1 只在 3.5e 语料内工作。

### 4. 私有单用户
项目面向个人使用，不是公共多租户服务。

### 5. 设计先于扩展
先把契约与行为压实，再做框架与规模化。

## 文档索引

- `docs/product_scope.md`：产品范围与非目标
- `docs/architecture_overview.md`：系统分层与数据流
- `docs/source_bootstrap_plan.md`：bootstrap source 准入策略
- `docs/metadata_contract.md`：共享 vocabulary 与 locator 语义
- `docs/corpus_ingestion_design.md`：ingestion 设计
- `docs/chunking_retrieval_design.md`：chunking/retrieval 设计
- `docs/citation_policy.md`：引用策略
- `docs/model_strategy.md`：模型策略
- `docs/evaluation_plan.md`：评测方案
- `docs/standards/pr_evidence.md`：流水线 PR 的最低证据标准
- `configs/source_registry.yaml`：来源注册表
- `evals/phase1_gold.yaml`：`srd_35` 上的 Phase 1 gold 评测集

## 当前形态

1. raw source -> canonical corpus
2. canonical -> retrieval-ready evidence units
3. evidence units -> 本地检索索引
4. 基于 evidence 回答问题
5. 输出 claim/segment 级引用

## 下一步

ingestion、chunking、lexical retrieval、候选聚合与 evidence-pack 契约已在 `srd_35` 上就位。下一步是闭合 Phase 1：带 grounding 约束的 answer generation、claim / segment 级别的 citation 渲染、abstain 行为，并在 `evals/phase1_gold.yaml` 上跑出第一次评测结果。
