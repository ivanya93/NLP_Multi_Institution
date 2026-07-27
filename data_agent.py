"""Claude-powered data agent for the IPSS Financial Observatory.

WHAT THIS FILE DOES (plain language)
-------------------------------------
This powers the "AI Assistant" tab. Instead of the model just making up
an answer, it can call small Python functions ("tools") that look up real
numbers in the currently-filtered KPI table — e.g. "what's the median cost
per beneficiary for Creche?" — and then writes its answer using those real
numbers. It can also generate negotiation talking points and let the user
download the conversation as a text file.

WHAT THIS FILE DOES (technical)
--------------------------------
Implements Anthropic tool use (function calling): TOOLS_SCHEMA describes
each tool's name/parameters to the model, `_tools_impl()` provides the
actual Python implementations bound to the current (filtered) DataFrame,
and `_run_agent()` runs the request/tool-call/tool-result loop until the
model returns a final text answer. `render_chat()` wires this into the
Streamlit chat UI and follows the dashboard's EN/PT language toggle for
both its own labels and the instruction it gives the model.
"""

import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from i18n import TRANSLATIONS

MODEL = "claude-sonnet-4-6"

# KPI columns and grouping dimensions the tools are allowed to query.
# Kept as an explicit allow-list (rather than letting the model pass any
# column name) so a hallucinated/misspelled column fails with a clear error
# message the model can recover from, instead of a raw pandas KeyError.
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
    """Build the four tool functions, closing over the current (already
    filtered by the sidebar) DataFrame and the funding-coverage target.
    Each function returns a plain string (JSON) — that's the format the
    Claude API expects back as a tool_result."""

    def dataset_info() -> str:
        """Tool: high-level shape of the data, so the model knows what
        values/dimensions it can ask for before making other tool calls."""
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
        """Tool: e.g. median monthly_cost_per_beneficiary grouped by concelho.
        This is the workhorse for most "compare X across Y" questions."""
        if kpi not in NUMERIC_KPIS:
            return f"Unknown KPI '{kpi}'. Choose from: {NUMERIC_KPIS}"
        if group_by not in DIMENSIONS:
            return f"Unknown dimension '{group_by}'. Choose from: {DIMENSIONS}"
        if agg not in ("median", "mean", "min", "max", "count", "sum"):
            return "agg must be one of median|mean|min|max|count|sum"
        out = df.groupby(group_by)[kpi].agg(agg).round(3).sort_values(ascending=False)
        return out.to_json(force_ascii=False)

    def filter_records(dimension: str, value: str) -> str:
        """Tool: full-detail rows matching a dimension (e.g. institution_id
        contains "9c027b3d", or concelho contains "Faro"). Used when the
        model needs record-level detail rather than an aggregate."""
        if dimension not in DIMENSIONS:
            return f"Unknown dimension '{dimension}'. Choose from: {DIMENSIONS}"
        sel = df[df[dimension].astype(str).str.contains(value, case=False, na=False)]
        if sel.empty:
            return f"No records where {dimension} matches '{value}'."
        cols = ["institution_id", "resposta_social_clean", "concelho", "ano"] + NUMERIC_KPIS
        return sel[cols].round(2).to_json(orient="records", force_ascii=False)

    def coverage_gap_report() -> str:
        """Tool: per social response, how far below (or above) the 50%
        funding target the median institution sits, in both percentage
        points and actual euros per beneficiary per month. This is the
        one tool built specifically for the "give me negotiation talking
        points" use case — the model is instructed to always call this
        rather than eyeballing numbers from aggregate_kpi."""
        rep = {}
        for name, g in df.groupby("resposta_social_clean"):
            med_cov = g["funding_coverage"].median()
            med_cost = g["monthly_cost_per_beneficiary"].median()
            med_fund = g["monthly_social_security_funding_per_beneficiary"].median()
            gap_eur = max(0.0, target * med_cost - med_fund)  # euros still needed to reach the target
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

    # Map tool name (as the model will call it) -> Python function. The
    # `lambda i: ...` wrappers exist because the Claude API sends tool
    # inputs as a single dict per call; this unpacks that dict into the
    # named arguments each underlying function expects.
    return {
        "dataset_info": lambda i: dataset_info(),
        "aggregate_kpi": lambda i: aggregate_kpi(i["kpi"], i["group_by"], i.get("agg", "median")),
        "filter_records": lambda i: filter_records(i["dimension"], i["value"]),
        "coverage_gap_report": lambda i: coverage_gap_report(),
    }


