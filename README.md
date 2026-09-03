# SEO Project Management

A simple, visual project tracker for the SEO campaign. White background, black
text, light icons. Built with Streamlit and deployed on Streamlit Community Cloud.

It shows the SEO action plan as:

- **📋 Tasks** — filterable table with inline progress bars
- **🗓️ Timeline** — Gantt view (Start Date → End Date)
- **📈 Overview** — tasks by category, by owner (PIC), and progress on measurable KPIs

The app reads its data from a **Google Sheet** you own. Until that sheet is
connected it renders the bundled sample data (`data/sample_tasks.csv`, seeded
from the original `DMCL_SEO Management` workbook's *ActionPlan* tab).

---

## Data model

One row per task. Column headers (first row of the sheet) must be exactly:

| Column | Meaning |
|---|---|
| `Task` | What to do (the action) |
| `Category` | Grouping, e.g. Content Production, Technical SEO, Backlink Management |
| `Detail` | Notes / extra context |
| `Duration` | `6 months`, `2 weeks`, `5 days` (number + unit) |
| `PIC` | Owner, e.g. FirstPage / DMCL |
| `Start Date` | `YYYY-MM-DD` |
| `End Date` | `YYYY-MM-DD` — **leave blank** to auto-compute as Start + Duration; fill it only when there is no Duration |
| `Result Number` | Committed target quantity (e.g. `1500`) |
| `Result Unit` | The value type (`Content`, `Files`, `Organic clicks`, `Links`, ...) |
| `Actual Number` | Reality so far — drives the progress bar (`Actual / Committed`) |
| `Frequency` | e.g. Weekly, Monthly (optional) |
| `Status` | `Not started` / `In progress` / `Done` / `At risk` |

**Progress bar** = `Actual Number ÷ Result Number` (capped at 100%). Tasks with no
committed number (recurring technical/monitoring work) show a Status badge instead
of a bar. **End Date** = `Start Date + Duration`; if there is no Duration, the app
uses the `End Date` you typed in.

---

## Connect your Google Sheet

1. **Create the sheet.** Make a Google Sheet with a tab named `Tasks` and the
   headers above. Quickest start: in the sheet, `File → Import → Upload`
   `data/sample_tasks.csv` (import into a new tab named `Tasks`).
2. **Get a service account** (Google Cloud → IAM → Service Accounts → create →
   add a JSON key). Enable the *Google Sheets API* and *Google Drive API* on the
   project.
3. **Share the sheet** with the service account's `client_email` (Viewer is enough).
4. **Add secrets.** Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`
   (local) or paste it into Streamlit Cloud → *App → Settings → Secrets*. Fill in
   the service-account JSON and your sheet `url`.
5. The badge under the title turns **🟢 Live from Google Sheet**. Edit the sheet,
   click **🔄 Refresh data** (or wait 5 min for the cache to expire).

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Without secrets it runs on the bundled sample data.

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io) → *New app* → pick this repo,
   branch `main`, main file `streamlit_app.py`.
3. Paste your secrets in the app settings. Every push to `main` auto-redeploys.
