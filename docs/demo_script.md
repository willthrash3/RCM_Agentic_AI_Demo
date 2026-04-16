# RCM Agentic AI Demo — Video Script

## Opening (30 seconds)

> "Revenue cycle management is one of healthcare's most document-heavy, rule-dense workflows — and historically one of the last to benefit from AI. Today I'm going to show you what it looks like when you put autonomous AI agents in the loop.
>
> This is a full-stack demo built on FastAPI, LangGraph, and Claude. Six specialized agents collaborate in real time to code claims, scrub errors, fight denials, verify eligibility, post payments, and flag issues — all while surfacing decisions that need a human back to a review queue."

---

## Section 1 — Executive Dashboard (1 minute)

**[Navigate to Dashboard]**

> "We start on the executive dashboard. Four KPI cards give you an at-a-glance view of revenue cycle health."

Point out each card:
- **Days in AR** — how long money sits uncollected before it comes in
- **First-Pass Rate** — percentage of claims paid without rework; the single best proxy for operational efficiency
- **Denial Rate** — what fraction of submitted claims are denied outright
- **Cash on Hand** — rolling collections

> "Color coding is meaningful. Green is on target, amber is watch, red means an alert threshold has been breached."

**[Point to AR Aging chart]**

> "The stacked bar chart breaks down accounts receivable aging by payer. Green is 0–30 days — money you expect soon. Red and dark red over 90 days is money at risk of becoming uncollectable. You want as much green as possible."

**[Point to Denial Rate trend line]**

> "The 30-day denial rate trend gives you the directional signal fast. A sudden uptick here is your early warning that something changed — a payer rule, a coding pattern, a documentation gap."

**[Point to Live Agent Activity feed]**

> "At the bottom, a live stream of every action any agent is taking — reasoning steps, tool calls, confidence scores. This is the audit trail that makes the system trustworthy."

---

## Section 2 — Running a Scenario (3–4 minutes)

**[Navigate to Scenario Runner]**

> "The scenario runner is how we demonstrate the agents responding to real-world events. Each scenario injects a specific condition into the database and fires the relevant agents."

### Scenario A: High-Value Denial Overturn

**[Click "Run Scenario" on High-Value Denial Overturn]**

> "This one is a great place to start. A twenty-eight-thousand-dollar inpatient claim has just been denied — CARC code CO-4, which means coding or diagnosis issues. The expected outcome is a three-agent chain: denial agent classifies it, coding agent corrects the diagnosis codes, and the appeal gets auto-submitted."

**[Watch the Live Agent Reactions feed fill in]**

> "Watch the agent trace feed. You can see the denial agent picking up the claim, reasoning through the CARC code, classifying the root cause. Now the coding agent fires — it's checking LCD rules, validating the CPT-ICD combination, writing a corrected coding suggestion. Finally the appeal letter is rendered and submitted to the payer — all in under 90 seconds, no human touched it."

> "For context, a human biller typically takes 20–40 minutes per appeal. This system processed it while we were talking."

---

### Scenario B: Payer Rule Change

**[Click "Run Scenario" on Payer Rule Change]**

> "Now let's do something that keeps revenue cycle managers up at night: a payer quietly changes an LCD — a Local Coverage Determination — adding new diagnosis restrictions to a common office visit code, 99214."

> "The scrubbing agent immediately scans the backlog. It flags 47 claims that are now non-compliant. The analytics agent raises a rule-change alert. Any claims scheduled to go out today are held until coding reviews them."

**[Point to the result JSON panel]**

> "The affected_count field in the response tells you exactly how many claims were caught before they went out the door as likely denials."

---

### Scenario C: Eligibility Gap

**[Click "Run Scenario" on Eligibility Gap]**

> "Coverage lapses are a silent revenue killer. Twelve patients have upcoming services with coverage that lapsed. The eligibility agent checks each one against the payer, flags the gap, and — because this requires human judgment before rebooking or financial counseling — it creates a task in the Human-in-the-Loop queue."

---

## Section 3 — Human-in-the-Loop Review Queue (1 minute)

**[Navigate to Review Queue]**

> "And here they are. The review queue is where the agents surface decisions that require human judgment — high-dollar amounts, ambiguous clinical documentation, out-of-network edge cases."

**[Click on an eligibility task]**

> "Each task shows the agent's recommended action and its full reasoning — not a black box output, but a transparent chain of thought you can agree with, override, or escalate."

**[Point to the three decision buttons]**

> "Three options: Approve, Reject, or Modify. When you approve, the agent picks up the outcome and continues the workflow automatically. Reject sends it back with a note. This is the human-AI handoff point — the agent handles volume and pattern matching, the human handles judgment calls."

---

## Section 4 — Claims and Denials (1 minute)

**[Navigate to Claims]**

> "All the underlying data is fully browsable. Here are the claims — filterable by status, payer, and date. You can see scrub scores written back by the scrubbing agent, and drill into any individual claim."

**[Navigate to Denials]**

> "The denials list shows every denied claim, categorized by root cause — coding, medical necessity, contractual, eligibility. These categories were set by the denial agent, not manually entered. The appeal deadline is calculated automatically based on each payer's timely filing window."

---

## Section 5 — AR Analytics (45 seconds)

**[Navigate to Analytics]**

> "For the finance team, the analytics page gives deeper trend views. Days in AR and first-pass rate over 30 days. Denial rate broken down by payer — you can immediately see if one payer is an outlier. And a 90-day cash flow forecast with confidence bands, driven by the collections agent's payment velocity model."

**[Click "Run Analytics Agent"]**

> "Clicking Run Analytics Agent triggers a fresh analysis pass — it computes current KPIs, compares against thresholds, and writes any alerts. Those alerts appear at the bottom of this page."

---

## Section 6 — Closing (30 seconds)

**[Return to Dashboard]**

> "What you've seen is a system where six specialized agents — coding, scrubbing, denial management, eligibility, ERA posting, and analytics — operate continuously, handle the high-volume pattern work, and surface the right exceptions to the right humans at the right time.
>
> The result: faster clean claim rates, fewer denials reaching payers, and revenue cycle staff spending their time on decisions that actually require human expertise — not data entry.
>
> This is what agentic AI in healthcare operations looks like."

---

## Recording Tips

- **Total runtime:** ~7 minutes
- Run **Payer Rule Change** and **High-Value Denial Overturn** in a dry run first to confirm the agent trace populates visibly before you hit record.
- Zoom in on the agent trace feed when scenarios run — that's the most visually compelling part.
- If you want the review queue pre-populated before recording, run the Eligibility Gap scenario first, then navigate to the queue.
- Use "Reset DB to Seed" on the Scenario Runner page to restore clean data between takes.
