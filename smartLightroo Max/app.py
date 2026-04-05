import streamlit as st
import pandas as pd

from config import init_session_state
from utils import load_app_styles
from ai_logic import recommend_mode, get_full_ai_state, auto_brightness_level
from database_pg import clear_all_logs, log_activity

from ui_header import render_header, render_status_badge
from ui_dashboard import render_dashboard
from ui_control import render_control_panel
from ui_scene import render_scene
from ui_result import render_result
from ui_database import render_database_tabs

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Classroom Lighting",
    page_icon="",
    layout="wide",
)

# ─────────────────────────────────────────────
# GLOBAL STYLE (ปรับเต็มจอ)
# ─────────────────────────────────────────────
st.markdown(f"""
<style>
{load_app_styles()}

/* 🔥 เต็มจอ */
.block-container {{
    max-width: 100% !important;
    padding-left: 2rem;
    padding-right: 2rem;
}}

/* 🔥 scene */
.scene-container {{
    width: 100%;
    height: 520px;
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid #1e293b;
    background: #020617;
}}

/* spacing */
.section-gap {{
    margin-top: 1.2rem;
}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────
init_session_state(st)

IS_ADMIN   = st.session_state["role"] == "admin"
ACTOR      = st.session_state.get("active_teacher") if not IS_ADMIN else "Admin"
ACTOR_ROLE = "admin" if IS_ADMIN else "teacher"

# ═════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════
render_header()
render_status_badge(IS_ADMIN, ACTOR)
st.divider()

# ═════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════
render_dashboard()
st.divider()

# ═════════════════════════════════════════════
# 🔥 SCENE เต็มจอ
# ═════════════════════════════════════════════
new_proj = render_scene(height=540)

# ═════════════════════════════════════════════
# 🎛 CONTROL + RESULT (ล่าง)
# ═════════════════════════════════════════════
st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

col_ctrl, col_result = st.columns([2, 1], gap="large")

with col_ctrl:
    chosen = render_control_panel(IS_ADMIN, ACTOR, ACTOR_ROLE)

# ── UPDATE AI
if chosen or st.session_state.get("last_sc"):
    sc = chosen if chosen else st.session_state.get("last_sc", {})

    # If user toggles projector from the 3D scene, sync that override into live state.
    if not chosen and sc:
        sc = {**sc, "projector": bool(new_proj)}

    ai_state = get_full_ai_state(
        people_count=sc["people"],
        lux=sc["lux"],
        projector_on=sc["projector"],
        hour=sc["hour"],
        brightness_pct=sc.get("brightness_pct"),
    )

    if sc.get("mode"):
        mode = sc["mode"]
        emoji = ""
        desc = sc.get("mode_desc", sc.get("desc", ""))
        baseline = recommend_mode(sc["lux"], sc["people"], sc["projector"], sc["hour"])[4]
        brightness_pct = sc.get("brightness_pct", auto_brightness_level(sc["people"]))
        ai_state = {**ai_state, "mode": mode, "brightness": brightness_pct}
    else:
        mode, emoji, desc, _, baseline = recommend_mode(
            sc["lux"],
            sc["people"],
            sc["projector"],
            sc["hour"]
        )

    sc = {**sc, "brightness_pct": ai_state["brightness"]}
    st.session_state["last_mode"] = mode
    st.session_state["last_sc"]   = sc
    st.session_state["last_ai_state"] = ai_state

    st.session_state["proj_override"][ai_state["mode"]] = bool(sc["projector"])

with col_result:
    render_result(IS_ADMIN, ACTOR, ACTOR_ROLE, chosen, new_proj)

# ═════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════
st.divider()
render_database_tabs(IS_ADMIN, ACTOR, ACTOR_ROLE)

# ═════════════════════════════════════════════
# ADMIN
# ═════════════════════════════════════════════
st.divider()

if IS_ADMIN:
    if st.button("ล้าง Log ทั้งหมด", type="secondary"):
        clear_all_logs()
        log_activity("Admin", "admin", "CLEAR_LOGS", "")
        st.rerun()

# ═════════════════════════════════════════════
# TEST
# ═════════════════════════════════════════════
if IS_ADMIN and "test_results" in st.session_state:

    st.subheader("Test Results")

    acc = st.session_state["test_accuracy"]
    sav = st.session_state["test_saving"]

    ta, tb = st.columns(2)

    ta.metric("Accuracy", f"{acc:.1f}%")
    tb.metric("Saving", f"{sav:.1f}%")

    dt = pd.DataFrame(st.session_state["test_results"])

    st.dataframe(dt, use_container_width=True)

st.caption("Smart Classroom Lighting System")