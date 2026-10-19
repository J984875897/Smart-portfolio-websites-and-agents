# S03-B Task 2 independent review

**Mode:** PR Review  
**Scope:** Task 2 brief/report and immutable task-2.diff: alignment page, navigation, S03-A handoff, and AppTest changes.  
**Health Score:** 94/100  
**Verdict:** The fixed-window UI and stale-result controls are largely compliant, but the live handoff must handle an S03-A result with no valid returns before Task 2 is accepted.

## Findings

### Warning — all-blocked upstream HKD result is presented as a usable handoff

**Symptom:** [alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/app/views/alignment.py:41) checks only whether `hkd_result` and its origin exist and are current. Lines 49–56 accept its reconciliation without checking for any `status == 'valid'` row, and line 96 enables the calculation button. An S03-A run with every row blocked (for example, all foreign assets lacking required FX) therefore enters the window check with no valid upstream return. The page even labels that branch an “有效港币对照” at line 57.  
**Source:** *Code Complete* — a missing guard at an input boundary lets an invalid workflow state look actionable.  
**Consequence:** The user receives a 60-month exclusion result rather than the operation guidance required by the binding spec for “无有效上游数据”. They may spend effort preparing timing evidence for data that cannot pass the preceding S03-A check.  
**Remedy:** Treat an absent or empty set of valid S03-A rows as unavailable upstream input, show a short instruction to resolve S03-A blocks, disable the action, and add an AppTest with an all-blocked reconciliation. Keep the core's detailed blocked-row behavior for mixed valid/blocked inputs.

### Suggestion — real asset names are discarded in the Chinese summary

**Symptom:** [alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/app/views/alignment.py:112) maps the “产品名称” column through `NAMES`, which contains only the five synthetic IDs. Every real saved-data asset therefore falls back to its `asset_id`, although `bundle.assets.name` is available in the live handoff.  
**Source:** *Domain-Driven Design* — the presentation loses a domain label that identifies the product being reviewed.  
**Consequence:** The compact Chinese summary is harder to inspect for real portfolios, especially when asset IDs are opaque.  
**Remedy:** Use `bundle.assets` to map real asset IDs to names and retain the existing synthetic labels for the artificial scenario. Add one real-handoff display assertion.

## Verified design points and limits

The page passes the full uploaded `read_file` frame to the approved core, preserving file/sheet/physical-row/hash binding. Its fingerprint covers decision, end month, mode, uploaded bytes/name/sheet, synthetic inputs, and the previous reconciliation; the prior live HKD origin compares source bundle assets, observations, and provenance content even when a version label is unchanged. Changed inputs clear both result and result-download controls. The UI calls `align_monthly` for calculations, keeps the synthetic case separate and labelled, uses a fixed 60-month result, and exposes Chinese summary, monthly status, full evidence, and report/coverage/matrix CSV downloads. The targeted 13-pass result is recorded in task-2-report.md; I did not rerun tests or browser checks. No production file was changed by this review.
