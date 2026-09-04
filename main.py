from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import time
import random
import string

app = FastAPI(title="EduQuest Pro API")

# Netlify va boshqa joylardan so'rovlarga 100% ruxsat berish (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "eduquest.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Sinflar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)
    
    # Ustozlar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            login TEXT UNIQUE NOT NULL,
            pass TEXT NOT NULL
        )
    """)
    
    # O'quvchilar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            login TEXT NOT NULL,
            pass TEXT NOT NULL,
            balance INTEGER DEFAULT 0
        )
    """)
    
    # Kuponlar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            points INTEGER NOT NULL,
            teacher_name TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            used_by TEXT DEFAULT ''
        )
    """)
    
    # Sovg'alar (Do'kon)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cost INTEGER NOT NULL,
            desc TEXT DEFAULT ''
        )
    """)
    
    # Sovg'a so'rovlari
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            cost INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at REAL NOT NULL,
            approved_at REAL,
            reward_number INTEGER,
            is_duty_activated INTEGER DEFAULT 0
        )
    """)

    # Standart sinflar bo'lmasa kiritish
    cursor.execute("SELECT COUNT(*) FROM classes")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO classes (name) VALUES (?)", [
            ("9-A",), ("9-B",), ("10-A",), ("10-B",)
        ])
        
    # Standart do'kon mahsulotlari
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO products (name, cost, desc) VALUES (?, ?, ?)", [
            ("Kitoblar to'plami", 250, "Badiiy kitoblar to'plami"),
            ("Maktab oshxonasida tushlik", 120, "1 martalik bepul tushlik")
        ])

    conn.commit()
    conn.close()

init_db()

# --- Modellar ---
class LoginReq(BaseModel):
    login: str
    password: str
    class_id: Optional[int] = None

class TeacherCreate(BaseModel):
    name: str

class BulkStudents(BaseModel):
    class_id: int
    names_text: str

class CouponCreate(BaseModel):
    points: int
    teacher_name: str

class ProductCreate(BaseModel):
    name: str
    cost: int
    desc: Optional[str] = ""

class RewardReqCreate(BaseModel):
    student_id: int
    product_id: str
    product_name: str
    cost: int

# --- API ENDPOINTLAR ---

@app.get("/")
def home():
    return {"status": "EduQuest Backend Active"}

@app.get("/api/classes")
def get_classes():
    conn = get_db()
    rows = conn.cursor().execute("SELECT * FROM classes").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/classes")
def add_class(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO classes (name) VALUES (?)", (data["name"],))
    conn.commit()
    conn.close()
    return {"message": "Sinf qo'shildi"}

@app.post("/api/login")
def login(req: LoginReq):
    # Admin
    if req.login == "admin" and req.password == "admin2026":
        return {"id": "admin", "name": "Super Admin", "role": "admin"}
    
    conn = get_db()
    cur = conn.cursor()
    
    # O'quvchi
    if req.class_id:
        st = cur.execute("SELECT * FROM students WHERE class_id=? AND LOWER(login)=LOWER(?) AND pass=?",
                         (req.class_id, req.login, req.password)).fetchone()
        conn.close()
        if st:
            return {"id": st["id"], "name": st["name"], "role": "student", "class_id": st["class_id"], "balance": st["balance"]}
        raise HTTPException(status_code=400, detail="O'quvchi login yoki paroli noto'g'ri!")
        
    # Ustoz
    tc = cur.execute("SELECT * FROM teachers WHERE LOWER(login)=LOWER(?) AND pass=?",
                     (req.login, req.password)).fetchone()
    conn.close()
    if tc:
        return {"id": tc["id"], "name": tc["name"], "role": "teacher"}
        
    raise HTTPException(status_code=400, detail="Login yoki parol noto'g'ri!")

# Ustozlar CRUD
@app.get("/api/admin/teachers")
def get_teachers():
    conn = get_db()
    rows = conn.cursor().execute("SELECT * FROM teachers").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/teachers")
def add_teacher(t: TeacherCreate):
    parts = t.name.strip().lower().split()
    login = (parts[1] + parts[0]) if len(parts) >= 2 else t.name.strip().lower()
    login = "".join(ch for ch in login if ch.isalnum())
    password = "49teacher"
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO teachers (name, login, pass) VALUES (?, ?, ?)", (t.name, login, password))
        conn.commit()
    except:
        conn.close()
        raise HTTPException(status_code=400, detail="Bunday ustoz allaqachon mavjud!")
    conn.close()
    return {"login": login, "pass": password}

@app.delete("/api/admin/teachers/{t_id}")
def delete_teacher(t_id: int):
    conn = get_db()
    conn.cursor().execute("DELETE FROM teachers WHERE id=?", (t_id,))
    conn.commit()
    conn.close()
    return {"message": "Ustoz o'chirildi"}

# O'quvchilar CRUD
@app.get("/api/admin/students")
def get_students(class_id: int):
    conn = get_db()
    rows = conn.cursor().execute("SELECT * FROM students WHERE class_id=?", (class_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/students/bulk")
def add_bulk_students(data: BulkStudents):
    conn = get_db()
    cur = conn.cursor()
    lines = [line.strip() for line in data.names_text.split("\n") if line.strip()]
    count = 0
    for name in lines:
        parts = name.strip().lower().split()
        login = (parts[1] + parts[0]) if len(parts) >= 2 else name.strip().lower()
        login = "".join(ch for ch in login if ch.isalnum())
        cur.execute("INSERT INTO students (class_id, name, login, pass, balance) VALUES (?, ?, ?, ?, ?)",
                    (data.class_id, name, login, "49student", 0))
        count += 1
    conn.commit()
    conn.close()
    return {"message": f"{count} ta o'quvchi qo'shildi!"}

@app.delete("/api/admin/students/{s_id}")
def delete_student(s_id: int):
    conn = get_db()
    conn.cursor().execute("DELETE FROM students WHERE id=?", (s_id,))
    conn.commit()
    conn.close()
    return {"message": "O'quvchi o'chirildi"}

# Do'kon CRUD
@app.get("/api/products")
def get_products():
    conn = get_db()
    rows = conn.cursor().execute("SELECT * FROM products").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/products")
def add_product(p: ProductCreate):
    conn = get_db()
    conn.cursor().execute("INSERT INTO products (name, cost, desc) VALUES (?, ?, ?)", (p.name, p.cost, p.desc))
    conn.commit()
    conn.close()
    return {"message": "Mahsulot qo'shildi"}

@app.delete("/api/products/{p_id}")
def delete_product(p_id: int):
    conn = get_db()
    conn.cursor().execute("DELETE FROM products WHERE id=?", (p_id,))
    conn.commit()
    conn.close()
    return {"message": "O'chirildi"}

# Kuponlar
@app.get("/api/teacher/coupons")
def get_teacher_coupons(teacher_name: str):
    conn = get_db()
    rows = conn.cursor().execute("SELECT * FROM coupons WHERE teacher_name=? ORDER BY id DESC", (teacher_name,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/teacher/coupons")
def create_coupon(c: CouponCreate):
    chars = string.ascii_uppercase.replace("I", "").replace("O", "") + "23456789"
    code = f"{''.join(random.choices(chars, k=4))}-{''.join(random.choices(chars, k=4))}"
    now = time.time()
    expires = now + (5 * 3600)
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO coupons (code, points, teacher_name, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (code, c.points, c.teacher_name, now, expires))
    conn.commit()
    conn.close()
    return {"code": code, "points": c.points}

# O'quvchi API'lari
@app.get("/api/student/profile/{s_id}")
def get_student_profile(s_id: int):
    conn = get_db()
    st = conn.cursor().execute("SELECT * FROM students WHERE id=?", (s_id,)).fetchone()
    conn.close()
    if not st:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")
    return dict(st)

@app.post("/api/student/redeem")
def redeem_coupon(data: dict):
    code = data.get("code", "").upper().strip()
    student_id = data.get("student_id")
    now = time.time()
    
    conn = get_db()
    cur = conn.cursor()
    coupon = cur.execute("SELECT * FROM coupons WHERE code=?", (code,)).fetchone()
    
    if not coupon:
        conn.close()
        raise HTTPException(status_code=400, detail="Bunday kupon mavjud emas!")
    if now > coupon["expires_at"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Kupon muddati (5 soat) tugagan!")
        
    used_by = coupon["used_by"].split(",") if coupon["used_by"] else []
    if str(student_id) in used_by:
        conn.close()
        raise HTTPException(status_code=400, detail="Siz bu kupondan foydalangansiz!")
        
    used_by.append(str(student_id))
    cur.execute("UPDATE coupons SET used_by=? WHERE id=?", (",".join(used_by), coupon["id"]))
    cur.execute("UPDATE students SET balance = balance + ? WHERE id=?", (coupon["points"], student_id))
    conn.commit()
    conn.close()
    return {"added": coupon["points"]}

# So'rovlar
@app.get("/api/admin/requests")
def get_all_requests():
    conn = get_db()
    rows = conn.cursor().execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/student/requests/{s_id}")
def get_student_requests(s_id: int):
    conn = get_db()
    rows = conn.cursor().execute("SELECT * FROM requests WHERE student_id=? ORDER BY id DESC", (s_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/student/request-reward")
def request_reward(req: RewardReqCreate):
    conn = get_db()
    cur = conn.cursor()
    st = cur.execute("SELECT * FROM students WHERE id=?", (req.student_id,)).fetchone()
    if not st or st["balance"] < req.cost:
        conn.close()
        raise HTTPException(status_code=400, detail="Ball yetarli emas!")
        
    cls = cur.execute("SELECT name FROM classes WHERE id=?", (st["class_id"],)).fetchone()
    class_name = cls["name"] if cls else "Noma'lum"
    
    cur.execute("UPDATE students SET balance = balance - ? WHERE id=?", (req.cost, req.student_id))
    cur.execute("""
        INSERT INTO requests (student_id, student_name, class_id, class_name, product_id, product_name, cost, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (st["id"], st["name"], st["class_id"], class_name, req.product_id, req.product_name, req.cost, time.time()))
    conn.commit()
    conn.close()
    return {"message": "Yuborildi"}

