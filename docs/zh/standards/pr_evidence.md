# PR 证据标准

> [English](../../standards/pr_evidence.md) | **中文**

流水线行为变更的 PR 必须提供可检查证据，而不只是“tests passed”。

## 按 PR 类型的最低证据要求

| PR 类型 | 必需证据 |
|---|---|
| Ingestion 变更 | 更新后的 fixture 预览（`tests/fixtures/PREVIEW.md`）和/或 `tests/fixtures/expected/` 下的 golden diff |
| Chunking 变更 | golden chunk diff + fixture 预览对应章节更新 |
| Retrieval 变更 | 基于 fixture corpus 的端到端示例（含 evidence handoff） |
| Schema 变更 | 更新后的 golden 输出 + schema validation gate 结果 |

## 基于 Fixture 的证据流程

1. 运行：`python scripts/preview_fixtures.py --update-golden`
2. 提交：
   - `tests/fixtures/srd_35/*.rtf`（来自真实 SRD 的 fixture 文件）
   - `tests/fixtures/srd_35/FIXTURE_SOURCE_MAP.json`
   - `tests/fixtures/PREVIEW.md`
   - `tests/fixtures/expected/extracted/*`
   - `tests/fixtures/expected/extracted_ir/*`
   - `tests/fixtures/expected/canonical/*`
3. 验证：`python -m unittest tests.test_golden_ingestion -v`

如果 PR 改变了流水线行为，但没有更新 preview/golden 证据，则视为不完整。
