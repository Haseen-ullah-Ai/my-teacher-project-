# Northwind Retail Group — Enterprise Risk Register

**Owner:** Enterprise Risk and Compliance  
**As of:** September 30, 2025  
**Review cadence:** Monthly

## Scoring and escalation

Risks are scored for likelihood and impact on a five-point scale. Inherent score is likelihood multiplied by impact, before controls; residual score reflects documented controls. A residual score of 15 or higher is Critical and requires an executive owner and monthly evidence of mitigation. Scores from 9 through 14 are High and require a quarterly action review. Scores from 4 through 8 are Moderate, and 1 through 3 are Low. A safety, privacy, or regulatory event is escalated regardless of numeric score.

Risk owners must record the risk statement, affected objective, control owner, due date, evidence, and current residual score. “No known issue” is not an acceptable control description. Open actions past due are marked overdue; they are not closed because a risk has been re-scored. Internal Audit may challenge scoring and evidence, and the Chief Risk Officer approves changes to Critical ratings.

## Current portfolio

| Risk | Inherent | Residual | Owner | Required evidence |
|---|---:|---:|---|---|
| Supplier disruption causes stockouts | 20 | 12 | Supply Chain | Vendor capacity and recovery plan |
| Incorrect sales or cost data drives decisions | 16 | 8 | Finance Data | Reconciliation and exception log |
| Refund processing delays harm customers | 12 | 6 | Customer Care | Approved-to-settled aging report |
| Expansion lease exposure exceeds returns | 15 | 9 | Strategy | Downside case and lease sensitivity |
| Personal information disclosed in reports | 15 | 5 | Security | Access review and redaction samples |

Scores are as of the stated date and do not prove that controls are operating effectively. Supplier delivery, defect, returns, and customer survey records have different denominators. Combining them into a single “service risk rate” is not approved. The Q3 operations memo's preliminary 92% on-time figure should be validated against the 94% pilot threshold and the supplier review's shipment-level method before an expansion decision.

## Key controls

Finance runs a monthly data-quality check for missing revenue, missing cost, duplicate transaction identifiers, and extreme values. The sales sample contains no transaction identifier, so duplicate detection cannot be completed from that file alone. An outlier is investigated against the order source; it is never silently deleted or capped. Reports show totals both including and excluding a confirmed anomalous record when the impact is material.

Customer reports should use least-privilege access, avoid direct identifiers, and log exports. A suspected disclosure is reported to Security within one hour. Refund controls reconcile approved cases to processor settlement weekly. Expansion proposals require a risk review before lease signature. Supplier concentration and alternate-source plans are reviewed twice yearly; high-volume vendors are assessed by business impact, not only supplier count.

## Exceptions and qualifications

The customer satisfaction report's sample lacks invitations and unique-customer IDs, so representativeness cannot be confirmed. The delivery sample lacks unit weights and accepted promise-date changes. Risk statements that rely on these files must preserve those caveats. Action owners provide evidence before the monthly meeting, and unresolved data issues remain open with an explicit due date.

**Caveat:** a draft register labels residual supplier disruption as 15, Critical. The approved table above gives it a residual score of 12, High. A separate draft says privacy escalation is within 24 hours; the current internal response objective is one hour. These differences are not equivalent versions and must be escalated to the risk owner, not averaged.

Risk acceptance is time-limited and signed by the executive accountable for the exposed objective. Acceptance does not remove regulatory or contractual obligations. The register is a management control document, not an audited assurance statement. Owners must distinguish measured facts, estimates, and assumptions, cite evidence dates, and refresh scores when a material event occurs. If a risk cannot be quantified from available source data, record a qualitative assessment and the missing evidence rather than presenting a false level of precision. This register supports governance and should not be used to claim that all listed risks are prevented.