@app.post("/api/admin/requests/{r_id}/approve")
def approve_request(r_id: int):
    conn = get_db()
    cur = conn.cursor()
    # Yangi unikal raqam generatsiya qilish
    last_num = cur.execute("SELECT MAX(reward_number) FROM requests").fetchone()[0]
    next_num = 1 if not last_num else last_num + 1
    
    cur.execute("UPDATE requests SET status='approved', reward_number=?, approved_at=? WHERE id=?", 
                (next_num, time.time(), r_id))
    conn.commit()
    conn.close()
    return {"reward_number": next_num}

@app.post("/api/admin/requests/{r_id}/reject")
def reject_request(r_id: int):
    conn = get_db()
    cur = conn.cursor()
    req = cur.execute("SELECT * FROM requests WHERE id=?", (r_id,)).fetchone()
    if req:
        cur.execute("UPDATE requests SET status='rejected' WHERE id=?", (r_id,))
        cur.execute("UPDATE students SET balance = balance + ? WHERE id=?", (req["cost"], req["student_id"]))
    conn.commit()
    conn.close()
    return {"message": "Rad etildi va ball qaytarildi"}

@app.post("/api/admin/requests/{r_id}/status")
def set_req_status(r_id: int, data: dict):
    conn = get_db()
    conn.cursor().execute("UPDATE requests SET status=? WHERE id=?", (data["status"], r_id))
    conn.commit()
    conn.close()
    return {"message": "Status yangilandi"}

