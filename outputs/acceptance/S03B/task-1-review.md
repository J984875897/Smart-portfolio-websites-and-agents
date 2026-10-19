# S03-B Task 1 independent review

**Mode:** PR Review  
**Scope:** Binding design, Task 1 plan, task-1.diff, and the four Task 1 files (alignment core, synthetic fixture, tests, acceptance script).  
**Health Score:** 80/100  
**Verdict:** Task 1 needs the period-finality and provenance fixes below before Task 2 consumes its interface. The fixed 60-month matrix, no-fill behavior, early/late synthetic scenarios, required FX fields, and original upstream failure retention otherwise match the specified behavior.

## Findings

### Critical — an unfinished monthly period can be accepted

**Symptom:** [alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/src/portfolio/data/alignment.py:40) rejects only an end month *later* than the Hong Kong decision month. Lines 89–100 require the observation to be within seven days of its month-end label and available by the decision, but never require the labelled month to have reached its last valid valuation day. [test_alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/tests/test_alignment.py:58) explicitly expects a January 31 monthly return to pass at January 24, with January 24 declared as both the end valuation and availability time.  
**Source:** *Domain-Driven Design* — the code conflates a recently observed mark with a completed monthly return, a domain distinction stated in the binding design.  
**Consequence:** A 60-month matrix may include an unfinished January return at a January 24 decision, creating look-ahead bias even though all parsed timestamps are ordered correctly. The source_name free-text declaration cannot establish finality by itself.  
**Remedy:** Enforce a conservative maturity rule for each period and update the boundary test to distinguish seven-day staleness from period completion. Preserve the explicitly required January 31 Hong Kong 17:00 result and February 1 Hong Kong 06:00 cross-market result; a blanket first-of-next-month rule would break those acceptance cases. **Status at review handoff:** core implementer is adding a local-date/FX-date maturity guard; re-review that change and the revised test before closing this finding.

### Warning — filtering an uploaded timing table misattributes its physical row

**Symptom:** [alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/src/portfolio/data/alignment.py:55) pairs each current row with `timing.attrs['source_rows'][i]`. Pandas retains those attrs when a file-backed DataFrame is filtered, but the list still refers to the original rows. Focused reproduction: load two timing records on physical CSV rows 2 and 3 with `read_file`, filter to the second record, and align its month. The resulting `timing_source_row` is 2; the source record is on row 3.  
**Source:** *The Pragmatic Programmer* — provenance is encoded in parallel positional structures that cease to move together after ordinary DataFrame transformations (a knowledge-coupling problem).  
**Consequence:** Coverage can point a reviewer to the wrong row in the uploaded evidence. A differently sized selection may also cause indexing errors in this path.  
**Remedy:** Bind physical-row metadata to each row at import or preserve a stable original-row index through filtering, then add a filtered-upload provenance test. Do not infer physical rows from the current DataFrame position.

## Verification and limits

The provenance case was reproduced with one focused Python call; the full suite was not rerun. The reported 23 passing targeted tests and offline synthetic script result are from task-1-report.md, not independently rerun here. This review covers the immutable task-1.diff; later fixes require a focused re-review. No code files were changed by this review.

## Focused re-review of task-1-fixed.diff

**Verdict:** Approved for Task 2 consumption against the amended binding spec. Both findings above are closed; the updated review score is **100/100**. This approval applies to the Task 1 core and its declared-evidence contract, not to the truth of a supplier's final-valuation or historical-availability claims.

- **Period maturity closed.** [alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/src/portfolio/data/alignment.py:92) now blocks a period before its month-end date in the asset's market timezone; foreign rows also wait for that date in UTC for FX. This implements the explicit rule added to the binding spec. [test_alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/tests/test_alignment.py:117) covers January 24 rejection, January 31 acceptance, a New York boundary, and the independent UTC FX boundary. The seven-day stale observation case is accepted only at a January 31 decision, with availability equal to the decision; it no longer allows use on January 24. The original early HKD and late USD synthetic cases remain represented in tests and the acceptance script.
- **Physical provenance closed.** [alignment.py](/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/src/portfolio/data/alignment.py:53) reparses the complete uploaded bytes, compares content and index with the passed frame, rejects filtered/reordered/reindexed frames, and then uses only reparsed metadata. The new tests cover transformed CSV frames, a blank physical CSV line with forged attrs, and a non-first named XLSX sheet. This resolves the demonstrated row-3-reported-as-row-2 case without trusting uploaded provenance columns.

The updated task-1-report.md records targeted **31 passed in 3.49s** and a passing offline acceptance script. I inspected the updated diff and tests but did not repeat those commands. The maturity rule is deliberately day-level: it cannot certify that a supplier's declared observation was truly that market's final valuation, as the binding spec explicitly notes. No further material spec or code-quality finding arose from the fixes.
