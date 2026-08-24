# 🎬 5-Minute Pitch Outline — Razorpay AI Finance Controller

## Pitch Structure

| Time | Section | Duration |
|------|---------|----------|
| 0:00–0:30 | Hook & Problem | 30s |
| 0:30–1:00 | Problem Deep Dive | 30s |
| 1:00–1:30 | Solution Overview | 30s |
| 1:30–3:30 | Live Demo | 2 min |
| 3:30–4:15 | Technical Deep Dive | 45s |
| 4:15–4:45 | Impact & Scalability | 30s |
| 4:45–5:00 | Close | 15s |

---

## Detailed Script

### 🎯 0:00–0:30 — Hook & Problem Statement

> *"Every month, finance teams at businesses using Razorpay spend 40 or more hours manually reconciling payments, settlements, and bank statements. They're cross-referencing spreadsheets, hunting for mismatches, and dealing with edge cases that simple rules can't handle. What if we could automate this — intelligently?"*

**Visual:** Show a split screen — messy spreadsheets on one side, your clean dashboard on the other.

---

### 📊 0:30–1:00 — Problem Deep Dive

> *"Here's what reconciliation actually looks like: You have payment records from Razorpay, grouped into settlements that get credited to your bank. Sounds simple — but in reality, you get rounding errors, delayed bank credits, mangled UTR numbers, and even duplicate refunds. Traditional rule-based systems catch the obvious cases but fail on ambiguous ones. That's where my solution comes in."*

**Visual:** Show sample data CSVs — highlight the mismatches you seeded in the data.

---

### 💡 1:00–1:30 — Solution Overview

> *"I built the Razorpay AI Finance Controller — a hybrid reconciliation engine. It uses deterministic rules for the 85% of cases that match exactly, and AI reasoning for the 15% that don't. But here's what makes it different: the AI has guardrails. It can explain WHY something doesn't match — maybe it's a processing delay, maybe a fee rounding — but it cannot override financial invariants. If a refund exceeds the payment, it's always flagged. No exceptions."*

**Visual:** Show architecture diagram (from README).

---

### 🖥️ 1:30–3:30 — Live Demo (THE MOST IMPORTANT PART)

Walk through the full flow:

1. **Upload CSVs** (0:15)
   > *"I upload four CSV files: payments, settlements, bank statement, and refunds. These have 50 payments, 10 settlements, and deliberate mismatches seeded in."*

2. **Click 'Run Reconciliation'** (0:10)
   > *"One click runs the entire three-pass pipeline plus AI analysis."*

3. **Show Dashboard** (0:30)
   > *"Here's the dashboard — I can see X% of records matched, Y mismatches, Z processed by AI. The pie chart shows the distribution, and the bar chart breaks down mismatches by type — amount errors, date delays, missing entries."*

4. **Click into a MATCHED record** (0:15)
   > *"Here's a perfectly matched payment — linked to its settlement, verified by deterministic rules."*

5. **Click into an AI_FLAGGED record** (0:30)
   > *"Now this is interesting — this settlement had a fuzzy UTR match and a 3-day date delay. The AI analyzed it and said: 'Likely a delayed bank credit — same UTR pattern, 3-day gap typical for weekend processing.' But because the amount also differed, the guardrail flagged it for human review. The AI can explain, but it can't approve."*

6. **Show Audit Log** (0:15)
   > *"Every single decision is logged — what happened, when, why, and whether it was a rule or AI. This is audit-ready."*

7. **Export Report** (0:05)
   > *"One click to export the full reconciliation report as CSV."*

---

### 🔧 3:30–4:15 — Technical Deep Dive

> *"Let me show you why this hybrid approach matters. Pure rules miss edge cases — a UTR with an extra space, a credit that arrived on Monday instead of Friday. Pure AI is unreliable for finance — you can't have a model 'decide' to match records when the amounts are off by 20%."*

> *"My guardrails enforce this: any amount difference over 5% is always flagged, regardless of what the AI thinks. Refunds exceeding payments are always flagged. The AI's role is advisory — it provides explanations and confidence scores, but hard financial invariants are non-negotiable."*

**Visual:** Show the guardrail code from `ai_reasoner.py`.

> *"And when there's no API key, the system falls back to heuristic matching using fuzzy string similarity and date proximity — so it works offline too."*

---

### 📈 4:15–4:45 — Impact & Scalability

> *"Results: 60-70% of manual reconciliation workload automated. Full audit trail for compliance. Zero unsafe AI decisions."*

> *"For production, I'd scale this with PostgreSQL, Celery for background jobs, and a webhook integration with Razorpay's Settlement Recon API for real-time data. The architecture is modular — each component is swappable."*

---

### 🎤 4:45–5:00 — Close

> *"I built this in [X] days. It's open source, fully tested, and ready to extend. The Razorpay AI Finance Controller shows that AI in finance doesn't have to be a black box — it can be transparent, guardrailed, and genuinely useful. Thank you."*

---

## 🎥 Recording Tips

1. **Tool:** Use OBS Studio (free) for screen recording with face cam in the corner
2. **Resolution:** 1920x1080 at minimum
3. **Audio:** Use a decent microphone, speak clearly and with energy
4. **Pace:** Don't rush — the demo is the star, spend the most time there
5. **Practice:** Do 2-3 dry runs before recording the final version
6. **Show enthusiasm:** Evaluators want to see you're excited about what you built
7. **Upload:** YouTube (unlisted) or Google Drive — make sure the link works!

## 📋 Pre-Recording Checklist

- [ ] API server running (`uvicorn app.main:app --port 8000`)
- [ ] Dashboard running (`streamlit run frontend/dashboard.py`)
- [ ] Sample data generated (`python data/generate_sample_data.py`)
- [ ] Database clean (delete `recon.db` for a fresh demo)
- [ ] Screen recording software ready (OBS / Loom / Zoom)
- [ ] Microphone tested
- [ ] Browser tabs closed (no notifications during recording)
- [ ] Practice run completed at least once
