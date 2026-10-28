# Transcript Intelligence: take-home analysis

Analysis of 100 call transcripts (27 support, 43 external, 30 internal) from Feb 3 to Apr 28, 2026. The work covers three things: topic categorization, sentiment across call types, and additional insights for different stakeholders.

## Run it

```bash
python3 -m venv .venv
./.venv/bin/pip install pandas numpy scikit-learn matplotlib vaderSentiment
./.venv/bin/python src/run_analysis.py
```

Outputs land in `outputs/` (CSV tables) and `outputs/charts/` (PNG charts). The source dataset is not modified.

## Layout

| File | Purpose |
| --- | --- |
| `src/load.py` | Reads each meeting folder into a meeting table and a sentence table. Derives call type and speaker side. |
| `src/categorize.py` | Rule-based theme taxonomy, plus a TF-IDF/KMeans cross-check. |
| `src/sentiment.py` | Sentiment by call type, theme, and time. VADER check against the shipped labels. |
| `src/insights.py` | Bonus insights: churn early warning, feature demand, competitor pressure, repeat support accounts. |
| `src/run_analysis.py` | Runs everything and writes `outputs/`. |

## 1. Categorization

**Approach: rule-based, with a clustering check.**

- Each meeting already has an LLM-written summary and topic tags. Rules over that text are transparent, so a panel can see why a call landed where it did, and a stakeholder can disagree by changing one keyword list.
- A keyword in the title counts three times as much as a keyword in the summary or tags. Titles are written by people and state the subject directly.
- Each meeting gets one primary theme (highest score) and any secondary themes that score at least 3. Secondary themes matter: a renewal call that discusses an outage is a renewal call, and it is also an outage call.
- As an independent check, TF-IDF on summaries plus KMeans (k=9) gives an adjusted Rand index of **0.25** against the rules. That is low. The clusters pick up real vocabulary (billing disputes, MFA/SSO, SOC 2 and PCI), but they blur the boundaries between outage, renewal and compliance. Treat the primary theme as a reasonable label, not ground truth.

### Themes

| Theme | Calls (primary) | External | Internal | Support | Example |
| --- | ---: | ---: | ---: | ---: | --- |
| Outage & reliability | 22 | 6 | 10 | 6 | *Detect Outage - Remediation Plan Review* |
| Billing & renewals | 19 | 14 | 0 | 5 | *Aegis / Quantum Edge - Renewal Concerns* |
| Compliance & audit | 18 | 11 | 4 | 3 | *Aegis / Redwood Clinical - ISO 27001 Preparation* |
| Product & roadmap | 11 | 2 | 8 | 1 | *Identity Team - Q2 Roadmap* |
| Identity & access | 11 | 4 | 2 | 5 | *Support Case #3677 - Coastal Living Co MFA Token Failures* |
| Backup & recovery | 7 | 1 | 2 | 4 | *Support Case #2638 - Pineridge Systems CloudPrime S3 Backup Connector* |
| Onboarding & deployment | 5 | 4 | 1 | 0 | *Aegis / Clearwater Medical - Comply v2 Deployment Kickoff* |
| Competitive intelligence | 4 | 1 | 3 | 0 | *Win/Loss Analysis - Q1* |
| Integrations & API | 3 | 0 | 0 | 3 | *Support Case #1750 - Vanta Health Systems SIEM Connector Issue* |

Full mapping: `outputs/categories_by_meeting.csv`. Cross-tab: `outputs/theme_by_call_type.csv`.

**Cross-cutting themes are undercounted by primary labels.** Outage appears (as primary or secondary) in 48 of 100 calls. SentinelShield, the competitor, is named in 22 calls, but "Competitive intelligence" is the primary theme of only 4.

## 2. Sentiment

