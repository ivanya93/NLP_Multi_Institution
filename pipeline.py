import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pdfplumber

try:
    import pytesseract
except ImportError:
    pytesseract = None
    warnings.warn(
        "pytesseract not installed - scanned PDFs (no text layer) will be "
        "skipped instead of OCR'd. Install with `pip install pytesseract`, "
        "and make sure the system OCR engine + Portuguese language pack are "
        "installed too (e.g. `apt-get install tesseract-ocr tesseract-ocr-por`)."
    )

pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 160)

PDF_FOLDER = Path("PDF_files")  # <-- folder containing all institution PDFs (any mix of years)

TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 3,
}

# OCR settings — only used for pages that have no text layer (scanned PDFs)
OCR_RESOLUTION = 300   # dpi - higher = more accurate but slower
OCR_LANG = "por"       # Portuguese Tesseract language pack


def normalize_pt_number(value_str):
    """Convert '1.234,56' / '-24,07' -> float. Returns np.nan if unparsable."""
    if value_str is None:
        return np.nan
    value_str = str(value_str).strip()
    if value_str == "":
        return np.nan
    negative = value_str.startswith("-")
    value_str = value_str.lstrip("-").replace(".", "").replace(",", ".")
    try:
        number = float(value_str)
    except ValueError:
        return np.nan
    return -number if negative else number


INSTITUTION_PATTERNS = {
    "ano": r"Ano:\s*(\d{4})",
    "nome_instituicao": r"Nome:\s*(.+)",              # first "Nome:" hit = institution
    "niss": r"NISS:\s*(\d+)",
    "concelho": r"Concelho:\s*(.+)",
}


def extract_institution_metadata(first_page_text):
    meta = {}
    for key, pattern in INSTITUTION_PATTERNS.items():
        match = re.search(pattern, first_page_text)
        meta[key] = match.group(1).strip() if match else None
    return meta


HEADER_PATTERNS = {
    "equipamento": r"Equipamento:\s*(.+)",
    "resposta_social": r"Resposta Social/Atividade:\s*(.+)",
    "n_medio_utentes": r"Nº Médio de Utentes:\s*([\d\.,]+)",
    "n_medio_funcionarios": r"Nº Médio de Funcionários:\s*([\d\.,]+)",
    "n_meses": r"Nº Meses:\s*(\d+)",
    "tipo_acordo": r"Tipo de Acordo:\s*(.+?)(?:\s{2,}|\n|$)",
}


def extract_header_metadata(text):
    header = {}
    for key, pattern in HEADER_PATTERNS.items():
        match = re.search(pattern, text)
        header[key] = match.group(1).strip() if match else None
    return header


def classify_page(text):
    """'beneficiary' (one Mapa A page per RS/Atividade), 'aggregate'
    (institution-wide Mapa A total), 'comparticipacoes' (authoritative ISS,IP
    funding per beneficiary), or 'other' (Balanço, Fluxos, etc.)."""
    if "Mapa Comparticipações ISS" in text:
        return "comparticipacoes"
    if "Número RS/Atividades agregadas" in text:
        return "aggregate"
    if "Resposta Social/Atividade:" in text:
        return "beneficiary"
    return "other"


def get_page_text(page):
    """Return (text, is_ocr) for a page: the native text layer if present,
    otherwise a whole-page OCR fallback (used for institution/header regex
    matching, where exact cell alignment doesn't matter)."""
    text = page.extract_text() or ""
    if text.strip() or pytesseract is None:
        return text, False
    image = page.to_image(resolution=OCR_RESOLUTION).original
    return pytesseract.image_to_string(image, lang=OCR_LANG), True


def get_page_tables(page, table_settings):
    """Return (tables, is_ocr) in the same list-of-rows-of-cells shape as
    page.extract_tables(). Falls back to per-cell OCR when the page has no
    text layer: cell boundaries still come from the page's real vector
    gridlines (via find_tables) - only the text inside each cell is filled
    in with Tesseract instead of pdfplumber's (empty) text extraction."""
    tables = page.extract_tables(table_settings=table_settings)
    has_text = any(cell for table in tables for row in table for cell in row if cell)
    if has_text or pytesseract is None:
        return tables, False

    found_tables = page.find_tables(table_settings=table_settings)
    if not found_tables:
        return [], False

    image = page.to_image(resolution=OCR_RESOLUTION).original
    scale = OCR_RESOLUTION / 72  # pdfplumber coordinates are in points (1/72")

    ocr_tables = []
    for table in found_tables:
        ocr_rows = []
        for row in table.rows:
            ocr_row = []
            for cell_bbox in row.cells:
                if cell_bbox is None:
                    ocr_row.append(None)
                    continue
                x0, top, x1, bottom = cell_bbox
                crop = image.crop((x0 * scale, top * scale, x1 * scale, bottom * scale))
                cell_text = pytesseract.image_to_string(
                    crop, lang=OCR_LANG, config="--psm 6"
                ).strip()
                ocr_row.append(cell_text or None)
            ocr_rows.append(ocr_row)
        ocr_tables.append(ocr_rows)
    return ocr_tables, True


