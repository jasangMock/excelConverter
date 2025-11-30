import sqlite3
import pandas as pd
import json

# 데이터베이스 연결
conn = sqlite3.connect('excel_converter.db')

# 1. 테이블 목록 확인
print("=== 테이블 목록 ===")
df_tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
print(df_tables)
print()

# 각 테이블의 내용을 확인합니다.
for table_name in df_tables['name']:
    print(f"\n=== '{table_name}' 테이블 내용 ===")
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        
        # JSON 데이터를 보기 좋게 출력하기 위한 처리
        for col in df.columns:
            if 'json' in col.lower():
                # apply는 각 셀에 함수를 적용
                df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)

        print(df.to_markdown(index=False)) # 테이블 형태로 예쁘게 출력

        # 개별 행 상세 출력 (선택적)
        # print("\n--- 상세 내용 ---")
        # for _, row in df.iterrows():
        #     print(row.to_dict())
    except Exception as e:
        print(f"'{table_name}' 테이블을 읽는 중 오류 발생: {e}")

conn.close()

