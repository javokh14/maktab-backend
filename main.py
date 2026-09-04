from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import time
import random
import string

app = FastAPI(title="EduQuest Pro API")

# Frontend bilan ulanish ruxsati
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

# Jadvallarni yaratish
def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # 1. Ustozlar
    c.execute('''CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        login TEXT UNIQUE,
        pass TEXT
    )''')
    
    # 2. Sinflar
    c.execute('''CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )''')
    
    # 3. O'quvchilar
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        class_id INTEGER,
        login TEXT,
        pass TEXT,
        balance INTEGER DEFAULT 0
    )''')
    
    # 4. 5 soatlik kuponlar
    c.execute('''CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        points INTEGER,
        teacher_name TEXT,
        created_at REAL,
        expires_at REAL,
        used_by TEXT DEFAULT ''
    )''')

    # 5. Sovg'a so'rovlari
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        student_name TEXT,
        class_id INTEGER,
        class_name TEXT,
        product_id TEXT,
        product_name TEXT,
        cost INTEGER,
        status TEXT,
        created_at REAL,
        reward_number INTEGER DEFAULT NULL,
        is_duty_activated INTEGER DEFAULT 0
    )''')

    # Boshlang'ich sinflarni kiritish
    c.execute('SELECT COUNT(*) FROM classes')
    if c.fetchone()[0] == 0:
        c.executemany('INSERT INTO classes (name) VALUES (?)', [("9-A",), ("9-B",), ("10-A",), ("10-B",)])

    conn.commit()
    conn.close()

init_db()

# Yordamchi mantiqlar
def format_login(name: str):
    parts = name.strip().lower().split()
    if len(parts) >= 2:
        return f"{parts[1]}{parts[0]}"
    return parts[0]

def generate_coupon_code():
    chars = string.ascii_uppercase + "23456789"
    c1 = "".join(random.choices(chars, k=4))
    c2 = "".join(random.choices(chars, k=4))
    return f"{c1}-{c2}"

# Pydantic shablonlar
class LoginRequest(BaseModel):
    login: str
    password: str
    class_id: int = None

class TeacherCreate(BaseModel):
    name: str

class BulkStudents(BaseModel):
    class_id: int
    names_text: str

class CouponCreate(BaseModel):
    points: int
    teacher_name: str

class CouponRedeem(BaseModel):
    student_id: int
    code: str

# --- API ENDPOINTLAR ---

# 1. Kirish (Admin: admin / admin2026)
@app.post("/api/login")
def login(req: LoginRequest):
    conn = get_db()
    c = conn.cursor()
    
    # Admin tekshiruvi
    if req.login == "admin" and req.password == "admin2026":
        conn.close()
        return {"role": "admin", "name": "Super Admin"}
    
    # Ustoz tekshiruvi
    c.execute('SELECT * FROM teachers WHERE LOWER(login) = ? AND pass = ?', (req.login.lower(), req.password))
    teacher = c.fetchone()
    if teacher:
        conn.close()
        return {"role": "teacher", "id": teacher["id"], "name": teacher["name"]}
    
    # O'quvchi tekshiruvi
    if req.class_id:
        c.execute('SELECT * FROM students WHERE class_id = ? AND LOWER(login) = ? AND pass = ?',
                  (req.class_id, req.login.lower(), req.password))
        student = c.fetchone()
        if student:
            conn.close()
            return {
                "role": "student",
                "id": student["id"],
                "name": student["name"],
                "class_id": student["class_id"],
                "balance": student["balance"]
            }
            
    conn.close()
    raise HTTPException(status_code=400, detail="Login yoki parol xato!")

# 2. Sinflar ro'yxatini olish
@app.get("/api/classes")
def get_classes():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM classes')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# 3. Ustoz qo'shish (Admin)
@app.post("/api/admin/teachers")
def add_teacher(req: TeacherCreate):
    conn = get_db()
    c = conn.cursor()
    auto_login = format_login(req.name)
    c.execute('INSERT INTO teachers (name, login, pass) VALUES (?, ?, ?)',
              (req.name, auto_login, "49teacher"))
    conn.commit()
    conn.close()
    return {"message": "Ustoz qo'shildi", "login": auto_login, "pass": "49teacher"}

# 4. O'quvchilarni ommaviy qo'shish (Admin)
@app.post("/api/admin/students/bulk")
def bulk_students(req: BulkStudents):
    conn = get_db()
    c = conn.cursor()
    lines = [l.strip() for l in req.names_text.split("\n") if l.strip()]
    
    for name in lines:
        log = format_login(name)
        c.execute('INSERT INTO students (name, class_id, login, pass, balance) VALUES (?, ?, ?, ?, 0)',
                  (name, req.class_id, log, "49student"))
    
    conn.commit()
    conn.close()
    return {"message": f"{len(lines)} ta o'quvchi qo'shildi"}

# 5. 5 soatlik kupon generatsiya qilish (Ustoz)
@app.post("/api/teacher/coupons")
def make_coupon(req: CouponCreate):
    conn = get_db()
    c = conn.cursor()
    code = generate_coupon_code()
    now = time.time()
    expires_at = now + (5 * 3600)  # Aynan 5 soat
    
    c.execute('INSERT INTO coupons (code, points, teacher_name, created_at, expires_at) VALUES (?, ?, ?, ?, ?)',
              (code, req.points, req.teacher_name, now, expires_at))
    conn.commit()
    conn.close()
    return {"code": code, "points": req.points, "expires_at": expires_at}

# 6. Kupondan ball olish (O'quvchi)
@app.post("/api/student/redeem")
def redeem_coupon(req: CouponRedeem):
    conn = get_db()
    c = conn.cursor()
    now = time.time()
    
    c.execute('SELECT * FROM coupons WHERE code = ?', (req.code.upper().strip(),))
    coupon = c.fetchone()
    
    if not coupon:
        conn.close()
        raise HTTPException(status_code=404, detail="Bunday kupon mavjud emas!")
        
    if now > coupon["expires_at"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Kupon muddati (5 soat) tugagan!")
        
    used_list = coupon["used_by"].split(",") if coupon["used_by"] else []
    if str(req.student_id) in used_list:
        conn.close()
        raise HTTPException(status_code=400, detail="Bu kupondan avval foydalangansiz!")
        
    used_list.append(str(req.student_id))
    c.execute('UPDATE coupons SET used_by = ? WHERE id = ?', (",".join(used_list), coupon["id"]))
    c.execute('UPDATE students SET balance = balance + ? WHERE id = ?', (coupon["points"], req.student_id))
    
    c.execute('SELECT balance FROM students WHERE id = ?', (req.student_id,))
    new_balance = c.fetchone()["balance"]
    
    conn.commit()
    conn.close()
    return {"message": "Ball hisobga qo'shildi", "added": coupon["points"], "balance": new_balance}