def extract_income_statement(table):
    """Return {label: (value_year1, value_year2)} for one Mapa A table.

    Value columns are taken as the *last two* columns of the row rather than
    a hardcoded row[2]/row[3], because some pages (notably OCR'd scans where
    the NOTAS divider line isn't always detected) come back with 3 columns
    instead of the usual 4 (label, NOTAS, year1, year2). Taking the last two
    columns works for both layouts.
    """
    labels, values_year1, values_year2 = [], [], []
    for row in table[2:]:
        label_cell = row[0] if len(row) > 0 else None
        val1_cell = row[-2] if len(row) >= 2 else None
        val2_cell = row[-1] if len(row) >= 1 else None
        labels.extend(label_cell.split("\n") if label_cell else [])
        values_year1.extend(val1_cell.split("\n") if val1_cell else [])
        values_year2.extend(val2_cell.split("\n") if val2_cell else [])

    n = min(len(labels), len(values_year1), len(values_year2))
    if n < len(labels):
        warnings.warn(
            f"Label/value count mismatch (labels={len(labels)}, "
            f"values={len(values_year1)}) - truncating to shortest."
        )

    return {
        labels[i].strip(): (normalize_pt_number(values_year1[i]), normalize_pt_number(values_year2[i]))
        for i in range(n)
    }


def detect_column_years(table):
    """Best-effort read of the literal year labels (e.g. '2025', '2024')
    from a Mapa A table's header row. Returns (year_col0, year_col1) as
    strings, or (None, None) if they can't be confidently detected. Uses the
    last two columns, same reasoning as extract_income_statement."""
    if len(table) < 2:
        return None, None
    header_row = table[1]
    if len(header_row) < 2:
        return None, None
    y0 = (header_row[-2] or "").strip()
    y1 = (header_row[-1] or "").strip()
    if re.fullmatch(r"\d{4}", y0) and re.fullmatch(r"\d{4}", y1):
        return y0, y1
    return None, None


LINE_ITEMS = {
    "vendas": "Vendas",
    "servicos_prestados": "Serviços prestados",
    "servicos_prestados_particulares": "Serviços prestados - Particulares",
    "subsidios_publicos": "Subsídios, doações e legados à exploração",
    "iss_ip":"ISS, IP",
    "iss_ip_2": "ISS, IP – Apoios excecionais e extraordinários",
    "outros_rendimentos": "Outros rendimentos",
    "custo_mercadorias": "Custo das mercadorias vendidas e das matérias consumidas",
    "fse": "Fornecimentos e serviços externos",
    "gastos_pessoal": "Gastos com pessoal",
    "outros_gastos": "Outros gastos",
    "ebitda": "Resultado antes de depreciações, gastos de financiamento e impostos",
    # Kept for reference if needed for KPIs
    "depreciacao": "Gastos/reversões de depreciação e de amortização",
    "resultado_liquido": "Resultado líquido do período",
}


NUM_PT = r"-?[\d.]+,\d{2}"
COMPARTICIPACOES_ROW_RE = re.compile(
    rf"^(?P<equipamento>\S+)\s+(?P<name>.+?)\s+(?P<tipo>Atividade|Resposta Soc)\s+"
    rf"(?P<utentes>{NUM_PT})\s+(?P<funcionarios>{NUM_PT})\s+"
    rf"(?P<conta72>{NUM_PT})\s+(?P<conta751>{NUM_PT})\s+"
    rf"(?P<conta751_apoios>{NUM_PT})\s+(?P<ap78>{NUM_PT})\s+"
    rf"(?P<an68>{NUM_PT})\s+(?P<total>{NUM_PT})\s+"
    rf"(?P<resultado>{NUM_PT})\s+(?P<gasto>{NUM_PT})$"
)


