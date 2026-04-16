# SRD 3.5 语料健康报告

> [English](../corpus_health_srd35.md) | **中文** — Issue #27 全流水线运行后生成。

## 概要

| 指标 | 值 |
|---|---|
| 来源文件（RTF） | 86 |
| 规范文档 | 2 743 |
| 分块 | 2 743 |
| 摄入错误 | 0 |
| 流水线 | fetch → ingest → chunk (v1-section-passthrough) |

全部 86 个 RTF 文件均无错误地完成摄入。

## 分块类型分布

| 类型 | 数量 | 占比 |
|---|---|---|
| `subsection` | 2 639 | 96.2 % |
| `generic` | 64 | 2.3 % |
| `rule_section` | 40 | 1.5 % |

`subsection` 占绝对多数是符合预期的：类型分类器仅在叶节点 section-path token 恰好与根节点 token 完全一致时（如 `['Races', 'Races']`）才将文档提升为 `rule_section`。大部分章节内容落在不同的子标题下，被正确分为 `subsection`。细粒度类型（`spell_entry`、`feat_entry` 等）需要 Phase 2 的条目级拆分。

## 内容长度分布（字符数）

| 百分位 | 字符数 |
|---|---|
| min | 60 |
| p25 | 335 |
| median | 846 |
| p75 | 1 948 |
| p90 | 3 362 |
| p99 | 14 832 |
| max | 96 958 |

中位分块约 850 字符（约 170 token）。分布右偏，原因是密集的结构化章节（法术列表、魔法物品目录）在 Phase 2 条目级解析之前无法进一步拆分。

## 边界过滤器修复（本 PR）

修复前的初次运行产出 **4 006 个分块**，存在两类误拆分：

### 1. 法术 / 异能属性行（消除 1 107 个误拆分）

RTF 法术条目将属性字段（Components、Range、Duration、Level 等）以粗体格式排版，导致 section detector 将其误识别为章节标题。每个法术因此被碎片化为约 8 个微分块，标题类似 `"Components: V, S"` 或 `"Spell Resistance: Yes"`。

**受影响文件（17 个）：** `SpellsA-B`、`SpellsC`、`SpellsD-E`、`SpellsF-G`、`SpellsH-L`、`SpellsM-O`、`SpellsP-R`、`SpellsS`、`SpellsT-Z`、`EpicSpells`、`DivineDomainsandSpells`、`PsionicSpells`、`PsionicPowersA-C`、`PsionicPowersD-F`、`PsionicPowersG-P`、`PsionicPowersQ-W`、`EpicMonsters(G-W)`。

**修复：** 在 `boundary_filter.py` 中添加 `_looks_spell_block_field()`，将属性行向前合并到前一个章节。修复后剩余为零。

### 2. `Table:` 命名标题被误认为章节（6 个文件）

标题为 `Table: Epic Leadership`、`Table: Armor and Shields` 等的表格被当作独立章节，而非合并到父章节。现有合并逻辑只捕获了包含 `|` 的表格行语法。

**受影响文件：** `DivineAbilitiesandFeats`、`EpicFeats`、`EpicLevelBasics`、`EpicMagicItems1`、`EpicMagicItems2`、`EpicSpells`。

**修复：** 扩展 `_looks_table_label_title()` 以同时匹配 `Table:` 前缀标题。修复后剩余为零。

**净结果：4 006 → 2 743 个分块（合并 1 263 个误拆分）。**

## 已知遗留问题

### Phase 2 — 条目级聚合（大分块）

21 个分块超过 20 000 字符。这些是将大量独立条目（法术、魔法物品、生物类型）聚合为单一规范文档的章节，原因是 Phase 1 的 section-passthrough 策略止步于 RTF 章节标题级别：

| 字符数 | 章节 |
|---|---|
| 96 958 | `SpellsS` / SpellsS intro（所有 S 级法术） |
| 79 974 | `TypesSubtypesAbilities` / TYPES, SUBTYPES, & SPECIAL ABILITIES |
| 77 190 | `SpellsP-R` / SpellsP-R intro |
| 71 154 | `MagicItemsV` / Wondrous Item Descriptions |
| … | （另外 17 个位于法术 / 魔法物品章节） |

这是 v1-section-passthrough 的预期局限。解决方案需要 Phase 2 在摄入阶段进行条目级拆分（识别单独的法术条目、魔法物品条目等作为规范文档边界）。

大多数 embedding 模型支持 8 000+ token（约 40 000 字符），因此在 embedding 阶段不会被截断，但对于这些大块内特定法术或物品的检索精度会较差。

### 已知误拆分 — `MagicItemsV` / `Opal: Daylight`（46 320 字符）

`MagicItemsV.rtf` 中 Helm of Brilliance 的描述将宝石-法术子条目以粗体标题格式排版（如 `Opal: Daylight`）。边界检测器将其中一个提升为章节边界，导致奇妙物品列表从 Helm of Brilliance 中间被截断，生成了一个内容有效但标题错误的分块。

这是单文件问题。修复需要边界过滤器理解物品描述内的 `ItemType: SpellName` 格式粗体文本不是章节边界——比当前修复范围更深层的变更。

### 法术章节导言大块

合并属性行拆分后，法术名称标题本身不再构成章节边界，因为在下一个粗体行之前的直接正文内容通常很短（一般只有学派描述，如 "Conjuration [Creation]"）。法术条目因此合并为每个文件一个大型导言章节。

这是 Phase 1 的已知局限：条目级法术拆分需要即使标题与下一粗体行之间文本很短也能识别法术名称标题。已列入 Phase 2 工作。

## 对下一步的意义

语料已足够干净，可以继续进行向量索引：

- 无摄入错误
- 无残留的属性行误拆分
- 中位分块（约 850 字符）完全在 embedding 模型上下文窗口范围内
- 大型聚合分块是检索精度问题而非正确性问题——查询仍能找到正确的文件/章节，只是粒度不如完整条目拆分的语料

Phase 2 条目级拆分应在首次针对单个法术或魔法物品名称的评测运行之前安排。
