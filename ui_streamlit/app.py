import io
import pandas as pd
import streamlit as st
import database # database.py 임포트

# --- 0. (중요) DB 초기화 및 설정 로드 ---
#→ 역할: 프로그램 시작할 때 필요한 라이브러리 불러오고, 데이터베이스 준비
database.init_db()

def load_config_to_session():
    templates, mappings = database.load_all_config_from_db()
    st.session_state['templates'] = templates
    st.session_state['mappings'] = mappings
    print("Config loaded from DB to session state.")

if 'templates' not in st.session_state:
    load_config_to_session()



# --- 유틸리티 함수 (load_headers 제외하고 이전과 동일) ---
def load_headers(uploaded_file):
    """ (변경 없음) 엑셀/CSV 파일을 읽어 헤더(컬럼명 리스트)만 반환 """
    if uploaded_file is None: return None
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='cp949', nrows=0) #nrows=0의 의미는 헤더만 읽기
        else:
            df = pd.read_excel(uploaded_file, nrows=0)
        return list(df.columns) # 예시: # → ['주문번호', '상품명', '수량']

    except Exception as e:
        st.error(f"파일 헤더를 읽는 중 오류 발생: {e}")
        return None

def load_data(uploaded_file):
    """ (변경 없음) 엑셀/CSV 파일을 읽어 전체 데이터(DataFrame) 반환 """
    # ... (이전 코드와 동일)
    if uploaded_file is None: return None
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                return pd.read_csv(uploaded_file, encoding='cp949')
            except Exception:
                uploaded_file.seek(0) # 파일 포인터를 처음으로 되돌림. 후에 read_csv 재시도 위해
                return pd.read_csv(uploaded_file, encoding='utf-8-sig')
        else:
            return pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"파일 데이터를 읽는 중 오류가 발생했습니다: {e}")
        return None

def to_excel_bytes(df):
    """ (변경 없음) DataFrame -> 엑셀 다운로드용 Bytes """
    # ... (이전 코드와 동일)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    bio.seek(0) # 버퍼의 시작 위치로 이동, 왜냐하면 다운로드 시 처음부터 읽어야 하니까, 그 의미를 쉽게 풀면, 파일 포인터를 처음으로 되돌리는 것과 같음
    return bio.getvalue()

# --- 변환 로직 함수 (수정됨) ---
def convert_to_rosen(df_data, mapping_rules):
     #로직 수정해야 할 듯.
    #현재 로직은...줄 그대로 복사해왔음. 즉, 튜플 하나하나 일치하는지 확인하지 않아
    #내가 원하는 로직은... 정리해서 프롬프트 넣기
    #안정성 고려, 다만 빠른 변환을 위해.. 둘 다 사용. Dynamic Programming 느낌. 둘 다 메모리에 저장
    """ (변경 없음) (요구사항 1-3) 원본 -> 로젠 변환 """
    # ... (이전 코드와 동일)
    out = pd.DataFrame()
    #out은 변환될 엑셀 표
    #여기서 각 속성(로제 양식 속성 등)이 모두 들어가는지..?
    for rosen_col, source_col in mapping_rules.get("simple_map", {}).items():
        #rosen_col은 로젠 엑셀의 속성, source_col은 이카운트 엑셀의 속성
        if source_col != "(선택 안 함)" and source_col in df_data.columns:
            # 실제로넌 (선택 안 함)이 아닐 것 => 수정사항
            # 매핑정보에 이카운트 속성이 사용자가 업로드한 파일(이카운트)에 존재한다면,
            out[rosen_col] = df_data[source_col]
            #변환될 엑셀 표의 로젠 속성에는 이카운트에 값이 저장됨
        elif source_col == "(선택 안 함)":
            out[rosen_col] = ""
    split_col = mapping_rules.get("split_col")
    if split_col and split_col in df_data.columns: #여기는 맞는지 살펴볼 필요가 있다. 일단 문법을 파악해야 해
        st.info(f"'{split_col}' 기준으로 파일 분리를 시도합니다.")
        df_naver = out[df_data[split_col].str.contains("네이버", na=False)]
        df_kakao = out[df_data[split_col].str.contains("카카오", na=False)]
        df_coupang = out[df_data[split_col].str.contains("쿠팡", na=False)]
        return {"naver": df_naver, "kakao": df_kakao, "coupang": df_coupang}
    #왜 return이 두개나 있지..? 그리고 해당 함수는 어쨌든, 로젠 송장 세개로 변환해주는 함수임.
    return {"single_file": out} #split_col(아마도 수집처column)가 없는 경우

