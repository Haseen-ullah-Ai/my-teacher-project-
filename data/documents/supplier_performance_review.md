# Northwind Retail Group — Supplier Performance Review

**Owner:** Supply Chain and Supplier Quality  
**Period reviewed:** Q3 2025  
**Prepared:** October 12, 2025

## Review method

This review summarizes supplier service using the `supplier_deliveries.csv` sample. On-time delivery is calculated at the shipment level by comparing `delivered_date` with `promised_date`; a shipment delivered on the promised date is on time. Missing dates are excluded from the rate and separately counted. Defect rate is supplied by the receiving inspection record and should be interpreted as defective units divided by inspected units, not as the fraction of shipments with any defect. The file contains no unit counts, so an aggregate unit-weighted defect rate cannot be reconstructed from it.

Northwind's Q3 operational goal is at least 94% on-time delivery and a defect rate below 2.0%. A supplier above 3.0% defects for two consecutive review periods enters a corrective action plan. Suppliers with a rate at or above 5.0% trigger an immediate quality hold review, not an automatic termination. Vendor decisions must consider affected volume, safety risk, substitutions, lead time, and contractual terms. A high shipment count does not necessarily mean high business impact.

## Findings and operational response

Procurement should review each supplier's promised and delivered dates for timezone, weekend, and rescheduling conventions before ranking vendors. A changed promise date is valid only when the change was accepted by Northwind before the original due date and preserved in the purchasing system. Late deliveries should be grouped by supplier and month, then connected to stockouts and customer impact where evidence exists. No analyst should infer lost sales from late delivery alone.

Receiving teams must record inspection sample size alongside defects. A zero defect rate with no inspected units is missing evidence, not proof of perfect quality. When inspection results are delayed, publish a provisional status and reissue the scorecard after completion. Suppliers have ten business days to respond to a corrective action request, followed by a 30-day verification window. Safety incidents bypass the ordinary timetable and go to Legal and Supplier Quality immediately.

## Data reconciliation

The Q3 operations memo circulated a preliminary aggregate on-time rate of 92%, while the current expansion strategy requires 94% to proceed with a pilot. This review's CSV is a sample dataset; its simple shipment-level calculation may not equal the operations dashboard because that dashboard may weight by units. Until source-system definitions are reconciled, use the CSV only for reproducible shipment-level analysis and label it clearly. The `promised_date` and `delivered_date` fields support lateness in calendar days, but do not identify carrier responsibility or approved schedule changes.

**Caveat:** the procurement working sheet uses a 3.5% defect escalation level. The approved hold review trigger is 5.0%, and the corrective action trigger is above 3.0% for two consecutive periods. A 3.5% single-period reading should prompt investigation but is not by itself the formal hold threshold.

The supplier scorecard also has an archived target of 90% on-time performance. That target is superseded by the current 94% operational goal. The scorecard should show numerator, denominator, missing-date rows, evaluation window, and weighting method. Suppliers should receive the same measurement definition used internally, with opportunity to correct factual date errors. Contractual service credits are assessed only after Procurement verifies the contract clause and qualifying events; a modeled late-day count is not a claim of contractual breach. The review supports sourcing decisions but cannot establish root cause without receiving, purchase order, and carrier evidence.
