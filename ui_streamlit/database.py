import sqlite3
import json
import streamlit as st
import os
DB_NAME = "excel_converter.db"

# 이 파일(database.py)이 있는 위치를 기준으로 DB 경로를 고정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)


def get_db_conn():
    """ 데이터베이스 커넥션을 반환합니다. """
    conn = sqlite3.connect(DB_PATH)
    #DB_NAME 이라는 파일이 없으면 자동으로 생성됨
    conn.row_factory = sqlite3.Row
    # 튜플에 접근할 때 컬럼명으로 접근 가능하게 설정
    return conn

def init_db():
    """ 앱 시작 시 호출, 테이블이 없으면 생성합니다. """
    conn = get_db_conn()
    with conn:
        # with을 사용하면 자동으로 트랜잭션 시작, 커밋/롤백 처리됨, 트랜잭션 관리 편리
        # 1. 양식(템플릿) 저장 테이블: (이름, [컬럼1, 컬럼2, ...])
        conn.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                name TEXT PRIMARY KEY,
                columns_json TEXT NOT NULL
            )
        """)
        # 2. 매핑 규칙 저장 테이블: (이름, {룰: 룰, ...})
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mappings (
                name TEXT PRIMARY KEY,
                rules_json TEXT NOT NULL
            )
        """)
    conn.close()
        ### **`conn.close()`의 4단계**
        # 1. 버퍼 플러시
        #    → 커밋 안 된 건 ROLLBACK (버림)
        #    → 커밋된 건 이미 디스크에 있음
        
        # 2. 파일 잠금 해제
        #    → 다른 프로세스가 접근 가능
        
        # 3. 파일 핸들 닫기
        #    → OS 자원 반환
        
        # 4. conn 객체 무효화
        #    → 더 이상 사용 불가

def save_template(name, columns_list):
    #templates라는 테이블에 name과 columns_json이라는 컬럼에 매개변수로 받은 
    # name과 columns_list를 json형태로 변환한 것을 저장
    """ 양식(헤더 리스트)을 DB에 저장/덮어쓰기 합니다. """

    print(f"DB에 저장할 템플릿 이름: {name}")
    print(f"DB에 저장할 템플릿 컬럼: {columns_list}")
    columns_json = json.dumps(columns_list,ensure_ascii=False) #한글 깨짐 방지
    conn = get_db_conn()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO templates (name, columns_json) VALUES (?, ?)",
            (name, columns_json)
        )
    conn.close()
    st.toast(f"✅ '{name}' 양식이 DB에 저장되었습니다.")

def save_mapping(name, rules_dict):
    #mappings라는 테이블에 name과 columns_json이라는 컬럼에 매개변수로 받은 
    # name과 columns_list를 json형태로 변환한 것을 저장
    """ 매핑 규칙(딕셔너리)을 DB에 저장/덮어쓰기 합니다. """
    rules_json = json.dumps(rules_dict, ensure_ascii=False) # 한글 깨짐 방지
    conn = get_db_conn()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO mappings (name, rules_json) VALUES (?, ?)",
            (name, rules_json)
        )
    conn.close()
    st.toast(f"✅ '{name}' 매핑이 DB에 저장되었습니다.")

#@st.cache_data(ttl=600) # 10분마다 DB에서 설정을 다시 로드
def load_all_config_from_db():
    """ DB에서 모든 템플릿과 매핑을 읽어 딕셔너리로 반환합니다. (캐시 사용) """
    #딕셔너리로 반환하는 이유: 
    conn = get_db_conn()
    templates = {}
    mappings = {}
    
    with conn:
        # 템플릿 로드
        cur = conn.execute("SELECT * FROM templates")
        for row in cur.fetchall():
            try:
                templates[row['name']] = json.loads(row['columns_json'])
            except json.JSONDecodeError:
                st.error(f"DB: '{row['name']}' 템플릿 로드 실패.")
                templates[row['name']] = None

        # 매핑 로드
        cur = conn.execute("SELECT * FROM mappings")
        for row in cur.fetchall():
            try:
                mappings[row['name']] = json.loads(row['rules_json'])
            except json.JSONDecodeError:
                st.error(f"DB: '{row['name']}' 매핑 로드 실패.")
                mappings[row['name']] = None
                
    conn.close()
        #반환 딕셔너리 예시
#     templates = {
#     '로젠양식': ['수하인명', '주소', '전화번호'],
#     '이카운트': ['수취인', '주소']
# }

# mappings = {
#     '이카운트→로젠': {'수취인': '수하인명', '주소': '수하인주소'},
#     '쿠팡→로젠': {...}
# }
    return templates, mappings

def delete_template(name):
    """ 특정 이름의 양식(템플릿)을 DB에서 삭제합니다. """
    conn = get_db_conn()
    try:
        with conn:
            cursor = conn.execute("DELETE FROM templates WHERE name = ?", (name,))
        if cursor.rowcount > 0:
            st.toast(f"🗑️ '{name}' 양식이 DB에서 삭제되었습니다.")
            print(f"DB에서 '{name}' 템플릿을 삭제했습니다.")
        else:
            print(f"DB에서 '{name}' 템플릿을 찾지 못해 삭제하지 못했습니다.")
    finally:
        conn.close()