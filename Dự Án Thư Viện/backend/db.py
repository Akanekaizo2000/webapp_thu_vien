import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database="library_db",
            user="postgres",
            password="121088",  # <-- Đổi "123" thành mật khẩu pgAdmin của bạn nếu khác
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print("Lỗi kết nối CSDL Local:", e)
        return None