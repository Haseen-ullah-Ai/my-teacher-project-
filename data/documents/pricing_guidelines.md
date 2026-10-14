# Northwind Retail Group — Pricing and Promotion Guidelines

**Owner:** Merchandising and Finance  
**Effective:** March 1, 2025  
**Review cadence:** Quarterly

## Price architecture

Northwind Retail Group sets everyday prices by category using landed product cost, expected handling expense, competitive position, and customer value. Every item must have a recorded standard cost and approved list price before it is activated. Gross margin percentage is calculated as (revenue minus cost) divided by revenue. It is not the same as contribution margin, which also includes variable fulfillment, payment, and service expenses. Reports using the sales sample's `cost` and `revenue` columns can calculate gross margin for rows where both fields are present, but should identify that the CSV does not include all variable expenses.

Category managers may approve a temporary discount up to 10% when the resulting gross margin remains at least 35%. A discount from 10% through 20% requires approval from the category director and Finance. A discount above 20%, or any price below landed cost, requires the Chief Commercial Officer and CFO. These are approval thresholds; they do not imply that a promotion is commercially advisable. Coupon stacking is disabled unless a campaign brief names the permitted combinations.

## Promotion controls

Each campaign brief must state the eligible dates, products, regions, discount funding, expected units, baseline period, and measurement owner. The standard post-campaign review compares units, gross revenue, gross margin dollars, return rate, and inventory position to a comparable baseline. A campaign is not deemed successful solely because unit volume increased. Merchandising should monitor cannibalization in adjacent products and disclose when a result depends on clearance inventory.

The planning guardrail is no more than 15% of regional revenue from promotions in a quarter without a documented exception. Finance measures this share from transaction-level discount flags; the current `sales_2025.csv` example does not include a discount column, so it cannot independently establish campaign share. Store teams may not infer discount depth from a lower observed average revenue per unit because category and basket mix also change.

## Regional and target interpretation

Quarter targets are maintained separately in `regional_targets.csv` and represent gross revenue before returns. Price changes should be evaluated against the approved regional target and a margin measure, not substituted for those targets. Use transaction date for quarter assignment. If a sales row lacks revenue or cost, report its count and value exposure; a missing cost does not make a known revenue disappear, while a missing revenue prevents a complete revenue calculation for that row.

Pricing exceptions are time-limited to 30 days and must name the approver. Permanent changes require a new price file and an effective date; a store email does not amend the master. Finance samples at least 25 discounted SKUs per region each quarter. A discrepancy greater than one percentage point between approved and observed discount depth is escalated within two business days. The compliance review records both the source price and transaction price to preserve a traceable calculation.

## Margin and data integrity

Costs must be refreshed when a supplier invoice, freight surcharge, or material change is confirmed. A stale cost can materially overstate margin and should be labeled. Outlier revenues may reflect business orders or data errors; confirm them against the order system before using them to justify a broad price change. Rounding should occur after aggregation, with intermediate computations retained to at least four decimal places.

**Caveat:** an older campaign playbook permits a discount up to 25% with regional VP approval. The current rule requires CCO and CFO approval above 20%. A draft also gives a 30% promotion share as the normal quarterly ceiling; the approved planning guardrail is 15% absent a documented exception.

Pricing decisions should consider customer fairness, local law, advertised-price promises, and contractual restrictions. A price change prompted by a temporary cost anomaly needs a documented review date and rollback condition. The guidelines are not a substitute for legal advice on regulated goods or consumer disclosures. Finance and Merchandising review compliance exceptions after each quarter, while Internal Audit may select campaigns independently. If a dataset lacks discount markers or complete costs, analysts must say which pricing conclusions are not measurable rather than creating proxy assumptions from incomplete fields. The company's goal is transparent value, sustainable margin, and consistent treatment across channels, not maximum short-term revenue at any cost.
