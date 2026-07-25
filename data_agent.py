"""Claude-powered data agent for the IPSS Financial Observatory.

Answers KPI questions over the filtered KPI table, produces negotiation
talking points for the ≥50% funding-coverage goal, and lets the team
download the conversation as a briefing note. UI text and the model's
answer language follow the dashboard's language toggle (English/Português).
"""

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from i18n import TRANSLATIONS

MODEL = "claude-sonnet-4-6"

NUMERIC_KPIS = [
    "monthly_revenue_per_beneficiary",
    "monthly_fee_per_beneficiary",
    "monthly_social_security_funding_per_beneficiary",
    "monthly_cost_per_beneficiary",
    "monthly_ebitda_per_beneficiary",
    "monthly_revenue_per_worker",
    "monthly_cost_per_worker",
    "monthly_labour_cost_per_worker",
    "beneficiary_worker_ratio",
    "funding_coverage",
    "n_medio_utentes",
    "n_medio_funcionarios",
]
DIMENSIONS = ["resposta_social_clean", "activity_group", "concelho", "institution_id", "ano"]


# ------------------------------------------------------------------ tool impls
def _tools_impl(df: pd.DataFrame, target: float):
    def dataset_info() -> str:
        return json.dumps({
            "rows": len(df),
            "institutions": int(df["institution_id"].nunique()),
            "years": sorted(int(y) for y in df["ano"].dropna().unique()),
            "social_responses": sorted(df["resposta_social_clean"].dropna().unique()),
            "activity_groups": sorted(df["activity_group"].dropna().unique()),
            "concelhos": sorted(df["concelho"].dropna().unique()),
            "kpis": NUMERIC_KPIS,
            "note": "funding_coverage is SS funding as a fraction of cost per "
                    f"beneficiary; the negotiation target is >= {target}.",
        }, ensure_ascii=False, indent=2)

    def aggregate_kpi(kpi: str, group_by: str, agg: str = "median") -> str:
        if kpi not in NUMERIC_KPIS:
            return f"Unknown KPI '{kpi}'. Choose from: {NUMERIC_KPIS}"
        if group_by not in DIMENSIONS:
            return f"Unknown dimension '{group_by}'. Choose from: {DIMENSIONS}"
        if agg not in ("median", "mean", "min", "max", "count", "sum"):
            return "agg must be one of median|mean|min|max|count|sum"
        out = df.groupby(group_by)[kpi].agg(agg).round(3).sort_values(ascending=False)
        return out.to_json(force_ascii=False)

    def filter_records(dimension: str, value: str) -> str:
        if dimension not in DIMENSIONS:
            return f"Unknown dimension '{dimension}'. Choose from: {DIMENSIONS}"
        sel = df[df[dimension].astype(str).str.contains(value, case=False, na=False)]
        if sel.empty:
            return f"No records where {dimension} matches '{value}'."
        cols = ["institution_id", "resposta_social_clean", "concelho", "ano"] + NUMERIC_KPIS
        return sel[cols].round(2).to_json(orient="records", force_ascii=False)

    def coverage_gap_report() -> str:
        rep = {}
        for name, g in df.groupby("resposta_social_clean"):
            med_cov = g["funding_coverage"].median()
            med_cost = g["monthly_cost_per_beneficiary"].median()
            med_fund = g["monthly_social_security_funding_per_beneficiary"].median()
            gap_eur = max(0.0, target * med_cost - med_fund)
            rep[name] = {
                "records": len(g),
                "median_cost_per_beneficiary": round(med_cost, 2),
                "median_ss_funding_per_beneficiary": round(med_fund, 2),
                "median_coverage": round(med_cov, 3),
                "meets_50pct_target": bool(med_cov >= target),
                "monthly_gap_to_target_eur_per_beneficiary": round(gap_eur, 2),
                "share_records_with_negative_ebitda":
                    round(float((g["monthly_ebitda_per_beneficiary"] < 0).mean()), 3),
            }
        return json.dumps(rep, ensure_ascii=False, indent=2)

    return {
        "dataset_info": lambda i: dataset_info(),
        "aggregate_kpi": lambda i: aggregate_kpi(i["kpi"], i["group_by"], i.get("agg", "median")),
        "filter_records": lambda i: filter_records(i["dimension"], i["value"]),
        "coverage_gap_report": lambda i: coverage_gap_report(),
    }


