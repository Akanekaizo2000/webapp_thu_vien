-- 1. XÓA BẢNG CŨ NẾU CÓ
DROP TABLE IF EXISTS borrow_records CASCADE;
DROP TABLE IF EXISTS book_copies CASCADE;
DROP TABLE IF EXISTS books CASCADE;
DROP TABLE IF EXISTS shelf_locations CASCADE;

-- 2. TẠO BẢNG Ô KỆ (200 VỊ TRÍ)
CREATE TABLE shelf_locations (
    location_code VARCHAR(20) PRIMARY KEY,
    rack_number INT NOT NULL,
    side VARCHAR(10) NOT NULL,
    shelf_tier INT NOT NULL
);

-- 3. TẠO BẢNG SÁCH
CREATE TABLE books (
    isbn VARCHAR(20) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(100),
    category VARCHAR(50)
);

-- 4. TẠO BẢNG BẢN SAO SÁCH
CREATE TABLE book_copies (
    barcode VARCHAR(50) PRIMARY KEY,
    isbn VARCHAR(20) REFERENCES books(isbn) ON DELETE CASCADE,
    location_code VARCHAR(20) REFERENCES shelf_locations(location_code),
    status VARCHAR(20) DEFAULT 'AVAILABLE'
);

-- 5. TẠO BẢNG LỊCH SỬ MƯỢN TRẢ
CREATE TABLE borrow_records (
    record_id SERIAL PRIMARY KEY,
    barcode VARCHAR(50) REFERENCES book_copies(barcode),
    student_id VARCHAR(20) NOT NULL,
    borrow_date DATE DEFAULT CURRENT_DATE,
    due_date DATE,
    return_date DATE,
    status VARCHAR(20) DEFAULT 'BORROWING'
);

-- 6. TỰ ĐỘNG SINH 200 Ô KỆ (K01 -> K10, L/R, T01 -> T10)
DO $$
DECLARE
    r INT;
    s TEXT;
    t INT;
    side_code TEXT;
    loc_code TEXT;
BEGIN
    FOR r IN 1..10 LOOP
        FOR s_idx IN 1..2 LOOP
            IF s_idx = 1 THEN
                s := 'LEFT'; 
                side_code := 'L';
            ELSE
                s := 'RIGHT'; 
                side_code := 'R';
            END IF;

            FOR t IN 1..10 LOOP
                loc_code := 'K' || LPAD(r::text, 2, '0') || '-' || side_code || '-T' || LPAD(t::text, 2, '0');
                
                INSERT INTO shelf_locations (location_code, rack_number, side, shelf_tier)
                VALUES (loc_code, r, s, t)
                ON CONFLICT (location_code) DO NOTHING;
            END LOOP;
        END LOOP;
    END LOOP;
END $$;

-- 7. THÊM SÁCH VÀ MÃ VẠCH MẪU ĐỂ TEST
INSERT INTO books (isbn, title, author, category) VALUES
('978-0131103627', 'Lập Trình C Căn Bản', 'Brian W. Kernighan', 'Công nghệ thông tin'),
('978-0132350884', 'Clean Code', 'Robert C. Martin', 'Công nghệ thông tin')
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO book_copies (barcode, isbn, location_code, status) VALUES
('BC-CS-001', '978-0131103627', 'K01-L-T01', 'AVAILABLE'),
('BC-CS-002', '978-0132350884', 'K01-L-T02', 'AVAILABLE')
ON CONFLICT (barcode) DO NOTHING;