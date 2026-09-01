import io
import re
import pandas as pd
from datetime import date
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import get_db_connection

app = FastAPI(title="MIT Smart Library API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. API ĐĂNG NHẬP & PHÂN QUYỀN
class LoginRequest(BaseModel):
    student_id: str
    password: str

@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Lỗi kết nối CSDL")
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, full_name, role, password, is_locked FROM users WHERE student_id = %s;", (req.student_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or user['password'] != req.password:
        raise HTTPException(status_code=401, detail="Sai mã người dùng hoặc mật khẩu!")
    if user['is_locked']:
        raise HTTPException(status_code=403, detail="Tài khoản bị khóa do vi phạm phạt quá hạn!")

    return {"message": "Đăng nhập thành công", "user": {"student_id": user['student_id'], "full_name": user['full_name'], "role": user['role']}}

# 2. API LẤY SƠ ĐỒ KỆ & DỮ LIỆU SÁCH
@app.get("/api/shelves")
def get_all_shelves():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Lỗi kết nối CSDL")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.location_code, s.rack_number, s.side, s.shelf_tier,
               bc.barcode, b.title as book_title, bc.status as copy_status
        FROM shelf_locations s
        LEFT JOIN book_copies bc ON s.location_code = bc.location_code
        LEFT JOIN books b ON bc.isbn = b.isbn
        ORDER BY s.rack_number, s.side, s.shelf_tier;
    """)
    rows = cursor.fetchall()
    conn.close()
    return {"data": rows}

# 3. API IMPORT FILE EXCEL (Hỗ trợ cấu trúc 2 cột Trái/Phải & T1->T10)
@app.post("/api/librarian/import-excel")
async def import_excel(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Vui lòng chọn file Excel (.xlsx hoặc .xls)")
    
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Lỗi kết nối CSDL")
    cursor = conn.cursor()

    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content), header=None)
        
        current_rack = 1
        current_tier = 1
        count_inserted = 0

        for idx, row in df.iterrows():
            # CHỈ nhận diện số Kệ và Tầng ở Cột A (cột index 0)
            col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            
            if "Kệ" in col_a:
                rack_match = re.search(r'Kệ\s*(\d+)', col_a, re.IGNORECASE)
                if rack_match:
                    current_rack = int(rack_match.group(1))
            
            if "Tầng" in col_a:
                tier_match = re.search(r'Tầng\s*(\d+)', col_a, re.IGNORECASE)
                if tier_match:
                    current_tier = int(tier_match.group(1))

            # Giới hạn an toàn: Kệ (1 -> 10), Tầng (1 -> 10)
            valid_rack = max(1, min(10, current_rack))
            valid_tier = max(1, min(10, current_tier))

            # Xử lý Mặt Trái (Cột B -> F)
            title_l = str(row[1]).strip() if len(row) > 1 and pd.notna(row[1]) and str(row[1]).strip() not in ['Tên sách', 'Trái', ''] else None
            if title_l and not title_l.startswith(('Kệ', 'Tầng')):
                year_l = int(row[2]) if len(row) > 2 and pd.notna(row[2]) and str(row[2]).isdigit() else None
                author_l = str(row[3]).strip() if len(row) > 3 and pd.notna(row[3]) else "Chưa rõ"
                qty_l = int(row[4]) if len(row) > 4 and pd.notna(row[4]) and str(row[4]).isdigit() else 1
                
                loc_l = f"K{valid_rack:02d}-L-T{valid_tier:02d}"
                isbn_l = f"ISBN-{abs(hash(title_l + author_l)) % 10000000000:010d}"

                cursor.execute("""
                    INSERT INTO books (isbn, title, author, publish_year, category)
                    VALUES (%s, %s, %s, %s, 'Chung')
                    ON CONFLICT (isbn) DO UPDATE SET title = EXCLUDED.title, author = EXCLUDED.author;
                """, (isbn_l, title_l, author_l, year_l))

                for i in range(qty_l):
                    bc = f"BC-K{valid_rack:02d}L-T{valid_tier:02d}-{abs(hash(title_l + str(i))) % 100000:05d}"
                    cursor.execute("""
                        INSERT INTO book_copies (barcode, isbn, location_code, status)
                        VALUES (%s, %s, %s, 'AVAILABLE') ON CONFLICT (barcode) DO NOTHING;
                    """, (bc, isbn_l, loc_l))
                    count_inserted += 1

            # Xử lý Mặt Phải (Cột G -> K)
            title_r = str(row[6]).strip() if len(row) > 6 and pd.notna(row[6]) and str(row[6]).strip() not in ['Tên sách', 'Phải', ''] else None
            if title_r and not title_r.startswith(('Kệ', 'Tầng')):
                year_r = int(row[7]) if len(row) > 7 and pd.notna(row[7]) and str(row[7]).isdigit() else None
                author_r = str(row[8]).strip() if len(row) > 8 and pd.notna(row[8]) else "Chưa rõ"
                qty_r = int(row[9]) if len(row) > 9 and pd.notna(row[9]) and str(row[9]).isdigit() else 1
                
                loc_r = f"K{valid_rack:02d}-R-T{valid_tier:02d}"
                isbn_r = f"ISBN-{abs(hash(title_r + author_r)) % 10000000000:010d}"

                cursor.execute("""
                    INSERT INTO books (isbn, title, author, publish_year, category)
                    VALUES (%s, %s, %s, %s, 'Chung')
                    ON CONFLICT (isbn) DO UPDATE SET title = EXCLUDED.title, author = EXCLUDED.author;
                """, (isbn_r, title_r, author_r, year_r))

                for i in range(qty_r):
                    bc = f"BC-K{valid_rack:02d}R-T{valid_tier:02d}-{abs(hash(title_r + str(i))) % 100000:05d}"
                    cursor.execute("""
                        INSERT INTO book_copies (barcode, isbn, location_code, status)
                        VALUES (%s, %s, %s, 'AVAILABLE') ON CONFLICT (barcode) DO NOTHING;
                    """, (bc, isbn_r, loc_r))
                    count_inserted += 1

        conn.commit()
        conn.close()
        return {"message": f"Nạp thành công {count_inserted} cuốn sách từ file Excel vào các ô kệ CSDL!"}

    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Lỗi đọc file Excel: {str(e)}")

# 4. API MƯỢN TRẢ & TÍNH TIỀN PHẠT QUÁ HẠN
class BorrowReq(BaseModel):
    barcode: str
    student_id: str

@app.post("/api/borrow")
def borrow_book(req: BorrowReq):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Lỗi kết nối CSDL")
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_locked FROM users WHERE student_id = %s;", (req.student_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Mã độc giả không tồn tại!")
    if user['is_locked']:
        conn.close()
        raise HTTPException(status_code=400, detail="Tài khoản đang bị khóa do nợ phạt quá hạn!")

    cursor.execute("UPDATE book_copies SET status = 'BORROWED' WHERE barcode = %s AND status = 'AVAILABLE';", (req.barcode,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Sách không có sẵn hoặc đang được mượn!")

    cursor.execute("""
        INSERT INTO borrow_records (barcode, student_id, borrow_date, due_date, status)
        VALUES (%s, %s, CURRENT_DATE, CURRENT_DATE + INTERVAL '14 days', 'BORROWING');
    """, (req.barcode, req.student_id))
    
    conn.commit()
    conn.close()
    return {"message": "Mượn sách thành công! Hạn trả là 14 ngày tới."}

@app.post("/api/return")
def return_book(barcode: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Lỗi kết nối CSDL")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT record_id, student_id, due_date, location_code 
        FROM borrow_records br
        JOIN book_copies bc ON br.barcode = bc.barcode
        WHERE br.barcode = %s AND br.status = 'BORROWING';
    """, (barcode,))
    rec = cursor.fetchone()
    
    if not rec:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu mượn của mã vạch này!")

    today = date.today()
    due_date = rec['due_date']
    fine = 0
    if today > due_date:
        overdue_days = (today - due_date).days
        fine = overdue_days * 5000  # Phạt 5.000đ/ngày

    cursor.execute("UPDATE book_copies SET status = 'AVAILABLE' WHERE barcode = %s;", (barcode,))
    cursor.execute("""
        UPDATE borrow_records 
        SET return_date = CURRENT_DATE, fine_amount = %s, status = 'RETURNED'
        WHERE record_id = %s;
    """, (fine, rec['record_id']))

    if fine >= 50000:
        cursor.execute("UPDATE users SET is_locked = TRUE WHERE student_id = %s;", (rec['student_id'],))

    conn.commit()
    conn.close()
    return {"message": f"Trả sách thành công! Phí phạt quá hạn: {fine:,} VNĐ", "return_to_location": rec['location_code']}

