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

## 契约落点

本契约适用于以下文件：

- `configs/source_registry.yaml`
- `configs/bootstrap_sources/srd_35.manifest.json`
- `schemas/common.schema.json`
- `examples/canonical_document.example.json`
- `examples/chunk.example.json`
- `examples/answer_with_citations.example.json`

若未来 schema 与本文冲突，应先更新本文，或在同一 PR 中同时更新。
