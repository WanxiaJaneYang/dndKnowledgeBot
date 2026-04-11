# D&D 3.5 知识问答助手

> [English](README.md) | **中文**

一个私有、个人使用的 RAG 项目，用于回答 **Dungeons & Dragons 3.5e** 规则问题，并返回带 **来源引用** 的答案。

## 项目状态

当前处于 **早期实现阶段**（Phase 1 基线路径进行中）。

当前重点：

- 明确产品范围与边界
- 固化语料与元数据契约
- 推进 ingestion / evaluation 基础能力
- 开始端到端 baseline（chunking + retrieval + evidence-pack QA）

设计文档仍是主约束，但 ingestion 与评测证据链已经落地并用于回归。

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

## 当前形态

1. raw source -> canonical corpus
2. canonical -> retrieval-ready evidence units
3. evidence units -> 本地检索索引
4. 基于 evidence 回答问题
5. 输出 claim/segment 级引用

## 下一步

当前最优先事项是推进 Issue #5：落地第一条端到端 baseline（rule-aware chunking + retrieval + evidence-pack QA），并在已提交的 gold set 上跑出可解释失败标签。
