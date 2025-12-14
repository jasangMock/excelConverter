import streamlit as st
import database
from utils import load_headers, load_data_merged_header  # 아까 만든 load_headers 함수 가져오기
def render_template_manager(template_key, label_text):
    """
    템플릿(양식) 하나를 관리하는 화면을 그리는 함수
    - template_key: "ecount", "rosen" 등 식별자
    - label_text: "이카운트 주문서", "로젠 송장" 등 화면 표시용 이름
    """
    
    # 1. 현재 상태 확인 (DB 정보가 세션에 있는지)
    saved_headers = st.session_state.templates.get(template_key)

    # [A] 이미 저장된 경우 -> 정보 보여주고 삭제 버튼 제공
    if saved_headers:
        st.info(f"✅ '{label_text}' 양식은 이미 설정되어 있습니다.")
        
        # 데이터를 보기 좋게 접어서 보여줌 (Expandable)
        with st.expander("등록된 헤더 정보 보기"):
            st.write(saved_headers)
        
        # 삭제 로직
        if st.button(f"🗑️ '{label_text}' 설정 삭제", key=f"del_{template_key}"):
            database.delete_template(template_key)
            if template_key in st.session_state.templates:
                del st.session_state.templates[template_key]
            st.rerun()

    # [B] 저장된 게 없는 경우 -> 업로드 및 등록 화면 제공
    else:
        st.warning(f"아직 '{label_text}' 설정이 없습니다. 파일을 등록해주세요.")
        
        # (1) 헤더 줄 번호 설정
        row_idx = st.number_input(
            f"'{label_text}' 파일의 제목 줄 번호 (보통 1)", 
            min_value=1, value=1, 
            key=f"row_{template_key}"
        ) - 1
        
        # (2) 파일 업로드
        uploaded_file = st.file_uploader(f"{label_text} 샘플 파일", key=f"up_{template_key}")
        
        if uploaded_file:
                    pwd = st.text_input("파일 비밀번호", type="password", key=f"pwd_{template_key}")
                    
                    # -------------------------------------------------------
                    # [수정 포인트] (4) 헤더 분석: 로젠이냐 아니냐에 따라 도구를 다르게 씀
                    # -------------------------------------------------------
                    headers = []
                    
                    # [CASE 1] 로젠 송장 (복잡한 병합 헤더)
                    if template_key == "rosen_invoice":
                        # 아까 만든 스마트 병합 함수 사용 (DataFrame을 반환함)
                        # 이 함수는 내부적으로 2줄을 읽어서 1줄로 합쳐줍니다.
                        df_temp = load_data_merged_header(uploaded_file, start_row_idx=row_idx)
                        
                        if df_temp is not None:
                            headers = df_temp.columns.tolist() # DataFrame의 컬럼만 뽑아서 리스트로
                    
                    # [CASE 2] 이카운트 등 일반 파일 (단순 1줄 헤더)
                    else:
                        # 기존에 쓰던 일반 로더 사용
                        headers = load_headers(uploaded_file, header_row_idx=row_idx, password=pwd)

                    # -------------------------------------------------------
                    
                    if headers:
                        st.write(f"감지된 헤더 ({len(headers)}개):", headers)
                        
                        # (5) 저장 버튼
                        if st.button("✅ 이 양식 저장", key=f"save_{template_key}"):
                            template_data = {
                                "headers": headers,       # 깔끔하게 정리된 헤더 이름들
                                "header_row_idx": row_idx # 시작 줄 위치
                            }
                            
                            database.save_template(template_key, template_data)
                            st.session_state.templates[template_key] = template_data
                            
                            st.success("저장되었습니다! (줄 번호 및 헤더 정보)")
                            st.rerun()