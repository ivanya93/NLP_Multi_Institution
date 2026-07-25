"""UI text for the IPSS Financial Observatory, English and European Portuguese.

WHAT THIS FILE DOES (plain language)
-------------------------------------
Every piece of text the app shows on screen — button labels, tab names,
chart titles, the chatbot's suggested questions — lives here twice: once
in English, once in Portuguese. When someone flips the language switch in
the sidebar, app.py and data_agent.py just read from a different half of
this dictionary; none of the display logic itself changes.

WHAT THIS FILE DOES (technical)
--------------------------------
`TRANSLATIONS` is a dict keyed by language code ("en" / "pt"), each value
itself a dict of string keys -> label. Callers do `t = TRANSLATIONS[lang]`
then `t["some_key"]`; keys containing `{placeholder}` (e.g. "{target}") are
filled in with `.format(...)` at the call site. Keep keys identical across
both languages — a missing key raises KeyError immediately rather than
silently falling back to English, which is what we want while the app is
still small enough to catch that in testing rather than in front of users.
To add a third language, add another top-level key (e.g. "es") with every
key from "en" translated; nothing else in the codebase needs to change.
"""

TRANSLATIONS = {
    "en": {
        # sidebar
        "app_name": "IPSS Observatory",
        "app_subtitle": "OCIP financial statements · KPIs by social response and region",
        "language_label": "Language",
        "filters_header": "Filters",
        "funding_basis_label": "SS funding basis",
        "funding_basis_options": [
            "Authoritative (Comparticipações + Subsídios)",
            "Mapa A ISS,IP lines only",
        ],
        "funding_basis_help": (
            "The Mapa A ISS,IP lines miss funding for institutions that book it "
            "under other P&L lines (~half the sample). The authoritative basis "
            "uses the dedicated Comparticipações page, falling back to public "
            "subsidies (pipeline notebook, section 7)."
        ),
        "year_label": "Year",
        "institution_filter_label": "Institution",
        "activity_group_label": "Activity group",
        "social_response_label": "Social response",
        "region_label": "Region (concelho)",
        "coverage_header": "Coverage",
        "institutions_metric": "Institutions",
        "records_metric": "Social-response records",
        "beneficiaries_metric": "Beneficiaries (avg users)",
        "downloads_header": "Downloads",
        "kpi_csv_button": "KPI table (CSV)",
        "raw_csv_button": "Full raw data (CSV)",
        "footer_caption": "CNIS · NLP Group Project · Porto Business School",
        "no_data_warning": "No records match the current filters.",
        "missing_outputs_error": (
            "KPI outputs not found. Run `python pipeline.py data/PDF_files "
            "data/outputs` first."
        ),
        # main title
        "main_title": "IPSS Financial Observatory",
        "main_caption": (
            "Income statements by social response, extracted from OCIP submissions. "
            "Negotiation benchmark: Social Security funding ≥ {target} of total "
            "cost per beneficiary."
        ),
        # tabs
        "tab_overview": "Overview",
        "tab_by_response": "By Social Response",
        "tab_by_region": "By Region",
        "tab_institution": "Institution Explorer",
        "tab_assistant": "AI Assistant",
        "tab_data": "Data",
        # overview tab
        "median_cost_metric": "Median cost / beneficiary",
        "median_funding_metric": "Median SS funding / beneficiary",
        "median_coverage_metric": "Median funding coverage",
        "coverage_delta_suffix": "vs {target} target",
        "responses_above_target_metric": "Responses at ≥{target} target",
        "median_ebitda_metric": "Median EBITDA / beneficiary",
        "coverage_chart_title": "Funding coverage vs the {target} target, by social response",
        "coverage_chart_caption": "Median SS funding as % of total cost per beneficiary. Target line: {target}.",
        "cost_vs_funding_chart_title": "Cost vs funding per beneficiary, by activity group",
        "series_cost": "Cost",
        "series_funding": "SS funding",
        "series_fees": "Family fees",
        "deficit_flag": (
            "**Structural deficit flag:** {n} of {total} social-response records "
            "({pct}) operate with negative monthly EBITDA per beneficiary under "
            "current funding."
        ),
        # by response / by region tabs
        "kpi_selectbox_label": "KPI",
        "distribution_title": "{kpi} — distribution by social response",
        "summary_stats_title": "Summary statistics",
        "median_by_concelho_title": "{kpi} — median by concelho",
        "region_x_response_title": "Region × social response (medians)",
        # institution explorer
        "institution_label": "Institution",
        "concelho_metric": "Concelho",
        "year_metric": "Year",
        "responses_metric": "Social responses",
        "avg_benef_metric": "Avg beneficiaries",
        "col_social_response": "Social response",
        "col_avg_users": "Avg users",
        "col_avg_staff": "Avg staff",
        "col_revenue_benef": "Revenue/benef.",
        "col_cost_benef": "Cost/benef.",
        "col_funding_benef": "SS funding/benef.",
        "col_ebitda_benef": "EBITDA/benef.",
        "col_coverage": "Coverage",
        "col_benef_worker": "Benef./worker",
        "download_institution_button": "Download this institution (CSV)",
        # data tab
        "kpi_table_title": "KPI table (filtered)",
        "raw_data_title": "Raw extracted data (all institutions)",
        # KPI labels
        "kpi_labels": {
            "monthly_revenue_per_beneficiary": "Monthly revenue / beneficiary (€)",
            "monthly_fee_per_beneficiary": "Monthly fee / beneficiary (€)",
            "monthly_social_security_funding_per_beneficiary": "Monthly SS funding / beneficiary (€)",
            "monthly_cost_per_beneficiary": "Monthly cost / beneficiary (€)",
            "monthly_ebitda_per_beneficiary": "Monthly EBITDA / beneficiary (€)",
            "monthly_revenue_per_worker": "Monthly revenue / worker (€)",
            "monthly_cost_per_worker": "Monthly cost / worker (€)",
            "monthly_labour_cost_per_worker": "Monthly labour cost / worker (€)",
            "beneficiary_worker_ratio": "Beneficiary / worker ratio",
            "funding_coverage": "SS funding coverage of cost (%)",
        },
        # chatbot
        "assistant_heading": "AI Assistant",
        "assistant_caption": (
            "Ask about the KPIs (respects the sidebar filters) or request "
            "negotiation talking points for the {target} funding-coverage goal."
        ),
        "assistant_missing_key": "Add ANTHROPIC_API_KEY to .streamlit/secrets.toml to enable the assistant.",
        "assistant_suggestions": [
            "Which social responses are below the {target} funding target, and by how much?",
            "Compare cost per beneficiary between Idosos and Infância.",
            "Draft 3 talking points for the Ministry negotiation.",
        ],
        "chat_input_placeholder": "Ask about the IPSS KPI data...",
        "chat_spinner": "Analyzing...",
        "chat_error": "Error calling the model: {error}",
        "download_conversation_button": "Download conversation (.txt)",
        "clear_conversation_button": "Clear conversation",
        "transcript_you": "You",
        "transcript_assistant": "Assistant",
        "transcript_header": "IPSS FINANCIAL OBSERVATORY - SESSION NOTES",
        "answer_language_instruction": "Answer in English, regardless of the question's language.",
    },
    "pt": {
        # sidebar
        "app_name": "Observatório IPSS",
        "app_subtitle": "Contas de gerência OCIP · KPIs por resposta social e região",
        "language_label": "Idioma",
        "filters_header": "Filtros",
        "funding_basis_label": "Base do financiamento SS",
        "funding_basis_options": [
            "Autoritativa (Comparticipações + Subsídios)",
            "Apenas linhas ISS,IP do Mapa A",
        ],
        "funding_basis_help": (
            "As linhas ISS,IP do Mapa A não captam o financiamento das instituições "
            "que o registam noutras rubricas (~metade da amostra). A base "
            "autoritativa usa a página de Comparticipações dedicada, recorrendo aos "
            "subsídios públicos apenas quando não há correspondência (notebook do "
            "pipeline, secção 7)."
        ),
        "year_label": "Ano",
        "institution_filter_label": "Instituição",
        "activity_group_label": "Grupo de atividade",
        "social_response_label": "Resposta social",
        "region_label": "Região (concelho)",
        "coverage_header": "Cobertura",
        "institutions_metric": "Instituições",
        "records_metric": "Registos por resposta social",
        "beneficiaries_metric": "Beneficiários (utentes médios)",
        "downloads_header": "Transferências",
        "kpi_csv_button": "Tabela de KPIs (CSV)",
        "raw_csv_button": "Dados brutos completos (CSV)",
        "footer_caption": "CNIS · Projeto de Grupo NLP · Porto Business School",
        "no_data_warning": "Nenhum registo corresponde aos filtros atuais.",
        "missing_outputs_error": (
            "Não foram encontrados os resultados dos KPIs. Execute primeiro "
            "`python pipeline.py data/PDF_files data/outputs`."
        ),
        # main title
        "main_title": "Observatório Financeiro das IPSS",
        "main_caption": (
            "Demonstrações de resultados por resposta social, extraídas dos OCIP "
            "submetidos. Referência de negociação: financiamento da Segurança "
            "Social ≥ {target} do custo total por beneficiário."
        ),
        # tabs
        "tab_overview": "Visão Geral",
        "tab_by_response": "Por Resposta Social",
        "tab_by_region": "Por Região",
        "tab_institution": "Explorador de Instituições",
        "tab_assistant": "Assistente IA",
        "tab_data": "Dados",
        # overview tab
        "median_cost_metric": "Custo mediano / beneficiário",
        "median_funding_metric": "Financiamento SS mediano / beneficiário",
        "median_coverage_metric": "Cobertura mediana do financiamento",
        "coverage_delta_suffix": "vs meta de {target}",
        "responses_above_target_metric": "Respostas com ≥{target} da meta",
        "median_ebitda_metric": "EBITDA mediano / beneficiário",
        "coverage_chart_title": "Cobertura do financiamento vs meta de {target}, por resposta social",
        "coverage_chart_caption": "Financiamento SS mediano como % do custo total por beneficiário. Linha de meta: {target}.",
        "cost_vs_funding_chart_title": "Custo vs financiamento por beneficiário, por grupo de atividade",
        "series_cost": "Custo",
        "series_funding": "Financiamento SS",
        "series_fees": "Comparticipação familiar",
        "deficit_flag": (
            "**Alerta de défice estrutural:** {n} de {total} registos por resposta "
            "social ({pct}) operam com EBITDA mensal negativo por beneficiário, "
            "face ao financiamento atual."
        ),
        # by response / by region tabs
        "kpi_selectbox_label": "KPI",
        "distribution_title": "{kpi} — distribuição por resposta social",
        "summary_stats_title": "Estatísticas resumo",
        "median_by_concelho_title": "{kpi} — mediana por concelho",
        "region_x_response_title": "Região × resposta social (medianas)",
        # institution explorer
        "institution_label": "Instituição",
        "concelho_metric": "Concelho",
        "year_metric": "Ano",
        "responses_metric": "Respostas sociais",
        "avg_benef_metric": "Beneficiários médios",
        "col_social_response": "Resposta social",
        "col_avg_users": "Utentes médios",
        "col_avg_staff": "Funcionários médios",
        "col_revenue_benef": "Receita/benef.",
        "col_cost_benef": "Custo/benef.",
        "col_funding_benef": "Financ. SS/benef.",
        "col_ebitda_benef": "EBITDA/benef.",
        "col_coverage": "Cobertura",
        "col_benef_worker": "Benef./trabalhador",
        "download_institution_button": "Transferir esta instituição (CSV)",
        # data tab
        "kpi_table_title": "Tabela de KPIs (filtrada)",
        "raw_data_title": "Dados brutos extraídos (todas as instituições)",
        # KPI labels
        "kpi_labels": {
            "monthly_revenue_per_beneficiary": "Receita mensal / beneficiário (€)",
            "monthly_fee_per_beneficiary": "Comparticipação mensal / beneficiário (€)",
            "monthly_social_security_funding_per_beneficiary": "Financiamento SS mensal / beneficiário (€)",
            "monthly_cost_per_beneficiary": "Custo mensal / beneficiário (€)",
            "monthly_ebitda_per_beneficiary": "EBITDA mensal / beneficiário (€)",
            "monthly_revenue_per_worker": "Receita mensal / trabalhador (€)",
            "monthly_cost_per_worker": "Custo mensal / trabalhador (€)",
            "monthly_labour_cost_per_worker": "Custo mensal com pessoal / trabalhador (€)",
            "beneficiary_worker_ratio": "Rácio beneficiários / trabalhador",
            "funding_coverage": "Cobertura do custo pelo financiamento SS (%)",
        },
        # chatbot
        "assistant_heading": "Assistente IA",
        "assistant_caption": (
            "Pergunte sobre os KPIs (respeita os filtros da barra lateral) ou peça "
            "argumentos de negociação para a meta de {target} de cobertura do "
            "financiamento."
        ),
        "assistant_missing_key": "Adicione ANTHROPIC_API_KEY a .streamlit/secrets.toml para ativar o assistente.",
        "assistant_suggestions": [
            "Quais respostas sociais estão abaixo da meta de financiamento de {target}, e por quanto?",
            "Compare o custo por beneficiário entre Idosos e Infância.",
            "Redija 3 argumentos para a negociação com o Ministério.",
        ],
        "chat_input_placeholder": "Pergunte sobre os dados de KPIs das IPSS...",
        "chat_spinner": "A analisar...",
        "chat_error": "Erro ao contactar o modelo: {error}",
        "download_conversation_button": "Transferir conversa (.txt)",
        "clear_conversation_button": "Limpar conversa",
        "transcript_you": "Você",
        "transcript_assistant": "Assistente",
        "transcript_header": "OBSERVATÓRIO FINANCEIRO DAS IPSS - NOTAS DA SESSÃO",
        "answer_language_instruction": "Responda em português europeu (pt-PT), independentemente da língua da pergunta.",
    },
}