# JSON-schema description of the same four tools, sent to the Claude API so
# the model knows they exist and what arguments each one takes. This must
# stay in sync with the function names/signatures in _tools_impl() above.
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

# The model's instructions. `{language_instruction}` is filled in at render
# time from i18n.py so the same prompt drives both an English-only and a
# Portuguese-only assistant depending on the dashboard's language toggle.
SYSTEM_TEMPLATE = """You are the data analyst of the Confederation, which represents
Portuguese IPSS. You analyze a KPI table extracted from OCIP filings (income
statements by social response / 'resposta social', per institution).

Context: the Confederation negotiates with the Ministry of Labour, Solidarity
and Social Security (via the Compromisso de Cooperação) aiming for Social
Security funding of at least 50% of total cost per beneficiary, per social
response. All monetary values are EUR per month unless stated otherwise.
Institutions and their equipment are anonymized (INST_xxxx, EQUIP_xxxx).

Rules:
- Always fetch real numbers with your tools; never invent values.
- When asked for negotiation arguments or talking points, call
  coverage_gap_report and build arguments from the actual gaps.
- Be specific: cite the social response, the € values, and the coverage %.
- Note limitations honestly (small sample, medians, one filing year) when relevant.
- Never name the Confederation or spell out its acronym or legal name, even if
  the user names it first or asks you directly. Always call it "the
  Confederation" / "a Confederação". The same applies to institution and
  equipment names: only ever refer to them by their anonymized IDs.
- {language_instruction}"""


# --------------------------------------------------------- anonymization guard
# The rule above tells the model never to name the Confederation, but that is
# probabilistic — the model knows the sector and can still emit the real name,
# especially in long Portuguese answers or when the user names it first. This is
# the deterministic backstop, applied to every answer before it is displayed.
#
# The acronym and the full legal name, accents optional (the model does drop
# them) and tolerant of the line breaks it may wrap the name in.
_ORG_NAME = (r"Confedera[cç][aã]o\s+Nacional\s+das\s+Institui[cç][oõ]es"
             r"\s+de\s+Solidariedade|CNIS")

# Order matters: the article and contraction forms have to be consumed before
# the bare form, otherwise "do CNIS" would come out as "do a Confederação".
# The optional "(?:[oa]\s+)?" absorbs the article in "do o CNIS"-style hits and
# in "da Confederação Nacional ...", where the name already carries its own.
_ORG_SUBS = {
    "pt": [
        (rf"\b[Dd](?:o|a|e)\s+(?:[oa]\s+)?(?:{_ORG_NAME})\b", "da Confederação"),
        (rf"\b[Nn](?:o|a)\s+(?:[oa]\s+)?(?:{_ORG_NAME})\b", "na Confederação"),
        (rf"\b[Pp]el(?:o|a)\s+(?:[oa]\s+)?(?:{_ORG_NAME})\b", "pela Confederação"),
        (rf"\b[Aa]o\s+(?:[oa]\s+)?(?:{_ORG_NAME})\b", "à Confederação"),
        (rf"[Àà]\s+(?:[oa]\s+)?(?:{_ORG_NAME})\b", "à Confederação"),
        (rf"\b[OoAa]\s+(?:{_ORG_NAME})\b", "a Confederação"),
        (rf"\b(?:{_ORG_NAME})\b", "a Confederação"),
    ],
    "en": [
        (rf"\b[Tt]he\s+(?:{_ORG_NAME})\b", "the Confederation"),
        (rf"\b(?:{_ORG_NAME})\b", "the Confederation"),
    ],
}


def _starts_sentence(text, index):
    """True if `index` is the first non-space position of a sentence."""
    before = text[:index].rstrip()
    return not before or before[-1] in ".!?:;\n•-"


