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