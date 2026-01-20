import pandas as pd
import streamlit as st
import constants as C
import utils as U

NAVER = "\ub124\uc774\ubc84"
KAKAO = "\uce74\uce74\uc624"
COUPANG = "\ucfe0\ud321"
BULK_CODE_COL = "\ucd9c\uace0\uc9c0\ucf54\ub4dc"


def modify_order_file(df):
    return df.copy()


def process_all_conversions(order_df, mapping_rules, target_headers):
    order_norm = modify_order_file(order_df)
    invoice_outputs = convert_to_invoice(order_df, mapping_rules, target_headers)
    return {
        "order": order_norm,
        "invoice": invoice_outputs,
    }


def _fixed_value_for_target(target_col):
    if target_col == C.ROSEN_DELIVERY_FEE_COL:
        return C.ROSEN_SHIPPING_COST
    if target_col == C.ROSEN_FEE_TYPE_COL:
        return C.ROSEN_COST_TYPE
    return ""


def convert_to_invoice(df_data, mapping_rules, target_headers):
    simple_map_list = mapping_rules.get("simple_map", []) if mapping_rules else []
    if not simple_map_list:
        st.warning("Save invoice mapping rules first.")
        return {"single_file": pd.DataFrame(columns=target_headers)}

    series_by_col = {}
    for target in target_headers:
        rule = next((r for r in simple_map_list if r.get("target") == target), None)
        if not rule:
            series_by_col[target] = pd.Series([""] * len(df_data))
            continue

        source_col = rule.get("source")
        if source_col == "__FIXED_VALUE__":
            val = _fixed_value_for_target(target)
            series_by_col[target] = pd.Series([val] * len(df_data))
        elif source_col and source_col != C.NOT_SELECTED and source_col in df_data.columns:
            series_by_col[target] = df_data[source_col].fillna("").astype(str)
        else:
            series_by_col[target] = pd.Series([""] * len(df_data))

    out = pd.DataFrame(series_by_col)

    split_col = mapping_rules.get("split_col") if mapping_rules else None
    if split_col and split_col in df_data.columns:
        mask_naver = df_data[split_col].astype(str).str.contains(NAVER, na=False)
        mask_kakao = df_data[split_col].astype(str).str.contains(KAKAO, na=False)
        mask_coupang = df_data[split_col].astype(str).str.contains(COUPANG, na=False)
        return {
            "naver": out[mask_naver],
            "kakao": out[mask_kakao],
            "coupang": out[mask_coupang],
        }

    return {"single_file": out}


def convert_to_bulk_upload(order_df, export_df, match_rules, bulk_rules, bulk_template_headers):
    def get_merged_col(df, col_base, suffix=""):
        if col_base in df.columns:
            return col_base
        if suffix and f"{col_base}{suffix}" in df.columns:
            return f"{col_base}{suffix}"
        return None

    cols_cfg = match_rules.get("match_columns", {}) if match_rules else {}
    transform = bulk_rules.get("transform", {}) if bulk_rules else {}

    def build_key(row, prefix):
        parts = []
        for field in ["name", "address", "contact_mobile", "item", "msg"]:
            col = cols_cfg.get(f"{prefix}_{field}")
            parts.append(U.clean_text(str(row[col])) if col in row else "")
        return "_".join(parts)

    if cols_cfg:
        order_df['__MATCH_KEY__'] = order_df.apply(lambda r: build_key(r, "ecount"), axis=1)
        export_df['__MATCH_KEY__'] = export_df.apply(lambda r: build_key(r, "invoice"), axis=1)
    else:
        st.warning("Bulk match rules are empty.")
        return None

    merged = pd.merge(order_df, export_df, on='__MATCH_KEY__', how='left', suffixes=('_erp', '_inv'))

    out = pd.DataFrame()
    for header in bulk_template_headers:
        col = get_merged_col(merged, header) or get_merged_col(merged, header, suffix="_erp") or get_merged_col(merged, header, suffix="_inv")
        out[header] = merged[col] if col else ""

    src_col_name = transform.get('source_col')
    rules = transform.get('rules', {})
    if src_col_name:
        src_col = get_merged_col(merged, src_col_name) or get_merged_col(merged, src_col_name, suffix="_erp") or get_merged_col(merged, src_col_name, suffix="_inv")
        if src_col and BULK_CODE_COL in out.columns:
            out[BULK_CODE_COL] = merged[src_col].map(rules).fillna("")

    return out