def scrub_org_name(text, lang="en"):
    """Replace every mention of the client organization with a generic label.

    Applied to the model's final answer (and therefore also to whatever the
    user downloads as a conversation transcript), so the real name cannot
    reach the screen even if the model ignores its instructions.

    Capitalization follows sentence position, not the matched text: the
    acronym is upper-case wherever it appears, so copying its case would
    produce "Data from The Confederation shows ...".
    """
    if not text:
        return text

    def _replace(match, replacement):
        if _starts_sentence(match.string, match.start()):
            return replacement[0].upper() + replacement[1:]
        return replacement

    for pattern, replacement in _ORG_SUBS.get(lang, _ORG_SUBS["en"]):
        text = re.sub(pattern, lambda m, r=replacement: _replace(m, r), text)
    return text


# ---------------------------------------------------------------------- agent
def _run_agent(client, system, user_message, history, impl, lang="en"):
    """The tool-use loop: ask Claude for a response; if it wants to call a
    tool, run it locally and send the result back; repeat until Claude
    replies with plain text instead of a tool call. `history` is the prior
    turns of this conversation (kept in st.session_state by render_chat),
    so the model has context across multiple questions."""
    messages = history + [{"role": "user", "content": user_message}]
    while True:
        response = client.messages.create(
            model=MODEL, max_tokens=1500, system=system,
            tools=TOOLS_SCHEMA, messages=messages,
        )
        if response.stop_reason != "tool_use":
            # Model is done calling tools and has written its final answer.
            # Scrubbed here rather than at the call site so every path that
            # consumes an answer (display, history, transcript download) gets
            # the anonymized text.
            answer = "".join(b.text for b in response.content if b.type == "text")
            return scrub_org_name(answer, lang)

        # Model asked to call one or more tools in this turn — run each one
        # locally and package the results the way the API expects them back.
        results = []
        for block in (b for b in response.content if b.type == "tool_use"):
            fn = impl.get(block.name)
            result = fn(block.input) if fn else f"Tool {block.name} not found"
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": result})
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})
        # Loop again: the model now sees the tool result and either calls
        # another tool or writes its final answer.


# ------------------------------------------------------------------- chat tab
def render_chat(df, raw_df, kpi_labels, target, lang="en"):
    """Renders the whole "AI Assistant" tab: suggested-question buttons,
    chat history, the input box, and the download/clear-conversation
    controls. Called once per Streamlit rerun from app.py."""
    t = TRANSLATIONS[lang]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except Exception:
        # No key configured (or the anthropic package failed to import) —
        # degrade gracefully instead of crashing the whole dashboard, since
        # every other tab works fine without this.
        st.warning(t["assistant_missing_key"])
        return

    impl = _tools_impl(df, target)
    system = SYSTEM_TEMPLATE.format(language_instruction=t["answer_language_instruction"])
    target_str = f"{target:.0%}"

    st.markdown(f"### {t['assistant_heading']}")
    st.caption(t["assistant_caption"].format(target=target_str))

    # One-click example questions, translated and with {target} filled in
    # (e.g. "...below the 50% funding target..."). Clicking one queues it
    # into chat_pending, picked up just below as if the user had typed it.
    suggestions = [s.format(target=target_str) for s in t["assistant_suggestions"]]
    cols = st.columns(len(suggestions))
    for i, s in enumerate(suggestions):
        if cols[i].button(s, width="stretch", key=f"sugg_{i}"):
            st.session_state.chat_pending = s

    # chat_msgs: what's shown on screen (both roles, display text only).
    # chat_history: what's sent back to the API on the next turn (Anthropic
    # message format) — kept separate because the API's message objects
    # aren't the same shape as what st.chat_message needs to render.
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
                    answer = _run_agent(client, system, prompt, st.session_state.chat_history, impl, lang)
                except Exception as e:
                    # e.g. API key invalid, rate limit, network error — show
                    # it in the chat itself rather than an unhandled crash.
                    answer = t["chat_error"].format(error=e)
            st.markdown(answer)
        st.session_state.chat_msgs.append({"role": "assistant", "content": answer})
        st.session_state.chat_history += [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ]

    if st.session_state.chat_msgs:
        # Let the team save a session's Q&A as a plain-text briefing note
        # (e.g. to paste into negotiation prep docs) without needing to
        # copy-paste from the chat UI by hand.
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
