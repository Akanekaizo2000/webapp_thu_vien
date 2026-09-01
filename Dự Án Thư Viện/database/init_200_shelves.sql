-- Hàm/Đoạn code khởi tạo tự động 200 vị trí ô kệ cho kho thư viện
DO $$
DECLARE
    r INT;           -- Số kệ (1 -> 10)
    s TEXT;          -- Mặt (LEFT / RIGHT)
    t INT;           -- Tầng (1 -> 10)
    side_code TEXT;  -- L / R
    loc_code TEXT;   -- Ví dụ: K01-L-T01
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