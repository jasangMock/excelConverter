import io
import pandas as pd
import streamlit as st
import msoffcrypto              # 엑셀 암호를 해제해주는 열쇠 도구

from xlrd import XLRDError


def load_headers(uploaded_file, header_row_idx=0, password=None):
    """
    업로드된 파일(CSV 또는 엑셀)에서 헤더(컬럼명) 목록을 읽어옵니다.
    암호화된 엑셀 파일 처리를 지원하며, 불필요한 컬럼을 필터링합니다.
    """
    if uploaded_file is None:
        return None

    try:
        uploaded_file.seek(0)  # 파일 포인터를 처음으로 되돌립니다.

        # 1. CSV 파일 처리
        if uploaded_file.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='cp949', header=header_row_idx, nrows=0)

        # 2. 엑셀 파일 처리
        else:
            target_file = uploaded_file

            # (A) 암호 해제 시도
            if password:
                try:
                    decrypted_workbook = io.BytesIO()
                    office_file = msoffcrypto.OfficeFile(uploaded_file)
                    office_file.load_key(password=password)
                    office_file.decrypt(decrypted_workbook)

                    decrypted_workbook.seek(0)
                    target_file = decrypted_workbook
                except Exception:
                    st.error("🔒 비밀번호가 틀렸습니다.")
                    return None

            # (B) 엑셀 읽기
            try:
                df = pd.read_excel(target_file, header=header_row_idx, nrows=0)
            except XLRDError as e:
                if "encrypted" in str(e):
                    st.warning("🔒 암호화된 파일입니다. 비밀번호를 입력해주세요.")
                    return None
                raise e
            except Exception as e:
                if "encrypted" in str(e) or "password" in str(e).lower():
                    st.warning("🔒 암호화된 파일입니다. 비밀번호를 입력해주세요.")
                    return None
                raise e

        # "Unnamed: ..." 또는 빈 컬럼 필터링
        raw_columns = list(df.columns)
        return [col for col in raw_columns if str(col).strip() and not str(col).startswith("Unnamed:")]

    except Exception as e:
        st.error(f"파일 헤더를 읽는 중 오류 발생: {e}")
        return None

def load_data_merged_header(uploaded_file, start_row_idx=1): 
    """
    2줄 이상으로 병합된 복잡한 헤더를 깔끔한 1줄 헤더로 변환하여 읽어옵니다.
    - 줄바꿈 문자(\n) 제거 기능 포함
    - 세로 병합(값이 동일) -> 하나로
    - 계층형(값이 다름) -> 이어붙임
    """
    try:
        # 1. 2줄을 헤더로 읽어옵니다.
        df = pd.read_excel(uploaded_file, header=[start_row_idx, start_row_idx + 1])
        
        new_columns = []
        
        # 2. 멀티 인덱스 컬럼 정리
        for col in df.columns:
            # [수정 포인트] 값을 가져오자마자 줄바꿈(\n)부터 제거하고 공백(strip)을 정리합니다.
            # 이렇게 해야 "No.\n" 와 "No." 가 같은 값으로 인식됩니다.
            top_level = str(col[0]).replace('\n', '').strip() if pd.notna(col[0]) else ""
            bottom_level = str(col[1]).replace('\n', '').strip() if pd.notna(col[1]) else ""
            
            # ------------------------------------------------------------------
            # 로직 시작 (이제 깨끗한 문자열로 비교합니다)
            # ------------------------------------------------------------------
            
            # [CASE 1] 세로 병합 (위/아래 텍스트가 줄바꿈 제거 후 똑같은 경우)
            if top_level == bottom_level:
                new_columns.append(top_level)

            # [CASE 2] 일반적인 세로 병합 (아랫줄이 비어있음)
            elif "Unnamed" in bottom_level or bottom_level == "nan" or bottom_level == "":
                new_columns.append(top_level)

            # [CASE 3] 상위 헤더가 비어있는 경우
            elif "Unnamed" in top_level or top_level == "nan" or top_level == "":
                new_columns.append(bottom_level)
            
            # [CASE 4] 진짜 계층형 헤더 (위/아래 값이 다름)
            else:
                clean_name = f"{top_level}_{bottom_level}"
                new_columns.append(clean_name)
        
        # 3. 정리된 컬럼 적용
        df.columns = new_columns
        
        # 디버깅용: 최종 컬럼 확인 (필요 시 주석 해제)
        # print("Final Columns:", df.columns.tolist())
        
        return df

    except Exception as e:
        print(f"Error merging headers: {e}")
        return None


def rules_to_dataframe(rules_dict, default_list):
    """딕셔너리 형태의 규칙을 DataFrame으로 변환"""
    if rules_dict:
        data = [{"수집처명": k, "쇼핑몰코드": v} for k, v in rules_dict.items()]
    else:
        data = default_list
    return pd.DataFrame(data)

def dataframe_to_rules(df):
    """DataFrame을 저장용 딕셔너리로 변환"""
    rule_dict = {}
    for _, row in df.iterrows():
        key = str(row["수집처명"]).strip()
        val = str(row["쇼핑몰코드"]).strip()
        
        # 유효성 검사 (빈 값 제외)
        if key and val and key.lower() != "none" and val.lower() != "none":
            rule_dict[key] = val
    return rule_dict