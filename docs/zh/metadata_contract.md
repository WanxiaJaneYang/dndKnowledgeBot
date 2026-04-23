# 元数据契约

> [English](../metadata_contract.md) | **中文**

## 目标

定义一套共享元数据词汇，用于统一来源配置、schema 与 examples，避免字段翻译层。

## 共享词汇

### 核心字段

- `source_id`
  稳定的 snake_case 来源标识，例如 `srd_35`、`phb_35`。
- `edition`
  版本标签。Phase 1 统一使用 `3.5e`。
- `source_type`
  来源类型枚举：
  - `core_rulebook`
  - `supplement_rulebook`
  - `errata_document`
  - `faq_document`
  - `srd`
  - `curated_commentary`
  - `personal_note`
- `authority_level`
  权威级别枚举：
  - `official`
  - `official_reference`
  - `curated_secondary`
  - `personal_note`

### Locator 语义

- `locator`
  证据对象级定位信息，挂在 canonical document、chunk、citation 上。
- `locator_policy`
  来源级定位策略，挂在 manifest / registry 等来源策略对象上。

两者边界：
- `locator_policy` 用于说明某个来源“应该如何定位”。
- `locator` 用于记录某个证据对象“实际定位到哪里”。

## 证据级 locator 形状

`locator` 必须同时支持分页与非分页来源。

可用字段：
- `page_range`
- `section_path`
- `entry_id`
- `entry_title`
- `source_location`

至少要有一个字段存在。

## 示例

### 非分页来源示例（`srd_35`）

```json
{
  "source_ref": {
    "source_id": "srd_35",
    "title": "System Reference Document",
    "edition": "3.5e",
    "source_type": "srd",
    "authority_level": "official_reference"
  },
  "locator": {
    "section_path": ["Classes", "Fighter", "Class Features", "Bonus Feats"],
    "entry_title": "Bonus Feats",
    "source_location": "ClassesI.rtf > Bonus Feats"
  }
}
```

### 分页来源示例（`phb_35`）

```json
{
  "source_ref": {
    "source_id": "phb_35",
    "title": "Player's Handbook",
    "edition": "3.5e",
    "source_type": "core_rulebook",
    "authority_level": "official"
  },
  "locator": {
    "section_path": ["Chapter 3: Classes", "Fighter", "Class Features", "Bonus Feats"],
    "entry_title": "Bonus Feats",
    "page_range": {
      "start": 37,
      "end": 38
    }
  }
}
```

## Chunk Adjacency 字段

`schemas/chunk.schema.json` 设置了 `additionalProperties: false`，并将以下 adjacency 字段声明为可选的字符串属性（不在 `required` 中）：

- `parent_chunk_id` —— 当 chunk 属于某个更大的条目或表格时的父 chunk 标识符。
- `previous_chunk_id` —— 前一相邻 chunk 的标识符。
- `next_chunk_id` —— 后一相邻 chunk 的标识符。

这些是已知的、schema 定义的字段 —— 生产者可以省略，但不得以其他自定义名称输出额外的 adjacency 字段。字段缺失意味着该 chunk 是边界块（所在 section 的第一个或最后一个，或无父级的顶层块）。

Adjacency 字段支撑那些需要 chunk 上下文而非仅单次检索命中的下游推理 —— 例如，合并共同描述一条规则的相邻 chunk，或在单独检索到某个法术条目时浮出其父 section。它们也被镜像进词法检索索引（见 `scripts/retrieval/lexical_index.py`），使检索无需额外查询 chunk 对象即可读取。

## 答案段落中的 source_ref 与 locator

`source_ref` 与 `locator` 在 `schemas/common.schema.json` 中一次性定义，并被规范文档、chunk 与 citation 原样复用。这是从摄入一路贯通到最终答案的溯源链：

1. 摄入阶段为每个规范文档附上 `source_ref` 与 `locator`。
2. Chunker 将它们传播（可能窄化 `locator`）到每个产出的 chunk。
3. 检索层在每个证据项上保留两个字段（见 `scripts/retrieval/evidence_pack.py::EvidenceItem`）。
4. 答案层将它们复制进 `schemas/answer_with_citations.schema.json` 中 `citations[]` 条目，每项是一个可复用对象，包含 `citation_id`、`chunk_id`、`source_ref`、`locator`、`excerpt`。
5. `answer_segments[].citation_ids` 通过 id 引用这些 citation 对象，将 claim 文本绑定到已保留的溯源。

由于 `source_ref` 与 `locator` 端到端保持相同形态，答案渲染可以在无需字段翻译的情况下，将一个被引段落解析回其来源。Chunk 内窄化（例如某个具体段落）存在于 citation 层的 `locator` 与 `excerpt` 里，而非在重复的 chunk 记录中 —— 见 `docs/citation_policy.md` §5。

## 契约落点

本契约适用于以下文件：

- `configs/source_registry.yaml`
- `configs/bootstrap_sources/srd_35.manifest.json`
- `schemas/common.schema.json`
- `examples/canonical_document.example.json`
- `examples/chunk.example.json`
- `examples/answer_with_citations.example.json`

若未来 schema 与本文冲突，应先更新本文，或在同一 PR 中同时更新。
