import sqlite3
import os

# 데이터베이스 파일 이름
DB_NAME = "excel_converter.db"

# 데이터베이스 파일이 현재 폴더에 있는지 확인
if not os.path.exists(DB_NAME):
    print(f"❌ 오류: '{DB_NAME}' 파일을 찾을 수 없습니다.")
    print("스크립트가 데이터베이스 파일과 같은 폴더에 있는지 확인해주세요.")
else:
    try:
        # 데이터베이스에 연결
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        print(f"'{DB_NAME}'에 연결되었습니다.")

        # 'templates' 테이블의 모든 레코드 삭제
        # 테이블에 레코드가 하나만 있다고 하셨으므로, 이 명령으로 해당 레코드가 삭제됩니다.
        cursor.execute("DELETE FROM templates")

        # 변경사항 저장
        conn.commit()

        # 삭제된 행의 수 확인
        if cursor.rowcount > 0:
            print(f"✅ 'templates' 테이블에서 {cursor.rowcount}개의 레코드를 성공적으로 삭제했습니다.")
        else:
            print("🤷‍♀️ 'templates' 테이블에 삭제할 레코드가 없습니다.")

    except Exception as e:
        print(f"❌ 작업 중 오류가 발생했습니다: {e}")

    finally:
        # 연결 종료
        if 'conn' in locals() and conn:
            conn.close()
            print("데이터베이스 연결을 닫았습니다.")

