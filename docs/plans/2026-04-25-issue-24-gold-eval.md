# Issue #24 — Phase 1 Gold-Set Eval Run with Tagged Failures

> **Status:** design
> **Target issues:** #24 (primary), #5 (rollup — closes once this lands)
> **Author:** 2026-04-25

## 1. Goal

Build the Phase 1 regression-eval harness: run the rule-based answer pipeline
(`build_answer(retrieve_evidence(question))`, shipped under #23) against every
case in `evals/phase1_gold.yaml`, classify each outcome with interpretable
failure tags, and commit a stable per-case report. The harness is a
**reporter**, not a CI gate; failures show up as tagged data, not red builds.

The point is to give the next round of retrieval / shaping / answer changes
a fixed reference: change a thing, rerun, diff the tags.

## 2. Scope and non-goals

### In scope

- New package `scripts/eval/`: contracts, runner, tagger, report writer.
- One CLI entry point, `scripts/run_phase1_eval.py`, that runs the full set
  and writes both `evals/reports/phase1_gold_latest.json` (machine) and
  `evals/reports/phase1_gold_latest.md` (human summary).
- Per-case, per-citation diagnostics so the markdown report is reviewable
  case-by-case (per user direction on Q2 of brainstorm).
- Documentation: append a "How to rerun" section to `evals/README.md`.
- Tests over synthetic cases for every failure tag.

### Non-goals

- Pass/fail gating in CI. The harness exits 0 regardless of tag counts;
  consumers (humans, future CI) interpret the report.
- LLM-based citation assessment. `citation_mismatch` v1 is a token-overlap
  heuristic, deliberately weak and explicit about that.
- Multi-run trend analysis or time-series dashboards. v1 keeps a single
  `_latest.{json,md}` pair; archives are YAGNI.
- The Chinese mirror (`phase1_gold.zh.yaml`). Out of scope; v1 evaluates
  the English set only.
- Changes to `evals/phase1_gold.yaml`. v1 consumes the existing case
  contract verbatim.

## 3. Proposed design

### 3.1 Pipeline

```
phase1_gold.yaml  →  run_case (per case)  →  CaseOutcome  →  Report
                          │
                          ├─ retrieve_evidence(question)
                          ├─ build_answer(pack)
                          └─ tag_case(case, pack, result) → tags
```

`run_phase1_eval.py` loads all cases, executes them sequentially (no
parallelism in v1; the index is small and tagging is cheap), and writes
the report.

### 3.2 Failure tag taxonomy

Eight tags, each derived from one of the four fields a `CaseOutcome` carries
(`actual_answer_type`, citation `source_ref`, citation `locator`, support
type on the primary segment) compared against the case's
`expected_*` fields.

| Tag | Trigger condition |
|---|---|
| `retrieval_miss` | `actual_answer_type == "grounded"` AND no citation's `source_ref["source_id"]` ∈ `expected_source_ids`. (For abstain-expected cases this tag never fires.) |
| `wrong_section` | `grounded` AND `expected_section_or_entry` is non-empty AND no citation's `locator["section_path"]` overlaps the **head** of `expected_section_or_entry`. See §3.3 for the matching rule. |
| `wrong_entry` | `grounded` AND `expected_section_or_entry` is non-empty AND at least one citation matches the section root AND no citation's `locator["section_path"]` (or `locator["entry_title"]`) matches the **tail** of `expected_section_or_entry`. |
| `citation_mismatch` | `grounded` AND at least one citation's `excerpt` shares **zero** tokens with the gold case's `question` after stopword removal. Per-citation flag rolled up to a per-case tag. **Independent of other tags** — fires regardless of whether the case is otherwise clean. See §3.4. |
| `unsupported_inference` | `grounded`, primary segment's `support_type == "supported_inference"`, AND `expected_behavior == "direct_answer"`. (When `expected_behavior == "supported_inference"`, this is the right answer — no tag.) |
| `missing_abstain` | `actual_answer_type == "grounded"` AND `expected_behavior == "abstain"`. |
| `unnecessary_abstain` | `actual_answer_type == "abstain"` AND `expected_behavior != "abstain"`. |
| `edition_boundary_failure` | Any citation whose `source_ref["edition"] != "3.5e"`. (Constraint filters in `scripts/retrieval/filters.py` should make this impossible — if it fires, it's a regression of the hard filter, which is exactly what tagged data is for.) |

Tags are non-exclusive: a single case can carry multiple tags. The runner
collects all that fire. **Empty-`expected_section_or_entry` handling**:
when the gold case carries `expected_section_or_entry: []` (e.g. all
abstain cases in v1), the `wrong_section` and `wrong_entry` checks are
skipped entirely — the section/entry tagger has nothing to compare against,
and any tagging would be vacuously wrong. The other six tags still apply
normally.

### 3.3 Section / entry matching rule

`expected_section_or_entry` is a list of strings ordered roughly
outer-to-inner, but the gold set is loose about whether the first element
is a source-file name (`"CombatI.rtf"`), a section root (`"Combat: Movement"`),
or a section synonym. The matching rule has to be tolerant.

**Pre-check — empty list short-circuits:** if
`expected_section_or_entry == []`, this matcher is **not invoked**.
The §3.2 trigger conditions for `wrong_section` and `wrong_entry`
require a non-empty list, so the indexing below (`[0]`, `[-1]`) is only
ever reached on a list with at least one element.

**Definitions** (assume `len(expected_section_or_entry) >= 1`):

- `expected_head`: `expected_section_or_entry[0]` after dropping a trailing
  `.rtf` extension and lowercasing. If the result still doesn't look like
  a section name (it's a filename like `combati`) and a second element
  exists, fall back to `expected_section_or_entry[1]` lowercased.
  If only one element exists and it's filename-shaped, use it as-is —
  matching is a substring test, so a filename that happens to share
  a token with a section root will still match.
- `expected_tail`: the last element of `expected_section_or_entry`,
  lowercased.

**Matching:**

- A citation **matches the section root** if any of its
  `locator["section_path"]` elements (lowercased) contains `expected_head`
  as a substring, OR the colon-prefix of any `section_path` element
  matches the colon-prefix of `expected_head` (so `"Combat: Attacks of
  Opportunity"` and `"Combat"` both match an expected head of `"combat"`).
- A citation **matches the entry** if `expected_tail` is a substring of any
  `locator["section_path"]` element OR of `locator["entry_title"]` (when
  present).

**Result:**

- `wrong_section` fires when no citation matches the section root.
- `wrong_entry` fires when at least one citation matches the section root
  but no citation matches the entry. (If both fire, we report only
  `wrong_section` — the more specific tag wins when sections are wrong
  too.)

This is intentionally generous; the gold set was built before the
hierarchical-chunking work (#60) and uses a mix of section labels and
filenames. Tightening is a follow-up once #60 lands.

### 3.4 `citation_mismatch` heuristic

For each citation in a grounded answer:

1. Tokenize `case.question` — lowercase, split on non-word chars, drop
   stopwords (use a small built-in list — see §4.4).
2. Tokenize `citation.excerpt` the same way.
3. If the intersection is **empty**, flag this specific citation.

A case is tagged `citation_mismatch` if **any** citation flags. The
report's per-case detail includes a `citations: [{citation_id, mismatch:
true|false, shared_tokens: [...]}]` block so a reviewer can see exactly
which citations flagged and why.

This is a deliberately weak signal:

- False positives expected on heavily paraphrased questions where the
  excerpt uses synonyms (e.g. "How do I cast a spell when surrounded?"
  vs an excerpt about "casting defensively"). The report exposes the
  shared-token list so a reviewer can confirm or override.
- False negatives expected on excerpts that share generic tokens but
  don't actually support the claim. v1 tolerates these; the v2 LLM
  composer will tighten this.

The point of the heuristic is to surface obvious cases (citation excerpt
about something completely unrelated) for the eval reviewer to inspect,
not to be a rigorous NLI judge.

### 3.5 Per-case outcome shape

```python
@dataclass(frozen=True)
class CaseOutcome:
    eval_id: str
    question: str
    question_type: str
    expected_behavior: Literal["direct_answer", "supported_inference",
                                "narrow_answer", "abstain"]
    actual_answer_type: Literal["grounded", "abstain"]
    tags: tuple[str, ...]                 # failure tags; empty == clean
    actual_summary: ActualSummary         # see below
    citation_checks: tuple[CitationCheck, ...]
    diagnostics: dict[str, Any]           # abstain code, signal counts, etc.

@dataclass(frozen=True)
class ActualSummary:
    primary_excerpt: str | None           # None if abstained
    primary_support_type: str | None      # None if abstained
    citations: tuple[CitationSummary, ...]
    abstention_reason: str | None         # None if grounded

@dataclass(frozen=True)
class CitationSummary:
    citation_id: str
    chunk_id: str
    source_id: str
    edition: str
    section_path: tuple[str, ...]
    entry_title: str | None

@dataclass(frozen=True)
class CitationCheck:
    citation_id: str
    source_match: bool                    # source_id ∈ expected_source_ids
    section_match: bool | None            # None when expected_section_or_entry == []; see §3.3
    entry_match: bool | None              # None when expected_section_or_entry == []; see §3.3
    edition_match: bool                   # edition == "3.5e"
    token_overlap: tuple[str, ...]        # for citation_mismatch heuristic
    citation_mismatch: bool               # token_overlap == ()
```

### 3.6 Report shape — JSON

`evals/reports/phase1_gold_latest.json`:

```json
{
  "dataset_id": "phase1_gold_v1",
  "run_started_at": "2026-04-25T12:34:56Z",
  "case_count": 30,
  "tag_counts": {
    "retrieval_miss": 4,
    "wrong_section": 2,
    "wrong_entry": 3,
    "citation_mismatch": 1,
    "unsupported_inference": 0,
    "missing_abstain": 0,
    "unnecessary_abstain": 1,
    "edition_boundary_failure": 0,
    "_clean": 19
  },
  "behavior_match_rate": 0.83,
  "cases": [
    { /* CaseOutcome dict */ }
  ]
}
```

`_clean` counts cases with empty `tags`. `behavior_match_rate` is the
share of cases where the actual answer_type matches the expected behavior
class (grounded vs abstain), rounded to 2 decimals.

### 3.7 Report shape — Markdown

`evals/reports/phase1_gold_latest.md` opens with the metadata header and
tag-count table, then lists **failing cases first** (grouped by tag,
in the §3.2 tag order). The clean tail is collapsed at the end into a
one-line "N clean cases (P1-…, P1-…, …)" summary so reviewers can focus
on failures. Per-case template (failing case form):

```markdown
### P1-DL-001 — direct_lookup → direct_answer

**Question:** When does a character provoke an attack of opportunity from movement?

**Tags:** *(clean)*    (or, e.g.) **Tags:** `wrong_entry`, `citation_mismatch`

**Expected:** sources=[srd_35], section_or_entry=["Combat: Attacks of Opportunity", "Movement"]

**Actual:** grounded · primary support: direct_support
> *(primary excerpt, truncated to ~200 chars)*

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | Combat > Attack of Opportunity | yes | yes | no | ["attack", "opportunity"] |
| cit_2 | srd_35 · 3.5e | Spells > Magic Missile | no | n/a | n/a | [] |
```

The `section` and `entry` columns render `n/a` when the gold case's
`expected_section_or_entry` is empty (i.e. the corresponding
`CitationCheck` field is `None`).

### 3.8 CLI

`scripts/run_phase1_eval.py`:

```
python scripts/run_phase1_eval.py
python scripts/run_phase1_eval.py --top-k 10
python scripts/run_phase1_eval.py --eval-set evals/phase1_gold.yaml
python scripts/run_phase1_eval.py --output-dir evals/reports
python scripts/run_phase1_eval.py --skip-md
```

- Default eval set: `evals/phase1_gold.yaml`.
- Default output dir: `evals/reports/`.
- `--skip-md` writes only JSON (faster, useful in tight loops).
- Missing-db guard: same shape as `answer_question.py` — clear stderr +
  exit 1.
- Always exits 0 on a successful run, regardless of tag counts. (Future:
  a `--fail-on TAG` flag to gate CI; out of scope for v1.)
- Stdout: prints the tag-count table and the count of clean cases.

## 4. Data model

### 4.1 New dataclasses (`scripts/eval/contracts.py`)

`CaseOutcome`, `ActualSummary`, `CitationSummary`, `CitationCheck` per §3.5,
plus:

```python
@dataclass(frozen=True)
class GoldCase:
    eval_id: str
    question: str
    question_type: str
    expected_source_ids: tuple[str, ...]
    expected_section_or_entry: tuple[str, ...]
    expected_behavior: Literal["direct_answer", "supported_inference",
                                "narrow_answer", "abstain"]
    expected_answer_notes: str

@dataclass(frozen=True)
class EvalReport:
    dataset_id: str
    run_started_at: str
    case_count: int
    tag_counts: dict[str, int]
    behavior_match_rate: float
    cases: tuple[CaseOutcome, ...]
```

### 4.2 Module layout

```
scripts/eval/
  __init__.py
  contracts.py          # GoldCase, CaseOutcome, …, EvalReport
  loader.py             # load_gold_set(path) → tuple[GoldCase, ...]
  runner.py             # run_case(case, ...) → CaseOutcome
  tagger.py             # tag_case(case, pack, result) → (tags, checks)
  matching.py           # _section_match, _entry_match, token utilities
  report.py             # write_json, write_markdown, format_tag_counts
scripts/run_phase1_eval.py  # CLI

tests/test_eval_loader.py
tests/test_eval_tagger.py
tests/test_eval_matching.py
tests/test_eval_report.py
tests/test_eval_runner.py   # smoke: per-case orchestration over fakes
```

### 4.3 Stopword list

A short built-in list used by the citation_mismatch heuristic and the
shared-tokens display:

```python
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "have", "has", "had", "having",
    "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "and", "or", "but", "not", "no", "if", "then", "else",
    "i", "you", "he", "she", "it", "we", "they", "this", "that",
    "what", "when", "where", "who", "why", "how", "which",
    "can", "could", "would", "should", "may", "might", "must",
    "shall", "will",
})
```

Short and project-internal. Not pulling NLTK or another dependency for
this; the heuristic doesn't need fine resolution.

### 4.4 Tokenization

```python
import re
_WORD = re.compile(r"[a-z0-9]+")