def extract_comparticipacoes(text):
    """Regex-parse the 'Mapa Comparticipações ISS, IP' page into one dict per
    beneficiary row: {truncated_name: total_comparticipacao}."""
    rows = {}
    for line in text.splitlines():
        match = COMPARTICIPACOES_ROW_RE.match(line.strip())
        if match:
            rows[match.group("name").strip()] = normalize_pt_number(match.group("total"))
    return rows


def strip_code_prefix(resposta_social_name):
    """'1103 - CRECHE' -> 'CRECHE'; 'CANTINA SOCIAL' -> 'CANTINA SOCIAL'."""
    if resposta_social_name is None:
        return None
    return re.sub(r"^\d+\s*-\s*", "", resposta_social_name).strip().upper()


def match_comparticipacao(resposta_social_name, comparticipacoes_by_name):
    """Prefix-match a Mapa A beneficiary name against the (possibly truncated)
    names parsed from the Mapa Comparticipações page."""
    target = strip_code_prefix(resposta_social_name)
    if target is None:
        return np.nan, None

    matches = [
        (key, value) for key, value in comparticipacoes_by_name.items()
        if target.startswith(key.upper()) or key.upper().startswith(target)
    ]
    if len(matches) == 1:
        return matches[0][1], matches[0][0]
    if len(matches) > 1:
        warnings.warn(f"Ambiguous comparticipação match for '{resposta_social_name}': {matches}")
    return np.nan, None


ALLOWED_ACTIVITIES = [
    "ESTRUTURA RESIDENCIAL PARA PESSOAS IDOSAS",
    "SERVIÇO DE APOIO DOMICILIÁRIO",
    "CENTRO DE DIA",
    "CRECHE",
    "ESTABELECIMENTO DE EDUCAÇÃO PRÉ-ESCOLAR",
]

ACTIVITY_GROUP = {
    "ESTRUTURA RESIDENCIAL PARA PESSOAS IDOSAS": "Idosos",
    "SERVIÇO DE APOIO DOMICILIÁRIO": "Idosos",
    "CENTRO DE DIA": "Idosos",
    "CRECHE": "Infância",
    "ESTABELECIMENTO DE EDUCAÇÃO PRÉ-ESCOLAR": "Infância",
}


def matched_allowed_activity(resposta_social_name):
    """Return the canonical ALLOWED_ACTIVITIES entry this beneficiary matches,
    or None if it's outside the elderly-care/childcare scope."""
    name = strip_code_prefix(resposta_social_name)
    if name is None:
        return None
    for allowed in ALLOWED_ACTIVITIES:
        if allowed in name or name in allowed:
            return allowed
    return None


def is_allowed_activity(resposta_social_name):
    return matched_allowed_activity(resposta_social_name) is not None


def process_pdf(pdf_path):
    """Return (beneficiary_records, aggregate_record, institution_meta)
    for one institution's PDF."""

    beneficiary_records = []
    aggregate_record = None
    comparticipacoes_by_name = {}
    institution_meta = {"source_file": pdf_path.name}

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text, is_ocr_text = get_page_text(page)

            if page_number == 1:
                institution_meta.update(extract_institution_metadata(text))
                continue  # page 1 has no Mapa A table

            page_type = classify_page(text)

            if page_type == "comparticipacoes":
                comparticipacoes_by_name = extract_comparticipacoes(text)
                continue

            if page_type not in ("beneficiary", "aggregate"):
                continue

            tables, is_ocr_tables = get_page_tables(page, TABLE_SETTINGS)
            if not tables:
                continue

            pnl = extract_income_statement(tables[0])
            header = extract_header_metadata(text)

            # Sanity-check the assumed "col 0 = this filing's own year" order
            # now that 2024 (and other-year) filings are mixed in with 2025 ones.
            #year_col0, year_col1 = detect_column_years(tables[0])
            #if year_col0 and year_col0 != institution_meta.get("ano"):
                #warnings.warn(
                    #f"{pdf_path.name} p.{page_number}: table header shows "
                    #f"{year_col0}/{year_col1} but page 1 'Ano' is "
                    #f"{institution_meta.get('ano')} - check column order."
                #)

            record = {
                "source_file": pdf_path.name,
                "page": page_number,
                "resposta_social": header["resposta_social"],
                "equipamento": header["equipamento"],
                "tipo_acordo": header["tipo_acordo"],
                "n_medio_utentes": normalize_pt_number(header["n_medio_utentes"]),
                "n_medio_funcionarios": normalize_pt_number(header["n_medio_funcionarios"]),
                "n_meses": float(header["n_meses"]) if header["n_meses"] else 12.0,
                "is_ocr": is_ocr_text or is_ocr_tables,
            }
            for col, label in LINE_ITEMS.items():
                record[col] = pnl.get(label, (np.nan, np.nan))[0]  # index 0 = this filing's own year

            if page_type == "beneficiary":
                beneficiary_records.append(record)
            else:  # aggregate
                aggregate_record = record

    # Join authoritative ISS,IP funding onto each beneficiary via prefix matching.
    for record in beneficiary_records:
        funding, matched_key = match_comparticipacao(
            record["resposta_social"], comparticipacoes_by_name
        )
        record["ss_funding_authoritative"] = funding
        record["_comparticipacoes_matched_key"] = matched_key

    return beneficiary_records, aggregate_record, institution_meta


