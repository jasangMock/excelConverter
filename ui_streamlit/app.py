import database 
import os
import pandas as pd             # 엑셀 데이터를 다루는 핵심 라이브러리
import streamlit as st          # 화면에 에러나 경고를 띄우기 위해 필요
import io                       # 파일을 디스크에 저장하지 않고 '메모리'에서만 다루기 위한 도구
from xlrd import XLRDError
from utils import load_headers  # utils.py에서 load_headers 함수 가져오기
from ui_components import render_template_manager # UI 컴포넌트 함수 가져오기
import constants as C  # 상수 파일 가져오기

# --- 0. DB 초기화 및 설정 로드 ---
database.init_db()



# 현재 파이썬이 실행되는 위치(작업 디렉토리) 출력
print("현재 파이썬 작업 경로:", os.getcwd())
# 파이썬이 바라보는 DB 파일의 절대 경로 출력
print("파이썬이 여는 DB 경로:", os.path.abspath('Excel_converter.db'))


def load_config_to_session():
    templates, mappings = database.load_all_config_from_db()
    print("Loaded templates from DB:", templates)
    print("Loaded mappings from DB:", mappings)
    st.session_state['templates'] = templates
    st.session_state['mappings'] = mappings

#if 'templates' not in st.session_state:
#    load_config_to_session()
load_config_to_session()
# --- 유틸리티 함수 ---

    
def load_data(uploaded_file, header_row_idx=0):
    """ (수정됨) header_row_idx 반영하여 데이터 읽기 """
    if uploaded_file is None: return None
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                return pd.read_csv(uploaded_file, encoding='cp949', header=header_row_idx)
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding='utf-8-sig', header=header_row_idx)
        else:
            return pd.read_excel(uploaded_file, header=header_row_idx)
    except Exception as e:
        st.error(f"파일 데이터를 읽는 중 오류가 발생했습니다: {e}")
        return None

def to_excel_bytes(df):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    bio.seek(0)
    return bio.getvalue()

def clean_text(text):
    """매칭을 위해 공백 제거 및 문자열 변환"""
    return str(text).replace(" ", "").strip()

# --- 1. 로젠 변환 로직 (요구사항 반영) ---

def convert_to_rosen(df_data, mapping_rules):
    """ 
    이카운트 -> 로젠 변환 
    (1:1 변환이므로 별도 식별자 매칭 불필요) 
    """
    out = pd.DataFrame()
    
    # 1. 사용자 설정 매핑 적용
    # (주의: "(선택 안 함)"인 경우 빈 문자열로 처리)
    simple_map = mapping_rules.get("simple_map", {})
    for rosen_col, source_col in simple_map.items():
        if source_col and source_col != "(선택 안 함)" and source_col in df_data.columns:
            out[rosen_col] = df_data[source_col]
        else:
            out[rosen_col] = "" # 빈 값 처리

    # 2. 상수 값을 사용하여 고정값 적용
    out['택배운임'] = C.ROSEN_SHIPPING_COST
    out['운임구분'] = C.ROSEN_COST_TYPE
    
    # 3. 특수 매핑 로직 (수취인 연락처 -> 전화번호 & 핸드폰번호 둘 다 넣기)
    # (매핑 규칙에서 '수하인전화번호'와 '수하인핸드폰번호'가 각각 매핑되어 있다면 위 1번에서 처리됨)
    # 만약 사용자가 매핑을 안 했을 경우를 대비해 로직을 넣을 수도 있지만, 
    # 현재는 사용자가 '매핑 설정' 탭에서 직접 연결하는 구조를 따릅니다.

    # 4. 파일 분리 (수집처 기준)
    split_col = mapping_rules.get("split_col")
    if split_col and split_col in df_data.columns:
        st.info(f"'{split_col}' 컬럼을 기준으로 파일(네이버, 카카오, 쿠팡)을 분리합니다.")
        
        # 데이터가 없는 경우 빈 DF 반환 방지
        df_naver = out[df_data[split_col].str.contains("네이버", na=False)]
        df_kakao = out[df_data[split_col].str.contains("카카오", na=False)]
        df_coupang = out[df_data[split_col].str.contains("쿠팡", na=False)]
        
        return {"naver": df_naver, "kakao": df_kakao, "coupang": df_coupang}
    
    return {"single_file": out}


