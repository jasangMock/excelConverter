import pandas as pd
import io
import streamlit as st
import constants as C
import utils as U

  # --- 유틸리티 및 파일 처리 함수 ---



# --- 핵심 비즈니스 로직 ---
def convert_to_rosen(df_data, mapping_rules):
    """ 
    이카운트 -> 로젠 변환 (리스트 매핑 구조 + 합포장 텍스트 강조)
    """
    # 1. simple_map 리스트 가져오기
    simple_map_list = mapping_rules.get("simple_map", [])
    
    if not simple_map_list:
        st.warning("매핑 설정 정보가 없습니다.")
        return {"single_file": pd.DataFrame()}

    # [중요] 이카운트 파일에서 '수량'을 나타내는 컬럼명을 찾습니다.
    # 보통 "수량"이지만, 사용자가 올린 파일에 따라 다를 수 있으니 확인이 필요합니다.
    qty_col_name = "수량"  # 기본값
    if "수량(소단위)" in df_data.columns: # 이카운트 변형 케이스 대비
        qty_col_name = "수량(소단위)"

    output_columns = []
    output_series_list = []

    # 2. 매핑 리스트를 순서대로 순회하며 컬럼 생성
    for rule in simple_map_list:
        target_col = rule.get("target", "")  # 로젠(타겟) 컬럼명
        source_col = rule.get("source", "")  # 이카운트(소스) 컬럼명

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
            # 데이터를 복사해서 가져옵니다.
            #col_data = df_data[source_col].astype(str).copy()
            # (1) NaN 값을 빈 값("")으로 채우기
            col_data = df_data[source_col].fillna("")
            
            # (2) 문자로 변환 후, 끝이 .0으로 끝나는 숫자 형태 제거 (2.0 -> 2)
            # regex=True는 정규표현식을 쓴다는 뜻입니다.
            col_data = col_data.astype(str).replace(r'\.0$', '', regex=True)
            
            # (3) 혹시라도 "nan"이라는 글자로 변한 게 있다면 빈 값으로 치환
            col_data = col_data.replace('nan', '')
            
            # ---------------------------------------------------------------
            # [수정된 로직] 품목명이고, 수량이 1보다 크면 접두어(★) 추가
            # ---------------------------------------------------------------
            if target_col == "품목명" and qty_col_name in df_data.columns:
                # 수량 컬럼을 숫자로 변환 (에러 발생 시 1로 취급)
                qtys = pd.to_numeric(df_data[qty_col_name], errors='coerce').fillna(1)
                
                # 수량이 1보다 큰 행의 인덱스(True/False)를 찾음
                mask = qtys > 1
                
                # 해당 행들에 대해서만 품목명 앞에 "★[N개]" 붙이기
                # 예: "막걸리" -> "★[2개] 막걸리"
                col_data.loc[mask] =   col_data.loc[mask] + "★[" + qtys.loc[mask].astype(int).astype(str) + "개] "
            # ---------------------------------------------------------------
            if target_col == "박스수량":
                col_data = pd.Series([1] * len(df_data))
        # (C) 매핑되지 않았거나 빈 헤더인 경우
        else:
            col_data = pd.Series([""] * len(df_data))

        output_columns.append(target_col)
        output_series_list.append(col_data)

    # 3. DataFrame 생성 (중복/빈 헤더 허용)
    out = pd.concat(output_series_list, axis=1)
    out.columns = output_columns 

    # 4. 파일 분리 (수집처 기준)
    split_col = mapping_rules.get("split_col")
    if split_col and split_col in df_data.columns:
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

    print("df_ecount Columns:", df_ecount.columns.tolist())
    print("df_invoice Columns:", df_invoice.columns.tolist())
    print("")

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
        'item': '쇼핑물상품명',  'name': '수취인', 
        'addr': '주소', 'contact': '수취인연락처1', 'msg': '배송요청사항'
    }.items()}
    
    i_map = {k: cols_cfg.get(f'invoice_{k}', v) for k, v in {
        'item': '물품명', 'name': '수하인_이름', 
        'addr': '수하인_주소', 'contact': '수하인_휴대폰', 'msg': '배송메세지'
    }.items()}


    print("E-Map:", e_map)
    print("I-Map:", i_map)
    print("")

    # --- 3. 필수 컬럼 체크 ---
    missing = [f"이카운트-{c}" for c in e_map.values() if c not in df_ecount.columns] + \
              [f"송장-{c}" for c in i_map.values() if c not in df_invoice.columns]
    
    if missing:
        st.error(f"매칭에 필요한 컬럼이 파일에 없습니다: {', '.join(missing)}")
        return None

    # --- 4. 키 생성 (최종 수정: 주소 표준화 & nan 해결) ---
    def build_key(row, m):
        # [1] 주소 표준화 내부 함수 (경기도 -> 경기, 공백 제거)
        def normalize_addr(addr):
            if not isinstance(addr, str): return ""
            
            # 1. 공백 제거 (띄어쓰기 차이 방지)
            addr = addr.replace(" ", "")
            
            # 2. 행정구역 표준화 (긴 이름 -> 짧은 이름으로 통일)
            # 앞부분이 이 단어로 시작하면 짧은 단어로 바꿔치기 합니다.
            mapping = {
                "서울특별시": "서울", "경기도": "경기", "강원도": "강원",
                "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전라남도": "전남",
                "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "제주도": "제주",
                "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
                "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종"
            }
            
            for long_name, short_name in mapping.items():
                if addr.startswith(long_name):
                    addr = addr.replace(long_name, short_name, 1)
                    break
            return addr

        # [2] 데이터 전처리
        # 주소: 위에서 만든 함수로 표준화 후 앞 6글자만 사용 (경기도->경기 로 줄었으니 1글자 늘림)
        clean_address = normalize_addr(str(row[m['addr']]))[:6]
        
        # 메세지: nan 제거
        raw_msg = str(row[m['msg']])
        if raw_msg.lower() in ['nan', 'none', '']:
            clean_msg = ""
        else:
            clean_msg = U.clean_text(raw_msg)
            
        # [3] 최종 키 조합
        return "_".join([
            U.clean_text(str(row[m['name']])),       # 이름
            clean_address,                           # 표준화된 주소 (핵심!)
            U.clean_text(str(row[m['contact']]))[:7],# 전화번호
            U.clean_text(str(row[m['item']]))[:5],       # 상품명
         #   clean_quantity(row[m['qty']]),           # 수량
            clean_msg                                # 메세지
        ])

  # --- 4. 키 생성 (nan 제거 로직 추가됨) ---
    # (앞서 작성하신 build_key 함수가 여기에 있어야 합니다)
    
    # [1] 키 생성 실행
    df_ecount['__MATCH_KEY__'] = df_ecount.apply(lambda r: build_key(r, e_map), axis=1)
    df_invoice['__MATCH_KEY__'] = df_invoice.apply(lambda r: build_key(r, i_map), axis=1)

    # ==============================================================================
    # [디버깅용 코드 1] 병합 전(Before Merge) 키 생성 상태 확인
    # ==============================================================================
    import streamlit as st

    with st.expander("🔑 [1단계] 키 생성 결과 비교 (병합 전)", expanded=True):
        st.write("이카운트와 송장 파일에서 생성된 **매칭 키(__MATCH_KEY__)**를 비교합니다.")
        st.info("💡 팁: 양쪽의 키 모양이 **토씨 하나 안 틀리고 똑같아야** 매칭이 성공합니다.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 1️⃣ 이카운트 (ERP)")
            # 보기 편하게 __MATCH_KEY__를 맨 앞으로 가져와서 보여줍니다
            cols_e = ['__MATCH_KEY__'] + [c for c in df_ecount.columns if c != '__MATCH_KEY__']
            st.dataframe(df_ecount[cols_e].head())

        with col2:
            st.markdown("### 2️⃣ 택배 송장")
            # 보기 편하게 __MATCH_KEY__를 맨 앞으로 가져와서 보여줍니다
            cols_i = ['__MATCH_KEY__'] + [c for c in df_invoice.columns if c != '__MATCH_KEY__']
            st.dataframe(df_invoice[cols_i].head())
    # ==============================================================================


    # --- 5. 병합 및 결과 생성 ---
    merged = pd.merge(df_ecount, df_invoice, on='__MATCH_KEY__', how='left', suffixes=('_erp', '_inv'))


    # ==============================================================================
    # [디버깅용 코드 2] 병합 후(After Merge) 결과 확인
    # ==============================================================================
    with st.expander("🔍 [2단계] 병합된 데이터(Merged) 상세 확인", expanded=True):
        st.success(f"병합 완료! 총 {len(merged)}개의 행이 있습니다.")

        # 1. 컬럼 이름 확인하기
        st.write("📋 **전체 컬럼 이름 목록 (송장번호 컬럼명 확인용):**")
        st.code(merged.columns.tolist()) 

        # 2. 데이터프레임 시각화
        st.write("📊 **전체 데이터 미리보기:**")
        st.dataframe(merged)

        # 3. 매칭 키 확인
        st.write("🔑 **최종 병합된 키(__MATCH_KEY__) 확인:**")
        st.dataframe(merged[['__MATCH_KEY__']].head())
    # ==============================================================================
    
    print("Merged Columns:", merged.columns.tolist())
    print("")

    out = pd.DataFrame()
    
    # 쇼핑몰코드 변환
    transform = mapping_rules.get("transform", {})
    rules = transform.get('rules', {})
    src_col = get_merged_col(merged, transform.get('source_col', '수집처'))
    print("Source Column for Mall Code:", src_col  )
    print("")

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