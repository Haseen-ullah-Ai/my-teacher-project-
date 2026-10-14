# Northwind Retail Group — Q3 2025 Operations Memo

**From:** Chief Operating Officer  
**Date:** October 8, 2025  
**Distribution:** Regional vice presidents, Finance, Store Operations

## Summary

Q3 closed with uneven performance across Northwind Retail Group's four regions. Finance's approved baseline is in `regional_targets.csv`: North $215,000, South $200,000, East $225,000, and West $195,000. The sales extract is gross recognized sales, before returns. Managers should use that definition for target attainment and should not subtract estimated returns from the CSV. The data-quality review identified a missing revenue value and one unusually large transaction; the outlier must be checked against its source record before it is used in a forecast.

Store Operations recorded an overall supplier on-time delivery rate of 92% in an early draft dashboard, below the 94% pilot readiness threshold in the current expansion strategy. That aggregate is preliminary because several promised dates were entered after delivery and two suppliers had incomplete records. Regional leaders must not treat the 92% figure as a final vendor score. Supplier-level rates and defect data should be reviewed before deciding whether to accelerate a location pilot.

## Actions for the next 30 days

North should submit a replenishment recovery plan for outdoor goods, with a weekly in-stock review and explicit owner for high-volume items. South should confirm holiday staffing plans and report turnover using the HR-approved denominator. East should conduct a lease sensitivity at plus or minus 10% and avoid signing a site before Finance verifies the 11% rent-to-revenue gate. West should review the five suppliers with the highest late-delivery impact, measured by affected units rather than number of shipments.

Customer Care should present the Q3 satisfaction score with sample size and channel mix. The sample `customer_feedback.csv` is not a complete customer census and includes repeated survey channels. A mean score is descriptive, not a causal explanation for revenue or returns. Finance should reconcile gross sales, refunds, and processor settlements separately before issuing a net revenue view.

## Performance and data notes

For an operational pulse, a region within 5% of target is considered watch-list; more than 5% below target should receive a recovery plan. This memo's early appendix used 95% attainment as the threshold for intervention, which remains consistent with a 5% shortfall. Quarter results should be grouped by transaction date, not file modification date. Missing category or cost values should be reported and excluded only from metrics that require them; do not discard a row's available revenue just because its cost is missing.

Leaders must attach source extracts to decisions and preserve extraction time. Use whole-quarter data only after September transactions are complete and Finance's close is posted. An outlier can be a valid bulk order, a keying error, or a duplicated import; until reviewed, show results both including and excluding the affected row. Do not silently cap or overwrite it.

## Draft figures and qualifications

**Caveat:** the opening paragraph in the circulated draft lists North Q3 target as $220,000, but the approved policy and target CSV set it at $215,000. The same draft's East paragraph says $220,000; the approved value is $225,000. These were copied from an earlier planning sheet and are not approved baselines.

An operations note also says “all refunds are processed within ten days.” That is not a measured result and does not match the five-business-day service objective in the returns policy. Until the refund ledger is reconciled, do not publish a refund compliance percentage. The COO requests a corrected memo appendix by October 20 with target source, gross sales totals, record exclusions, late delivery definition, and approved owners. Corrections should be versioned, not written over the original. Any analysis requested from these files must state that financial results are sample operational records rather than audited financial statements. The memo supports immediate action planning; it does not authorize changes to sales targets, compensation plans, or capital approvals. Regional VPs should distinguish confirmed facts from operational hypotheses and route unresolved differences to Finance instead of choosing whichever figure supports a preferred conclusion.
