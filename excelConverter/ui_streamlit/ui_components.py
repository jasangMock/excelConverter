import streamlit as st
import database
from utils import load_headers, load_data_merged_header


def render_template_manager(template_type, label_text):
    """
    Template manager UI per template type.
    """
    if "active_templates" not in st.session_state:
        st.session_state.active_templates = {}

    templates_for_type = st.session_state.templates.get(template_type, {})
    template_names = sorted(templates_for_type.keys())

    if template_names:
        selected_name = st.selectbox(
            f"{label_text} 템플릿 선택",
            template_names,
            key=f"select_{template_type}",
        )
        st.session_state.active_templates[template_type] = selected_name
        selected_template = templates_for_type[selected_name]

        st.info(f"✅ '{label_text}' 템플릿이 설정되어 있습니다.")
        with st.expander("헤더 보기"):
            st.write(selected_template.get("headers", []))

        if st.button(
            f"🗑️ '{label_text}' 템플릿 삭제",
            key=f"del_{template_type}_{selected_template['id']}",
        ):
            database.delete_template(selected_template["id"])
            del st.session_state.templates[template_type][selected_name]
            if not st.session_state.templates[template_type]:
                del st.session_state.templates[template_type]
            if st.session_state.active_templates.get(template_type) == selected_name:
                st.session_state.active_templates.pop(template_type, None)
            st.rerun()
    else:
        st.warning(f"⚠️ '{label_text}' 템플릿이 없습니다. 아래에서 새로 등록하세요.")

    st.divider()
    st.subheader(f"{label_text} 템플릿 추가")

    template_name = st.text_input(
        "템플릿 이름",
        value="default",
        key=f"name_{template_type}",
    ).strip()

    row_idx = st.number_input(
        f"'{label_text}' 헤더 행 번호 (1부터)",
        min_value=1,
        value=1,
        key=f"row_{template_type}",
    ) - 1

    uploaded_file = st.file_uploader(
        f"{label_text} 파일 업로드",
        key=f"up_{template_type}",
    )

    if uploaded_file:
        pwd = st.text_input(
            "엑셀 비밀번호 (필요 시)",
            type="password",
            key=f"pwd_{template_type}",
        )

        headers = []
        if template_type == "export":
            df_temp = load_data_merged_header(uploaded_file, start_row_idx=row_idx)
            if df_temp is not None:
                headers = df_temp.columns.tolist()
        else:
            headers = load_headers(uploaded_file, header_row_idx=row_idx, password=pwd)

        if headers:
            st.write(f"헤더 ({len(headers)}개):", headers)

            if st.button("✅ 템플릿 저장", key=f"save_{template_type}"):
                if not template_name:
                    st.error("템플릿 이름을 입력하세요.")
                    return

                template_id = database.save_template(
                    template_type,
                    template_name,
                    headers,
                    row_idx,
                )

                new_template = {
                    "id": template_id,
                    "name": template_name,
                    "type": template_type,
                    "headers": headers,
                    "header_row_idx": row_idx,
                }

                st.session_state.templates.setdefault(template_type, {})[template_name] = new_template
                st.session_state.active_templates[template_type] = template_name

                st.success("템플릿 저장 완료")
                st.rerun()
