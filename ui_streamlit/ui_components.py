import streamlit as st
import database
from utils import load_headers  # 아까 만든 load_headers 함수 가져오기

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
            # (3) 비밀번호 입력 (필요시)
            pwd = st.text_input("파일 비밀번호 (암호가 걸린 경우만 입력)", type="password", key=f"pwd_{template_key}")
            
            # (4) 헤더 분석 (utils의 함수 사용)
            headers = load_headers(uploaded_file, header_row_idx=row_idx, password=pwd)
            
            if headers:
                st.write("감지된 헤더:", headers)
                # (5) 저장 버튼
                if st.button("✅ 이 양식 저장", key=f"save_{template_key}"):

# [수정 포인트] 헤더 리스트만 저장하지 말고, 줄 번호도 같이 묶어서 저장!
                    template_data = {
                        "headers": headers,       # 컬럼 이름들
                        "header_row_idx": row_idx # 몇 번째 줄인지 (0, 1, 2...)
                    }

                    database.save_template(template_key,template_data)
                  # 세션에도 동일하게 업데이트
                    st.session_state.templates[template_key] = template_data
                    st.success("저장되었습니다! (줄 번호 설정 포함)")
                    st.rerun()