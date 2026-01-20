import streamlit as st

import database
import constants as C
import services
from ui_components import render_template_list, render_template_single
from utils import reset_conversion, rules_to_dataframe, dataframe_to_rules, load_data, load_data_v2, to_excel_bytes


# --- Init DB and session cache ---
database.init_db()
#DB연결하고 테이블 없으면 생성하기 (templated,mappings)


def load_config_to_session():
    templates = database.load_templates()
    mappings = database.load_mappings()
    #templates와 mappings는 각 속성을 타입으로 가짐. 타입에는 그 타입에 해당하는 탬플릿 또는 매핑이 배열로써 할당되엉 있음.
    st.session_state['templates'] = templates
    st.session_state['mappings'] = mappings
    _ensure_active_templates(templates)


def _ensure_active_templates(templates):
    st.session_state.setdefault("active_templates", {})
    for template_type, template_list in templates.items():
        if not template_list:
            continue
        active_id = st.session_state["active_templates"].get(template_type)
        ids = [t["id"] for t in template_list]
        if active_id not in ids: #일단 왜 각 타입의 배열의 첫 번쨰 값의 id를 세션에 각 타입에 저장하는지 모르겠음.
            st.session_state["active_templates"][template_type] = template_list[0]["id"]


def get_templates(template_type):
    return st.session_state.get("templates", {}).get(template_type, [])


def get_active_template(template_type):
    templates = get_templates(template_type)
    if not templates:
        return None
    active_id = st.session_state.get("active_templates", {}).get(template_type)
    for tmpl in templates:
        if tmpl["id"] == active_id:
            return tmpl
    return templates[0]


def _sources_match(a, b):
    return sorted(a or []) == sorted(b or [])


def get_mapping_rules(mapping_type, target_template_id=None, source_template_ids=None):
    mappings = st.session_state.get("mappings", {}).get(mapping_type, [])
    if target_template_id is None and source_template_ids is None:
        return mappings[0]["rules"] if mappings else None
    for mapping in mappings:
        if target_template_id is not None and mapping.get("target_template_id") != target_template_id:
            continue
        if source_template_ids is None or _sources_match(mapping.get("sources"), source_template_ids):
            return mapping["rules"]
    return None


def upsert_mapping_state(mapping_type, target_template_id, source_template_ids, rules):
    mappings = st.session_state.setdefault("mappings", {}).setdefault(mapping_type, [])
    for mapping in mappings:
        if mapping["target_template_id"] == target_template_id and _sources_match(mapping.get("sources"), source_template_ids):
            mapping["rules"] = rules
            mapping["sources"] = list(source_template_ids or [])
            return
    mappings.append(
        {
            "mapping_type": mapping_type,
            "target_template_id": target_template_id,
            "sources": list(source_template_ids or []),
            "rules": rules,
        }
    )


load_config_to_session()


# --- Streamlit UI ---
st.set_page_config(page_title=C.PAGE_TITLE, layout="wide")
st.title(C.MAIN_TITLE)

page_run, page_setup = st.tabs([C.TAB_RUN, C.TAB_SETUP])


