import random
import time
import streamlit as st
from ai_logic import SCENARIOS
from database import get_teacher_profiles, get_courses, log_activity
from config import MODE_ICONS


MANUAL_MODE_OPTIONS = [
    "LECTURE_MODE",
    "PRESENT_MODE",
    "GROUP_MODE",
    "AUTO_DIM",
    "ENERGY_SAVE",
    "MORNING_MODE",
]

MANUAL_MODE_LABELS = {
    "LECTURE_MODE": "Lecture Mode — สว่างเต็มห้อง",
    "PRESENT_MODE": "Present Mode — โปรเจกเตอร์/สไลด์",
    "GROUP_MODE": "Group Mode — แสงสม่ำเสมอ",
    "AUTO_DIM": "Auto Dim — ลดแสงเมื่อแสงธรรมชาติมาก",
    "ENERGY_SAVE": "Energy Save — ประหยัดไฟ",
    "MORNING_MODE": "Morning Mode — แสงเช้า",
}

MANUAL_MODE_DESC = {
    "LECTURE_MODE": "Full brightness · No projector",
    "PRESENT_MODE": "Projector on · Dim front lights",
    "GROUP_MODE": "Even lighting · Collaboration",
    "AUTO_DIM": "Natural light detected · Dimming",
    "ENERGY_SAVE": "Few people · Most lights off",
    "MORNING_MODE": "Early class · Warm sunrise light",
}