TOOLS_SCHEMA = [
    {"name": "dataset_info",
     "description": "Overview of the KPI dataset: dimensions, KPIs, coverage.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "aggregate_kpi",
     "description": "Aggregate one KPI grouped by one dimension.",
     "input_schema": {"type": "object", "properties": {
         "kpi": {"type": "string"},
         "group_by": {"type": "string",
                      "description": "resposta_social_clean | activity_group | concelho | institution_id | ano"},
         "agg": {"type": "string", "description": "median (default) | mean | min | max | count | sum"}},
         "required": ["kpi", "group_by"]}},
    {"name": "filter_records",
     "description": "Return full KPI records where a dimension matches a value (substring, case-insensitive).",
     "input_schema": {"type": "object", "properties": {
         "dimension": {"type": "string"}, "value": {"type": "string"}},
         "required": ["dimension", "value"]}},
    {"name": "coverage_gap_report",
     "description": "Per social response: median cost, SS funding, coverage vs the 50% "
                    "target, € gap per beneficiary, and negative-EBITDA share. Use this "
                    "for negotiation talking points.",
     "input_schema": {"type": "object", "properties": {}}},
]

SYSTEM_TEMPLATE = """You are the data analyst of CNIS (Confederação Nacional das Instituições
de Solidariedade), which represents Portuguese IPSS. You analyze a KPI table
extracted from OCIP filings (income statements by social response / 'resposta
social', per institution).

Context: CNIS negotiates with the Ministry of Labour, Solidarity and Social
Security (via the Compromisso de Cooperação) aiming for Social Security funding
of at least 50% of total cost per beneficiary, per social response. All monetary
values are EUR per month unless stated otherwise. Institutions are anonymized
(INST_xxxx).

Rules:
- Always fetch real numbers with your tools; never invent values.
- When asked for negotiation arguments or talking points, call
  coverage_gap_report and build arguments from the actual gaps.
- Be specific: cite the social response, the € values, and the coverage %.
- Note limitations honestly (small sample, medians, one filing year) when relevant.
- {language_instruction}"""


# ---------------------------------------------------------------------- agent
def _run_agent(client, system, user_message, history, impl):
    messages = history + [{"role": "user", "content": user_message}]
    while True:
        response = client.messages.create(
            model=MODEL, max_tokens=1500, system=system,
            tools=TOOLS_SCHEMA, messages=messages,
        )
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        results = []
        for block in (b for b in response.content if b.type == "tool_use"):
            fn = impl.get(block.name)
            result = fn(block.input) if fn else f"Tool {block.name} not found"
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": result})
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})


# ------------------------------------------------------------------- chat tab
def render_chat(df, raw_df, kpi_labels, target, lang="en"):
    t = TRANSLATIONS[lang]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except Exception:
        st.warning(t["assistant_missing_key"])
        return

    impl = _tools_impl(df, target)
    system = SYSTEM_TEMPLATE.format(language_instruction=t["answer_language_instruction"])
    target_str = f"{target:.0%}"

    st.markdown(f"### {t['assistant_heading']}")
    st.caption(t["assistant_caption"].format(target=target_str))

    suggestions = [s.format(target=target_str) for s in t["assistant_suggestions"]]
    cols = st.columns(len(suggestions))
    for i, s in enumerate(suggestions):
        if cols[i].button(s, width="stretch", key=f"sugg_{i}"):
            st.session_state.chat_pending = s

    if "chat_msgs" not in st.session_state:
        st.session_state.chat_msgs = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_msgs:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input(t["chat_input_placeholder"])
    if "chat_pending" in st.session_state:
        prompt = st.session_state.pop("chat_pending")

    if prompt:
        st.session_state.chat_msgs.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner(t["chat_spinner"]):
                try:
                    answer = _run_agent(client, system, prompt, st.session_state.chat_history, impl)
                except Exception as e:
                    answer = t["chat_error"].format(error=e)
            st.markdown(answer)
        st.session_state.chat_msgs.append({"role": "assistant", "content": answer})
        st.session_state.chat_history += [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ]

    if st.session_state.chat_msgs:
        transcript = "\n\n".join(
            f"{t['transcript_you'] if m['role'] == 'user' else t['transcript_assistant']}: {m['content']}"
            for m in st.session_state.chat_msgs
        )
        header = (
            f"{t['transcript_header']}\n"
            f"Date: {datetime.now():%Y-%m-%d %H:%M}\n" + "=" * 50 + "\n\n"
        )
        c1, c2 = st.columns(2)
        c1.download_button(t["download_conversation_button"],
                           (header + transcript).encode("utf-8"),
                           f"ipss_insights_{datetime.now():%Y%m%d_%H%M}.txt",
                           width="stretch")
        if c2.button(t["clear_conversation_button"], width="stretch"):
            st.session_state.chat_msgs = []
            st.session_state.chat_history = []
            st.rerun()
