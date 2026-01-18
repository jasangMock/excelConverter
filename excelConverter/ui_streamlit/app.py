import database 
import os
import streamlit as st          # 화면에 에러나 경고를 띄우기 위해 필요
from ui_components import render_template_manager # UI 컴포넌트 함수 가져오기
import constants as C  # 상수 파일 가져오기
from utils import reset_conversion, rules_to_dataframe, dataframe_to_rules, load_data, load_data_v2,to_excel_bytes  # 유틸리티 함수 임포트
import services  # 핵심 로직이 담긴 서비스 모듈 임포트


# --- 0. DB 초기화 및 설정 로드 ---
database.init_db()

# 현재 파이썬이 실행되는 위치(작업 디렉토리) 출력
print("현재 파이썬 작업 경로:", os.getcwd())
# 파이썬이 바라보는 DB 파일의 절대 경로 출력
print("파이썬이 여는 DB 경로:", os.path.abspath('Excel_converter.db'))


def load_config_to_session():
    templates, mappings = database.load_all_config_from_db()
    print("Loaded templates from DB:", templates)
    print("")
    print("Loaded mappings from DB:", mappings)
    print("")
    st.session_state['templates'] = templates
    st.session_state['mappings'] = mappings
    _ensure_active_templates(templates)


def _ensure_active_templates(templates):
    if "active_templates" not in st.session_state:
        st.session_state["active_templates"] = {}
    for template_type, template_map in templates.items():
        if not template_map:
            continue
        if st.session_state["active_templates"].get(template_type) not in template_map:
            st.session_state["active_templates"][template_type] = next(iter(template_map.keys()))


def get_active_template(template_type):
    templates = st.session_state.get("templates", {}).get(template_type, {})
    if not templates:
        return None
    active_name = st.session_state.get("active_templates", {}).get(template_type)
    if active_name in templates:
        return templates[active_name]
    return next(iter(templates.values()))


def get_mapping_rules(mapping_type, source_template_id=None, target_template_id=None):
    mappings = st.session_state.get("mappings", {}).get(mapping_type, [])
    if source_template_id is None and target_template_id is None:
        return mappings[0]["rules"] if mappings else None
    for mapping in mappings:
        if mapping["source_template_id"] == source_template_id and mapping["target_template_id"] == target_template_id:
            return mapping["rules"]
    return None


def upsert_mapping_state(mapping_type, source_template_id, target_template_id, rules):
    mappings = st.session_state.mappings.setdefault(mapping_type, [])
    for mapping in mappings:
        if mapping["source_template_id"] == source_template_id and mapping["target_template_id"] == target_template_id:
            mapping["rules"] = rules
            return
    mappings.append(
        {
            "mapping_type": mapping_type,
            "source_template_id": source_template_id,
            "target_template_id": target_template_id,
            "rules": rules,
        }
    )

#if 'templates' not in st.session_state:
#    load_config_to_session()
load_config_to_session()


# ######################################################################
# --- Streamlit UI 구성 ---
# ######################################################################

st.set_page_config(page_title=C.PAGE_TITLE, layout="wide")
st.title(C.MAIN_TITLE)

page_run, page_setup = st.tabs([C.TAB_RUN, C.TAB_SETUP])

 # ########## 1. 실행 페이지 ##########
