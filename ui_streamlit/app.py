import database 
import os
import streamlit as st          # 화면에 에러나 경고를 띄우기 위해 필요
from ui_components import render_template_manager # UI 컴포넌트 함수 가져오기
import constants as C  # 상수 파일 가져오기
from utils import rules_to_dataframe, dataframe_to_rules, load_data  # 유틸리티 함수 임포트
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
        rules = st.session_state.mappings.get(C.MAP_ECOUNT_TO_ROSEN)
        
        # 2. 이카운트 템플릿 정보 확인 (여기에 줄 번호가 들어있음!)
        # 키값("ecount")은 설정 페이지에서 저장할 때 쓴 키와 같아야 합니다.
        tmpl_ecount = st.session_state.templates.get("ecount", {})
        
        if not rules:
            st.error("⚠️ '설정' 탭에서 [이카운트 -> 로젠] 매핑을 먼저 해주세요.")
        elif not tmpl_ecount:
             st.error("⚠️ '설정' 탭에서 [이카운트] 양식을 먼저 등록해주세요.")
        else:
            # [변경점] 사용자에게 묻지 않고 저장된 값 가져오기 (없으면 기본값 0=1번째 줄)
            saved_row_idx = tmpl_ecount.get("header_row_idx", 0)
            
            # 사용자에게 안내 문구 정도는 띄워주면 친절함 (선택사항)
            st.caption(f"ℹ️ 설정된 제목 줄 위치: {saved_row_idx + 1}번째 줄")

            up_file = st.file_uploader("이카운트 주문 엑셀 업로드", key="run_ecount")
            
            if up_file:
                # [변경점] 가져온 saved_row_idx를 바로 사용
                df = services.load_data(up_file, header_row_idx=saved_row_idx)
                
                # ... (이하 기존 로직 동일) ...
                # print("df") ...
                if df is not None:
                    if st.button("변환 실행"):
                        res = services.convert_to_rosen(df, rules)
                        
                        cols = st.columns(3)
                        idx = 0
                        for name, df_res in res.items():
                            with cols[idx % 3]:
                                st.success(f"✅ {name} ({len(df_res)}건)")
                                st.dataframe(df_res.head(3), use_container_width=True)
                                st.download_button(
                                    f"⬇️ {name}_로젠.xlsx",
                                    data=services.to_excel_bytes(df_res),
                                    file_name=f"rosen_{name}.xlsx"
                                )
                            idx += 1

    # --- [실행] 일괄 양식 생성 ---
    with tab_bulk:
        st.subheader("이카운트 + 내보내기(송장) ➔ 일괄 양식")
        st.info("ℹ️ 수취인+연락처+품목+메시지가 모두 일치하는 주문을 자동으로 연결합니다.")
        
        rules_bulk = st.session_state.mappings.get(C.MAP_BULK_ECOUNT)
        print("Bulk Mapping Rules:", rules_bulk)
        print("")
        
        # 템플릿 정보 가져오기 (이카운트 & 로젠)
        tmpl_ecount = st.session_state.templates.get("ecount", {})
        tmpl_rosen = st.session_state.templates.get("rosen", {})

        if not rules_bulk:
            st.error("⚠️ '설정' 탭에서 [일괄 양식 매핑]을 먼저 해주세요.")
        elif not tmpl_ecount or not tmpl_rosen:
             st.error("⚠️ '설정' 탭에서 [이카운트] 및 [로젠] 양식을 등록해주세요.")
        else:
            # [변경점] 사용자 입력 제거 -> 저장된 값 호출
            h1 = tmpl_ecount.get("header_row_idx", 0)
            h2 = tmpl_rosen.get("header_row_idx", 0)
            
            st.caption(f"ℹ️ 설정된 제목 줄: 이카운트({h1+1}행), 송장파일({h2+1}행)")

            c1, c2 = st.columns(2)
            with c1:
                # h1 입력창 삭제됨
                up_erp = st.file_uploader("1) 이카운트 원본", key="bulk_erp")
            with c2:
                # h2 입력창 삭제됨
                up_inv = st.file_uploader("2) 로젠 내보내기(송장)", key="bulk_inv")
            
            if up_erp and up_inv:
                # [변경점] 저장된 h1, h2 사용
                df_e = load_data(up_erp, header_row_idx=h1)
                df_i = load_data(up_inv, header_row_idx=h2)

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
                                data=services.to_excel_bytes(final_df),
                                file_name="ecount_bulk_upload.xlsx"
                            )