# 5. API AI CHATBOT TRA CỨU TỰ ĐỘNG
@app.get("/api/chatbot/query")
def ai_chatbot_query(question: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Lỗi kết nối CSDL")
    cursor = conn.cursor()
    
    kw = f"%{question}%"
    cursor.execute("""
        SELECT b.title, b.author, bc.barcode, bc.status, bc.location_code
        FROM books b
        JOIN book_copies bc ON b.isbn = bc.isbn
        WHERE b.title ILIKE %s OR b.author ILIKE %s;
    """, (kw, kw))
    books = cursor.fetchall()
    conn.close()

    if not books:
        return {"answer": f"🤖 **Trợ lý AI MIT**: Rất tiếc, không tìm thấy cuốn sách nào khớp với '{question}'. Hãy kiểm tra lại từ khóa nhé!"}

    res_text = f"🤖 **Trợ lý AI MIT**: Tìm thấy <b>{len(books)}</b> cuốn sách phù hợp:<br><ul class='mt-2 space-y-1'>"
    for b in books:
        st = "<span class='text-emerald-600 font-bold'>[Có sẵn]</span>" if b['status'] == 'AVAILABLE' else "<span class='text-rose-600 font-bold'>[Đã mượn]</span>"
        res_text += f"<li>• <b>{b['title']}</b> ({b['author']}) 👉 Vị trí: <code class='bg-amber-100 text-mit-red px-1 rounded font-black'>{b['location_code']}</code> {st}</li>"
    res_text += "</ul>"

    return {"answer": res_text}