def convert_to_bulk_upload(df_original, df_invoice, mapping_rules):
    """ (수정됨) (요구사항 4) 원본 + 송장 -> 이카운트 일괄 변환 """
    
    # 1. '병합 키(Merge Key)' 생성 (질문 1)
    merge_keys = mapping_rules.get('merge_keys', [])
    merge_on_cols = []
    
    # 임시 병합 키 컬럼 생성 (예: '수취인'과 '수하인명'을 __KEY_0__ 으로)
    for i, (src_key, inv_key) in enumerate(merge_keys):
        if src_key != "(선택 안 함)" and inv_key != "(선택 안 함)":
            merge_col_name = f"__MERGE_KEY_{i}__"
            # (데이터 타입이 다를 수 있으므로 str로 통일하여 병합)
            if src_key in df_original.columns:
                df_original[merge_col_name] = df_original[src_key].astype(str)
            if inv_key in df_invoice.columns:
                df_invoice[merge_col_name] = df_invoice[inv_key].astype(str)
            
            if merge_col_name in df_original and merge_col_name in df_invoice:
                 merge_on_cols.append(merge_col_name)
    #결과적으로 meroge_on_cols에는 병합에 사용할 컬럼명이 들어감.
    if not merge_on_cols:
        st.error("오류: 병합 키(Merge Key)가 설정되지 않았거나, 파일에 해당 컬럼이 없습니다.")
        return None
    
    # (how="left": 원본 주문 데이터를 기준으로, 송장 정보가 있으면 붙김)
    merged_df = pd.merge(df_original, df_invoice, on=merge_on_cols, how="left")
    
    # 2. '일괄 양식' 컬럼 생성 (필드 매핑)
    out = pd.DataFrame()
    field_map = mapping_rules.get("field_map", {})
    
    for bulk_col, (source_type, source_col) in field_map.items():
        # (병합 시 원본/송장 컬럼명이 겹칠 수 있으므로, 원본 DataFrame에서 우선 참조)
        if source_type == "원본" and source_col in df_original.columns:
            out[bulk_col] = merged_df[f"{source_col}_x"] if f"{source_col}_x" in merged_df else merged_df[source_col]
        elif source_type == "송장" and source_col in df_invoice.columns:
            out[bulk_col] = merged_df[f"{source_col}_y"] if f"{source_col}_y" in merged_df else merged_df[source_col]

    # 3. '쇼핑몰 코드' 등 변환 로직 (질문 2)
    transform = mapping_rules.get("transform", {})
    if transform:
        src_col = transform.get('source_col') # 예: '수집처'
        trg_col = transform.get('target_col') # 예: '쇼핑몰코드'
        rules = transform.get('rules', {})   # 예: {'네이버': '00001'}
        
        # (src_col이 _x (원본) 컬럼일 수 있음)
        src_col_in_merged = f"{src_col}_x" if f"{src_col}_x" in merged_df else src_col

        if trg_col and rules and src_col_in_merged in merged_df.columns:
            st.info(f"'{src_col_in_merged}' -> '{trg_col}' 변환 적용 중...")
            # .map()을 사용하여 값 변환
            out[trg_col] = merged_df[src_col_in_merged].map(rules)
    
    # 임시 병합 키 컬럼 제거
    out = out.drop(columns=[col for col in out.columns if "__MERGE_KEY" in str(col)], errors='ignore')
    return out


# ######################################################################
# --- Streamlit UI 구성 ---
# ######################################################################

st.set_page_config(page_title="excelConverter v4 (Full)", layout="wide")
st.title("🚚 excelConverter v4 (필수 필드 / 병합 기능)")

# --- 메인 1. 실행 페이지 / 메인 2. 설정 페이지 ---
page_run, page_setup = st.tabs(["실행 (매일 작업)", "설정 (최초 1회)"])