def _tokenize(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS}
```

Identical for question and excerpt tokenization. Stable across Python
versions; no Unicode edge cases for D&D English text.

## 5. Key decisions

1. **Reporter, not gate.** v1 always exits 0. Tagged data is the
   deliverable; gating is policy that the project doesn't yet have data
   to set defensibly.
2. **Per-citation `citation_mismatch` with rolled-up case tag.**
   Heuristic is weak and explicit about that; the per-citation detail
   in the markdown lets a reviewer override visually. Direction from
   user feedback during brainstorm.
3. **Generous section/entry matching.** Substring + colon-prefix
   tolerance, because the gold set was built before hierarchical
   chunking and uses mixed labels (filenames, section roots, synonyms).
   Tighten when #60 lands.
4. **JSON + Markdown side-by-side, no archives.** Markdown is for
   review-at-a-glance; JSON is for diff. Archives are YAGNI until we
   have a use case.
5. **No parallelism.** 30 cases × ~50 ms each is well under a minute;
   the simplicity of sequential execution beats the complexity of
   process pools or asyncio for this size.
6. **Single eval set in v1.** The Chinese mirror exists but adds new
   dimensions (tokenization, stopwords, expected-section labels in
   Chinese). Defer to a follow-up.

## 6. Alternatives considered

- **Pass/fail CI gate from day one.** Rejected: setting thresholds without
  a baseline would either be too tight (red CI on first run) or too loose
  (no value). The gate should follow the first few real reports.
- **LLM-graded citation_mismatch.** Real NLI scoring of citation excerpt
  against question. Better signal, more cost + non-determinism + new
  dependency. Defer to v2 alongside the LLM composer.
- **Skip citation_mismatch in v1.** Was the original brainstorm
  recommendation. User overrode in favor of weak heuristic + per-case
  visibility — the right call because the alternative ("not evaluated"
  in the report) hides the question entirely.
- **Single inline CLI script.** Lighter footprint but tag rules and
  matching logic are worth unit-testing in isolation. Module layout
  pays for itself within one round of tag-rule tuning.
- **Timestamped report archives.** Useful for bisecting; not useful
  enough yet to justify the directory growth. Add when the gold set
  triples in size or when we actually want to bisect.

## 7. Risks and open questions

1. **Section-matching false positives.** Substring matching on
   short tokens like "combat" can over-match. Mitigation: per-case
   citation table makes it visible; tighten when the gold set adds
   negative section-match cases.
2. **Citation_mismatch noise.** Paraphrased questions will trigger
   the heuristic. Mitigation: shared-tokens column lets the
   reviewer see at a glance whether the flag is real.
3. **Gold set's `expected_section_or_entry` is loosely structured.**
   First element sometimes is a filename, sometimes a section root,
   sometimes a synonym. The matching rule (§3.3) hand-waves this with
   substring tolerance and a `.rtf` strip. If the loose structure
   ever causes a high false-positive `wrong_section` count, the gold
   set itself should be normalized (separate work item).
4. **Behavior class collapse.** Mapping
   `{direct_answer, supported_inference, narrow_answer}` → `grounded`
   loses information. v1 uses `unsupported_inference` to recover
   one slice (direct expected, supported produced). `narrow_answer`
   isn't represented in the v1 gold set, so we don't model it; if
   the set adds a `narrow_answer` case later, the tagger needs an
   explicit rule.
5. **No Chinese set evaluation.** `phase1_gold.zh.yaml` exists but
   isn't covered. Out of scope for v1; flagged as a follow-up.

## 8. Next steps

This PR is **docs-only**: it lands the design spec for #24 and does not
close it. #24's "Done when" criteria require an executable harness and
a committed report — both ship in the implementation PR, not here.

1. **This PR (docs-only).** Spec review and approval. Refs #24, #5;
   does not close them.
2. **Implementation PR (closes #24, contributes to #5).** Implement
   per §4.2 layout: contracts → loader → tagger + matching → report
   writer → runner → CLI. Tests covering each tag's trigger, the
   section/entry matching tolerance (including the empty-list
   short-circuit), the token-overlap heuristic, the report shape
   (both JSON and Markdown), and an end-to-end runner smoke against
   a small synthetic gold set. Run against the real index and commit
   `evals/reports/phase1_gold_latest.{json,md}` as PR evidence per
   `docs/standards/pr_evidence.md`. Append a "How to rerun"
   subsection to `evals/README.md`. Merge of the implementation PR
   closes #24; with #23 already merged, that PR also closes rollup #5.
3. **Follow-up backlog (out of scope for both PRs):**
   - Chinese set evaluation (`phase1_gold.zh.yaml`).
   - `--fail-on TAG` CI gate flag.
   - LLM-graded `citation_mismatch` once v2 composer lands.
   - Tighten section matching after #60 (hierarchical chunking) lands.