with page_run:
    st.sidebar.button("⚙️ 설정 새로고침", on_click=load_config_to_session)
    
    tab_rosen, tab_bulk = st.tabs(["1. 로젠 송장 변환", "2. 이카운트 일괄 양식 생성"])

    # --- [실행] 로젠 송장 변환 ---
    with tab_rosen:
        st.subheader("이카운트 ERP ➔ 로젠 송장 양식")
        
        # 1. 매핑 규칙 확인
        tmpl_ecount = get_active_template(C.TPL_TYPE_ORDER)
        tmpl_rosen = get_active_template(C.TPL_TYPE_INVOICE)
        rules = None
        if tmpl_ecount and tmpl_rosen:
            rules = get_mapping_rules(C.MAP_ORDER_TO_INVOICE, tmpl_ecount["id"], tmpl_rosen["id"])
        
        # 2. 이카운트 템플릿 정보 확인 (여기에 줄 번호가 들어있음!)
        # 키값("ecount")은 설정 페이지에서 저장할 때 쓴 키와 같아야 합니다.
        
        if not rules:
            st.error("⚠️ '설정' 탭에서 [이카운트 -> 로젠] 매핑을 먼저 해주세요.")
        elif not tmpl_ecount:
             st.error("⚠️ '설정' 탭에서 [이카운트] 양식을 먼저 등록해주세요.")
        else:
            # [변경점] 사용자에게 묻지 않고 저장된 값 가져오기 (없으면 기본값 0=1번째 줄)
            saved_row_idx = tmpl_ecount.get("header_row_idx", 0)
            
            # 사용자에게 안내 문구 정도는 띄워주면 친절함 (선택사항)
            st.caption(f"ℹ️ 설정된 제목 줄 위치: {saved_row_idx + 1}번째 줄")

            up_file = st.file_uploader(
                    "이카운트 주문 엑셀 업로드", 
                    key="run_ecount", 
                    on_change=reset_conversion  # 파일이 바뀌면 자동으로 이전 결과 삭제
                )
                # 1. 파일 업로더 (on_change를 사용하여 파일이 바뀌면 세션 삭제)

            if up_file:
                df = load_data(up_file, header_row_idx=saved_row_idx)
                
                #print("df")
                #print(df)
                #print("df columns:", df.columns.tolist() if df is not None else "df is None")
                #print("")

                if df is not None:
                    # 2. 변환 실행 버튼
                    if st.button("변환 실행", type="primary"):
                        with st.spinner("데이터 변환 중입니다..."):
                                # 서비스 함수 딱 하나만 호출하면 끝!
                            results = services.process_all_conversions(df, rules)
                            st.session_state.conversion_result = results
                            st.success("모든 변환이 완료되었습니다!")

                    # 3. 결과 표시 (세션에 있을 때만)
                    if "conversion_result" in st.session_state:
                        results = st.session_state.conversion_result
                        # (1) 수정된 이카운트 파일 섹션 (독립적으로 표시)
                        st.markdown("### 📂 1. 수정된 이카운트 원본 (합포장 반영)")
                        st.caption("수량이 1보다 큰 주문은 `상품명 x 수량`으로 변경되고, 수량은 1로 통일되었습니다.")

                        df_ecount = results['ecount']
                        st.dataframe(df_ecount.head(3), use_container_width=True)

                        st.download_button(
                            label="⬇️ 수정된_이카운트_다운로드.xlsx",
                            data=to_excel_bytes(df_ecount),
                            file_name="modified_ecount_source.xlsx",
                            key="btn_ecount_down",
                            use_container_width=True
                        )

                        st.divider() # 깔끔한 구분선

                        st.markdown("### 🚛 2. 로젠 택배 발송용 파일")

                        rosen_dict = results['rosen']
            
                        # (중요) 만약 파일 내용과 세션 결과가 맞지 않는 상황을 방지하고 싶다면
                        # 여기에 추가적인 체크 로직을 넣을 수도 있습니다.
                        
                        cols = st.columns(3)
                        for idx, (name, df_res) in enumerate(rosen_dict.items()):
                            with cols[idx % 3]:
                                st.success(f"✅ {name} ({len(df_res)}건)")
                                
                                # 헤더 중복 처리 로직 (display_df)
                                display_df = df_res.copy()
                                new_cols = []
                                seen = {}
                                for col in display_df.columns:
                                    base = col if str(col).strip() else "빈헤더"
                                    if base in seen:
                                        seen[base] += 1
                                        new_cols.append(f"{base}_{seen[base]}")
                                    else:
                                        seen[base] = 0
                                        new_cols.append(base)
                                display_df.columns = new_cols
                                
                                st.dataframe(display_df.head(3), use_container_width=True)
                                
                                st.download_button(
                                    f"⬇️ {name}_로젠.xlsx",
                                    data=to_excel_bytes(df_res),
                                    file_name=f"rosen_{name}.xlsx",
                                    key=f"dl_btn_{name}_{idx}" # 인덱스 추가로 키 중복 방지
                                )
                                idx += 1

    # --- [실행] 일괄 양식 생성 ---
    with tab_bulk:
        st.subheader("이카운트 + 내보내기(송장) ➔ 일괄 양식")
        st.info("ℹ️ 수취인+연락처+품목+메시지가 모두 일치하는 주문을 자동으로 연결합니다.")
        
        tmpl_order = get_active_template(C.TPL_TYPE_ORDER)
        tmpl_export = get_active_template(C.TPL_TYPE_EXPORT)
        tmpl_bulk = get_active_template(C.TPL_TYPE_BULK)
        match_rules = None
        mapping_rules = None
        if tmpl_order and tmpl_export:
            match_rules = get_mapping_rules(C.MAP_BULK_MATCH, tmpl_order["id"], tmpl_export["id"])
        if tmpl_order and tmpl_bulk:
            mapping_rules = get_mapping_rules(C.MAP_BULK_MAPPING, tmpl_order["id"], tmpl_bulk["id"])
        rules_bulk = {
            "match_columns": (match_rules or {}).get("match_columns", {}),
            "transform": (mapping_rules or {}).get("transform", {}),
        }


        if not tmpl_order or not tmpl_export:
            st.error("Register order/export templates first.")
        elif not tmpl_bulk:
            st.error("Register a bulk template first.")
        elif not match_rules:
            st.error("Save bulk match rules first.")
        elif not mapping_rules:
            st.error("Save bulk mapping rules first.")
        else:
            h1 = tmpl_order.get("header_row_idx", 0)
            h2 = tmpl_export.get("header_row_idx", 0)
            
            st.caption(f"Header rows: order({h1+1}), export({h2+1})")
            
            c1, c2 = st.columns(2)
            with c1:
                up_erp = st.file_uploader("1) Order file", key="bulk_erp")
            with c2:
                up_inv = st.file_uploader("2) Export file", key="bulk_inv")
            
            if up_erp and up_inv:
                df_e = load_data(up_erp, header_row_idx=h1)
                df_i = load_data_v2(up_inv, is_merged=True)
            
                print("df_e columns:", df_e.columns.tolist() if df_e is not None else "df_e is None")
                print("df_i columns:", df_i.columns.tolist() if df_i is not None else   "df_i is None")
                print("")
                
                if df_e is not None and df_i is not None:
                    if st.button("일괄 양식 생성"):
                        final_df = services.convert_to_bulk_upload(df_e, df_i, rules_bulk)
                        if final_df is not None:
                            st.success(f"✅ 생성 완료! (총 {len(final_df)}건)")
                            st.dataframe(final_df.head(), use_container_width=True)
                            st.download_button(
                                "⬇️ 이카운트_일괄업로드.xlsx",
                                data=to_excel_bytes(final_df),
                                file_name="ecount_bulk_upload.xlsx"
                            )

