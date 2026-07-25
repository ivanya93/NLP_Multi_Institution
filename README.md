# IPSS Financial Observatory

Extracts KPIs from Portuguese IPSS financial filings (OCIP) and presents them in a bilingual (EN/PT) Streamlit dashboard with an AI assistant — a Natural Language Processing group project for the Executive Master in Business Analytics & AI at Porto Business School.

## Context

[CNIS](https://cnis.pt) represents IPSS (Instituições Particulares de Solidariedade Social) in Portugal and negotiates with the Ministry of Labour, Solidarity and Social Security over the public funding these institutions receive per social response (*resposta social* — e.g. elderly care, childcare), under the *Compromisso de Cooperação para o Setor Social e Solidário*.

To ground those negotiations in data, this project extracts financial statements from the **OCIP** ("Conta de Gerência") PDFs institutions submit to Social Security — income statements, staffing, and identification data, broken down by social response — and turns them into comparable KPIs across institutions and regions.

## What it does

1. **Extraction pipeline** (`pipeline.py`) — parses a folder of OCIP PDFs (native text or scanned/OCR'd), pulling per-beneficiary income statements, staffing counts, and authoritative Social Security funding figures. Cross-validates each institution's beneficiary-level sums against its own aggregate page, filters down to elderly-care and childcare responses, and anonymizes institution identity before computing KPIs.
2. **KPI dashboard** (`app.py`) — a Streamlit app with filters (year, institution, activity group, social response, region) and six views: Overview, By Social Response, By Region, Institution Explorer, AI Assistant, and raw Data.
3. **AI assistant** (`data_agent.py`) — a Claude-powered chatbot with tools over the live KPI table, for ad-hoc questions and for generating negotiation talking points against the funding-coverage target.
4. **Bilingual UI** (`i18n.py`) — a sidebar toggle switches the entire dashboard and the assistant's answer language between English and European Portuguese.

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
├── requirements-app.txt          # Minimal deps to run the Streamlit app
└── requirements.txt              # Full environment freeze (notebook/pipeline dev)
```

## Setup

```bash
git clone <this-repo>
cd NLP_Multi_Institution
pip install -r requirements-app.txt
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

## Team / course

Group project for the NLP course, Executive Master in Business Analytics & AI, Porto Business School.
