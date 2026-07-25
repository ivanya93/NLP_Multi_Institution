"""IPSS Financial Observatory — OCIP KPI dashboard + AI assistant.

Streamlit app over the multi-institution OCIP pipeline outputs
(data/outputs/kpi_df.csv, raw_df.csv). Organized by social response and
region, with a Claude-powered chatbot for KPI questions and negotiation
talking points. UI available in English and European Portuguese (sidebar
toggle) since the team is bilingual and the data/negotiation counterpart
(Ministry of Labour, Solidarity and Social Security) is Portuguese-speaking.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from i18n import TRANSLATIONS

# ---------------------------------------------------------------- page config
st.set_page_config(
    page_title="IPSS Financial Observatory",
    page_icon="📊",
    layout="wide",
)

# Corporate palette
NAVY = "#1F3A5F"
STEEL = "#4A6FA5"
GREY = "#6C757D"
GREEN = "#2E7D5B"
RED = "#B0413E"

st.markdown(
    f"""
    <style>
    h1, h2, h3 {{ color: {NAVY}; }}
    [data-testid="stMetricValue"] {{ color: {NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: #F4F6F9; }}
    div[data-testid="stMetric"] {{
        background-color: #FFFFFF;
        border: 1px solid #DDE3EC;
        border-radius: 8px;
        padding: 12px 16px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ load data
BASE = Path(__file__).resolve().parent
OUT = BASE / "data" / "outputs"

TARGET_COVERAGE = 0.50  # negotiation goal: SS funding >= 50% of cost/beneficiary
TARGET_STR = f"{TARGET_COVERAGE:.0%}"


@st.cache_data
def load_data():
    kpi = pd.read_csv(OUT / "kpi_df.csv")
    raw = pd.read_csv(OUT / "raw_df.csv")
    # Two ways of measuring SS funding per beneficiary:
    # 1) Mapa A "ISS, IP" P&L lines (the notebook KPI) - missing when the
    #    institution books the funding under a different line (~half the rows).
    # 2) Authoritative ss_funding (Mapa Comparticipações page, falling back to
    #    "Subsídios de entidades públicas"), per notebook section 7.
    kpi["ss_funding_benef_mapa_a"] = kpi["monthly_social_security_funding_per_beneficiary"]
    kpi["ss_funding_benef_auth"] = (
        kpi["monthly_social_security_funding"] / kpi["n_medio_utentes"]
    )
    kpi["resposta_social_clean"] = (
        kpi["resposta_social"].str.replace(r"^\d+\s*-\s*", "", regex=True).str.title()
    )
    return kpi, raw


# --------------------------------------------------------------- language toggle
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
t = TRANSLATIONS[lang]
KPI_LABELS = t["kpi_labels"]

try:
    kpi_df, raw_df = load_data()
except FileNotFoundError:
    st.error(t["missing_outputs_error"])
    st.stop()

# -------------------------------------------------------------------- sidebar
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
    _fund_col = ("ss_funding_benef_auth" if basis == t["funding_basis_options"][0]
                 else "ss_funding_benef_mapa_a")
    kpi_df = kpi_df.copy()
    kpi_df["monthly_social_security_funding_per_beneficiary"] = kpi_df[_fund_col]
    kpi_df["funding_coverage"] = kpi_df[_fund_col] / kpi_df["monthly_cost_per_beneficiary"]

    years = sorted(kpi_df["ano"].dropna().unique())
    institutions = sorted(kpi_df["institution_id"].dropna().unique())
    groups = sorted(kpi_df["activity_group"].dropna().unique())
    responses = sorted(kpi_df["resposta_social_clean"].dropna().unique())
    concelhos = sorted(kpi_df["concelho"].dropna().unique())

    f_years = st.multiselect(t["year_label"], years, default=years)
    f_inst = st.multiselect(t["institution_filter_label"], institutions, default=institutions)
    f_groups = st.multiselect(t["activity_group_label"], groups, default=groups)
    f_resp = st.multiselect(t["social_response_label"], responses, default=responses)
    f_conc = st.multiselect(t["region_label"], concelhos, default=concelhos)

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
with tab_overview:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t["median_cost_metric"], f"€ {df['monthly_cost_per_beneficiary'].median():,.0f}/mo")
    c2.metric(t["median_funding_metric"], f"€ {df['monthly_social_security_funding_per_beneficiary'].median():,.0f}/mo")
    med_cov = df["funding_coverage"].median()
    c3.metric(
        t["median_coverage_metric"],
        f"{med_cov:.0%}",
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
    )
    cov["funding_coverage_pct"] = cov["funding_coverage"] * 100
    st.bar_chart(cov, x="resposta_social_clean", y="funding_coverage_pct",
                 color="#4A6FA5", horizontal=True, height=320)
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
    st.bar_chart(grp, x="activity_group",
                 y=[t["series_cost"], t["series_funding"], t["series_fees"]],
                 stack=False, height=320,
                 color=["#B0413E", "#1F3A5F", "#4A6FA5"])

    deficit = df[df["monthly_ebitda_per_beneficiary"] < 0]
    st.markdown(
        t["deficit_flag"].format(
            n=len(deficit), total=len(df), pct=f"{len(deficit)/len(df):.0%}"
        )
    )

# ---------------------------------------------------------- by social response
with tab_resp:
    kpi_choice = st.selectbox(
        t["kpi_selectbox_label"], list(KPI_LABELS), format_func=KPI_LABELS.get, key="kpi_resp"
    )
    plot_df = df.copy()
    if kpi_choice == "funding_coverage":
        plot_df[kpi_choice] = plot_df[kpi_choice] * 100

    st.markdown(f"### {t['distribution_title'].format(kpi=KPI_LABELS[kpi_choice])}")
    st.scatter_chart(
        plot_df, x="resposta_social_clean", y=kpi_choice,
        color="activity_group", height=380,
    )

    st.markdown(f"### {t['summary_stats_title']}")
    summary = (
        plot_df.groupby("resposta_social_clean")[kpi_choice]
        .agg(records="count", median="median", mean="mean", min="min", max="max")
        .round(1)
        .sort_values("median", ascending=False)
    )
    st.dataframe(summary, width="stretch")

# -------------------------------------------------------------------- by region
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
    )
    st.bar_chart(reg, x="concelho", y=kpi_choice_r, horizontal=True,
                 color="#1F3A5F", height=max(300, 24 * len(reg)))

    st.markdown(f"### {t['region_x_response_title']}")
    pivot = reg_df.pivot_table(
        index="concelho", columns="resposta_social_clean",
        values=kpi_choice_r, aggfunc="median",
    ).round(1)
    st.dataframe(pivot, width="stretch")

# ---------------------------------------------------------- institution explorer
with tab_inst:
    inst = st.selectbox(t["institution_label"], sorted(df["institution_id"].unique()))
    inst_df = df[df["institution_id"] == inst]
    meta_cols = st.columns(4)
    meta_cols[0].metric(t["concelho_metric"], str(inst_df["concelho"].iloc[0]))
    meta_cols[1].metric(t["year_metric"], str(int(inst_df["ano"].iloc[0])))
    meta_cols[2].metric(t["responses_metric"], len(inst_df))
    meta_cols[3].metric(t["avg_benef_metric"], f"{inst_df['n_medio_utentes'].sum():,.0f}")

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
with tab_chat:
    from data_agent import render_chat  # separate module keeps app.py readable

    render_chat(df, raw_df, KPI_LABELS, TARGET_COVERAGE, lang)

# ------------------------------------------------------------------------ data
with tab_data:
    st.markdown(f"### {t['kpi_table_title']}")
    st.dataframe(df.round(2), width="stretch", height=420)
    st.markdown(f"### {t['raw_data_title']}")
    st.dataframe(raw_df.round(2), width="stretch", height=320)