# ########## 2. 설정 페이지 ##########
with page_setup:
    st.warning("⚠️ 설정은 DB에 자동 저장됩니다.")
    t1, t2, t3,t4 = st.tabs([C.SETUP_TAB1_TITLE, C.SETUP_TAB2_TITLE, C.SETUP_TAB3_TITLE, C.SETUP_TAB4_TITLE])

    # --- [설정] 1. 양식 등록 ---
    with t1:
        st.write("각 엑셀 파일의 헤더(제목) 정보를 등록합니다.")
        
        #selected_tmp의 예시값: "ecount", "rosen" 등
        selected_tmp = st.selectbox(
            C.TEMPLATE_TYPES_IN_ORDER,
            format_func=lambda x: C.TEMPLATE_TYPE_LABELS[x],
        )


        # 선택된 양식에 해당하는 UI 컴포넌트를 렌더링합니다.
        if selected_tmp:
            render_template_manager(selected_tmp, C.TEMPLATE_TYPE_LABELS[selected_tmp])

  # --- [설정] 2. 로젠 변환 매핑 ---
    with t2:
        st.subheader("이카운트 ➔ 로젠 매핑")
        
        # 1. 템플릿 데이터(딕셔너리) 가져오기
        src_template = get_active_template(C.TPL_TYPE_ORDER)
        tgt_template = get_active_template(C.TPL_TYPE_INVOICE)
        
        # 2. 딕셔너리에서 'headers' 리스트만 안전하게 추출
        # (DB에 headers가 없거나 비어있을 경우를 대비해 빈 리스트 []를 기본값으로 둠)
        src_headers = src_template.get("headers", []) if src_template else []
        tgt_headers = tgt_template.get("headers", []) if tgt_template else []

        # 디버깅용 출력 (리스트가 잘 나오는지 확인)
        #print("src_headers:", src_headers)
        #print("tgt_headers:", tgt_headers)
        #print("")

        # 리스트가 비어있는지 확인
        if not src_headers or not tgt_headers:
            st.error("먼저 '1. 양식 등록'에서 이카운트와 로젠 양식을 등록해주세요.")
        else:
            with st.form("map_rosen_form"):
                # 단순 매핑
                st.write("##### 1:1 컬럼 연결")
                current_rules = get_mapping_rules(C.MAP_ORDER_TO_INVOICE, src_template["id"], tgt_template["id"]) or {}
                current_map = current_rules.get("simple_map", {})
                

                # --- [설정] 2. 로젠 변환 매핑 화면 ---
                new_simple_map_list = [] 

                for i, t_col in enumerate(tgt_headers):
                    # 1. 헤더가 빈 값(또는 Unnamed)인지 확인
                    is_empty = not str(t_col).strip() or str(t_col).startswith("Unnamed:")

                    # 2. 고정값 처리 (고정값은 보여줌)
                    if t_col in [C.ROSEN_DELIVERY_FEE_COL, C.ROSEN_FEE_TYPE_COL]:
                        st.text_input(
                            f"{i+1}. {t_col} (고정값)", 
                            value=str(C.ROSEN_SHIPPING_COST) if t_col == C.ROSEN_DELIVERY_FEE_COL else C.ROSEN_COST_TYPE, 
                            disabled=True, 
                            key=f"fixed_{i}"
                        )
                        new_simple_map_list.append({"target": t_col, "source": "__FIXED_VALUE__"})
                        continue

                    # 3. 빈 헤더인 경우: UI에서는 생략하고 리스트에만 빈 상태로 추가
                    if is_empty:
                        # 사용자에게 보여주지 않지만, 결과물 순서를 위해 리스트에는 추가
                        new_simple_map_list.append({"target": "", "source": C.NOT_SELECTED})
                        continue

                    # 4. 일반 헤더인 경우: 기존 매핑 값 찾기 및 UI 표시
                    prev_val = C.NOT_SELECTED
                    if isinstance(current_map, list) and i < len(current_map):
                        prev_val = current_map[i].get("source", C.NOT_SELECTED)

                    options = [C.NOT_SELECTED] + src_headers
                    idx = options.index(prev_val) if prev_val in options else 0

                    val = st.selectbox(
                        f"{i+1}. 로젠 [{t_col}] <== 이카운트 [?]",
                        options,
                        index=idx,
                        key=f"rm_{i}_{t_col}" 
                    )

                    # 리스트에 저장
                    new_simple_map_list.append({"target": t_col, "source": val})
                
                st.write("##### 파일 분리 기준")
                
                # 수집처 컬럼 선택
                prev_split = current_rules.get("split_col", C.NOT_SELECTED)
                
                split_options = [C.NOT_SELECTED] + src_headers
                split_idx = split_options.index(prev_split) if prev_split in src_headers else 0
                
                split_col = st.selectbox("수집처(네이버/카카오 등) 구분 컬럼", split_options, index=split_idx)

                if st.form_submit_button("매핑 저장"):
                    full_rule = {"simple_map": new_simple_map_list, "split_col": split_col}
                    
                    # DB 저장 함수 호출 (import 확인 필요)
                    database.save_mapping(C.MAP_ORDER_TO_INVOICE, src_template["id"], tgt_template["id"], full_rule)
                    
                    # 세션 상태 업데이트
                    upsert_mapping_state(C.MAP_ORDER_TO_INVOICE, src_template["id"], tgt_template["id"], full_rule)
                    st.success("저장 완료")

    # --- [Setup] 3. Bulk match rules ---
    with t3:
        st.subheader("Bulk match rules")

        tmpl_order = get_active_template(C.TPL_TYPE_ORDER)
        tmpl_export = get_active_template(C.TPL_TYPE_EXPORT)

        order_cols = tmpl_order.get("headers", []) if tmpl_order else []
        export_cols = tmpl_export.get("headers", []) if tmpl_export else []

        if not order_cols or not export_cols:
            st.error("Register order/export templates first.")
        else:
            with st.form("bulk_match_form"):
                saved_match = get_mapping_rules(
                    C.MAP_BULK_MATCH,
                    tmpl_order["id"],
                    tmpl_export["id"],
                ) or {}
                curr_match = saved_match.get("match_columns", {})

                c1, c2 = st.columns(2)
                with c1:
                    st.write("Order")
                with c2:
                    st.write("Export")

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

                if st.form_submit_button("Save match rules"):
                    full_cfg = {"match_columns": selected_values}
                    database.save_mapping(C.MAP_BULK_MATCH, tmpl_order["id"], tmpl_export["id"], full_cfg)
                    upsert_mapping_state(C.MAP_BULK_MATCH, tmpl_order["id"], tmpl_export["id"], full_cfg)
                    st.success("Match rules saved")
                    st.rerun()

    # --- [Setup] 4. Bulk mapping rules ---
    with t4:
        st.subheader("Bulk mapping rules")

        tmpl_order = get_active_template(C.TPL_TYPE_ORDER)
        tmpl_bulk = get_active_template(C.TPL_TYPE_BULK)

        if not tmpl_order or not tmpl_bulk:
            st.error("Register order/bulk templates first.")
        else:
            with st.form("bulk_mapping_form"):
                saved_cfg = get_mapping_rules(
                    C.MAP_BULK_MAPPING,
                    tmpl_order["id"],
                    tmpl_bulk["id"],
                ) or {}

                st.write("---")
                st.write("Mall code mapping")
                st.caption("Map order mall codes to bulk format codes.")

                curr_rules = saved_cfg.get("transform", {}).get("rules", {})
                df_rules = rules_to_dataframe(curr_rules, C.DEFAULT_MALL_RULES)

                edited_df = st.data_editor(
                    df_rules,
                    column_config={
                        "수집처명": st.column_config.TextColumn("수집처명", required=True),
                        "쇼핑몰코드": st.column_config.TextColumn("쇼핑몰코드", required=True),
                    },
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True,
                    key="editor_rules",
                )

                if st.form_submit_button("Save mapping rules"):
                    rule_dict = dataframe_to_rules(edited_df)

                    full_cfg = {
                        "transform": {
                            "source_col": "수집처명",
                            "rules": rule_dict,
                        }
                    }

                    database.save_mapping(C.MAP_BULK_MAPPING, tmpl_order["id"], tmpl_bulk["id"], full_cfg)
                    upsert_mapping_state(C.MAP_BULK_MAPPING, tmpl_order["id"], tmpl_bulk["id"], full_cfg)
                    st.success("Mapping rules saved")
                    st.rerun()