**Two signals, one check.** Each sentence ships with a sentiment label (positive, neutral, negative). I also scored every sentence with VADER. Sentence-level agreement is weak (Cohen's kappa 0.11), because VADER was built for social-media text and does poorly on business language. At the meeting level, the shipped `sentiment_score` (1 to 5) correlates with the VADER mean at **r = 0.83**, so the meeting-level scores are consistent with the text. The report uses the shipped labels for sentence shares and the meeting scores for trends.

### What the trends say

**1. The March 10 outage split the data in two.** Average meeting sentiment before and after the outage:

| Call type | Before | After | Change |
| --- | ---: | ---: | ---: |
| External (customers) | 4.25 (n=15) | 3.42 (n=28) | -0.83 |
| Internal | 3.80 (n=9) | 3.26 (n=21) | -0.54 |
| Support | 3.07 (n=10) | 2.86 (n=17) | -0.21 |

The external drop is the largest, and it is the most important for the business. The before/after comparison mixes meeting types, so the per-type rows are the ones to read.

**2. Customers are more negative than our own staff, and the gap is wide.** On external calls, 20% of customer-side sentences are negative, against 4% from Aegis staff. Support calls are worse: 39% of customer-side sentences are negative. Outside of calls, the scores tell you little. What the customer says is where the risk is. (`outputs/sentiment_by_side.csv`)

**3. Outage and integrations are the lowest-sentiment themes.** Outage & reliability averages 2.43; Integrations & API averages 2.40. Compliance & audit (4.27) and Onboarding & deployment (4.62) are the highest. The product's compliance story is landing well, and outage handling is what drags relationships down. (`outputs/sentiment_by_theme.csv`)

**4. Weekly trend.** External sentiment starts high (4.8 in the week of Feb 2) and falls steadily through March. Support stays low throughout, which suggests support calls are a constant floor and not a reaction to the outage. (`charts/weekly_sentiment.png`)

### What it could mean

- The outage did more than cause a single bad week. It moved customer conversations from renewal and roadmap topics to outage and churn topics. Post-outage external calls touch outage in 68% of cases, against 13% before.
- Customer sentiment is the earliest signal we have. Before the outage, 4 of 15 external calls contained a churn signal. After, 17 of 28 did.

## 3. Additional insights

Four are implemented, and four more are described below.

### Implemented

**a) Churn early warning (`outputs/churn_early_warning.csv`).** An account with one or more `churn_signal` moments on any call counts as at risk. Across 24 accounts, 22 have a churn signal dated after the outage. Accounts with three churn signals and recent activity include Brightpath Commerce, Summit Trust, Cobalt Software and Meridian Capital. *Who uses it:* account managers and CS leadership, to prioritize outreach before a renewal date.

**b) Feature demand from customers (`outputs/feature_demand.csv`).** Feature-gap moments grouped by theme. Compliance & audit leads with 13 mentions (7 from external calls), followed by Billing & renewals with 8 (7 external). The demand is for proactive alerting on seat overages and for compliance report formats. *Who uses it:* product managers, to choose the next roadmap items from customer evidence instead of internal opinion.

**c) Competitor pressure over time (`outputs/competitor_pressure_weekly.csv`).** SentinelShield appears in 61.5% of calls in the week of March 9, the outage week. In the seven weeks after, it appears in 0% to 33% of calls each week. The competitor is mentioned mostly on internal and external calls, rarely in support calls. *Who uses it:* sales leadership and product marketing, to tell when a competitive threat is picking up and what it is saying in deals.

**d) Repeat support accounts (`outputs/support_repeat_accounts.csv`).** Eight accounts have more than one support case. Silverline Brands has three, and its average sentiment is 2.9. Repeat cases are a sign that the first fix did not hold. *Who uses it:* support leadership, to find tickets that need root-cause follow-up before they become churn.

### Described, not implemented

**e) Renewal-risk score.** Combine the signals above (churn moments, negative customer share, outage mentions, competitor mentions) into one score per renewal, updated after each call. *Who uses it:* sales managers forecasting renewals. *Approach:* a logistic model trained on renewal outcomes. The dataset does not contain outcomes, so the first version would be a weighted rule that is calibrated later.

**f) Action-item follow-through.** Every meeting has 3 to 4 action items (`outputs/action_items_by_call_type.csv`). The dataset has no completion data, so we cannot tell whether they were done. If they were linked to the tracker, a panel could see which teams drop follow-ups after an outage. *Who uses it:* engineering managers and PMs. *Approach:* join action items to Jira or Linear and measure time to close by owner and by call type.

**g) Talk-time and speaker dynamics.** Speaker turns show who drives each call. In the sample, a few people speak far more than others (Maria Santos, Kevin O'Brien and Sarah Chen have the most sentences). Talk-time share by role could show whether customers get enough air time on renewal calls. *Who uses it:* account managers and call coaches.

**h) Early outage detection from call language.** Concern and technical-issue moments often appear in calls before a formal incident is opened. A keyword alert on "alerts delayed" or "dead screen" in support calls might catch an incident hours earlier. *Who uses it:* on-call engineering and support leads. *Approach:* a streaming classifier on support transcripts, with a threshold tuned to the false-alarm rate that on-call can tolerate.

