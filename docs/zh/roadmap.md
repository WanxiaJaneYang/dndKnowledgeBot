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
- [ ] 实现 chunker
- [ ] 选定 baseline 本地向量索引 + embedding 模型 + answer 模型
- [ ] 搭建向量索引与 embedding 流水线
- [ ] 实现 retrieval pipeline（filter → retrieve → threshold）
- [ ] 实现带 grounding 约束的 answer generation
- [ ] 实现 citation 渲染
- [ ] 实现 abstain 行为
- [ ] 在 Phase 0 测试集上跑评测

## Phase 2 - 质量提升

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