# ########## 2. 설정 페이지 ##########
with page_setup:
    st.warning("⚠️ 설정은 DB에 자동 저장됩니다.")
    t1, t2, t3 = st.tabs([C.SETUP_TAB1_TITLE, C.SETUP_TAB2_TITLE, C.SETUP_TAB3_TITLE])

    # --- [설정] 1. 양식 등록 ---
    with t1:
        st.write("각 엑셀 파일의 헤더(제목) 정보를 등록합니다.")
        
        #selected_tmp의 예시값: "ecount", "rosen" 등
        selected_tmp = st.selectbox("설정할 양식 선택", C.TEMPLATE_KEYS_IN_ORDER, format_func=lambda x: C.TEMPLATE_LABELS[x])


        # 선택된 양식에 해당하는 UI 컴포넌트를 렌더링합니다.
        if selected_tmp:
            render_template_manager(selected_tmp, C.TEMPLATE_LABELS[selected_tmp])

  # --- [설정] 2. 로젠 변환 매핑 ---
    with t2:
        st.subheader("이카운트 ➔ 로젠 매핑")
        
        # 1. 템플릿 데이터(딕셔너리) 가져오기
        src_template = st.session_state.templates.get("ecount", {})
        tgt_template = st.session_state.templates.get("rosen", {})
        
        # 2. 딕셔너리에서 'headers' 리스트만 안전하게 추출
        # (DB에 headers가 없거나 비어있을 경우를 대비해 빈 리스트 []를 기본값으로 둠)
        src_headers = src_template.get("headers", [])
        tgt_headers = tgt_template.get("headers", [])

        # 디버깅용 출력 (리스트가 잘 나오는지 확인)
        print("src_headers:", src_headers)
        print("tgt_headers:", tgt_headers)
        print("")

        # 리스트가 비어있는지 확인
        if not src_headers or not tgt_headers:
            st.error("먼저 '1. 양식 등록'에서 이카운트와 로젠 양식을 등록해주세요.")
        else:
            with st.form("map_rosen_form"):
                # 단순 매핑
                st.write("##### 1:1 컬럼 연결")
                current_map = st.session_state.mappings.get(C.MAP_ECOUNT_TO_ROSEN, {}).get("simple_map", {})
                
                new_simple_map = {}
                
                # 타겟(로젠) 헤더 리스트를 루프로 돌림
                for t_col in tgt_headers:
                    # 고정값 처리
                    if t_col in [C.ROSEN_DELIVERY_FEE_COL, C.ROSEN_FEE_TYPE_COL]:
                        st.text_input(
                            f"{t_col} (고정값)", 
                            value=str(C.ROSEN_SHIPPING_COST) if t_col == C.ROSEN_DELIVERY_FEE_COL else C.ROSEN_COST_TYPE, 
                            disabled=True
                        )
                        continue
                        
                    # 기존 매핑 값 가져오기
                    prev_val = current_map.get(t_col, C.NOT_SELECTED)
                    
                    idx = 0
                    # 선택 목록 리스트 만들기 (선택안함 + 소스 헤더들)
                    options = [C.NOT_SELECTED] + src_headers

                    if prev_val in options:
                        idx = options.index(prev_val)
                    
                    # 셀렉트박스 생성
                    val = st.selectbox(
                        f"로젠 [{t_col}] <== 이카운트 [?]", 
                        options, 
                        index=idx, 
                        key=f"rm_{t_col}"
                    )
                    
                    # [수정] t_col은 이미 컬럼명(문자열)이므로 바로 키로 사용
                    new_simple_map[t_col] = val 
                
                st.write("##### 파일 분리 기준")
                
                # 수집처 컬럼 선택
                prev_split = st.session_state.mappings.get(C.MAP_ECOUNT_TO_ROSEN, {}).get("split_col", C.NOT_SELECTED)
                
                split_options = [C.NOT_SELECTED] + src_headers
                split_idx = split_options.index(prev_split) if prev_split in src_headers else 0
                
                split_col = st.selectbox("수집처(네이버/카카오 등) 구분 컬럼", split_options, index=split_idx)

                if st.form_submit_button("매핑 저장"):
                    full_rule = {"simple_map": new_simple_map, "split_col": split_col}
                    
                    # DB 저장 함수 호출 (import 확인 필요)
                    database.save_mapping(C.MAP_ECOUNT_TO_ROSEN, full_rule)
                    
                    # 세션 상태 업데이트
                    st.session_state.mappings[C.MAP_ECOUNT_TO_ROSEN] = full_rule
                    st.success("저장 완료")
   
   # --- [설정] 3. 일괄 양식 매칭 설정 ---
    with t3:
        st.subheader("일괄 양식 생성을 위한 '식별자 매칭' 설정")
        st.info("두 파일을 연결하기 위해, 의미가 같은 컬럼끼리 짝지어 주세요.")
        
        # 1. 세션에서 템플릿 정보(딕셔너리)를 가져옴
        tmpl_ecount = st.session_state.templates.get("ecount", {})
        tmpl_rosen  = st.session_state.templates.get("rosen", {}) 

        # 2. 딕셔너리 안에서 'headers' 리스트만 추출
        e_cols = tmpl_ecount.get("headers", [])
        i_cols = tmpl_rosen.get("headers", [])
        
        if not e_cols or not i_cols:
            st.error("이카운트와 로젠 내보내기 양식을 먼저 등록해주세요.")
        else:
            # 폼 시작
            with st.form("bulk_match_form"):



        # 현재 저장된 설정 가져오기
                saved_cfg = st.session_state.mappings.get(C.MAP_BULK_ECOUNT, {})
                curr_match = saved_cfg.get("match_columns", {})
                
                c1, c2 = st.columns(2)
                with c1: st.write("##### 이카운트 (원본)")
                with c2: st.write("##### 로젠 (내보내기)")

                # ---------------------------------------------------------
                # [Refactoring] 반복문을 통한 동적 UI 생성 (DRY 원칙 적용)
                # ---------------------------------------------------------
                selected_values = {} # 결과를 담을 딕셔너리

                for field in C.BULK_MAPPING_FIELDS:
                            # 1. 키 자동 생성 (Convention 활용)
                            # 예: id="item" -> e_key="ecount_item", i_key="invoice_item"
                            e_key = f"ecount_{field.id}"
                            i_key = f"invoice_{field.id}"

                            # 2. 이카운트 (왼쪽)
                            e_idx = e_cols.index(curr_match.get(e_key)) if curr_match.get(e_key) in e_cols else 0
                            
                            selected_values[e_key] = c1.selectbox(
                                field.label_e,   # namedtuple은 .으로 접근 가능 (가독성 UP)
                                e_cols, 
                                index=e_idx,
                                key=f"bulk_{field.id}_ecount" 
                            )

                            # 3. 로젠 (오른쪽)
                            i_idx = i_cols.index(curr_match.get(i_key)) if curr_match.get(i_key) in i_cols else 0
                            
                            selected_values[i_key] = c2.selectbox(
                                field.label_i, 
                                i_cols, 
                                index=i_idx,
                                key=f"bulk_{field.id}_invoice"
                            )

            # 쇼핑몰 코드 변환 규칙 (Data Editor)
            # ---------------------------------------------------------
                st.write("---")
                st.write("##### 쇼핑몰 코드 변환 규칙")
                st.caption("ℹ️ 이카운트 [수집처] ↔ 로젠 [쇼핑몰 코드] 매핑")

                curr_rules = saved_cfg.get("transform", {}).get("rules", {})
                df_rules = rules_to_dataframe(curr_rules, C.DEFAULT_MALL_RULES)

                edited_df = st.data_editor(
                    df_rules,
                    column_config={
                        "수집처명": st.column_config.TextColumn("이카운트 수집처명", required=True),
                        "쇼핑몰코드": st.column_config.TextColumn("로젠 쇼핑몰코드", required=True),
                    },
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True,
                    key="editor_rules"
                )

                # ---------------------------------------------------------
                # 저장 로직
                # ---------------------------------------------------------
                if st.form_submit_button("설정 저장"):
                    # 1. 규칙 변환 (Utils 사용)
                    rule_dict = dataframe_to_rules(edited_df)

                    # 2. 전체 설정 구성
                    full_cfg = {
                        "match_columns": selected_values, # 반복문에서 수집한 값들
                        "transform": {
                            "source_col": "수집처", 
                            "rules": rule_dict
                        }
                    }
                    
                    database.save_mapping(C.MAP_BULK_ECOUNT, full_cfg)
                    st.session_state.mappings[C.MAP_BULK_ECOUNT] = full_cfg
                    st.success("매핑 설정 저장 완료!")
                    st.rerun()