# =========================
# Run Tab
# =========================
with page_run:
    st.sidebar.button("Reload DB", on_click=load_config_to_session)
    tab_invoice, tab_bulk = st.tabs(["1. Order -> Invoice", "2. Order + Export -> Bulk"])

    # --- Order -> Invoice ---
    with tab_invoice:
        order_templates = get_templates(C.TPL_TYPE_ORDER)
        invoice_templates = get_templates(C.TPL_TYPE_INVOICE)

        if not order_templates:
            st.error("Register order templates first.")
        elif not invoice_templates:
            st.error("Register invoice template first.")
        else:
            sel_order = st.selectbox("Select order template", order_templates, format_func=lambda t: t["name"], key="run_order_tpl")
            sel_invoice = st.selectbox("Select invoice template", invoice_templates, format_func=lambda t: t["name"], key="run_invoice_tpl")

            rules = get_mapping_rules(C.MAP_ORDER_TO_INVOICE, target_template_id=sel_invoice["id"], source_template_ids=[sel_order["id"]])
            if not rules:
                st.error("Save mapping rules first.")
            else:
                saved_row_idx = sel_order.get("header_row_idx", 0)
                st.caption(f"Order header row: {saved_row_idx + 1}")

                up_file = st.file_uploader("Upload order file", key="run_order_file", on_change=reset_conversion)
                if up_file:
                    df = load_data(up_file, header_row_idx=saved_row_idx)
                    if df is not None:
                        if st.button("Run conversion", type="primary"):
                            with st.spinner("Processing..."):
                                results = services.process_all_conversions(df, rules, sel_invoice.get("headers", []))
                                st.session_state.conversion_result = results
                                st.success("Done")

                        if "conversion_result" in st.session_state:
                            results = st.session_state.conversion_result
                            st.markdown("### Order file (normalized)")
                            st.dataframe(results["order"].head(3), use_container_width=True)
                            st.download_button(
                                label="Download order",
                                data=to_excel_bytes(results["order"]),
                                file_name="order_normalized.xlsx",
                                use_container_width=True,
                                key="dl_order_norm",
                            )

                            st.divider()
                            st.markdown("### Invoice results")
                            for name, df_res in results["invoice"].items():
                                st.success(f"{name} ({len(df_res)} rows)")
                                st.dataframe(df_res.head(3), use_container_width=True)
                                st.download_button(
                                    f"Download {name}",
                                    data=to_excel_bytes(df_res),
                                    file_name=f"invoice_{name}.xlsx",
                                    key=f"dl_inv_{name}",
                                    use_container_width=True,
                                )

    # --- Order + Export -> Bulk ---
    with tab_bulk:
        tmpl_order = get_active_template(C.TPL_TYPE_ORDER)
        tmpl_export = get_active_template(C.TPL_TYPE_EXPORT)
        tmpl_bulk = get_active_template(C.TPL_TYPE_BULK)

        if not tmpl_order or not tmpl_export:
            st.error("Register order/export templates first.")
        elif not tmpl_bulk:
            st.error("Register bulk template first.")
        else:
            match_rules = get_mapping_rules(C.MAP_BULK_MATCH, target_template_id=tmpl_export["id"], source_template_ids=[tmpl_order["id"], tmpl_export["id"]])
            bulk_rules = get_mapping_rules(C.MAP_BULK_MAPPING, target_template_id=tmpl_bulk["id"], source_template_ids=[tmpl_order["id"]])

            if not match_rules:
                st.error("Save bulk match rules first.")
            elif not bulk_rules:
                st.error("Save bulk mapping rules first.")
            else:
                h1 = tmpl_order.get("header_row_idx", 0)
                h2 = tmpl_export.get("header_row_idx", 0)
                st.caption(f"Header rows: order({h1+1}), export({h2+1})")

                c1, c2 = st.columns(2)
                with c1:
                    up_erp = st.file_uploader("Order file", key="bulk_order")
                with c2:
                    up_inv = st.file_uploader("Export file", key="bulk_export")

                if up_erp and up_inv:
                    df_e = load_data(up_erp, header_row_idx=h1)
                    df_i = load_data_v2(up_inv, is_merged=True)
                    if df_e is not None and df_i is not None:
                        if st.button("Run bulk conversion"):
                            final_df = services.convert_to_bulk_upload(
                                df_e,
                                df_i,
                                match_rules,
                                bulk_rules,
                                tmpl_bulk.get("headers", []),
                            )
                            if final_df is not None:
                                st.success(f"Done ({len(final_df)} rows)")
                                st.dataframe(final_df.head(), use_container_width=True)
                                st.download_button(
                                    "Download bulk upload",
                                    data=to_excel_bytes(final_df),
                                    file_name="bulk_upload.xlsx",
                                )


