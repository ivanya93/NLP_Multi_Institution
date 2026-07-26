"""IPSS Financial Observatory — OCIP KPI dashboard + AI assistant.

WHAT THIS FILE DOES (plain language)
-------------------------------------
This is the main screen of the app. It loads the KPI numbers that
`pipeline.py` already extracted from the institutions' OCIP financial
filings, lets the user filter them (by year, institution, region, etc.),
and displays them as cards, charts and tables across six tabs. One of
those tabs embeds an AI chat assistant (built in `data_agent.py`) that can
answer questions about the filtered data in plain English or Portuguese.

WHAT THIS FILE DOES (technical)
--------------------------------
Streamlit script (re-run top-to-bottom on every user interaction) over the
multi-institution OCIP pipeline outputs (data/outputs/kpi_df.csv,
raw_df.csv). UI text is fully bilingual (EN/PT) via `i18n.py`, since the
team is bilingual and the negotiation counterpart (Ministry of Labour,
Solidarity and Social Security) is Portuguese-speaking.
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from i18n import TRANSLATIONS

# Portuguese place names keep these small connector words lowercase (unless
# they're the first word), e.g. "PÓVOA DE VARZIM" -> "Póvoa de Varzim".
_PT_LOWERCASE_PARTICLES = {"de", "da", "do", "das", "dos", "e", "a", "o", "à", "às"}


def titlecase_pt(text):
    words = str(text).split(" ")
    return " ".join(
        w.lower() if i > 0 and w.lower() in _PT_LOWERCASE_PARTICLES
        else w[:1].upper() + w[1:].lower()
        for i, w in enumerate(words)
    )


def _remove_chip(session_key, item):
    """on_click callback for a chip's × button: drop just that one value
    from the given multiselect's selection (safe to mutate session_state
    here, since callbacks run before the widget re-instantiates)."""
    st.session_state[session_key] = [
        x for x in st.session_state[session_key] if x != item
    ]


def chip_multiselect(label, options, session_key, placeholder):
    """A multiselect whose own selected-item pills are hidden in favor of a
    wrapping chip row below it — each chip has a working × (removes just
    that value) instead of the pills piling up inside the box. A CSS
    ::before keeps showing the placeholder text even once something is
    selected (hiding the pills would otherwise leave the box looking
    empty)."""
    box_key = f"{session_key}_box"
    box = st.container(key=box_key)
    with box:
        selected = st.multiselect(
            label, options, default=options, key=session_key, placeholder=placeholder,
        )
    # The ::before placeholder-text rule (shared CSS block below) needs the
    # actual placeholder string, which varies by language, so it's injected
    # here per box instead of hardcoded in that static block.
    st.markdown(
        f"""
        <style>
        .st-key-{box_key} [data-baseweb="select"] > div > div:first-child:has([data-baseweb="tag"])::before {{
            content: "{placeholder}";
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    if selected:
        chip_row = st.container(key=f"{session_key}_chip_row")
        with chip_row:
            for item in selected:
                st.button(
                    f"{item}  ×", key=f"{session_key}_chip_remove_{item}",
                    on_click=_remove_chip, args=(session_key, item),
                )
    return selected

# ---------------------------------------------------------------- page config
st.set_page_config(
    page_title="IPSS Financial Observatory",
    page_icon="📊",
    layout="wide",
)

# ------------------------------------------------------------- theming (CSS)
# Only style things Streamlit's own theme system doesn't already handle
# (metric-card borders), and do it with Streamlit's CSS *variables* instead
# of hardcoded hex colors. These variables automatically switch value when
# the user picks Light / Dark / System from the app menu (top-right "⋮").
# Earlier versions of this file hardcoded a light sidebar background and a
# dark navy heading color — those look fine in Light mode but turn into
# barely-visible dark-on-dark text in Dark mode. Using var(--...) instead
# lets Streamlit pick colors with the right contrast for whichever theme is
# active, so nothing needs to be duplicated per theme.
st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 8px;
        padding: 12px 16px;
    }

    /* chip_multiselect() filters (Year, Institution, Activity Group, Social
       response): hide the multiselect's own selected-item pills — the chip
       row below (with working × removal) replaces them. Those pills are
       <span data-baseweb="tag">, not <div>, hence no tag-name filter. The
       [class*=...] substring match covers every "<key>_select_box"
       container without listing each filter's key individually. */
    [class*="_select_box"] [data-baseweb="tag"] {
        display: none !important;
    }
    [class*="_select_box"] [data-baseweb="select"] > div > div:first-child::before {
        color: var(--text-color);
        opacity: 0.6;
        font-size: 0.875rem;
        padding-left: 8px;
        white-space: nowrap;
    }

    /* Same filters: lay their chip rows out horizontally, wrapping onto new
       lines as needed, instead of Streamlit's default vertical stack. */
    [class*="_select_chip_row"] {
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 0.25rem 0.75rem !important;
    }
    [class*="_select_chip_row"] button {
        background: transparent;
        border: none;
        padding: 0;
        font-size: 0.875rem;
        color: var(--text-color);
        opacity: 0.55;
    }
    [class*="_select_chip_row"] button:hover {
        opacity: 0.9;
        color: var(--primary-color);
        background: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ load data
BASE = Path(__file__).resolve().parent
OUT = BASE / "data" / "outputs"

# Negotiation benchmark from the project brief: CNIS wants Social Security
# funding to cover at least 50% of the cost per beneficiary, per social
# response. This single constant drives the "target" callouts across the
# whole dashboard (metrics, chart captions, chatbot system prompt).
TARGET_COVERAGE = 0.50
TARGET_STR = f"{TARGET_COVERAGE:.0%}"


@st.cache_data  # cached so the CSVs are only re-read when the files change,
                # not on every filter click / tab switch
def load_data():
    """Load the two CSVs pipeline.py produces and add a couple of derived
    columns the dashboard needs but the pipeline doesn't compute directly."""
    kpi = pd.read_csv(OUT / "kpi_df.csv")
    raw = pd.read_csv(OUT / "raw_df.csv")

    # There are two different ways to measure "Social Security funding per
    # beneficiary" in the source data, and they disagree for about half the
    # rows (see pipeline.py section 7 for why). We compute both here and let
    # the user pick which one drives the dashboard via the sidebar radio:
    #   1) "Mapa A" — the ISS,IP line items on the standard income-statement
    #      page. Simple, but blank whenever an institution books that
    #      funding under a different accounting line.
    #   2) "Authoritative" — the dedicated Comparticipações ISS,IP page
    #      (falling back to the public-subsidies line only if no match was
    #      found there). More complete, which is why it's the default.
    kpi["ss_funding_benef_mapa_a"] = kpi["monthly_social_security_funding_per_beneficiary"]
    kpi["ss_funding_benef_auth"] = (
        kpi["monthly_social_security_funding"] / kpi["n_medio_utentes"]
    )

    # "1103 - CRECHE" -> "Crèche": strip the internal numeric code prefix
    # and title-case it, purely for a nicer display label in charts/tables.
    kpi["resposta_social_clean"] = (
        kpi["resposta_social"].str.replace(r"^\d+\s*-\s*", "", regex=True).str.title()
    )

    # "PÓVOA DE VARZIM" -> "Póvoa de Varzim": the source PDFs write concelho
    # names in all caps; title-case them for display (see titlecase_pt above
    # for why plain .str.title() isn't enough here).
    kpi["concelho"] = kpi["concelho"].apply(titlecase_pt)
    return kpi, raw


# --------------------------------------------------------------- language toggle
# Kept in session_state so it survives Streamlit's rerun-on-every-click model
# instead of resetting to English each time a filter changes.
if "lang" not in st.session_state:
    st.session_state.lang = "en"

with st.sidebar:
    lang_choice = st.radio(
        "🌐 Language / Idioma", ["English", "Português"],
        index=0 if st.session_state.lang == "en" else 1,
        horizontal=True,
    )
    st.session_state.lang = "en" if lang_choice == "English" else "pt"

lang = st.session_state.lang
t = TRANSLATIONS[lang]          # shorthand: t["some_key"] -> label in the active language
KPI_LABELS = t["kpi_labels"]    # KPI column name -> human-readable label, in that language

# Activity Group and Social response are the only two filters whose actual
# option *values* (not just their labels) change with the language. Without
# this, switching language leaves their multiselect's session_state holding
# values from the old language (e.g. "Seniors") that don't match the new
# language's options (e.g. "Idosos") — Streamlit then silently drops them,
# clearing the filter. Remap each selected value from the old language back
# to its canonical Portuguese key, then forward into the new language.
_prev_lang = st.session_state.get("_prev_lang")
if _prev_lang is not None and _prev_lang != lang:
    _old_t = TRANSLATIONS[_prev_lang]
    for _key, _value_map_name in [
        ("f_groups_select", "activity_group_values"),
        ("f_resp_select", "resposta_social_values"),
    ]:
        if _key in st.session_state:
            _reverse = {v: k for k, v in _old_t[_value_map_name].items()}
            _forward = t[_value_map_name]
            st.session_state[_key] = [
                _forward.get(_reverse.get(v, v), v) for v in st.session_state[_key]
            ]
st.session_state["_prev_lang"] = lang

try:
    kpi_df, raw_df = load_data()
except FileNotFoundError:
    # Happens if someone runs the app before ever running pipeline.py, or
    # points OUT at the wrong folder. Fail loudly with a helpful message
    # rather than crashing on a cryptic pandas error further down.
    st.error(t["missing_outputs_error"])
    st.stop()

# -------------------------------------------------------------------- sidebar
# Everything that narrows down "which rows count" lives in the sidebar:
# the funding-basis choice, then the five filter dropdowns. `df` (built at
# the end of this block) is the single filtered dataset every tab reads from.
with st.sidebar:
    st.title(t["app_name"])
    st.caption(t["app_subtitle"])
    st.markdown("---")

    st.subheader(t["filters_header"])
    basis = st.radio(
        t["funding_basis_label"],
        t["funding_basis_options"],
        help=t["funding_basis_help"],
    )
    # Swap in whichever of the two funding columns (see load_data() above)
    # the user picked, then recompute the derived "coverage" ratio from it.
    # Recomputing here (rather than precomputing both in load_data) keeps
    # exactly one "funding_coverage" column downstream, so every chart/tab
    # below doesn't need to know which basis is active.
    _fund_col = ("ss_funding_benef_auth" if basis == t["funding_basis_options"][0]
                 else "ss_funding_benef_mapa_a")
    kpi_df = kpi_df.copy()
    kpi_df["monthly_social_security_funding_per_beneficiary"] = kpi_df[_fund_col]
    kpi_df["funding_coverage"] = kpi_df[_fund_col] / kpi_df["monthly_cost_per_beneficiary"]

    # pipeline.py always writes the Portuguese social-response and activity-
    # group names; swap in the EN translations here so every filter, chart
    # and table downstream picks them up automatically (PT values are left
    # unchanged).
    kpi_df["resposta_social_clean"] = (
        kpi_df["resposta_social_clean"]
        .map(t["resposta_social_values"])
        .fillna(kpi_df["resposta_social_clean"])
    )
    kpi_df["activity_group"] = (
        kpi_df["activity_group"]
        .map(t["activity_group_values"])
        .fillna(kpi_df["activity_group"])
    )

    # Build each filter's option list from the data itself (not hardcoded),
    # so new years/institutions/regions show up automatically after
    # re-running pipeline.py with fresh PDFs.
    years = sorted(kpi_df["ano"].dropna().unique())
    institutions = sorted(kpi_df["institution_id"].dropna().unique())
    groups = sorted(kpi_df["activity_group"].dropna().unique())
    responses = sorted(kpi_df["resposta_social_clean"].dropna().unique())
    concelhos = sorted(kpi_df["concelho"].dropna().unique())

    # All five filters use the chip variant (see chip_multiselect above)
    # since their pill count can get long enough to be worth wrapping into
    # their own row below the box.
    f_years = chip_multiselect(
        t["year_label"], years, "f_years_select", t["multiselect_placeholder"],
    )
    f_inst = chip_multiselect(
        t["institution_filter_label"], institutions, "f_inst_select",
        t["multiselect_placeholder"],
    )
    f_groups = chip_multiselect(
        t["activity_group_label"], groups, "f_groups_select", t["multiselect_placeholder"],
    )
    f_resp = chip_multiselect(
        t["social_response_label"], responses, "f_resp_select", t["multiselect_placeholder"],
    )
    f_conc = chip_multiselect(
        t["region_label"], concelhos, "f_conc_select", t["multiselect_placeholder"],
    )

    # All five filters apply together (AND, not OR) — e.g. picking one
    # institution AND one year shows only that institution's records for
    # that year. Every tab from here on reads `df`, never `kpi_df` directly.
    df = kpi_df[
        kpi_df["ano"].isin(f_years)
        & kpi_df["institution_id"].isin(f_inst)
        & kpi_df["activity_group"].isin(f_groups)
        & kpi_df["resposta_social_clean"].isin(f_resp)
        & kpi_df["concelho"].isin(f_conc)
    ]

    st.markdown("---")
    st.subheader(t["coverage_header"])
    st.metric(t["institutions_metric"], df["institution_id"].nunique())
    st.metric(t["records_metric"], len(df))
    st.metric(t["beneficiaries_metric"], f"{df['n_medio_utentes'].sum():,.0f}")

    st.markdown("---")
    st.subheader(t["downloads_header"])
    # Both downloads respect the current filters/basis, so the team can
    # export exactly the slice of data they're looking at (e.g. for a
    # negotiation briefing deck) without re-running any code.
    st.download_button(
        t["kpi_csv_button"],
        df.to_csv(index=False).encode("utf-8"),
        "kpi_filtered.csv",
        "text/csv",
        width="stretch",
    )
    st.download_button(
        t["raw_csv_button"],
        raw_df.to_csv(index=False).encode("utf-8"),
        "raw_df.csv",
        "text/csv",
        width="stretch",
    )
    st.markdown("---")
    st.caption(t["footer_caption"])

if df.empty:
    # E.g. the user filtered to a year/institution combination that has no
    # matching rows. Stop here instead of letting every tab below crash on
    # empty-dataframe edge cases (median of nothing, etc.).
    st.warning(t["no_data_warning"])
    st.stop()

# ---------------------------------------------------------------------- tabs
st.title(t["main_title"])
st.caption(t["main_caption"].format(target=TARGET_STR))

tab_overview, tab_resp, tab_region, tab_inst, tab_chat, tab_data = st.tabs([
    t["tab_overview"], t["tab_by_response"], t["tab_by_region"],
    t["tab_institution"], t["tab_assistant"], t["tab_data"],
])

# ------------------------------------------------------------------- overview
# Headline numbers + two summary charts: are we, on average, near the 50%
# funding target, and how does cost/funding/fees break down by activity
# group (elderly care vs. childcare)?
with tab_overview:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t["median_cost_metric"], f"€ {df['monthly_cost_per_beneficiary'].median():,.0f}/mo")
    c2.metric(t["median_funding_metric"], f"€ {df['monthly_social_security_funding_per_beneficiary'].median():,.0f}/mo")
    med_cov = df["funding_coverage"].median()
    c3.metric(
        t["median_coverage_metric"],
        f"{med_cov:.0%}",
        # Green/red delta arrow vs. the 50% target, e.g. "-15% vs 50% target"
        delta=f"{med_cov - TARGET_COVERAGE:+.0%} {t['coverage_delta_suffix'].format(target=TARGET_STR)}",
    )
    share_above = (df["funding_coverage"] >= TARGET_COVERAGE).mean()
    c4.metric(t["responses_above_target_metric"].format(target=TARGET_STR), f"{share_above:.0%}")
    c5.metric(t["median_ebitda_metric"], f"€ {df['monthly_ebitda_per_beneficiary'].median():,.0f}/mo")

    st.markdown(f"### {t['coverage_chart_title'].format(target=TARGET_STR)}")
    cov = (
        df.groupby("resposta_social_clean")["funding_coverage"]
        .median()
        .sort_values()
        .reset_index()
        .rename(columns={"resposta_social_clean": t["col_social_response"]})
    )
    cov[t["col_funding_coverage_pct"]] = cov["funding_coverage"] * 100  # 0.35 -> 35, for the chart axis
    # A wrapped copy just for the axis labels: long social-response names
    # get a manual line break (see resposta_social_line_breaks); short ones
    # pass through unchanged.
    cov["_label"] = cov[t["col_social_response"]].map(
        lambda v: t["resposta_social_line_breaks"].get(v, v)
    )
    coverage_chart = (
        alt.Chart(cov)
        .mark_bar(color="#4A6FA5")
        .encode(
            y=alt.Y("_label:N", title=t["col_social_response"],
                    sort=cov["_label"].tolist(),
                    axis=alt.Axis(labelLimit=1000, labelExpr="split(datum.label, '\\n')")),
            x=alt.X(f"{t['col_funding_coverage_pct']}:Q", title=t["col_funding_coverage_pct"]),
        )
        .properties(height=320)
    )
    st.altair_chart(coverage_chart, width="stretch")
    st.caption(t["coverage_chart_caption"].format(target=TARGET_STR))

    st.markdown(f"### {t['cost_vs_funding_chart_title']}")
    grp = (
        df.groupby("activity_group")[
            ["monthly_cost_per_beneficiary",
             "monthly_social_security_funding_per_beneficiary",
             "monthly_fee_per_beneficiary"]
        ].median().reset_index()
        .rename(columns={
            "monthly_cost_per_beneficiary": t["series_cost"],
            "monthly_social_security_funding_per_beneficiary": t["series_funding"],
            "monthly_fee_per_beneficiary": t["series_fees"],
        })
    )
    grp_long = grp.melt(
        id_vars="activity_group", var_name="series", value_name="value",
        value_vars=[t["series_cost"], t["series_funding"], t["series_fees"]],
    )
    # Built with Altair directly (instead of st.bar_chart) so the x-axis
    # category labels render horizontally (labelAngle=0) rather than
    # Vega-Lite's auto-rotated default for this grouped-bar layout.
    cost_chart = (
        alt.Chart(grp_long)
        .mark_bar()
        .encode(
            x=alt.X("activity_group:N", title=t["activity_group_label"], axis=alt.Axis(labelAngle=0)),
            xOffset="series:N",
            y=alt.Y("value:Q", title=None),
            color=alt.Color(
                "series:N", title=None,
                scale=alt.Scale(
                    domain=[t["series_cost"], t["series_funding"], t["series_fees"]],
                    range=["#B0413E", "#1F3A5F", "#4A6FA5"],
                ),
            ),
        )
        .properties(height=320)
    )
    st.altair_chart(cost_chart, width="stretch")

    # Plain-language flag: how many of the filtered records are actually
    # losing money per beneficiary each month, given current funding.
    deficit = df[df["monthly_ebitda_per_beneficiary"] < 0]
    st.markdown(
        t["deficit_flag"].format(
            n=len(deficit), total=len(df), pct=f"{len(deficit)/len(df):.0%}"
        )
    )

# ---------------------------------------------------------- by social response
# Same idea as Overview, but lets the user pick *any* KPI and see its full
# spread (not just the median) per social response.
with tab_resp:
    kpi_choice = st.selectbox(
        t["kpi_selectbox_label"], list(KPI_LABELS), format_func=KPI_LABELS.get, key="kpi_resp"
    )
    plot_df = df.copy()
    if kpi_choice == "funding_coverage":
        plot_df[kpi_choice] = plot_df[kpi_choice] * 100  # display as a percentage, not a 0-1 fraction
    plot_df = plot_df.rename(columns={
        "resposta_social_clean": t["col_social_response"],
        "activity_group": t["activity_group_label"],
    })

    st.markdown(f"### {t['distribution_title'].format(kpi=KPI_LABELS[kpi_choice])}")
    # Built with Altair directly (instead of st.scatter_chart) so the x-axis
    # social-response labels render horizontally (labelAngle=0) rather than
    # Vega-Lite's auto-rotated default for this many-category axis. A wrapped
    # copy of the labels (kept out of the tooltip/groupby/Summary stats below)
    # gets a manual line break for the long names (see
    # resposta_social_line_breaks); short ones pass through unchanged.
    plot_df["_label"] = plot_df[t["col_social_response"]].map(
        lambda v: t["resposta_social_line_breaks"].get(v, v)
    )
    dist_chart = (
        alt.Chart(plot_df)
        .mark_circle(size=60)
        .encode(
            x=alt.X("_label:N", title=t["col_social_response"],
                    axis=alt.Axis(labelAngle=0, labelLimit=1000,
                                  labelExpr="split(datum.label, '\\n')")),
            y=alt.Y(f"{kpi_choice}:Q", title=KPI_LABELS[kpi_choice]),
            color=alt.Color(t["activity_group_label"], type="nominal"),
            tooltip=[t["col_social_response"], kpi_choice, t["activity_group_label"]],
        )
        .properties(height=380)
    )
    st.altair_chart(dist_chart, width="stretch")

    st.markdown(f"### {t['summary_stats_title']}")
    summary = (
        plot_df.groupby(t["col_social_response"])[kpi_choice]
        .agg(records="count", median="median", mean="mean", min="min", max="max")
        .round(1)
        .sort_values("median", ascending=False)
        .rename(columns={
            "records": t["summary_col_records"],
            "median": t["summary_col_median"],
            "mean": t["summary_col_mean"],
            "min": t["summary_col_min"],
            "max": t["summary_col_max"],
        })
    )
    st.dataframe(summary, width="stretch")

# -------------------------------------------------------------------- by region
# Same KPI-picker pattern as the tab above, but sliced by concelho (region)
# instead of social response — useful for spotting regional cost/funding gaps.
with tab_region:
    kpi_choice_r = st.selectbox(
        t["kpi_selectbox_label"], list(KPI_LABELS), format_func=KPI_LABELS.get, key="kpi_region"
    )
    reg_df = df.copy()
    if kpi_choice_r == "funding_coverage":
        reg_df[kpi_choice_r] = reg_df[kpi_choice_r] * 100

    st.markdown(f"### {t['median_by_concelho_title'].format(kpi=KPI_LABELS[kpi_choice_r])}")
    reg = (
        reg_df.groupby("concelho")[kpi_choice_r]
        .median().sort_values().reset_index()
        .rename(columns={"concelho": t["concelho_metric"]})
    )
    # Built with Altair (instead of st.bar_chart) so the value axis can show
    # the translated KPI label instead of the raw column name, same as the
    # "By response" tab's distribution chart.
    region_chart = (
        alt.Chart(reg)
        .mark_bar(color="#1F3A5F")
        .encode(
            y=alt.Y(f"{t['concelho_metric']}:N", sort=reg[t["concelho_metric"]].tolist()),
            x=alt.X(f"{kpi_choice_r}:Q", title=KPI_LABELS[kpi_choice_r]),
        )
        .properties(height=max(300, 24 * len(reg)))  # taller chart if there are many regions
    )
    st.altair_chart(region_chart, width="stretch")

    st.markdown(f"### {t['region_x_response_title']}")
    pivot = reg_df.rename(columns={
        "resposta_social_clean": t["col_social_response"],
        "concelho": t["concelho_metric"],
    }).pivot_table(
        index=t["concelho_metric"], columns=t["col_social_response"],
        values=kpi_choice_r, aggfunc="median",
    ).round(1)
    st.dataframe(pivot, width="stretch")

# ---------------------------------------------------------- institution explorer
# Drill down into a single (anonymized) institution: its identifying
# metadata and a per-social-response breakdown of every KPI, exportable on
# its own for use outside the app (e.g. a one-page institution brief).
with tab_inst:
    inst = st.selectbox(t["institution_label"], sorted(df["institution_id"].unique()))
    inst_df = df[df["institution_id"] == inst]
    meta_cols = st.columns(4)
    meta_cols[0].metric(t["concelho_metric"], str(inst_df["concelho"].iloc[0]))
    meta_cols[1].metric(t["year_metric"], str(int(inst_df["ano"].iloc[0])))
    meta_cols[2].metric(t["responses_metric"], len(inst_df))
    meta_cols[3].metric(t["avg_benef_metric"], f"{inst_df['n_medio_utentes'].sum():,.0f}")

    # Map internal column names -> display labels for just the columns we
    # want to show here (a curated subset, not every KPI in the dataset).
    show_cols = {
        "resposta_social_clean": t["col_social_response"],
        "n_medio_utentes": t["col_avg_users"],
        "n_medio_funcionarios": t["col_avg_staff"],
        "monthly_revenue_per_beneficiary": t["col_revenue_benef"],
        "monthly_cost_per_beneficiary": t["col_cost_benef"],
        "monthly_social_security_funding_per_beneficiary": t["col_funding_benef"],
        "monthly_ebitda_per_beneficiary": t["col_ebitda_benef"],
        "funding_coverage": t["col_coverage"],
        "beneficiary_worker_ratio": t["col_benef_worker"],
    }
    tbl = inst_df[list(show_cols)].rename(columns=show_cols).set_index(t["col_social_response"])
    tbl[t["col_coverage"]] = (tbl[t["col_coverage"]] * 100).round(0).astype("Int64").astype(str) + "%"
    st.dataframe(tbl.round(0), width="stretch")

    st.download_button(
        t["download_institution_button"],
        inst_df.to_csv(index=False).encode("utf-8"),
        f"{inst}.csv", "text/csv",
    )

# ----------------------------------------------------------------- AI assistant
# Delegated to data_agent.py to keep this file focused on the dashboard
# layout. The import is done here (not at the top of the file) so the
# assistant's dependencies (the `anthropic` package) are only touched when
# this tab is actually rendered.
with tab_chat:
    from data_agent import render_chat  # separate module keeps app.py readable

    render_chat(df, raw_df, KPI_LABELS, TARGET_COVERAGE, lang)

# ------------------------------------------------------------------------ data
# Escape hatch: the full filtered KPI table and the complete (unfiltered)
# raw extraction, for anyone who wants to eyeball the underlying numbers
# rather than a chart.
with tab_data:
    st.markdown(f"### {t['kpi_table_title']}")
    st.dataframe(df.round(2).rename(columns=t["data_columns"]), width="stretch", height=420)
    st.markdown(f"### {t['raw_data_title']}")
    st.dataframe(raw_df.round(2).rename(columns=t["data_columns"]), width="stretch", height=320)