## Data notes and limitations

- **Call type** was derived from attendee emails. Any attendee outside `aegiscloud.com` makes a call external. Titles starting with "Support Case #" are support. Internal calls contain only Aegis addresses. This matches the three call types in the brief.
- **Speaker side** was derived the same way: a speaker is vendor if their name matches an Aegis attendee on the call, and customer if the call is external and they do not. Some names on internal calls do not match any invitee, so the internal side is excluded from the side comparison.
- **The sample is small and unbalanced.** There are 15 external calls before the outage and 28 after. Before/after comparisons are directional, not statistically tight.
- **No outcomes data.** The dataset has no renewal results, churn confirmations or ticket resolution times. Every "churn" statement means a churn signal said on a call, not a churn that happened.
- **The dataset has the appearance of synthetic data**, with consistent company names, a single product storyline and a dated outage. I treated it as real for the analysis. No transcripts were generated or altered.

## Demo app: change the pipeline through an API and a UI

The `src/api.py` FastAPI service wraps the pipeline (`src/pipeline.py`). The `frontend/` folder is a Next.js UI that edits the config (title weight, outage date, theme keywords), runs the pipeline, and shows what changed since the previous run, including which calls moved theme.

### Run locally

Backend (from the project root):

```bash
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn api:app --app-dir src --port 8000 --reload
```

Frontend (second terminal):

```bash
cd frontend
npm install
npm run dev -- -p 3000
```

Open http://localhost:3000. The UI reads `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`, set in `frontend/.env.local`).

### Run with Docker

```bash
docker compose up --build
```

- API: http://localhost:8000/docs (interactive OpenAPI docs)
- UI: http://localhost:3000

The API image copies `dataset/` in. The UI's API URL is baked in at build time through the `NEXT_PUBLIC_API_URL` build argument in `docker-compose.yml`, because the browser calls the API directly.

### Logging

- **Backend:** each request is logged with method, path, status and time, plus startup, config changes, and run results. Set `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`) in the environment. Uvicorn's own access log is off so lines are not doubled.
- **Frontend:** every API call is logged with status and time, and so are step changes, runs, and filter changes. Output goes to the browser console. Set `NEXT_PUBLIC_LOG_LEVEL` (`debug`, `info`, `warn`, `error`) at build time.
- **Docker:** `docker compose logs -f api` and `docker compose logs -f web`.

### API endpoints

One group per assignment step.

| Method | Path | Step | What it does |
| --- | --- | --- | --- |
| GET | `/api/data` | 1 Load | Counts, date range, sample calls |
| POST | `/api/runs` | 2 to 4 | Run categorization and sentiment with the current config |
| GET | `/api/categories` | 2 Categories | Themes, keywords, call counts, example titles |
| GET | `/api/sentiment` | 3 Sentiment | By call type, weekly trend, before and after the outage, customer vs staff |
| GET | `/api/insights` | 4 Insights | Churn list, feature demand, competitor weekly, repeat support accounts |
| GET | `/api/calls` | 4 Drill-down | Calls filtered by `theme`, `call_type`, `account` |
| GET | `/api/config` / `PUT` | Config | Read or replace the config (422 on bad input) |
| POST | `/api/config/reset` | Config | Restore defaults |
| GET | `/api/runs/latest` | Any | Last run summary, including changes vs the run before |

Steps 2 to 4 return 409 until a run exists.

### Recommendations (home page radio group)

The home page has a radio group with the four recommendations. Each one is hidden until you pick it.

| Method | Path | Recommendation |
| --- | --- | --- |
| GET | `/api/recommendations/churn` | 1. Churn list for account managers |
| GET | `/api/recommendations/weekly` | 2. Weekly external sentiment and outage talk, with alert weeks |
| GET | `/api/recommendations/roadmap` | 3. Roadmap priorities: overage alerts and compliance report formats first |
| GET | `/api/recommendations/actions` | 4. Action-item tracker |
| PUT | `/api/recommendations/actions/{id}` | Set an action to `open` or `done` (kept in memory) |

Example: make "Billing" match only `renewal`, then run:

```bash
curl -X PUT localhost:8000/api/config -H 'content-type: application/json' \
  -d '{"title_weight":3,"outage_date":"2026-03-10","themes":{"Billing & renewals":["renewal"]}}'
curl -X POST localhost:8000/api/runs
```