def render_control_panel(is_admin: bool, actor: str | None, actor_role: str):
    st.subheader("Control")
    chosen = None

    def set_brightness_preset(preset: int) -> None:
        st.session_state["m_brightness"] = preset

    def reset_brightness_to_default() -> None:
        if st.session_state.get("m_proj_state"):
            st.session_state["m_brightness"] = 0
        else:
            default_bright = st.session_state.get("manual_default_brightness", 100)
            st.session_state["m_brightness"] = default_bright

    def sync_projector_brightness() -> None:
        if st.session_state.get("m_proj_state"):
            st.session_state["m_brightness"] = 0
        else:
            default_bright = st.session_state.get("manual_default_brightness", 100)
            st.session_state["m_brightness"] = default_bright

    # ── Step 1: วิชา ──────────────────────────────────────────
    st.markdown("**Step 1 — วิชาที่กำลังสอน**")
    teacher_for_courses = actor if not is_admin else None

    if is_admin:
        all_p = get_teacher_profiles()
        t_opts = ["— อาจารย์ —"] + [r[0] for r in all_p]
        adm_t = st.selectbox("เลือกอาจารย์", t_opts, key="adm_t_filt")
        teacher_for_courses = None if adm_t == "— อาจารย์ —" else adm_t

    courses = get_courses(teacher_for_courses)
    cproj_default = 0

    if courses:
        if teacher_for_courses:
            c_opts = {f"{r[1]} — {r[2]} ({r[3]}h)": r for r in courses}
        else:
            c_opts = {f"[{r[1]}] {r[2]} — {r[3]} ({r[4]}h)": r for r in courses}

        sel_cl = st.selectbox("วิชา", ["— ยังไม่เลือก —"] + list(c_opts.keys()), key="course_sel")
        if sel_cl != "— ยังไม่เลือก —":
            cd = c_opts[sel_cl]
            cid, ccode, cname, chours, cproj_default = (cd[0], cd[1], cd[2], cd[3], cd[4]) \
                if teacher_for_courses else (cd[0], cd[2], cd[3], cd[4], cd[5])
            st.session_state["active_course_id"] = cid
            st.markdown(
                f'<div class="chip">{ccode}</div>'
                f'<div class="chip">{chours}h</div>'
                f'<div class="chip">{"" if cproj_default else ""}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.session_state["active_course_id"] = None
    else:
        st.caption("ยังไม่มีวิชา → ไปแท็บ ")

    st.markdown("---")

    # ── Step 2: โปรไฟล์อาจารย์ ───────────────────────────────
    st.markdown("**Step 2 — โปรไฟล์อาจารย์**")
    profs2 = get_teacher_profiles()

    if is_admin:
        t_opts2 = ["— ไม่ระบุ —"] + [r[0] for r in profs2]
        sel_t2 = st.selectbox("อาจารย์ประจำคาบ", t_opts2, key="adm_prof")
    else:
        sel_t2 = actor

    prof = next((r for r in profs2 if r[0] == sel_t2), None) \
        if sel_t2 and sel_t2 != "— ไม่ระบุ —" else None

    if prof:
        t_name, t_mode, t_lux, t_notes, _ = prof
        ico = MODE_ICONS.get(t_mode, "")
        st.markdown(f"""<div style="background:#0d1f2d;border-radius:8px;padding:10px;
            border-left:3px solid #a78bfa;margin:6px 0;">
            <b style="color:#fff;">{ico} {t_mode.replace('_', ' ')}</b>
            &nbsp;<span style="color:#888;font-size:.8rem;">Lux {t_lux}</span><br>
            <span style="color:#666;font-size:.75rem;">{t_notes or '—'}</span>
            </div>""", unsafe_allow_html=True)

        if st.button(f"ใช้โปรไฟล์ {t_name}", use_container_width=True, type="primary", key="use_prof"):
            mode_presets = {
                "PRESENT_MODE": {"lux": t_lux, "people": 30, "projector": True,  "hour": 13},
                "LECTURE_MODE": {"lux": t_lux, "people": 35, "projector": False, "hour": 10},
                "GROUP_MODE":   {"lux": t_lux, "people": 18, "projector": False, "hour": 14},
                "AUTO_DIM":     {"lux": max(t_lux, 550), "people": 25, "projector": False, "hour": 12},
                "ENERGY_SAVE":  {"lux": t_lux, "people": 3,  "projector": False, "hour": 17},
                "MORNING_MODE": {"lux": t_lux, "people": 15, "projector": False, "hour": 8},
            }
            p = mode_presets.get(t_mode, {"lux": t_lux, "people": 25, "projector": False, "hour": 10})
            st.session_state["chosen_override"] = {
                "name": f"{t_name}",
                "triggered_by": "teacher_profile",
                "desc": f"โปรไฟล์ {t_name}",
                "teacher_name": t_name,
                "course_id": st.session_state.get("active_course_id"),
                **p,
            }

    st.markdown("---")

    # ── Step 3: จำนวนคนโดยประมาณ ───────────────────────────
    st.markdown("**Step 3 — จำนวนคนโดยประมาณ**")
    m_ppl = st.slider("จำนวนนักศึกษา (คน)", 0, 50, 25, key="m_ppl")
    m_lux  = st.slider("แสงธรรมชาติ (Lux)", 50, 800, 300, 10, key="m_lux")
    from ai_logic import auto_brightness_level
    default_bright = auto_brightness_level(m_ppl)
    if st.session_state.get("manual_people_prev") != m_ppl:
        st.session_state["m_brightness"] = 0 if st.session_state.get("m_proj_state") else default_bright
    st.session_state["manual_people_prev"] = m_ppl
    st.session_state["manual_default_brightness"] = default_bright
    st.markdown(
        f"""
        <div style="padding:10px 12px;border:1px solid rgba(96,165,250,.18);border-radius:10px;
        background:rgba(15,23,42,.55);margin-top:8px;margin-bottom:8px;">
          <div style="font-size:.85rem;color:#cbd5e1;">Bright ตามจำนวนคน</div>
          <div style="font-size:1.35rem;font-weight:800;color:#fff;">{default_bright}%</div>
          <div style="font-size:.72rem;color:#94a3b8;">ปรับได้เองด้านล่าง ถ้าเปลี่ยนจำนวนนักศึกษา จะรีเซ็ตกลับค่าพื้นฐานอัตโนมัติ</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Step 4: โปรเจกเตอร์ ──────────────────────────────────
    st.markdown("**Step 4 — โปรเจกเตอร์**")
    proj_state = st.toggle(
        "🎥 เปิด/ปิดโปรเจกเตอร์",
        value=st.session_state.get("m_proj_state", False),
        key="m_proj_state",
        on_change=sync_projector_brightness,
    )

    # ── Step 5: สถานการณ์ ─────────────────────────────────────
    st.markdown("**Step 5 — เลือกสถานการณ์สำหรับห้อง**")
    sc_cols = st.columns(2)
    for i, sc in enumerate(SCENARIOS):
        if sc_cols[i % 2].button(sc["name"], use_container_width=True, key=f"sc_{i}"):
            st.session_state["chosen_override"] = {
                **sc,
                "triggered_by": "scenario",
                "teacher_name": actor if not is_admin else None,
                "course_id":    st.session_state.get("active_course_id"),
            }

    st.markdown("---")

    # ── Auto / Random / Test ──────────────────────────────────
    a1, a2 = st.columns(2)
    auto_run = a1.toggle("Auto", value=False, key="auto_toggle")

    if is_admin and a2.button("20 Test", use_container_width=True):
        from test_scenarios import run_tests
        res, acc, sav = run_tests(save_to_db=True)
        st.session_state.update({"test_results": res, "test_accuracy": acc, "test_saving": sav})
        log_activity("Admin", "admin", "TEST_20", f"Accuracy={acc:.1f}%")

    if auto_run:
        chosen = {
            "name":         "Auto",
            "triggered_by": "auto_run",
            "teacher_name": actor if not is_admin else None,
            "course_id":    st.session_state.get("active_course_id"),
            "lux":          random.randint(100, 700),
            "people":       random.randint(0, 50),
            "projector":    random.choice([True, False]),
            "hour":         random.randint(7, 18),
            "desc":         "Auto-Run",
        }
        time.sleep(1)
        st.rerun()

    if st.button("Random", use_container_width=True, type="primary"):
        chosen = {
            "name":         "Random",
            "triggered_by": "manual",
            "teacher_name": actor if not is_admin else None,
            "course_id":    st.session_state.get("active_course_id"),
            "lux":          random.randint(100, 700),
            "people":       random.randint(0, 50),
            "projector":    random.choice([True, False]),
            "hour":         random.randint(7, 18),
            "desc":         "สุ่มค่า",
        }

    st.markdown("---")

    # ── Manual Lighting ───────────────────────────────────────
    st.markdown("**Manual — ปรับแสงไฟ / โหมดการนำเสนอ**")
    st.caption("โหมดนี้ไม่ผูกกับจำนวนคนแล้ว เลือกโหมดแสงเองได้โดยตรง")

    manual_mode = st.selectbox(
        "โหมดแสง/การนำเสนอ",
        MANUAL_MODE_OPTIONS,
        format_func=lambda mode_key: MANUAL_MODE_LABELS.get(mode_key, mode_key),
        key="manual_mode",
    )

    proj_state = st.session_state.get("m_proj_state", proj_state)
    bright_default = 0 if proj_state else default_bright
    bright_label = "แสงเพิ่มเติมโหมดโปรเจกเตอร์ (%)" if proj_state else "หลอด Bright (%)"

    m_brightness = st.slider(
        bright_label,
        10,
        100,
        st.session_state.get("m_brightness", bright_default),
        key="m_brightness",
    )
    if proj_state:
        st.caption("โหมดโปรเจกเตอร์เริ่มที่ 0% และเพิ่มแสงเสริมได้ตามต้องการ")
    else:
        st.caption(f"ปรับลด/เพิ่มแสงได้จากค่า default {default_bright}%")

    bright_cols = st.columns(4)
    for idx, preset in enumerate([25, 50, 75, 100]):
        bright_cols[idx].button(
            f"{preset}%",
            use_container_width=True,
            key=f"bright_{preset}",
            on_click=set_brightness_preset,
            args=(preset,),
        )

    st.button(
        "↩กลับค่าแสงตามจำนวนนักศึกษา",
        use_container_width=True,
        key="reset_bright",
        on_click=reset_brightness_to_default,
    )

    m_hour = st.slider("ชั่วโมง (0–23)", 0, 23, 10, key="m_hour")

    realtime_manual = st.toggle("Realtime Manual", value=True, key="manual_realtime")

    manual_payload = {
        "name":         "Manual",
        "triggered_by": "manual_realtime" if realtime_manual else "manual",
        "lux":          m_lux,
        "people":       m_ppl,
        "mode":         manual_mode,
        "mode_desc":    MANUAL_MODE_DESC.get(manual_mode, manual_mode),
        "brightness_pct": m_brightness,
        "projector":    proj_state,
        "hour":         m_hour,
        "desc":         f"{MANUAL_MODE_LABELS.get(manual_mode, manual_mode)} | {m_ppl} คน | Bright {m_brightness}% | Lux {m_lux} | {'Proj ON' if proj_state else 'Proj OFF'} | {m_hour}:00",
        "teacher_name": actor if not is_admin else None,
        "course_id":    st.session_state.get("active_course_id"),
    }

    if realtime_manual:
        chosen = manual_payload

    if st.button("รัน Manual", use_container_width=True, key="run_manual"):
        chosen = {**manual_payload, "triggered_by": "manual"}

    if "chosen_override" in st.session_state:
        chosen = st.session_state.pop("chosen_override")

    return chosen