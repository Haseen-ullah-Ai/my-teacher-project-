# Northwind Retail Group — Returns and Refund Policy

**Owner:** Customer Care and Finance  
**Effective date:** February 1, 2025  
**Applies to:** Retail and online orders in the United States

## Customer commitments

Customers may return most unused, resalable merchandise within 30 calendar days of delivery or purchase with a receipt or order identifier. Online returns may be started through Customer Care or the customer account portal. Refunds are issued to the original payment method after the returned item is received and inspected; the normal service target is five business days from inspection. A damaged or incorrect item is eligible for a prepaid return label and does not incur a restocking fee.

Final-sale items, gift cards, personalized goods, and products marked non-returnable at purchase are excluded except where required by law or where the product arrived damaged. Managers may approve a one-time courtesy exception up to $100. Exceptions above $100 require a Customer Care supervisor and should include the order identifier, reason, and approving employee in the case record. Store credit is offered only when a customer chooses it; staff must not represent store credit as the only remedy when a cash refund is otherwise owed.

## Accounting and performance definitions

Gross sales in `sales_2025.csv` are recorded before refunds. Refunds are recorded as negative adjustments in the finance ledger and are not included in that sample CSV. A net sales report must subtract the refund ledger total from gross recognized revenue and disclose both totals and the ledger extraction date. The approved regional targets are gross targets from `regional_targets.csv`; target attainment is not recalculated using net revenue unless Finance publishes a separate net target series.

The Q3 service objective is to resolve at least 90% of standard refund cases within five business days of inspection. A case waiting for customer-provided information is paused only after a timestamped request is sent. Weekly reporting separates elapsed calendar days from business days. Escalation is required when a refund exceeds $500, when suspected fraud is documented, or when the same order has more than two return requests in 60 days.

## Quality controls and customer protection

Returned merchandise must be classified as resalable, refurbishable, vendor-return, or write-off. The receiving associate records condition and disposition before inventory is updated. Finance reconciles refund approvals to payment processor settlements weekly. A refund that has been approved but not settled remains an outstanding liability and must not be described as completed. Customer Care reviews complaint themes monthly and sends repeated product defects to Merchandising and Supplier Quality.

Refund status messages must be plain language and must not promise a bank posting date beyond the processor's control. Personally identifying information should be minimized in reports; use case IDs rather than customer names. Suspected account takeover is sent to Risk and Security without delaying a legitimate refund, unless Legal instructs otherwise.

## Exceptions and known limitations

Peak-season returns can arrive after quarter close. Finance assigns revenue and refund adjustments according to the accounting recognition policy, not the date a manager reviews a case. Reports comparing Q3 gross sales with refund activity must clearly label the different windows. Sample feedback data is not a refund ledger, and its satisfaction scores should not be treated as direct proof that refund cases met the five-day service objective.

**Caveat:** a quick-reference card still states a 14-day return period for online purchases. That card is obsolete; the approved standard is 30 days. A separate pilot note mentions a 10-business-day refund objective, but the operational objective approved for Q3 is five business days. Neither draft overrides this policy.

The policy does not authorize employees to estimate refund totals from returned-unit counts or to assume all returns were refunded in the same quarter. Product exchanges, partial refunds, shipping credits, and payment reversals are distinct event types. Any analysis should identify the exact source table and status definition. In the absence of a reconciled refund ledger, state that net sales cannot be calculated from the sample sales and feedback files alone. The policy is reviewed twice annually by Customer Care, Finance, and Legal, with changes recorded by effective date so older orders can be assessed against the rules that applied when purchased.