# ########## 메인 1: 실행 (Run) 페이지 ##########
with page_run:
    st.sidebar.button("⚙️ 설정 새로고침 (DB Reload)", on_click=load_config_to_session)
    
    tab_run_rosen, tab_run_bulk = st.tabs([
        "1. 로젠 송장 변환", 
        "2. 이카운트 일괄 양식 생성"
    ])

    # --- 1-1. 로젠 송장 변환 실행 ---
    with tab_run_rosen:
        with st.expander("이카운트 -> 로젠 변환", expanded=True):
            rules = st.session_state.mappings.get("ecount_to_rosen")
            src_template = st.session_state.templates.get("ecount")

            if not rules or not src_template:
                st.error("⚠️ '설정' 탭에서 [이카운트 양식]과 [로젠 매핑]을 먼저 완료해주세요.")
            else:
                up_data = st.file_uploader("이카운트 '주문 데이터' 엑셀 업로드", key="run_ecount_data")
                if up_data:
                    df_data = load_data(up_data)
                    if df_data is not None:
                        # (수정됨 - 질문 3) '필수 속성' 검증
                        required_cols = [c['name'] for c in src_template if c['required']]
                        missing_cols = [col for col in required_cols if col not in df_data.columns]
                        
                        if missing_cols:
                            st.error(f"오류: 업로드한 파일에 필수 속성이 누락되었습니다: {missing_cols}")
                        else:
                            st.success("✅ 필수 속성 확인 완료.")
                            if st.button("로젠 양식으로 변환 실행", key="run_ecount_btn"):
                                with st.spinner("변환 중..."):
                                    result_dfs = convert_to_rosen(df_data, rules)
                                    for name, df_result in result_dfs.items():
                                        st.subheader(f"✅ {name} 변환 결과 (미리보기)")
                                        st.dataframe(df_result.head(5), use_container_width=True)
                                        st.download_button(
                                            f"⬇️ {name}.xlsx 다운로드",
                                            data=to_excel_bytes(df_result),
                                            file_name=f"rosen_{name}.xlsx"
                                        )
        # (다른 탭...)
        with st.expander("네이버 -> 로젠 변환", expanded=False):
            st.info("... (구현 방식 동일)")

    # --- 1-2. 이카운트 일괄 양식 생성 실행 ---
    with tab_run_bulk:
        tab_rb_ecount, tab_rb_store = st.tabs([
            "이카운트 원본 + 송장", "개별 스토어 원본 + 송장"
        ])
        
        with tab_rb_ecount:
            rules = st.session_state.mappings.get("bulk_ecount")
            src_template = st.session_state.templates.get("ecount")
            # (주의: '내보내기 양식'도 별도 템플릿으로 등록해야 함)
            inv_template = st.session_state.templates.get("rosen_invoice") # '내보내기 양식' 템플릿 이름
            
            if not rules or not src_template or not inv_template:
                st.error("⚠️ '설정' 탭에서 [이카운트 양식], [내보내기 양식], [일괄 매핑]을 모두 완료해주세요.")
                st.info("('내보내기 양식'은 '2. 대상 양식' 탭에서 'rosen_invoice' 등의 이름으로 등록해야 합니다.)")
            else:
                up_original = st.file_uploader("1) 이카운트 '원본 주문' 파일", key="bulk_ecount_orig")
                up_invoice = st.file_uploader("2) 로젠 '송장번호 포함(내보내기)' 파일", key="bulk_ecount_inv")
                
                if up_original and up_invoice:
                    df_orig = load_data(up_original)
                    df_inv = load_data(up_invoice)
                    
                    if df_orig is not None and df_inv is not None:
                        # (수정됨 - 질문 3) 양쪽 파일 '필수 속성' 검증
                        req_src = [c['name'] for c in src_template if c['required']]
                        req_inv = [c['name'] for c in inv_template if c['required']]
                        missing_src = [c for c in req_src if c not in df_orig.columns]
                        missing_inv = [c for c in req_inv if c not in df_inv.columns]

                        if missing_src or missing_inv:
                            if missing_src: st.error(f"원본 파일 필수 속성 누락: {missing_src}")
                            if missing_inv: st.error(f"송장 파일 필수 속성 누락: {missing_inv}")
                        else:
                            st.success("✅ 양쪽 파일 필수 속성 확인 완료.")
                            if st.button("이카운트 일괄 양식 생성", key="run_bulk_ecount_btn"):
                                with st.spinner("생성 중..."):
                                    df_result = convert_to_bulk_upload(df_orig, df_inv, rules)
                                    if df_result is not None:
                                        st.subheader("✅ 일괄 양식 생성 결과 (미리보기)")
                                        st.dataframe(df_result.head(), use_container_width=True)
                                        st.download_button(
                                            "⬇️ ecount_upload.xlsx 다운로드",
                                            data=to_excel_bytes(df_result),
                                            file_name="ecount_bulk_upload.xlsx"
                                        )
        with tab_rb_store:
            st.info("... (구현 방식 동일)")


