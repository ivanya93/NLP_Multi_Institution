# IPSS Financial Observatory

Extracts KPIs from Portuguese IPSS financial filings (OCIP) and presents them in a bilingual (EN/PT) Streamlit dashboard with an AI assistant — a Natural Language Processing group project for the Executive Master in Business Analytics & AI at Porto Business School.

**Live app:** [nlpmultiinstitution-4shb4sdxyeprkspt3tgrpz.streamlit.app](https://nlpmultiinstitution-4shb4sdxyeprkspt3tgrpz.streamlit.app/)

## Context

The Confederation represents IPSS (Instituições Particulares de Solidariedade Social) in Portugal and negotiates with the Ministry of Labour, Solidarity and Social Security over the public funding these institutions receive per social response (*resposta social* — e.g. elderly care, childcare), under the *Compromisso de Cooperação para o Setor Social e Solidário*.

To ground those negotiations in data, this project extracts financial statements from the **OCIP** ("Conta de Gerência") PDFs institutions submit to Social Security — income statements, staffing, and identification data, broken down by social response — and turns them into comparable KPIs across institutions and regions.

## What it does

1. **Extraction pipeline** (`pipeline.py`) — parses a folder of OCIP PDFs (native text or scanned/OCR'd), pulling per-beneficiary income statements, staffing counts, and authoritative Social Security funding figures. Cross-validates each institution's beneficiary-level sums against its own aggregate page, filters down to elderly-care and childcare responses, and anonymizes institution identity before computing KPIs.
2. **KPI dashboard** (`app.py`) — a Streamlit app with filters (year, institution, activity group, social response, region) and six views: Overview, By Social Response, By Region, Institution Explorer, AI Assistant, and raw Data.
3. **AI assistant** (`data_agent.py`) — a Claude-powered chatbot with tools over the live KPI table, for ad-hoc questions and for generating negotiation talking points against the funding-coverage target.
4. **Bilingual UI** (`i18n.py`) — a sidebar toggle switches the entire dashboard and the assistant's answer language between English and European Portuguese.

## Features

**Bilingual dashboard, six tabs** — everything below respects the sidebar filters (year, institution, activity group, social response, region) and the funding-basis toggle, so every tab always reflects the same slice of data.

- **Overview** — headline KPI cards (median cost, median SS funding, funding coverage vs. the 50% target, EBITDA), a chart ranking each social response by how close it is to the funding target, a cost-vs-funding-vs-fees breakdown by activity group, and a plain-language "structural deficit" flag (how many records are losing money per beneficiary today).
- **By Social Response** — pick any KPI and see its full spread (not just an average) across social responses (Creche, ERPI, Centro de Dia, etc.), plus a summary-statistics table.
- **By Region** — the same KPI picker, but by concelho (region), plus a region × social-response matrix for spotting geographic gaps.
- **Institution Explorer** — drill into one (anonymized) institution: its region, year, and a full KPI breakdown per social response it runs, exportable on its own.
- **AI Assistant** — a Claude-powered chatbot with real data access (not a static Q&A): ask it KPI questions in plain English or Portuguese, or ask it to draft negotiation talking points, and it looks up the real numbers before answering. Includes one-click suggested questions and a "download this conversation" button.
- **Data** — the full filtered KPI table and the complete raw extraction, for anyone who wants the numbers directly.

**Two funding-coverage views** — a sidebar toggle switches between the standard Mapa A "ISS, IP" P&L lines and an "authoritative" measure built from the dedicated Comparticipações page (which catches funding booked under other line items — about half the institutions). This matters because it changes the headline coverage number materially, and both are legitimate readings of the same underlying filings.

**One-click exports** — filtered KPI table, full raw data, a single institution's records, or the AI assistant's conversation, all downloadable as CSV/TXT directly from the sidebar or the relevant tab.

## KPIs

All KPIs are computed monthly, per social response, per institution:

- Revenue, fee, Social Security funding, cost, and EBITDA per beneficiary
- Revenue, cost, and labour cost per worker
- Beneficiary/worker ratio
- Social Security funding coverage of cost (vs. the negotiation target of ≥50%)

## Data & privacy

Raw OCIP PDFs contain real institution names and NIFs and are **not committed to this repo** (`data/PDF_files/` is git-ignored). The processed outputs in `data/outputs/` (`raw_df.csv`, `kpi_df.csv`, `kpi_table.csv`) are anonymized — institution identity is replaced with a stable hashed ID (`INST_xxxxxxxx`) before being written.

## Project structure

```
├── pipeline.py                  # PDF extraction + KPI computation (script version of the team notebook)
├── app.py                       # Streamlit dashboard
├── data_agent.py                # Claude chatbot (tools + system prompt)
├── i18n.py                      # EN/PT translation strings
├── Notebooks/
│   └── Multi_Institution_Pipeline_v2.ipynb   # Original exploratory notebook
├── data/
│   ├── PDF_files/                # Raw OCIP PDFs (git-ignored)
│   └── outputs/                  # Anonymized CSVs consumed by the app
├── requirements.txt              # Deps to run the Streamlit app (used by Streamlit Cloud)
└── requirements-notebook.txt     # Full environment freeze (notebook/pipeline dev)
```

## Setup

```bash
git clone <this-repo>
cd NLP_Multi_Institution
pip install -r requirements.txt
```

Add your Anthropic API key to `.streamlit/secrets.toml` (not committed):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

## Usage

Run the dashboard (KPI data in `data/outputs/` is already generated):

```bash
streamlit run app.py
```

To regenerate the KPI data after adding new OCIP PDFs to `data/PDF_files/`:

```bash
pip install pdfplumber pytesseract   # only needed for extraction, not the app
python pipeline.py data/PDF_files data/outputs
```

(Scanned/no-text-layer PDFs require the system Tesseract OCR engine with the Portuguese language pack: `tesseract-ocr` + `tesseract-ocr-por`.)

## Running with Docker

No local Python setup needed:

```bash
docker compose up --build
```

Then open <http://localhost:8501>.

The source files are bind-mounted into the container, so editing `app.py`, `i18n.py` or
`data_agent.py` reloads the app in the browser automatically — no rebuild, no restart.
Rebuild only when `requirements.txt` changes. Stop with `docker compose down`.

The image covers the dashboard only; `pipeline.py` still runs locally, since PDF extraction
needs the system Tesseract packages listed above. The AI assistant tab shows a
"missing key" warning unless you configure `ANTHROPIC_API_KEY` — note that `st.secrets`
reads `.streamlit/secrets.toml`, not environment variables, so passing `-e` alone has no
effect.

## Deploying on Streamlit Community Cloud

Point the deployment at this repo with **main file path** `app.py`. Streamlit Cloud installs from `requirements.txt` automatically. Add `ANTHROPIC_API_KEY` under the app's **Settings → Secrets** (same TOML format as `.streamlit/secrets.toml`, which is not committed to the repo).


## Team / course

Group project for the NLP course, Executive Master in Business Analytics & AI, Porto Business School.