def validate_institution(beneficiary_records, aggregate_record, institution_name):
    if aggregate_record is None:
        print(f"  [{institution_name}] No aggregate page found - skipping validation.")
        return True

    mismatches = []
    for key in LINE_ITEMS:
        summed = sum(r.get(key) or 0 for r in beneficiary_records)
        reported = aggregate_record.get(key)
        if reported is not None and abs(summed - reported) > 0.01:
            mismatches.append((key, summed, reported))

    if mismatches:
        print(f"  ⚠ [{institution_name}] Mismatches vs aggregate page:")
        for key, summed, reported in mismatches:
            print(f"      {key}: sum={summed:.2f} vs aggregate={reported:.2f}")
        return False

    print(f"  ✓ [{institution_name}] Beneficiary sums match the aggregate page.")
    return True


def compute_kpis(df):
    df = df.copy()

    df["ss_funding"] = df["ss_funding_authoritative"].fillna(df["subsidios_publicos"])

    df["revenue"] = df["servicos_prestados"].fillna(0) + df["subsidios_publicos"].fillna(0) +df["vendas"].fillna(0) + df["outros_rendimentos"].fillna(0)
    df["total_cost"] = -(
        df["custo_mercadorias"].fillna(0)
        + df["fse"].fillna(0)
        + df["gastos_pessoal"].fillna(0)
        + df["outros_gastos"].fillna(0)
    )
    df["labour_cost"] = -df["gastos_pessoal"].fillna(0)

    df["monthly_revenue"] = df["revenue"] / df["n_meses"] 
    df["monthly_fee"] = df["servicos_prestados"] / df["n_meses"]
    df["monthly_social_security_funding"] = df["ss_funding"] / df["n_meses"]
    df["monthly_cost"] = df["total_cost"] / df["n_meses"]
    df["monthly_ebitda"] = df["ebitda"] / df["n_meses"] 
    df["monthly_labour_cost"] = df["labour_cost"] / df["n_meses"]

    df["monthly_revenue_per_beneficiary"] = df["monthly_revenue"] / df["n_medio_utentes"]
    df["monthly_fee_per_beneficiary"] = df["servicos_prestados_particulares"] / df["n_medio_utentes"] / df["n_meses"]
    df["monthly_social_security_funding_per_beneficiary"] = (df["iss_ip"] + df["iss_ip_2"]) / df["n_meses"] / df["n_medio_utentes"]
    df["monthly_cost_per_beneficiary"] = df["monthly_cost"] / df["n_medio_utentes"]
    df["monthly_ebitda_per_beneficiary"] = df["monthly_revenue_per_beneficiary"] - df["monthly_cost_per_beneficiary"]


    df["monthly_revenue_per_worker"] = df["monthly_revenue"] / df["n_medio_funcionarios"]
    df["monthly_cost_per_worker"] = df["monthly_cost"] / df["n_medio_funcionarios"]
    df["monthly_labour_cost_per_worker"] = df["monthly_labour_cost"] / df["n_medio_funcionarios"]

    df["beneficiary_worker_ratio"] = df["n_medio_utentes"] / df["n_medio_funcionarios"]
    df["ss_funding_cost_coverage_ratio"] = df["monthly_social_security_funding"] / df["monthly_cost_per_beneficiary"]

    return df


