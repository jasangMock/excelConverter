import pandas as pd
import io
import streamlit as st
import constants as C
import utils as U

  # --- 유틸리티 및 파일 처리 함수 ---



# --- 핵심 비즈니스 로직 ---

def convert_to_rosen(df_data, mapping_rules):
    """ 
    이카운트 -> 로젠 변환 
    (1:1 변환이므로 별도 식별자 매칭 불필요) 
    """
    out = pd.DataFrame()
    
    # 1. 사용자 설정 매핑 적용
    simple_map = mapping_rules.get("simple_map", {})
    for rosen_col, source_col in simple_map.items():
        if source_col and source_col != "(선택 안 함)" and source_col in df_data.columns:
            out[rosen_col] = df_data[source_col]
        else:
            out[rosen_col] = "" # 빈 값 처리

    # 2. 상수 값을 사용하여 고정값 적용
    out['택배운임'] = C.ROSEN_SHIPPING_COST
    out['운임구분'] = C.ROSEN_COST_TYPE
    
    # 3. 특수 매핑 로직 (필요 시 추가)

    # 4. 파일 분리 (수집처 기준)
    split_col = mapping_rules.get("split_col")
    if split_col and split_col in df_data.columns:
        st.info(f"'{split_col}' 컬럼을 기준으로 파일(네이버, 카카오, 쿠팡)을 분리합니다.")
        
        df_naver = out[df_data[split_col].str.contains("네이버", na=False)]
        df_kakao = out[df_data[split_col].str.contains("카카오", na=False)]
        df_coupang = out[df_data[split_col].str.contains("쿠팡", na=False)]
        
        return {"naver": df_naver, "kakao": df_kakao, "coupang": df_coupang}
    
    return {"single_file": out}


def convert_to_bulk_upload(df_ecount, df_invoice, mapping_rules):
    """ 
    이카운트 + 내보내기(송장) -> 일괄 양식
    식별 로직: 수취인 + 연락처 + 품목명 + 메시지
    """
    cols_cfg = mapping_rules.get("match_columns", {})
    
    e_name = cols_cfg.get('ecount_name', '수취인')
    e_contact = cols_cfg.get('ecount_contact', '수취인 연락처1')
    e_item = cols_cfg.get('ecount_item', '품목명(ERP)')
    e_msg = cols_cfg.get('ecount_msg', '배송요청사항')
    
    i_name = cols_cfg.get('invoice_name', '수하인명')
    i_contact = cols_cfg.get('invoice_contact', '수하인휴대폰')
    i_item = cols_cfg.get('invoice_item', '품목명')
    i_msg = cols_cfg.get('invoice_msg', '배송메세지')

    missing = []
    for c in [e_name, e_contact, e_item, e_msg]:
        if c not in df_ecount.columns: missing.append(f"이카운트-[{c}]")
    for c in [i_name, i_contact, i_item, i_msg]:
        if c not in df_invoice.columns: missing.append(f"송장-[{c}]")
    
    if missing:
        st.error(f"매칭에 필요한 컬럼이 파일에 없습니다: {', '.join(missing)}")
        st.warning("팁: '설정 > 3. 매핑 설정'에서 매칭에 사용할 컬럼 이름을 정확히 지정해주세요.")
        return None

    # 키 생성
    df_ecount['__MATCH_KEY__'] = (
        df_ecount[e_name].apply(U.clean_text) + "_" +
        df_ecount[e_contact].apply(U.clean_text) + "_" +
        df_ecount[e_item].apply(U.clean_text) + "_" +
        df_ecount[e_msg].apply(U.clean_text)
    )
    
    df_invoice['__MATCH_KEY__'] = (
        df_invoice[i_name].apply(U.clean_text) + "_" +
        df_invoice[i_contact].apply(U.clean_text) + "_" +
        df_invoice[i_item].apply(U.clean_text) + "_" +
        df_invoice[i_msg].apply(U.clean_text)
    )

    merged = pd.merge(df_ecount, df_invoice, on='__MATCH_KEY__', how='left', suffixes=('_erp', '_inv'))
    out = pd.DataFrame()
    
    transform = mapping_rules.get("transform", {})
    src_col = transform.get('source_col', '수집처')
    
    if src_col in df_ecount.columns:
        target_col_name = src_col if src_col in merged.columns else f"{src_col}_erp"
        if target_col_name in merged.columns:
            rules = transform.get('rules', {})
            out['쇼핑몰코드'] = merged[target_col_name].map(rules).fillna("")
        else:
            out['쇼핑몰코드'] = ""
    else:
        out['쇼핑몰코드'] = ""

    ecount_std_cols = ['주문번호', '묶음주문번호', '배송방법코드']
    for col in ecount_std_cols:
        if col in merged.columns: out[col] = merged[col]
        elif f"{col}_erp" in merged.columns: out[col] = merged[f"{col}_erp"]
        else: out[col] = ""

    inv_no_col = '운송장번호'
    if inv_no_col in merged.columns: out['송장번호'] = merged[inv_no_col]
    elif f"{inv_no_col}_inv" in merged.columns: out['송장번호'] = merged[f"{inv_no_col}_inv"]
    else: out['송장번호'] = ""

    return out