# SUBMISSION

## Approach

The analysis is implemented as a single-pass Python script that processes
99 JSON call-extraction files (92 with extracted use cases) through a linear
pipeline:

1. **Ingest** — read every JSON file, flatten safety and non-safety use cases
   into a tabular structure (one row per use case).
2. **Speaker classification** — parse email domains from evidence speaker
   fields to distinguish Voxel reps from customers.
3. **Cross-bucket duplicate detection** — within each call, compare safety
   and non-safety labels using string similarity + containment + token-overlap 
   fallback to find concepts placed in both buckets.
4. **Label normalization** — map raw labels to canonical labels via a
   keyword-first, fuzzy-match-second strategy, then assign each canonical
   label to a thematic taxonomy category.
5. **Quality issue tagging** — flag five issue types (cross-bucket duplicate,
   vendor-only evidence, label inflation, generic admin, inconsistent
   granularity) using rule-based heuristics.
6. **Opportunity scoring** — rank non-safety canonical labels by a composite
   score that rewards breadth of customer mentions and penalizes quality
   issues.

## Tools and Libraries

- **Python 3.10+** — language runtime
- **pandas** — tabular data manipulation and aggregation
- **difflib.SequenceMatcher** — string similarity for duplicate detection and
  fuzzy label matching (no external NLP dependency)
- **json / pathlib** — file I/O and JSON parsing
- **re / string** — regex-based speaker parsing and punctuation stripping
- **logging** — structured diagnostic output to stderr

No machine-learning models, LLM APIs, or databases are used.  The entire
pipeline runs locally with a single `pip install pandas` beyond the standard
library.

## Key Decisions and Trade-offs

- **Keyword mapping before fuzzy matching** — deterministic regex-aware
  lookup handles the majority of labels quickly and predictably; entries
  containing regex metacharacters (e.g. ``monitor.*adoption``) are compiled
  as patterns, while plain strings are matched as literal substrings.
  Fuzzy matching only runs on the remainder.  This avoids false merges that
  pure similarity would produce on short labels.
- **Configurable similarity threshold (0.65)** — a single constant controls
  both cross-bucket detection and label clustering, making it easy to tune.
- **Rule-based quality detection** — heuristics (keyword lists, label-length
  statistics) are transparent and auditable, though they may under- or
  over-flag edge cases compared to a trained classifier.
- **Scoring formula** — `call_count × 2 + customer_evidence_count −
  quality_issue_count` weights breadth of mentions most heavily while
  penalizing noisy data.  The multiplier is a judgment call; a different
  weighting would shift rankings.

## Assumptions and Limitations

- Each JSON file is treated as one unique customer call.
- Speaker role relies solely on email domain; names without email addresses
  are classified as "unknown."
- Label-inflation and generic-admin flags use keyword heuristics — they are
  directionally correct but not exhaustive.
- The taxonomy was built by inspecting the data; a different analyst might
  draw category boundaries differently.
- Fuzzy matching with `SequenceMatcher` is adequate for this dataset size but
  would not scale well to thousands of labels without switching to a faster
  library (e.g., `rapidfuzz`).
