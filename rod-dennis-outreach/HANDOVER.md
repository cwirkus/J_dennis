# Rod Dennis Outreach System — Handover Guide

## How to Run Locally

```bash
cp .env.example .env          # then fill in all API keys
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Open `dashboard-ui/index.html` in any browser
- API runs at http://localhost:8000
- API docs at http://localhost:8000/docs

---

## API Keys You Need

| Key | What it does | Where to get it |
|-----|-------------|-----------------|
| `ANTHROPIC_API_KEY` | Powers all AI generation — outreach emails, discovery, social drafts, inbox responses | console.anthropic.com |
| `ARTSY_CLIENT_ID` + `ARTSY_CLIENT_SECRET` | Gallery sourcing via Artsy API | developers.artsy.net |
| `HUNTER_API_KEY` | Finds and verifies email addresses for prospects | hunter.io |
| `PERPLEXITY_API_KEY` | Deep-research on individual prospects before outreach | perplexity.ai |
| `GMAIL_CREDENTIALS_JSON` | Sends approved emails from info@jrodneydennis.com via Gmail | Google Cloud Console — create an OAuth2 credential for the Gmail account, download the JSON, paste the entire JSON as a single-line string in this variable |
| `ROD_EMAIL` | The "from" address for all outbound email | Already defaulted to `info@jrodneydennis.com` |

---

## How to Deploy to Railway

1. Push the project to a GitHub repository
2. Go to [railway.app](https://railway.app), create a new project, connect the GitHub repo
3. Railway detects `railway.json` and uses the start command automatically
4. Go to **Variables** in the Railway dashboard, add every key from `.env.example`
5. Deploy — Railway builds and starts the app
6. Copy the Railway URL (e.g. `https://rod-outreach.up.railway.app`)
7. Open `dashboard-ui/index.html` in a text editor, change `API_BASE` at the top to the Railway URL
8. Open `index.html` locally — it now talks to the live Railway backend

> **Note on data persistence:** Railway's ephemeral filesystem resets on redeploy. All data lives in CSV files under `data/`. Back up that folder before redeploying, or migrate to a persistent store (e.g. Railway Postgres + a thin adapter layer) when the prospect list becomes critical.

---

## How to Use the Dashboard

Open `dashboard-ui/index.html` in any browser. Four tabs:

**OUTREACH** — AI-generated emails waiting for your review. Read each one, edit subject or body inline if needed, then click **Approve** to send or **Reject** to discard. Nothing sends until you click Approve.

**SOCIAL** — Weekly LinkedIn and Twitter drafts generated every Wednesday. Review, edit the text, click **Approve** when satisfied. Approved drafts show a reminder to copy and post manually — the system never posts to social media automatically.

**INBOX** — Incoming inquiries with AI-drafted responses. Read the message, review the draft, edit if needed, then **Approve & Send**. The response goes out via Gmail immediately on approval.

**STATS** — Pipeline overview: total prospects, pending approvals, emails sent this month, replies received. Also shows the last 5 discovery agent runs.

---

## Weekly Rhythm

| Day | What happens automatically |
|-----|---------------------------|
| Monday 8:00 AM | Discovery agent runs, finds up to 20 new prospects, adds them to the pipeline |
| Wednesday 9:00 AM | LinkedIn and Twitter drafts generated for the week |

**Your weekly actions:**
- Check the OUTREACH tab — approve or reject the pending emails in one sitting
- Check the SOCIAL tab — edit and approve the social drafts, then copy and post to LinkedIn/Twitter yourself
- Check the INBOX tab whenever you receive a new inquiry

---

## How to Add Prospects Manually

**Via API:**
```bash
curl -X POST http://localhost:8000/api/v1/prospects \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Smith", "organization": "Realist Gallery NYC", "email": "jane@realistgallery.com", "category": "gallery", "country": "US", "priority": "1", "status": "new"}'
```

**Via CSV:** Edit `data/prospects.csv` directly. Column headers must match exactly:
`name, organization, category, country, email, phone, website, priority, status, notes, date_contacted, last_activity, source`

---

## How to Trigger a Manual Discovery Run

```bash
curl -X POST http://localhost:8000/api/v1/discovery/run-now
```

Or use the interactive docs at http://localhost:8000/docs — find `POST /api/v1/discovery/run-now` and click **Try it out**.

---

## Data Files

All data lives in `data/` as CSV files. Back these up periodically.

| File | Contents |
|------|----------|
| `prospects.csv` | All contacts in the pipeline |
| `outreach_drafts.csv` | All generated and sent emails |
| `social_drafts.csv` | All social content drafts |
| `inbound_messages.csv` | All incoming inquiries and AI-drafted responses |
| `discovery_log.csv` | History of discovery agent runs |

---

## Nothing Sends Without Your Approval

This system generates drafts only. Every outbound email and every inquiry response requires your explicit **Approve** click in the dashboard before anything is sent.

Social content is never posted automatically. The system marks drafts approved and reminds you to copy and post yourself.

The discovery agent adds prospects to `prospects.csv` automatically, but no email is generated or sent to them until you trigger the outreach flow manually or via the API.
