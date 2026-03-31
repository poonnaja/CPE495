"""
Smart Classroom Lighting — FastAPI
เพื่อนดึงข้อมูลจาก PostgreSQL ผ่าน REST API นี้ได้เลย
"""
from fastapi import FastAPI, HTTPException, Query, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import os, asyncpg ,uvicorn
from datetime import datetime

# ──────────────────────────────────────────────
app = FastAPI(
    title="Smart Classroom Lighting API",
    description="CPE495 Group F — Real-time classroom data",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Config — ดึงจาก env variable
# ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")   # postgres://user:pass@host:5432/db
API_KEY      = os.getenv("API_KEY", "cpe495-secret-key")

bearer = HTTPBearer(auto_error=False)

def verify_key(cred: HTTPAuthorizationCredentials = Security(bearer)):
    if cred is None or cred.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return cred.credentials

# ──────────────────────────────────────────────
# DB Connection Pool
# ──────────────────────────────────────────────
pool: asyncpg.Pool = None

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

@app.on_event("shutdown")
async def shutdown():
    await pool.close()

async def get_db():
    async with pool.acquire() as conn:
        yield conn

# ──────────────────────────────────────────────
# Pydantic schemas (สำหรับ POST)
# ──────────────────────────────────────────────
class SensorLogIn(BaseModel):
    lux_value:    int
    ldr_value:    int
    pir_detected: int          # 0 or 1
    people_count: int
    projector_on: int          # 0 or 1
    hour:         int

class RoomModeIn(BaseModel):
    sensor_log_id:     int
    mode_selected:     str
    mode_emoji:        str
    mode_desc:         str
    triggered_by:      str
    teacher_name:      Optional[str] = None
    course_id:         Optional[int] = None
    projector_override:Optional[int] = None

class TeacherProfileIn(BaseModel):
    teacher_name:   str
    preferred_mode: str
    preferred_lux:  int
    notes:          Optional[str] = None

class CourseIn(BaseModel):
    teacher_name:      str
    course_code:       str
    course_name:       str
    hours_per_week:    int
    default_projector: int = 0   # 0 or 1

# ══════════════════════════════════════════════
#  ROOT
# ══════════════════════════════════════════════
@app.get("/", tags=["Info"])
async def root():
    return {
        "project": "Smart Classroom Lighting",
        "version": "1.0.0",
        "group": "CPE495 Group F",
        "docs": "/docs",
        "endpoints": [
            "/sensor-logs", "/room-modes",
            "/energy-logs", "/teacher-profiles",
            "/courses", "/summary", "/activity-log",
        ],
    }

# ══════════════════════════════════════════════
#  SUMMARY — ดึงภาพรวม (ไม่ต้อง auth)
# ══════════════════════════════════════════════
@app.get("/summary", tags=["Public"])
async def get_summary(db=Depends(get_db)):
    total      = await db.fetchval("SELECT COUNT(*) FROM sensor_logs")
    avg_saving = await db.fetchval("SELECT ROUND(AVG(energy_saved_pct)::numeric,1) FROM energy_logs")
    proj_count = await db.fetchval("SELECT COUNT(*) FROM sensor_logs WHERE projector_on=1")
    total_saved= await db.fetchval("SELECT COALESCE(SUM(energy_saved_w),0) FROM energy_logs")
    modes      = await db.fetch(
        "SELECT mode_selected, COUNT(*) AS cnt FROM room_modes GROUP BY mode_selected ORDER BY cnt DESC")
    return {
        "total_runs":     total,
        "avg_saving_pct": float(avg_saving or 0),
        "projector_uses": proj_count,
        "total_saved_w":  int(total_saved),
        "mode_breakdown": [dict(r) for r in modes],
    }

# ══════════════════════════════════════════════
#  SENSOR LOGS
# ══════════════════════════════════════════════
@app.get("/sensor-logs", tags=["Sensor"])
async def list_sensor_logs(
    limit:  int = Query(50,  ge=1, le=500),
    offset: int = Query(0,   ge=0),
    hour:   Optional[int] = None,
    db=Depends(get_db),
):
    q = "SELECT * FROM sensor_logs"
    params = []
    if hour is not None:
        q += " WHERE hour=$1"
        params.append(hour)
    q += " ORDER BY id DESC LIMIT $%d OFFSET $%d" % (len(params)+1, len(params)+2)
    params += [limit, offset]
    rows = await db.fetch(q, *params)
    return [dict(r) for r in rows]

@app.post("/sensor-logs", tags=["Sensor"], dependencies=[Depends(verify_key)])
async def create_sensor_log(body: SensorLogIn, db=Depends(get_db)):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = await db.fetchrow(
        """INSERT INTO sensor_logs
           (timestamp,lux_value,ldr_value,pir_detected,people_count,projector_on,hour)
           VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
        now, body.lux_value, body.ldr_value,
        body.pir_detected, body.people_count,
        body.projector_on, body.hour)
    return {"id": row["id"], "timestamp": now}

# ══════════════════════════════════════════════
#  ROOM MODES
# ══════════════════════════════════════════════
@app.get("/room-modes", tags=["Modes"])
async def list_room_modes(
    limit:        int = Query(50, ge=1, le=500),
    offset:       int = Query(0,  ge=0),
    teacher_name: Optional[str] = None,
    mode:         Optional[str] = None,
    db=Depends(get_db),
):
    filters, params = [], []
    if teacher_name:
        params.append(teacher_name)
        filters.append(f"teacher_name=${len(params)}")
    if mode:
        params.append(mode)
        filters.append(f"mode_selected=${len(params)}")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params += [limit, offset]
    rows = await db.fetch(
        f"""SELECT rm.*, c.course_code, c.course_name
            FROM room_modes rm
            LEFT JOIN courses c ON rm.course_id=c.id
            {where}
            ORDER BY rm.id DESC LIMIT ${len(params)-1} OFFSET ${len(params)}""",
        *params)
    return [dict(r) for r in rows]

@app.post("/room-modes", tags=["Modes"], dependencies=[Depends(verify_key)])
async def create_room_mode(body: RoomModeIn, db=Depends(get_db)):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = await db.fetchrow(
        """INSERT INTO room_modes
           (timestamp,sensor_log_id,mode_selected,mode_emoji,mode_desc,
            triggered_by,teacher_name,course_id,projector_override)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id""",
        now, body.sensor_log_id, body.mode_selected, body.mode_emoji,
        body.mode_desc, body.triggered_by, body.teacher_name,
        body.course_id, body.projector_override)
    return {"id": row["id"], "timestamp": now}

# ══════════════════════════════════════════════
#  ENERGY LOGS
# ══════════════════════════════════════════════
@app.get("/energy-logs", tags=["Energy"])
async def list_energy_logs(
    limit:        int = Query(50, ge=1, le=500),
    offset:       int = Query(0,  ge=0),
    teacher_name: Optional[str] = None,
    db=Depends(get_db),
):
    filters, params = [], []
    if teacher_name:
        params.append(teacher_name)
        filters.append(f"e.teacher_name=${len(params)}")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params += [limit, offset]
    rows = await db.fetch(
        f"""SELECT e.*, c.course_code, c.course_name
            FROM energy_logs e
            LEFT JOIN courses c ON e.course_id=c.id
            {where}
            ORDER BY e.id DESC LIMIT ${len(params)-1} OFFSET ${len(params)}""",
        *params)
    return [dict(r) for r in rows]

# ══════════════════════════════════════════════
#  TEACHER PROFILES (public read / auth write)
# ══════════════════════════════════════════════
@app.get("/teacher-profiles", tags=["Teachers"])
async def list_teacher_profiles(db=Depends(get_db)):
    rows = await db.fetch("SELECT * FROM teacher_profiles ORDER BY teacher_name")
    return [dict(r) for r in rows]

@app.get("/teacher-profiles/{name}", tags=["Teachers"])
async def get_teacher_profile(name: str, db=Depends(get_db)):
    row = await db.fetchrow(
        "SELECT * FROM teacher_profiles WHERE teacher_name=$1", name)
    if not row:
        raise HTTPException(404, detail="Teacher not found")
    return dict(row)

@app.post("/teacher-profiles", tags=["Teachers"], dependencies=[Depends(verify_key)])
async def upsert_teacher_profile(body: TeacherProfileIn, db=Depends(get_db)):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        """INSERT INTO teacher_profiles
           (teacher_name,preferred_mode,preferred_lux,notes,created_at,updated_at)
           VALUES($1,$2,$3,$4,$5,$5)
           ON CONFLICT(teacher_name) DO UPDATE SET
             preferred_mode=$2, preferred_lux=$3,
             notes=$4, updated_at=$5""",
        body.teacher_name, body.preferred_mode,
        body.preferred_lux, body.notes, now)
    return {"status": "ok", "teacher_name": body.teacher_name}

@app.delete("/teacher-profiles/{name}", tags=["Teachers"], dependencies=[Depends(verify_key)])
async def delete_teacher_profile(name: str, db=Depends(get_db)):
    await db.execute("DELETE FROM teacher_profiles WHERE teacher_name=$1", name)
    return {"status": "deleted", "teacher_name": name}

# ══════════════════════════════════════════════
#  COURSES
# ══════════════════════════════════════════════
@app.get("/courses", tags=["Courses"])
async def list_courses(
    teacher_name: Optional[str] = None,
    db=Depends(get_db),
):
    if teacher_name:
        rows = await db.fetch(
            "SELECT * FROM courses WHERE teacher_name=$1 ORDER BY course_code",
            teacher_name)
    else:
        rows = await db.fetch("SELECT * FROM courses ORDER BY teacher_name, course_code")
    return [dict(r) for r in rows]

@app.post("/courses", tags=["Courses"], dependencies=[Depends(verify_key)])
async def upsert_course(body: CourseIn, db=Depends(get_db)):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        """INSERT INTO courses
           (teacher_name,course_code,course_name,hours_per_week,default_projector,created_at)
           VALUES($1,$2,$3,$4,$5,$6)
           ON CONFLICT(teacher_name,course_code) DO UPDATE SET
             course_name=$3, hours_per_week=$4, default_projector=$5""",
        body.teacher_name, body.course_code.upper(),
        body.course_name, body.hours_per_week,
        body.default_projector, now)
    return {"status": "ok", "course_code": body.course_code.upper()}

@app.delete("/courses/{course_id}", tags=["Courses"], dependencies=[Depends(verify_key)])
async def delete_course(course_id: int, db=Depends(get_db)):
    await db.execute("DELETE FROM courses WHERE id=$1", course_id)
    return {"status": "deleted", "course_id": course_id}

# ══════════════════════════════════════════════
#  ACTIVITY LOG (Admin only)
# ══════════════════════════════════════════════
@app.get("/activity-log", tags=["Admin"], dependencies=[Depends(verify_key)])
async def list_activity_log(
    limit:  int = Query(100, ge=1, le=1000),
    actor:  Optional[str] = None,
    action: Optional[str] = None,
    db=Depends(get_db),
):
    filters, params = [], []
    if actor:
        params.append(actor); filters.append(f"actor=${len(params)}")
    if action:
        params.append(action); filters.append(f"action=${len(params)}")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params.append(limit)
    rows = await db.fetch(
        f"SELECT * FROM activity_log {where} ORDER BY id DESC LIMIT ${len(params)}",
        *params)
    return [dict(r) for r in rows]

# ══════════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════════

if __name__ == "__main__":
    # ดึงค่า PORT จาก Environment Variable ที่ Render กำหนดให้
    port = int(os.environ.get("PORT", 10000))
    # รัน uvicorn โดยระบุ host เป็น 0.0.0.0
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