# --- 2. 일괄 양식 변환 로직 (핵심 수정: 4가지 속성 매칭) ---

def convert_to_bulk_upload(df_ecount, df_invoice, mapping_rules):
    """ 
    이카운트 + 내보내기(송장) -> 일괄 양식
    식별 로직: 수취인 + 연락처 + 품목명 + 메시지
    """
    
    # --- 1. 매핑 설정에서 컬럼명 가져오기 ---
    # (사용자가 '매핑 설정' 탭에서 지정한 컬럼명을 가져옵니다)
    # 예: Ecount의 '수취인' 컬럼이 실제 파일에선 '받는분'일 수 있음.
    
    cols_cfg = mapping_rules.get("match_columns", {})
    
    # 이카운트 쪽 컬럼명
    e_name = cols_cfg.get('ecount_name', '수취인')
    e_contact = cols_cfg.get('ecount_contact', '수취인 연락처1')
    e_item = cols_cfg.get('ecount_item', '품목명(ERP)')
    e_msg = cols_cfg.get('ecount_msg', '배송요청사항')
    
    # 송장(내보내기) 쪽 컬럼명
    i_name = cols_cfg.get('invoice_name', '수하인명')
    i_contact = cols_cfg.get('invoice_contact', '수하인휴대폰') # 혹은 수하인전화
    i_item = cols_cfg.get('invoice_item', '품목명')
    i_msg = cols_cfg.get('invoice_msg', '배송메세지')

    # 필수 컬럼 확인
    missing = []
    for c in [e_name, e_contact, e_item, e_msg]:
        if c not in df_ecount.columns: missing.append(f"이카운트-[{c}]")
    for c in [i_name, i_contact, i_item, i_msg]:
        if c not in df_invoice.columns: missing.append(f"송장-[{c}]")
    
    if missing:
        st.error(f"매칭에 필요한 컬럼이 파일에 없습니다: {', '.join(missing)}")
        st.warning("팁: '설정 > 3. 매핑 설정'에서 매칭에 사용할 컬럼 이름을 정확히 지정해주세요.")
        return None

    # --- 2. 복합 키(Composite Key) 생성 ---
    # 4가지 정보를 합쳐서 '고유 ID'를 만듭니다. (공백 제거 등 전처리 포함)
    
    # 이카운트 키 생성
    df_ecount['__MATCH_KEY__'] = (
        df_ecount[e_name].apply(clean_text) + "_" +
        df_ecount[e_contact].apply(clean_text) + "_" +
        df_ecount[e_item].apply(clean_text) + "_" +
        df_ecount[e_msg].apply(clean_text)
    )
    
    # 송장 키 생성
    df_invoice['__MATCH_KEY__'] = (
        df_invoice[i_name].apply(clean_text) + "_" +
        df_invoice[i_contact].apply(clean_text) + "_" +
        df_invoice[i_item].apply(clean_text) + "_" +
        df_invoice[i_msg].apply(clean_text)
    )

    # --- 3. 병합 (Merge) ---
    # 이카운트(원본)를 기준으로 송장 정보를 옆에 붙입니다.
    merged = pd.merge(df_ecount, df_invoice, on='__MATCH_KEY__', how='left', suffixes=('_erp', '_inv'))
    
    # --- 4. 결과 데이터 생성 ---
    out = pd.DataFrame()
    
    # (1) 쇼핑몰 코드 (변환 규칙 적용)
    # 예: 수집처가 '네이버'면 '00001'
    transform = mapping_rules.get("transform", {})
    src_col = transform.get('source_col', '수집처') # 이카운트의 '수집처'
    
    if src_col in df_ecount.columns:
        # 병합된 데이터프레임에서도 해당 컬럼을 찾음 (이름 충돌 시 _erp가 붙었을 수 있음)
        target_col_name = src_col if src_col in merged.columns else f"{src_col}_erp"
        
        if target_col_name in merged.columns:
            rules = transform.get('rules', {})
            # 값이 없으면 원래 값 유지하거나 빈칸 (여기서는 룰에 없으면 빈칸)
            out['쇼핑몰코드'] = merged[target_col_name].map(rules).fillna("")
        else:
            out['쇼핑몰코드'] = ""
    else:
        out['쇼핑몰코드'] = ""

    # (2) 주문번호, 묶음주문번호, 배송방법코드 (이카운트에서 가져옴)
    # 사용자가 지정한 컬럼명을 써야 하지만, 우선 요구사항의 표준 이름을 찾습니다.
    ecount_std_cols = ['주문번호', '묶음주문번호', '배송방법코드']
    for col in ecount_std_cols:
        # 병합 과정에서 이름이 변경되었을 수 있으므로 확인
        if col in merged.columns:
            out[col] = merged[col]
        elif f"{col}_erp" in merged.columns:
            out[col] = merged[f"{col}_erp"]
        else:
            out[col] = "" # 없으면 빈 값

    # (3) 송장번호 (송장 파일에서 가져옴)
    # 송장 파일의 '운송장번호' 컬럼
    inv_no_col = '운송장번호' # (추후 매핑 설정 가능하게 변경 가능)
    if inv_no_col in merged.columns:
        out['송장번호'] = merged[inv_no_col]
    elif f"{inv_no_col}_inv" in merged.columns:
        out['송장번호'] = merged[f"{inv_no_col}_inv"]
    else:
        out['송장번호'] = "" # 매칭 실패했거나 컬럼이 없으면 빈 값

    return out


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
        
        # 설정 확인
        rules = st.session_state.mappings.get(C.MAP_ECOUNT_TO_ROSEN)
        if not rules:
            st.error("⚠️ '설정' 탭에서 [이카운트 -> 로젠] 매핑을 먼저 해주세요.")
        else:
            # 헤더 위치 지정 기능 추가
            row_idx = st.number_input("데이터 파일의 제목(Header)은 몇 번째 줄인가요?", min_value=1, value=1, step=1) - 1
            up_file = st.file_uploader("이카운트 주문 엑셀 업로드", key="run_ecount")
            
            if up_file:
                df = load_data(up_file, header_row_idx=row_idx)
                if df is not None:
                    if st.button("변환 실행"):
                        res = convert_to_rosen(df, rules)
                        
                        # 결과 출력 (3개로 분리된 것 or 1개)
                        cols = st.columns(3)
                        idx = 0
                        for name, df_res in res.items():
                            with cols[idx % 3]:
                                st.success(f"✅ {name} ({len(df_res)}건)")
                                st.dataframe(df_res.head(3), use_container_width=True)
                                st.download_button(
                                    f"⬇️ {name}_로젠.xlsx",
                                    data=to_excel_bytes(df_res),
                                    file_name=f"rosen_{name}.xlsx"
                                )
                            idx += 1

    # --- [실행] 일괄 양식 생성 ---
    with tab_bulk:
        st.subheader("이카운트 + 내보내기(송장) ➔ 일괄 양식")
        st.info("ℹ️ 수취인+연락처+품목+메시지가 모두 일치하는 주문을 자동으로 연결합니다.")
        
        rules_bulk = st.session_state.mappings.get(C.MAP_BULK_ECOUNT)
        if not rules_bulk:
            st.error("⚠️ '설정' 탭에서 [일괄 양식 매핑]을 먼저 해주세요.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                h1 = st.number_input("이카운트 파일 제목 줄 번호", min_value=1, value=1, key="h1") - 1
                up_erp = st.file_uploader("1) 이카운트 원본", key="bulk_erp")
            with c2:
                h2 = st.number_input("송장 파일 제목 줄 번호", min_value=1, value=1, key="h2") - 1
                up_inv = st.file_uploader("2) 로젠 내보내기(송장)", key="bulk_inv")
            
            if up_erp and up_inv:
                df_e = load_data(up_erp, header_row_idx=h1)
                df_i = load_data(up_inv, header_row_idx=h2)
                
                if df_e is not None and df_i is not None:
                    if st.button("일괄 양식 생성"):
                        final_df = convert_to_bulk_upload(df_e, df_i, rules_bulk)
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
    t1, t2, t3 = st.tabs([C.SETUP_TAB1_TITLE, C.SETUP_TAB2_TITLE, C.SETUP_TAB3_TITLE])

    # --- [설정] 1. 양식 등록 ---
    with t1:
        st.write("각 엑셀 파일의 헤더(제목) 정보를 등록합니다.")
        
        selected_tmp = st.selectbox("설정할 양식 선택", C.TEMPLATE_KEYS_IN_ORDER, format_func=lambda x: C.TEMPLATE_LABELS[x])

        # 선택된 양식에 해당하는 UI 컴포넌트를 렌더링합니다.
        if selected_tmp:
            render_template_manager(selected_tmp, C.TEMPLATE_LABELS[selected_tmp])

        # --- [설정] 2. 로젠 변환 매핑 ---
    with t2:
        st.subheader("이카운트 ➔ 로젠 매핑")
        
        src_cols = st.session_state.templates.get("ecount")
        tgt_cols = st.session_state.templates.get("rosen")
        
        if not src_cols or not tgt_cols:
            st.error("먼저 '1. 양식 등록'에서 이카운트와 로젠 양식을 등록해주세요.")
        else:
            with st.form("map_rosen_form"):
                # 단순 매핑
                st.write("##### 1:1 컬럼 연결")
                current_map = st.session_state.mappings.get(C.MAP_ECOUNT_TO_ROSEN, {}).get("simple_map", {})
                new_simple_map = {}
                
                # 타겟(로젠) 컬럼을 기준으로 소스(이카운트)를 선택
                for t_col in tgt_cols:
                    # 고정값인 경우 스킵 가능하나, 보여주는게 명확함
                    if t_col in ['택배운임', '운임구분']:
                        st.text_input(f"{t_col} (고정값)", value="2900" if t_col=='택배운임' else "신용", disabled=True)
                        continue
                        
                    prev_val = current_map.get(t_col, "(선택 안 함)")
                    idx = 0
                    if prev_val in ["(선택 안 함)"] + src_cols:
                        idx = (["(선택 안 함)"] + src_cols).index(prev_val)
                    
                    val = st.selectbox(f"로젠 [{t_col}] <== 이카운트 [?]", ["(선택 안 함)"] + src_cols, index=idx, key=f"rm_{t_col}")
                    new_simple_map[t_col] = val
                
                st.write("##### 파일 분리 기준")
                # 수집처 컬럼 선택
                prev_split = st.session_state.mappings.get(C.MAP_ECOUNT_TO_ROSEN, {}).get("split_col", "(선택 안 함)")
                split_idx = (["(선택 안 함)"] + src_cols).index(prev_split) if prev_split in src_cols else 0
                split_col = st.selectbox("수집처(네이버/카카오 등) 구분 컬럼", ["(선택 안 함)"] + src_cols, index=split_idx)

                if st.form_submit_button("매핑 저장"):
                    full_rule = {"simple_map": new_simple_map, "split_col": split_col}
                    database.save_mapping(C.MAP_ECOUNT_TO_ROSEN, full_rule)
                    st.session_state.mappings[C.MAP_ECOUNT_TO_ROSEN] = full_rule
                    st.success("저장 완료")

    # --- [설정] 3. 일괄 양식 매칭 설정 ---
    with t3:
        st.subheader("일괄 양식 생성을 위한 '식별자 매칭' 설정")
        st.info("두 파일을 연결하기 위해, 의미가 같은 컬럼끼리 짝지어 주세요.")
        
        e_cols = st.session_state.templates.get("ecount")
        i_cols = st.session_state.templates.get("rosen_invoice")
        
        if not e_cols or not i_cols:
            st.error("이카운트와 로젠 내보내기 양식을 먼저 등록해주세요.")
        else:
            with st.form("bulk_match_form"):
                curr_match = st.session_state.mappings.get(C.MAP_BULK_ECOUNT, {}).get("match_columns", {})
                
                c1, c2 = st.columns(2)
                with c1: st.write("##### 이카운트 (원본)")
                with c2: st.write("##### 로젠 (내보내기)")

                # 1. 수취인 이름
                en = c1.selectbox("수취인 이름 컬럼", e_cols, index=e_cols.index(curr_match.get('ecount_name')) if curr_match.get('ecount_name') in e_cols else 0)
                in_ = c2.selectbox("수하인 이름 컬럼", i_cols, index=i_cols.index(curr_match.get('invoice_name')) if curr_match.get('invoice_name') in i_cols else 0)

                # 2. 연락처
                ec = c1.selectbox("연락처 컬럼", e_cols, index=e_cols.index(curr_match.get('ecount_contact')) if curr_match.get('ecount_contact') in e_cols else 0)
                ic = c2.selectbox("연락처(휴대폰) 컬럼", i_cols, index=i_cols.index(curr_match.get('invoice_contact')) if curr_match.get('invoice_contact') in i_cols else 0)
                
                # 3. 품목명
                ei = c1.selectbox("품목명 컬럼", e_cols, index=e_cols.index(curr_match.get('ecount_item')) if curr_match.get('ecount_item') in e_cols else 0)
                ii = c2.selectbox("품목명 컬럼", i_cols, index=i_cols.index(curr_match.get('invoice_item')) if curr_match.get('invoice_item') in i_cols else 0)

                # 4. 메시지
                em = c1.selectbox("배송메시지 컬럼", e_cols, index=e_cols.index(curr_match.get('ecount_msg')) if curr_match.get('ecount_msg') in e_cols else 0)
                im = c2.selectbox("배송메시지 컬럼", i_cols, index=i_cols.index(curr_match.get('invoice_msg')) if curr_match.get('invoice_msg') in i_cols else 0)

                st.write("##### 쇼핑몰 코드 변환 규칙")
                st.write("예: 네이버스마트스토어=00001 (한 줄에 하나씩)")
                prev_rules = st.session_state.mappings.get(C.MAP_BULK_ECOUNT, {}).get("transform", {}).get("rules", {})
                rules_str = "\n".join([f"{k}={v}" for k,v in prev_rules.items()])
                txt_rules = st.text_area("변환 규칙 입력", value=rules_str if rules_str else "네이버스마트스토어=00001\n카카오 선물하기=00003\n쿠팡=00004")

                if st.form_submit_button("설정 저장"):
                    # 규칙 파싱
                    rule_dict = {}
                    for line in txt_rules.split("\n"):
                        if "=" in line:
                            k, v = line.split("=", 1)
                            rule_dict[k.strip()] = v.strip()

                    full_cfg = {
                        "match_columns": {
                            "ecount_name": en, "ecount_contact": ec, "ecount_item": ei, "ecount_msg": em,
                            "invoice_name": in_, "invoice_contact": ic, "invoice_item": ii, "invoice_msg": im
                        },
                        "transform": {
                            "source_col": "수집처", # 이카운트는 보통 '수집처' 고정이라 가정 (필요시 선택 가능하게 변경)
                            "rules": rule_dict
                        }
                    }
                    database.save_mapping(C.MAP_BULK_ECOUNT, full_cfg)
                    st.session_state.mappings[C.MAP_BULK_ECOUNT] = full_cfg
                    st.success("설정 저장 완료")