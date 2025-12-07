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

        # ---------------------------------------------------------
        # 1. 'mappings' 테이블의 모든 레코드 삭제 (먼저 삭제)
        # ---------------------------------------------------------
        # 주의: 테이블 이름이 'mappings'가 아니라면 실제 이름으로 수정해주세요.
        cursor.execute("DELETE FROM mappings")
        mappings_count = cursor.rowcount # 삭제된 개수 저장

        # ---------------------------------------------------------
        # 2. 'templates' 테이블의 모든 레코드 삭제
        # ---------------------------------------------------------
        cursor.execute("DELETE FROM templates")
        templates_count = cursor.rowcount # 삭제된 개수 저장

        # 변경사항 저장 (이 시점에 두 테이블의 삭제가 확정됩니다)
        conn.commit()

        # 결과 출력
        if mappings_count > 0:
            print(f"✅ 'mappings' 테이블에서 {mappings_count}개의 레코드를 삭제했습니다.")
        else:
            print("🤷‍♀️ 'mappings' 테이블은 이미 비어있거나 삭제할 내용이 없습니다.")

        if templates_count > 0:
            print(f"✅ 'templates' 테이블에서 {templates_count}개의 레코드를 삭제했습니다.")
        else:
            print("🤷‍♀️ 'templates' 테이블은 이미 비어있거나 삭제할 내용이 없습니다.")

    except sqlite3.OperationalError as e:
        print(f"❌ 데이터베이스 오류 (테이블 이름 확인 필요): {e}")
    except Exception as e:
        print(f"❌ 작업 중 오류가 발생했습니다: {e}")

    finally:
        # 연결 종료
        if 'conn' in locals() and conn:
            conn.close()
            print("데이터베이스 연결을 닫았습니다.")