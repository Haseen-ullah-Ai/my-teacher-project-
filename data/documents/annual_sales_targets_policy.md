# Northwind Retail Group — FY2025 Annual Sales Targets Policy

**Owner:** Finance and Commercial Planning  
**Effective:** January 1, 2025  
**Version:** 2.1

## Purpose and scope

This policy establishes the revenue targets used to evaluate Northwind Retail Group's four sales regions during fiscal year 2025. The regions are North, South, East, and West. The targets are planning thresholds, not guarantees of customer demand. Finance publishes quarter-level targets in `regional_targets.csv`; that file is the operational source of truth for automated comparisons. Amounts are in US dollars and represent gross recognized sales before returns unless a report explicitly says it is using net revenue.

The annual targets, calculated from the quarter rows in the CSV, are North $840,000, South $780,000, East $880,000, and West $760,000. The company-wide annual target is $3,260,000. Quarter values should sum exactly to each annual figure. Finance owns corrections to a published row and must retain the prior value in its change record. A presentation or memo must not silently replace the CSV value.

## Quarterly target schedule

| Region | Q1 | Q2 | Q3 | Q4 | FY2025 |
|---|---:|---:|---:|---:|---:|
| North | $190,000 | $205,000 | $215,000 | $230,000 | $840,000 |
| South | $175,000 | $190,000 | $200,000 | $215,000 | $780,000 |
| East | $195,000 | $210,000 | $225,000 | $250,000 | $880,000 |
| West | $165,000 | $180,000 | $195,000 | $220,000 | $760,000 |

Q3 is July 1 through September 30, inclusive. Revenue on the boundary date of September 30 belongs to Q3 when the transaction is recognized that day. The CSV date field uses ISO format. A transaction with a missing revenue is excluded from numerical totals and reported separately; it must not be imputed without a documented method. Currency should be rounded to cents only for presentation, not before aggregation.

## Measurement and accountability

Attainment is actual gross revenue divided by target revenue, expressed as a percentage. At or above 100% is “met”; 95% to less than 100% is “watch”; below 95% is “below plan.” These labels are management signals, not automatic compensation decisions. Sales operations reviews attainment monthly, while Finance certifies each quarter after the returns window and reconciliation are complete. The Q3 operating dashboard may be preliminary before October 15; it should carry a preliminary label.

The executive scorecard uses the CSV's gross `revenue` column for attainment. The returns policy separately reports net revenue after refunds. Do not compare that net figure with a gross target without showing both values and explaining the difference. Costs are not deducted from sales revenue for this measure; margin analysis is a separate calculation using the `cost` column.

## Exceptions and controls

Finance may authorize a target adjustment only through a dated approval signed by the Chief Financial Officer and regional vice president. A weather disruption, store closure, or supply interruption can support a reforecast, but does not change the approved baseline. Every report should cite the quarter, region, target amount, actual amount, and source row or data range. Outliers, missing values, and duplicates must be flagged before approval.

**Caveat:** the Q3 operations memo refers to a $220,000 North target. That was an early planning draft; this policy and the published target CSV both set North Q3 at $215,000. A separate summary paragraph in the memo also calls East's Q3 target $220,000, while the approved table is $225,000. These draft figures are not approvals.

Regional leaders may request a mid-quarter forecast update, but forecast revisions must remain distinct from baseline attainment. Forecasts are useful for staffing and inventory decisions, not for changing the historical performance denominator. Finance should preserve the CSV snapshot used for each close, note the extraction timestamp, and attach evidence of any approved correction. Reports produced from an incomplete extract must state the missing date range and should avoid definitive full-quarter claims. Any currency conversion for an international supplier or marketplace must use the monthly Finance rate table and remain outside the US-dollar source values until a reconciled conversion is approved.
