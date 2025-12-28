import pandas as pd
import io
import streamlit as st
import constants as C
import utils as U

  # --- 유틸리티 및 파일 처리 함수 ---



# --- 핵심 비즈니스 로직 ---


def convert_to_rosen(df_data, mapping_rules):
    """ 
    이카운트 -> 로젠 변환 (리스트 매핑 구조 반영)
    """
    # 1. simple_map 리스트 가져오기
    simple_map_list = mapping_rules.get("simple_map", [])
    
    if not simple_map_list:
        st.warning("매핑 설정 정보가 없습니다.")
        return {"single_file": pd.DataFrame()}

    output_columns = []
    output_series_list = []

    # 2. 매핑 리스트를 순서대로 순회하며 컬럼 생성
    for rule in simple_map_list:
        target_col = rule.get("target", "")  # 로젠의 컬럼명 (비어있을 수 있음)
        source_col = rule.get("source", "")  # 이카운트의 컬럼명 (또는 특수 값)

        # (A) 고정값 처리
        if source_col == "__FIXED_VALUE__":
            if target_col == C.ROSEN_DELIVERY_FEE_COL:
                val = C.ROSEN_SHIPPING_COST
            elif target_col == C.ROSEN_FEE_TYPE_COL:
                val = C.ROSEN_COST_TYPE
            else:
                val = ""
            col_data = pd.Series([val] * len(df_data))

        # (B) 이카운트 컬럼 매핑 처리
        elif source_col and source_col != C.NOT_SELECTED and source_col in df_data.columns:
            col_data = df_data[source_col]
        
        # (C) 매핑되지 않았거나 빈 헤더인 경우
        else:
            col_data = pd.Series([""] * len(df_data))

        output_columns.append(target_col)
        output_series_list.append(col_data)

    # 3. 모든 시리즈를 가로로 합쳐서 DataFrame 생성
    # axis=1로 합치면 리스트의 순서가 곧 엑셀의 컬럼 순서가 됩니다.
    out = pd.concat(output_series_list, axis=1)
    out.columns = output_columns  # 최종 헤더 설정 (빈 문자열 포함)

    # 4. 파일 분리 (수집처 기준)
    split_col = mapping_rules.get("split_col")
    if split_col and split_col in df_data.columns:
        # 가독성을 위해 info 메시지는 한 번만 출력
        # 원본 데이터(df_data)의 인덱스를 기준으로 out에서 필터링합니다.
        
        mask_naver = df_data[split_col].str.contains("스마트스토어", na=False)
        mask_kakao = df_data[split_col].str.contains("카카오", na=False)
        mask_coupang = df_data[split_col].str.contains("쿠팡", na=False)
        
        return {
            "naver": out[mask_naver],
            "kakao": out[mask_kakao],
            "coupang": out[mask_coupang]
        }
    
    return {"single_file": out}


def convert_to_bulk_upload(df_ecount, df_invoice, mapping_rules):
    # --- 1. 유틸리티 함수 정의 ---
    def get_merged_col(df, col_base, suffix="_erp"):
        """merged DF에서 원본 또는 접미사가 붙은 컬럼을 안전하게 가져옴"""
        if col_base in df.columns: return col_base
        if f"{col_base}{suffix}" in df.columns: return f"{col_base}{suffix}"
        return None

    def clean_quantity(val):
        """1.0 -> 1로 변환하는 로직 통합"""
        try:
            return str(int(float(val)))
        except (ValueError, TypeError):
            return U.clean_text(str(val))

    def format_numeric_str(series):
        """지수 표기법 방지 및 nan 제거"""
        return series.astype(str).str.split('.').str[0].replace(['nan', 'None'], '')

    # --- 2. 매핑 설정 로드 ---
    cols_cfg = mapping_rules.get("match_columns", {})
    
    # 설정값 매핑 (Dictionary로 관리하면 반복문 사용 가능)
    e_map = {k: cols_cfg.get(f'ecount_{k}', v) for k, v in {
        'item': '쇼핑물상품명', 'qty': '수량', 'name': '수취인', 
        'addr': '주소', 'contact': '수취인연락처1', 'msg': '배송요청사항'
    }.items()}
    
    i_map = {k: cols_cfg.get(f'invoice_{k}', v) for k, v in {
        'item': '물품명', 'qty': '박스수량', 'name': '수하인_이름', 
        'addr': '수하인_주소', 'contact': '수하인_휴대폰', 'msg': '배송메세지'
    }.items()}

    # --- 3. 필수 컬럼 체크 ---
    missing = [f"이카운트-{c}" for c in e_map.values() if c not in df_ecount.columns] + \
              [f"송장-{c}" for c in i_map.values() if c not in df_invoice.columns]
    
    if missing:
        st.error(f"매칭에 필요한 컬럼이 파일에 없습니다: {', '.join(missing)}")
        return None

    # --- 4. 키 생성 (개선된 방식) ---
    def build_key(row, m):
        return "_".join([
            U.clean_text(str(row[m['name']])),
            U.clean_text(str(row[m['addr']]))[:8],
            U.clean_text(str(row[m['contact']]))[:7],
            U.clean_text(str(row[m['item']])),
            clean_quantity(row[m['qty']]),
            U.clean_text(str(row[m['msg']]))
        ])

    df_ecount['__MATCH_KEY__'] = df_ecount.apply(lambda r: build_key(r, e_map), axis=1)
    df_invoice['__MATCH_KEY__'] = df_invoice.apply(lambda r: build_key(r, i_map), axis=1)

    # (디버깅 로직 생략 - 필요시 유지)

    # --- 5. 병합 및 결과 생성 ---
    merged = pd.merge(df_ecount, df_invoice, on='__MATCH_KEY__', how='left', suffixes=('_erp', '_inv'))
    
    out = pd.DataFrame()
    
    # 쇼핑몰코드 변환
    transform = mapping_rules.get("transform", {})
    rules = transform.get('rules', {})
    src_col = get_merged_col(merged, transform.get('source_col', '수집처'))
    out['쇼핑몰코드'] = merged[src_col].map(rules).fillna("") if src_col else ""

    # 표준 컬럼 복사
    for col in ['주문번호', '묶음주문번호']:
        target = get_merged_col(merged, col)
        out[col] = format_numeric_str(merged[target]) if target else ""

    out['배송방법코드'] = "KGB"

    # 송장번호 추출
    inv_col = get_merged_col(merged, '운송장번호', suffix="_inv")
    out['송장번호'] = format_numeric_str(merged[inv_col]) if inv_col else ""

    return out