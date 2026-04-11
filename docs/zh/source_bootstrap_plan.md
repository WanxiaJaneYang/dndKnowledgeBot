# 初始来源引导方案

> [English](../source_bootstrap_plan.md) | **中文**

## 1. 目标

定义 Phase 1 的第一批准入语料，让后续的评测、摄入、分块与检索都围绕同一批真实来源展开。

这份文档要解决的问题是：

> 第一批 corpus 先收什么、按什么准入、目录怎么落地？

## 2. 范围与非目标

### 范围内

- 选定 Phase 1 的 bootstrap source
- 定义第一批来源的准入规则
- 定义最低 provenance 要求
- 定义 bootstrap 集合的 edition 写法
- 定义 `data/raw/`、`data/extracted/`、`data/canonical/` 的首版目录布局

### 非目标

- 一次性确定长期完整语料范围
- 决定最终 extraction 工具链
- 一次性准入所有核心规则书
- 解决后续 errata / FAQ 覆盖策略
- 决定最终 chunking 或 retrieval 的实现细节

## 3. 方案

Phase 1 的 bootstrap 应先只准入 **`srd_35`**。

这意味着：

- 第一批 admitted source slice 是 D&D 3.5e SRD
- 第一版 gold evaluation set 先围绕 SRD 能覆盖的问题编写
- 第一轮 ingestion spike 先处理 SRD，而不是直接从 PHB / DMG / MM PDF 开始

PHB、DMG、MM 仍然保留在 registry 中，但在 bootstrap 阶段先不准入，等第一条真实链路验证完 source、locator、ingestion contract 之后再扩展。

bootstrap 阶段的准入规则是：

- 来源必须在 registry 中被明确选中
- 来源必须严格属于 D&D 3.5e 边界
- 来源必须有清晰 provenance
- 来源必须显式标注 `source_type`、`authority_level`、`edition`
- 来源的原始输入形式必须稳定，可复现后续摄入

下列情况应拒绝或延后：

- edition 身份不清
- provenance 缺失或过弱
- 来源是非官方评论、同人内容或 AI 生成摘要
- extraction 路径噪声过大，已经妨碍 contract 验证

## 4. 数据模型或模式

### 4.1 Registry 状态

bootstrap 准入应使用以下状态：

- `admitted_bootstrap`
  已进入第一批准入语料，现在就可以用于评测与 ingestion spike。
- `planned_later`
  明确属于后续 Phase 1 扩展范围，但还没进入 bootstrap slice。
- `excluded_phase1`
  明确不在当前阶段范围内。

目前还没有来源使用 `excluded_phase1`。这个状态先保留，供后续显式排除来源时直接使用。

### 4.2 Provenance 字段

每个 bootstrap 来源至少应保留：

- `source_id`
- 来源标题
- `edition`
- `source_type`
- `authority_level`
- 描述原始制品或上游形式的说明
- 足以支撑后续 citation 的 locator 信息
- 已知 extraction / structure caveat 说明

对于 `srd_35`，bootstrap 阶段优先保留 source-native 结构；页码引用等到后续准入真的带分页来源时再强化。

### 4.3 Edition 写法

bootstrap 集合中的 edition 统一写成：

- `3.5e`

不要在结构化元数据里混用：

- `3.5`
- `v3.5`
- `D&D 3.5`

### 4.4 目录布局

bootstrap corpus 先按 `source_id` 组织：

```text
data/
|-- raw/
|   `-- srd_35/
|-- extracted/
|   `-- srd_35/
`-- canonical/
    `-- srd_35/
```

含义如下：

- `data/raw/srd_35/` 放原始来源制品或整理后的来源快照
- `data/extracted/srd_35/` 放提取后的文本或中间结构化结果
- `data/canonical/srd_35/` 放 canonical document JSON

## 5. 关键决策

### 先用 `srd_35`

之所以先选 `srd_35`，是因为它最适合低成本验证产品 contract。

和直接从 PDF 起步相比，SRD-first 有这些好处：

- 结构更清晰
- extraction 噪声更低
- 更容易先把非分页 locator 设计跑通
- 更快看到 grounded answer、citation rendering、abstain 行为是否成立

### PHB / DMG / MM 先延后

项目应先在一个结构更干净的真实来源上证明 contract 成立，再去面对 OCR、页码映射、复杂版式恢复这些问题。

### 保留 `excluded_phase1`

虽然当前还没用到，但这个状态是有意义的。以后需要显式排除某类来源时，不必再临时发明新词。

## 6. 备选方案

### 方案 A：先用一个 PHB 章节

优点是更早测试书籍型页码引用。

这次没选它，因为：

- 它太早把版式与提取噪声引进来了
- 会让 locator 和 ingestion 验证过度依赖 PDF 质量

### 方案 B：一开始就并行准入多种窄来源

优点是覆盖面更快变宽。

这次没选它，因为：

- source policy 还没稳定时，多来源会放大歧义
- 失败后更难判断到底是哪一层坏了

### 方案 C：一次性准入所有核心规则书

优点是看起来更接近最终产品。

这次没选它，因为：

- 第一轮 contract 验证的面太大
- 容易把 source 和 locator 的问题埋在 corpus 规模里

## 7. 风险与开放问题

- SRD 的结构虽然比 PDF 干净，但仍可能暴露 locator 或 extraction 边角问题。
- SRD-first 还不能真正测试页码型 citation。
- 后续有些问题可能只存在于 PHB 而不在 SRD 中，所以 gold set 需要诚实反映 SRD 覆盖边界。
- `srd_35` 之后扩展哪个来源仍是开放问题。目前最可能的是一个窄 PHB slice，但还不是锁定决策。

## 8. 下一步

- 在 source registry 中把 `srd_35` 标成 `admitted_bootstrap`
- 围绕 SRD 可覆盖问题编写第一版 gold evaluation set
- 对 `data/raw/srd_35/` 跑第一轮 ingestion spike
- 只有当 bootstrap slice 证明 contract 足够稳时，才扩展到 `srd_35` 之外的来源