# ########## 메인 2: 설정 (Setup) 페이지 ##########
with page_setup:
    st.warning("⚠️ 여기서 설정한 내용은 DB에 영구 저장됩니다.")
    
    tab_setup_source, tab_setup_target, tab_setup_mapping = st.tabs([
        "1. 원본 양식 설정 (이카운트, 네이버...)",
        "2. 대상 양식 설정 (로젠, 일괄 양식, 내보내기)",
        "3. 매핑 설정 (연결하기)"
    ])

    # --- 2-1. 원본 양식(템플릿) 설정 (수정됨) ---
    with tab_setup_source:
        sources = ["ecount", "naver", "kakao", "coupang"]
        for name in sources:
            with st.expander(f"'{name}' 원본 양식 설정"):
                up_file = st.file_uploader(f"'{name}' 엑셀 양식 파일 업로드", type=['xlsx', 'csv'], key=f"setup_{name}")
                
                if up_file:
                    headers = load_headers(up_file)
                    if headers:
                        st.info("파일에서 다음 속성(헤더)을 감지했습니다. '필수' 항목을 체크하고 저장하세요.")
                        # (수정됨 - 질문 3) 필수 속성 체크 UI
                        with st.form(key=f"form_setup_{name}"):
                            template_config = [] # [{name: 'col1', required: True}, ...]
                            for col in headers:
                                # (이전에 저장된 값이 있으면 그걸 기본값으로)
                                current_config = st.session_state.templates.get(name, [])
                                is_checked = False
                                for item in current_config:
                                    if item['name'] == col and item['required']:
                                        is_checked = True
                                        break
                                
                                is_required = st.checkbox(f"`{col}`", value=is_checked, key=f"req_{name}_{col}")
                                template_config.append({"name": col, "required": is_required})
                            
                            if st.form_submit_button("✅ 이 양식 저장"):
                                database.save_template(name, template_config)
                                st.session_state.templates[name] = template_config
                                st.success("저장 완료!")

                st.subheader(f"현재 등록된 '{name}' 양식 속성")
                current_template = st.session_state.templates.get(name)
                if current_template:
                    # (수정됨) 필수/선택 나눠서 보여주기
                    required = [c['name'] for c in current_template if c['required']]
                    optional = [c['name'] for c in current_template if not c['required']]
                    st.code(f"필수 속성 ({len(required)}개): {required}\n선택 속성 ({len(optional)}개): {optional}")
                else:
                    st.code("등록된 양식이 없습니다.")

    # --- 2-2. 대상 양식(템플릿) 설정 (수정됨) ---
    with tab_setup_target:
        # (수정됨) 'rosen_invoice' (내보내기 양식) 추가
        targets = ["rosen", "rosen_invoice", "ecount_bulk"] 
        target_names = {
            "rosen": "로젠 송장 양식 (변환 대상)", 
            "rosen_invoice": "로젠 내보내기 양식 (송장번호 포함)",
            "ecount_bulk": "이카운트 일괄 양식"
        }
        st.info("'내보내기 양식'은 '일괄 양식 생성' 시 '필수 속성' 검증에 사용됩니다.")
        
        for name in targets:
            # (UI는 원본 양식 설정과 동일)
            with st.expander(f"'{target_names.get(name, name)}' 대상 양식 설정"):
                up_file = st.file_uploader(f"'{name}' 엑셀 양식 파일 업로드", type=['xlsx', 'csv'], key=f"setup_{name}")
                if up_file:
                    headers = load_headers(up_file)
                    if headers:
                        with st.form(key=f"form_setup_{name}"):
                            template_config = []
                            for col in headers:
                                current_config = st.session_state.templates.get(name, [])
                                is_checked = False
                                for item in current_config:
                                    if item['name'] == col and item['required']:
                                        is_checked = True
                                        break
                                is_required = st.checkbox(f"`{col}`", value=is_checked, key=f"req_{name}_{col}")
                                template_config.append({"name": col, "required": is_required})
                            
                            if st.form_submit_button("✅ 이 양식 저장"):
                                database.save_template(name, template_config)
                                st.session_state.templates[name] = template_config
                                st.success("저장 완료!")

                st.subheader(f"현재 등록된 '{name}' 양식 속성")
                current_template = st.session_state.templates.get(name)
                if current_template:
                    required = [c['name'] for c in current_template if c['required']]
                    optional = [c['name'] for c in current_template if not c['required']]
                    st.code(f"필수 속성 ({len(required)}개): {required}\n선택 속성 ({len(optional)}개): {optional}")
                else:
                    st.code("등록된 양식이 없습니다.")

    # --- 2-3. 매핑 설정 (수정됨) ---
    with tab_setup_mapping:
        
        # (이카운트 -> 로젠 매핑)
        with st.expander("3-1. 이카운트 양식 => 로젠 송장 양식 매핑"):
            src_template = st.session_state.templates.get("ecount")
            target_template = st.session_state.templates.get("rosen")
            
            if not src_template or not target_template:
                st.warning("먼저 '1. 원본'과 '2. 대상' 탭에서 [이카운트]와 [로젠] 양식을 모두 등록해야 합니다.")
            else:
                src_cols = [c['name'] for c in src_template]
                target_cols = [c['name'] for c in target_template]
                options = ["(선택 안 함)"] + src_cols

                with st.form(key="form_ecount_to_rosen"):
                    current_mapping = st.session_state.mappings.get("ecount_to_rosen", {})
                    new_rules = {}
                    
                    st.subheader("단순 매핑")
                    simple_map = {}
                    for target_col in target_cols:
                        default_val = current_mapping.get("simple_map", {}).get(target_col, "(선택 안 함)")
                        default_idx = options.index(default_val) if default_val in options else 0
                        simple_map[target_col] = st.selectbox(
                            f"'{target_col}' (로젠)  <── ",
                            options, index=default_idx, key=f"map_ecount_{target_col}"
                        )
                    new_rules["simple_map"] = simple_map
                    
                    st.subheader("파일 분리 규칙 (수집처)")
                    split_col_default = current_mapping.get("split_col", "(선택 안 함)")
                    split_col_idx = options.index(split_col_default) if split_col_default in options else 0
                    new_rules["split_col"] = st.selectbox(
                        "파일 분리 기준이 되는 '수집처' 컬럼 선택:",
                        options, index=split_col_idx, key="map_ecount_split"
                    )
                    
                    if st.form_submit_button("✅ 이카운트 -> 로젠 매핑 저장"):
                        database.save_mapping("ecount_to_rosen", new_rules)
                        st.session_state.mappings["ecount_to_rosen"] = new_rules
                        st.json(new_rules)

        # (다른 3개 매핑 버튼...)
        st.expander("3-2. 네이버 양식 => 로젠 송장 양식 매핑 (구현 방식 동일)", expanded=False)

        st.divider()
        st.subheader("일괄 양식 매핑 설정")
        
        # (수정됨 - 질문 1, 2) 일괄 양식 매핑 UI
        with st.expander("4-1. 이카운트 원본+송장 => 일괄 양식 매핑", expanded=True):
            # (주의: 'rosen_invoice' 사용)
            src_template = st.session_state.templates.get("ecount")
            invoice_template = st.session_state.templates.get("rosen_invoice")
            bulk_template = st.session_state.templates.get("ecount_bulk")
            
            if not src_template or not invoice_template or not bulk_template:
                st.warning("먼저 [이카운트], [로젠 내보내기], [이카운트 일괄] 양식을 모두 등록해야 합니다.")
            else:
                src_cols = [c['name'] for c in src_template]
                invoice_cols = [c['name'] for c in invoice_template]
                bulk_cols = [c['name'] for c in bulk_template]
                
                with st.form(key="form_bulk_ecount_map"):
                    current_mapping = st.session_state.mappings.get("bulk_ecount", {})
                    new_rules = {}

                    # --- 1. 병합 키(Merge Key) 설정 (질문 1) ---
                    st.subheader("1. 병합 키(Merge Key) 설정")
                    st.info("두 파일(원본, 송장)을 하나로 합칠 '공통 기준'을 설정합니다. (예: 수취인 <-> 수하인명)")
                    
                    current_merge_keys = current_mapping.get('merge_keys', [("(선택 안 함)", "(선택 안 함)")]*2)
                    merge_keys = []
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("`원본(이카운트)` 컬럼")
                        key_src_1 = st.selectbox("병합 키 1 (원본)", ["(선택 안 함)"] + src_cols, index=src_cols.index(current_merge_keys[0][0]) + 1 if current_merge_keys[0][0] in src_cols else 0)
                        key_src_2 = st.selectbox("병합 키 2 (원본)", ["(선택 안 함)"] + src_cols, index=src_cols.index(current_merge_keys[1][0]) + 1 if current_merge_keys[1][0] in src_cols else 0)
                    with c2:
                        st.write("`송장(내보내기)` 컬럼")
                        key_inv_1 = st.selectbox("병합 키 1 (송장)", ["(선택 안 함)"] + invoice_cols, index=invoice_cols.index(current_merge_keys[0][1]) + 1 if current_merge_keys[0][1] in invoice_cols else 0)
                        key_inv_2 = st.selectbox("병합 키 2 (송장)", ["(선택 안 함)"] + invoice_cols, index=invoice_cols.index(current_merge_keys[1][1]) + 1 if current_merge_keys[1][1] in invoice_cols else 0)
                    
                    merge_keys.append((key_src_1, key_inv_1))
                    merge_keys.append((key_src_2, key_inv_2))
                    new_rules['merge_keys'] = merge_keys

                    # --- 2. 필드 매핑 ---
                    st.subheader("2. 필드 매핑")
                    st.info("'일괄 양식'의 각 필드를 어떤 파일에서 가져올지 설정합니다.")
                    field_map = {}
                    options_map = ["(선택 안 함)"] + \
                                  [f"원본::{col}" for col in src_cols] + \
                                  [f"송장::{col}" for col in invoice_cols]
                    
                    current_field_map = current_mapping.get("field_map", {})
                    for col in bulk_cols:
                        default_val = "(선택 안 함)"
                        if col in current_field_map:
                            source_type, source_col = current_field_map[col]
                            default_val = f"{source_type}::{source_col}"
                        
                        default_idx = options_map.index(default_val) if default_val in options_map else 0
                        
                        selected = st.selectbox(f"'{col}' (일괄) <── ", options_map, index=default_idx, key=f"bm_{col}")
                        
                        if selected != "(선택 안 함)":
                            source_type_str, source_col_str = selected.split("::")
                            field_map[col] = (source_type_str, source_col_str)
                    new_rules['field_map'] = field_map

                    # --- 3. 변환 규칙 (쇼핑몰 코드) (질문 2) ---
                    st.subheader("3. 변환 규칙 (예: 쇼핑몰 코드)")
                    st.info("'수집처' 같은 값을 '쇼핑몰 코드'로 변환하는 규칙입니다.")
                    
                    current_transform = current_mapping.get("transform", {})
                    transform = {}
                    
                    c1, c2 = st.columns(2)
                    default_src = current_transform.get('source_col', "(선택 안 함)")
                    default_trg = current_transform.get('target_col', "(선택 안 함)")
                    
                    transform['source_col'] = c1.selectbox("기준 컬럼 (원본)", ["(선택 안 함)"] + src_cols, 
                                                           index=src_cols.index(default_src) + 1 if default_src in src_cols else 0, key="tr_src")
                    transform['target_col'] = c2.selectbox("적용 컬럼 (일괄)", ["(선택 안 함)"] + bulk_cols, 
                                                           index=bulk_cols.index(default_trg) + 1 if default_trg in bulk_cols else 0, key="tr_trg")
                    
                    default_rules_str = "\n".join([f"{k}={v}" for k, v in current_transform.get('rules', {}).items()])
                    if not default_rules_str:
                        default_rules_str = "네이버스마트스토어=00001\n카카오 선물하기=00003\n쿠팡=00004"
                        
                    transform_rules_str = st.text_area(
                        "변환 규칙 (한 줄에 하나씩, 예: 네이버=00001)", 
                        value=default_rules_str,
                        height=100
                    )
                    
                    rules_map = {}
                    for line in transform_rules_str.split("\n"):
                        if "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip():
                                rules_map[k.strip()] = v.strip()
                    transform['rules'] = rules_map
                    new_rules['transform'] = transform
                    
                    if st.form_submit_button("✅ 이카운트 일괄 양식 매핑 저장"):
                        database.save_mapping("bulk_ecount", new_rules)
                        st.session_state.mappings["bulk_ecount"] = new_rules
                        st.success("저장 완료!")
                        st.json(new_rules)