KPI_COLS = [
    "institution_id", "ano", "resposta_social", "activity_group",
    "n_medio_utentes", "n_medio_funcionarios",
    "monthly_revenue_per_beneficiary", "monthly_fee_per_beneficiary",
    "monthly_social_security_funding_per_beneficiary", "monthly_cost_per_beneficiary","monthly_ebitda_per_beneficiary",
    "monthly_revenue_per_worker", "monthly_cost_per_worker", "monthly_labour_cost_per_worker",
    "beneficiary_worker_ratio", "ss_funding_cost_coverage_ratio",
    
]


def run_batch(pdf_folder):
    pdf_paths = sorted(Path(pdf_folder).glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"No PDFs found in {pdf_folder}")

    all_beneficiary_rows = []
    validation_results = {}
    print(f"Found {len(pdf_paths)} PDF(s) to process.\n")

    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path.name} ...")
        beneficiary_records, aggregate_record, institution_meta = process_pdf(pdf_path)

        institution_name = institution_meta.get("nome_instituicao") or pdf_path.name
        validation_results[institution_name] = validate_institution(
            beneficiary_records, aggregate_record, institution_name
        )

        for record in beneficiary_records:
            record.update({
                "niss": institution_meta.get("niss"),
                "nome_instituicao": institution_meta.get("nome_instituicao"),
                "concelho": institution_meta.get("concelho"),
                "centro_distrital": institution_meta.get("centro_distrital"),
                "ano": institution_meta.get("ano"),
            })
            all_beneficiary_rows.append(record)

        print(f"  -> {len(beneficiary_records)} beneficiaries parsed "
              f"(validation above runs on ALL activities, before filtering).\n")

    combined = pd.DataFrame(all_beneficiary_rows)

    # Keep only elderly-care (ERPI/SAD/Centro de Dia) and childcare
    # (Creche/Pré-Escolar) beneficiaries. Filtering happens *after*
    # validate_institution() so the aggregate-page cross-check still runs
    # against each institution's complete, unfiltered set of activities.
    n_before = len(combined)
    combined["activity_group"] = combined["resposta_social"].apply(
        lambda name: ACTIVITY_GROUP.get(matched_allowed_activity(name))
    )
    combined = combined[combined["resposta_social"].apply(is_allowed_activity)].reset_index(drop=True)
    print(f"Kept {len(combined)}/{n_before} beneficiary rows after the "
          f"elderly-care/childcare activity filter.\n")

    kpi_df = compute_kpis(combined)
    return combined, kpi_df, validation_results
import hashlib

def anonymize_institutions(df, niss_col="niss", name_col="nome_instituicao"):
    """Replace NISS + institution name with a stable pseudonymous ID.
    Same institution -> same ID across runs (derived from NISS hash),
    but the original NISS/name are not retained in the output."""
    df = df.copy()

    def pseudo_id(niss):
        if pd.isna(niss):
            return "INST_UNKNOWN"
        digest = hashlib.sha256(str(niss).encode()).hexdigest()[:8]
        return f"INST_{digest}"

    df["institution_id"] = df[niss_col].apply(pseudo_id)
    df = df.drop(columns=[niss_col, name_col])
    return df


# ---------------------------------------------------------------------------
# Module driver: run the full pipeline and save outputs for the Streamlit app
# ---------------------------------------------------------------------------

def run(pdf_folder, out_dir=None):
    """Run the full pipeline over `pdf_folder`.

    Returns (raw_df, kpi_df, kpi_table, validation_results), anonymized.
    If `out_dir` is given, saves raw_df.csv and kpi_table.csv there.
    """
    raw_df, kpi_df, validation_results = run_batch(pdf_folder)
    raw_df = anonymize_institutions(raw_df)
    kpi_df = anonymize_institutions(kpi_df)
    kpi_table = kpi_df[KPI_COLS + ["concelho"]].round(2)

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_df.to_csv(out_dir / "raw_df.csv", index=False)
        kpi_df.round(2).to_csv(out_dir / "kpi_df.csv", index=False)
        kpi_table.to_csv(out_dir / "kpi_table.csv", index=False)
        print(f"Saved raw_df.csv, kpi_df.csv, kpi_table.csv to {out_dir}")

    return raw_df, kpi_df, kpi_table, validation_results


if __name__ == "__main__":
    import sys
    pdf_folder = sys.argv[1] if len(sys.argv) > 1 else "data/PDF_files"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "data/outputs"
    run(pdf_folder, out_dir)