@app.get("/api/admin/requests/by-number/{num}")
def get_req_by_number(num: int):
    conn = get_db()
    row = conn.cursor().execute("SELECT * FROM requests WHERE reward_number=?", (num,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return dict(row)

@app.post("/api/admin/requests/{r_id}/complete")
def complete_request(r_id: int):
    conn = get_db()
    conn.cursor().execute("UPDATE requests SET status='completed' WHERE id=?", (r_id,))
    conn.commit()
    conn.close()
    return {"message": "Topshirildi"}

@app.get("/api/student/duties/{class_id}")
def get_active_duties(class_id: int):
    now = time.time()
    conn = get_db()
    # 24 soat (86400 soniya) ichida faollashgan navbatchiliklar
    rows = conn.cursor().execute("""
        SELECT * FROM requests 
        WHERE class_id=? AND product_id='perm_duty' AND is_duty_activated=1 AND (approved_at + 86400) > ?
    """, (class_id, now)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/student/activate-duty/{r_id}")
def activate_duty(r_id: int):
    conn = get_db()
    conn.cursor().execute("UPDATE requests SET is_duty_activated=1, approved_at=? WHERE id=?", (time.time(), r_id))
    conn.commit()
    conn.close()
    return {"message": "Navbatchilik faollashtirildi"}