# =========================
# Setup Tab
# =========================
with page_setup:
    st.warning("Settings are stored in the local DB.")
    tab_templates, tab_mapping_invoice, tab_mapping_bulk = st.tabs([
        C.SETUP_TAB_TEMPLATES,
        C.SETUP_TAB_MAPPING_INVOICE,
        C.SETUP_TAB_MAPPING_BULK,
    ])

    # --- Templates ---
    with tab_templates:
        render_template_list(C.TPL_TYPE_ORDER, "Order template")

        st.subheader("Invoice template (single)")
        render_template_single(C.TPL_TYPE_INVOICE, "Invoice template")

        st.subheader("Export template (single)")
        render_template_single(C.TPL_TYPE_EXPORT, "Export template")

        st.subheader("Bulk upload templates (multiple)")
        render_template_list(C.TPL_TYPE_BULK, "Bulk template")

    # --- Order -> Invoice mapping ---
    with tab_mapping_invoice:
        src_template = get_active_template(C.TPL_TYPE_ORDER)
        tgt_template = get_active_template(C.TPL_TYPE_INVOICE)

        src_headers = src_template.get("headers", []) if src_template else []
        tgt_headers = tgt_template.get("headers", []) if tgt_template else []

        if not src_template or not tgt_template:
            st.error("Register order/invoice templates first.")
        elif not src_headers or not tgt_headers:
            st.error("Template headers are empty. Re-save templates.")
        else:
            st.caption(f"Using templates: order[{src_template['name']}], invoice[{tgt_template['name']}]")
            with st.form("map_invoice_form"):
                current_rules = get_mapping_rules(C.MAP_ORDER_TO_INVOICE, target_template_id=tgt_template["id"], source_template_ids=[src_template["id"]]) or {}
                current_map = current_rules.get("simple_map", [])

                new_simple_map_list = []
                for i, t_col in enumerate(tgt_headers):
                    if t_col in [C.ROSEN_DELIVERY_FEE_COL, C.ROSEN_FEE_TYPE_COL]:
                        st.text_input(
                            f"{i+1}. {t_col} (fixed)",
                            value=str(C.ROSEN_SHIPPING_COST) if t_col == C.ROSEN_DELIVERY_FEE_COL else C.ROSEN_COST_TYPE,
                            disabled=True,
                            key=f"fixed_{i}",
                        )
                        new_simple_map_list.append({"target": t_col, "source": "__FIXED_VALUE__"})
                        continue

                    prev_val = C.NOT_SELECTED
                    if isinstance(current_map, list) and i < len(current_map):
                        prev_val = current_map[i].get("source", C.NOT_SELECTED)

                    options = [C.NOT_SELECTED] + src_headers
                    idx = options.index(prev_val) if prev_val in options else 0

                    val = st.selectbox(
                        f"{i+1}. Invoice [{t_col}] <- Order column",
                        options,
                        index=idx,
                        key=f"rm_{i}_{t_col}",
                    )
                    new_simple_map_list.append({"target": t_col, "source": val})

                split_options = [C.NOT_SELECTED] + src_headers
                prev_split = current_rules.get("split_col", C.NOT_SELECTED)
                split_idx = split_options.index(prev_split) if prev_split in split_options else 0
                split_col = st.selectbox("Mall classifier column (optional)", split_options, index=split_idx)

                if st.form_submit_button("Save mapping"):
                    full_rule = {"simple_map": new_simple_map_list, "split_col": split_col}
                    database.save_mapping(C.MAP_ORDER_TO_INVOICE, tgt_template["id"], [src_template["id"]], full_rule)
                    upsert_mapping_state(C.MAP_ORDER_TO_INVOICE, tgt_template["id"], [src_template["id"]], full_rule)
                    st.success("Saved")
                    st.rerun()

    # --- Bulk mapping ---
    with tab_mapping_bulk:
        sub_match, sub_mapping = st.tabs(["A. Order/Export match", "B. Bulk column mapping"])

        with sub_match:
            tmpl_order = get_active_template(C.TPL_TYPE_ORDER)
            tmpl_export = get_active_template(C.TPL_TYPE_EXPORT)
            order_cols = tmpl_order.get("headers", []) if tmpl_order else []
            export_cols = tmpl_export.get("headers", []) if tmpl_export else []

            if not order_cols or not export_cols:
                st.error("Register order/export templates first.")
            else:
                with st.form("bulk_match_form"):
                    saved_match = get_mapping_rules(C.MAP_BULK_MATCH, target_template_id=tmpl_export["id"], source_template_ids=[tmpl_order["id"], tmpl_export["id"]]) or {}
                    curr_match = saved_match.get("match_columns", {})

                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("Order template")
                    with c2:
                        st.write("Export template")

                    selected_values = {}
                    bulk_mapping_fields = C.get_bulk_mapping_fields(saved_match)

                    for field in bulk_mapping_fields:
                        e_key = f"ecount_{field.id}"
                        i_key = f"invoice_{field.id}"

                        e_idx = order_cols.index(curr_match.get(e_key)) if curr_match.get(e_key) in order_cols else 0
                        selected_values[e_key] = c1.selectbox(
                            field.label_e,
                            order_cols,
                            index=e_idx,
                            key=f"bulk_{field.id}_ecount",
                        )

                        i_idx = export_cols.index(curr_match.get(i_key)) if curr_match.get(i_key) in export_cols else 0
                        selected_values[i_key] = c2.selectbox(
                            field.label_i,
                            export_cols,
                            index=i_idx,
                            key=f"bulk_{field.id}_invoice",
                        )

                    if st.form_submit_button("Save match"):
                        full_cfg = {"match_columns": selected_values}
                        database.save_mapping(C.MAP_BULK_MATCH, tmpl_export["id"], [tmpl_order["id"], tmpl_export["id"]], full_cfg)
                        upsert_mapping_state(C.MAP_BULK_MATCH, tmpl_export["id"], [tmpl_order["id"], tmpl_export["id"]], full_cfg)
                        st.success("Saved")
                        st.rerun()

        with sub_mapping:
            tmpl_order = get_active_template(C.TPL_TYPE_ORDER)
            tmpl_bulk = get_active_template(C.TPL_TYPE_BULK)

            if not tmpl_order or not tmpl_bulk:
                st.error("Register order/bulk templates first.")
            else:
                with st.form("bulk_mapping_form"):
                    saved_cfg = get_mapping_rules(C.MAP_BULK_MAPPING, target_template_id=tmpl_bulk["id"], source_template_ids=[tmpl_order["id"]]) or {}

                    curr_rules = saved_cfg.get("transform", {}).get("rules", {})
                    df_rules = rules_to_dataframe(curr_rules, C.DEFAULT_MALL_RULES)

                    edited_df = st.data_editor(
                        df_rules,
                        column_config={
                            "\ubab0\ucf54\ub4dc": st.column_config.TextColumn("Mall code", required=True),
                            "\ucd9c\uace0\uc9c0\ucf54\ub4dc": st.column_config.TextColumn("Warehouse code", required=True),
                        },
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        key="editor_rules",
                    )

                    if st.form_submit_button("Save bulk mapping"):
                        rule_dict = dataframe_to_rules(edited_df)
                        full_cfg = {
                            "transform": {
                                "source_col": "\ubab0\ucf54\ub4dc",
                                "rules": rule_dict,
                            }
                        }
                        database.save_mapping(C.MAP_BULK_MAPPING, tmpl_bulk["id"], [tmpl_order["id"]], full_cfg)
                        upsert_mapping_state(C.MAP_BULK_MAPPING, tmpl_bulk["id"], [tmpl_order["id"]], full_cfg)
                        st.success("Saved")
                        st.rerun()
