import io
import pandas as pd
import streamlit as st
import msoffcrypto              # 엑셀 암호를 해제해주는 열쇠 도구

from xlrd import XLRDError


def load_data_v2(uploaded_file, is_merged=False):
    if uploaded_file is None: return None
    
    try:
        # 일단 헤더 없이 전체를 읽어옵니다.
        raw_df = pd.read_excel(uploaded_file, header=None)
        
        # 🔍 진짜 제목 줄(Index) 찾기 로직
        header_row_idx = 0
        target_keywords = ['수하인', '운송장번호', '물품명', '이름']
        
        for idx, row in raw_df.iterrows():
            # 줄 내의 모든 값을 문자열로 합쳐서 키워드가 있는지 확인
            row_str = " ".join(row.astype(str))
            if any(key in row_str for key in target_keywords):
                header_row_idx = idx
                break
        
        st.info(f"💡 시스템이 분석한 제목 줄 위치: {header_row_idx + 1}행")

        if is_merged:
            # 찾은 위치(header_row_idx)부터 2줄을 헤더로 처리
            header_part = raw_df.iloc[header_row_idx : header_row_idx + 2]
            
            new_cols = []
            for i in range(len(raw_df.columns)):
                top = str(header_part.iloc[0, i]).replace('\n', '').strip() if pd.notna(header_part.iloc[0, i]) else ""
                bot = str(header_part.iloc[1, i]).replace('\n', '').strip() if pd.notna(header_part.iloc[1, i]) else ""
                
                # Unnamed 처리
                top = "" if "Unnamed" in top or top == "nan" else top
                bot = "" if "Unnamed" in bot or bot == "nan" else bot
                
                if top == bot or not bot: new_cols.append(top if top else f"Col_{i}")
                elif not top: new_cols.append(bot)
                else: new_cols.append(f"{top}_{bot}")

            # 헤더 2줄 다음부터 데이터로 슬라이싱
            df = raw_df.iloc[header_row_idx + 2 :].copy()
            df.columns = new_cols
        else:
            # 병합 셀이 아닌 경우 찾은 줄 하나만 헤더로 사용
            df = raw_df.iloc[header_row_idx + 1 :].copy()
            df.columns = raw_df.iloc[header_row_idx]

        # 데이터 정리: 모든 값이 비어있는 행 제거
        df = df.dropna(how='all').reset_index(drop=True)
        return df

    except Exception as e:
        st.error(f"지능형 로드 중 오류 발생: {e}")
        return None


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

# 수량 데이터를 깨끗하게 처리하는 헬퍼 함수
def clean_qty(val):
    try:
        # 1.0 같은 값을 1로 변환한 뒤 문자열로 반환
        return str(int(float(val)))
    except:
        return str(val)


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
        # [수정 부분] 필터링을 제거하고 모든 컬럼을 가져옵니다.
        # 'Unnamed: 1' 처럼 나오는 값들을 실제 빈 문자열("")로 치환하여 반환할 수 있습니다.
        raw_columns = list(df.columns)

# 'Unnamed'로 시작하는 컬럼은 실제 엑셀에서 헤더가 비어있는 칸입니다.
        # 이를 빈 문자열로 바꾸어 리턴하여 매핑 설정 시에도 보이게 합니다.
        processed_columns = [
            "" if str(col).startswith("Unnamed:") else str(col) 
            for col in raw_columns
        ]
        return processed_columns

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