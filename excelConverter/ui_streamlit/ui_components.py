import streamlit as st
import database
from utils import load_headers, load_data_merged_header


def _set_active_template(template_type, template_id):
    st.session_state.setdefault("active_templates", {})[template_type] = template_id


def _get_templates(template_type):
    return st.session_state.get("templates", {}).get(template_type, [])


def render_template_list(template_type, label_text):
    templates_for_type = _get_templates(template_type)
    template_names = {tmpl["name"]: tmpl for tmpl in templates_for_type}

    st.subheader(f"{label_text} list")
    if template_names:
        name_list = sorted(template_names.keys())
        selected_name = st.selectbox(f"Select {label_text}", name_list, key=f"sel_{template_type}")
        selected_template = template_names[selected_name]
        _set_active_template(template_type, selected_template["id"])

        st.caption(f"Headers: {len(selected_template.get('headers', []))}, starts at row {selected_template.get('header_row_idx', 0)+1}")
        with st.expander("Saved headers"):
            st.write(selected_template.get("headers", []))

        if st.button("Delete selected", key=f"del_{template_type}_{selected_template['id']}"):
            database.delete_template(selected_template["id"])
            st.session_state["templates"][template_type] = [t for t in templates_for_type if t["id"] != selected_template["id"]]
            st.session_state["active_templates"].pop(template_type, None)
            st.rerun()
    else:
        st.info("No templates found. Add one below.")

    _render_template_form(template_type, label_text, allow_multiple=True)


def render_template_single(template_type, label_text):
    templates_for_type = _get_templates(template_type)
    st.subheader(f"{label_text} single")

    if templates_for_type:
        selected = templates_for_type[0]
        _set_active_template(template_type, selected["id"])
        st.caption(f"Current: {selected['name']} (headers {len(selected.get('headers', []))})")
        with st.expander("Saved headers"):
            st.write(selected.get("headers", []))
        if st.button("Delete current", key=f"del_{template_type}_{selected['id']}"):
            database.delete_template(selected["id"])
            st.session_state["templates"][template_type] = []
            st.session_state["active_templates"].pop(template_type, None)
            st.rerun()
    else:
        st.info("No template registered. Add one below.")

    _render_template_form(template_type, label_text, allow_multiple=False)


def _render_template_form(template_type, label_text, allow_multiple):
    st.divider()
    st.write(f"Add {label_text}")

    template_name = st.text_input("Template name", value="default", key=f"name_{template_type}").strip()
    row_idx = st.number_input("Header start row (1-base)", min_value=1, value=1, key=f"row_{template_type}") - 1
    uploaded_file = st.file_uploader(f"Upload sample for {label_text}", key=f"up_{template_type}")

    headers = []
    if uploaded_file:
        pwd = st.text_input("Password (if needed)", type="password", key=f"pwd_{template_type}")
        if template_type == "export":
            df_temp = load_data_merged_header(uploaded_file, start_row_idx=row_idx)
            if df_temp is not None:
                headers = df_temp.columns.tolist()
        else:
            headers = load_headers(uploaded_file, header_row_idx=row_idx, password=pwd) or []

    if headers:
        st.write(f"Detected headers ({len(headers)}):", headers)
        if st.button("Save", key=f"save_{template_type}"):
            if not template_name:
                st.error("Template name is required.")
                return

            template_id = database.save_template(template_name, template_type, headers, row_idx)

            new_template = {
                "id": template_id,
                "name": template_name,
                "type": template_type,
                "headers": headers,
                "header_row_idx": row_idx,
            }

            tmpl_list = st.session_state.setdefault("templates", {}).setdefault(template_type, [])
            if not allow_multiple:
                tmpl_list.clear()
            tmpl_list.append(new_template)
            _set_active_template(template_type, template_id)

            st.success("Saved")
            st.rerun()
