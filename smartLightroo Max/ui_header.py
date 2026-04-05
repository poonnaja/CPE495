import streamlit as st
from database import get_teacher_profiles, log_activity


def render_header():
    with st.container():
        hA, hB = st.columns([2.5, 1.5])

        with hA:
            st.title("Smart Classroom Lighting")
            st.markdown(
                "<div style='color: #888; margin-top: -15px;'>"
                "<b>CPE495 – Group F</b> | AI-Powered Lighting Control & SQLite System"
                "</div>",
                unsafe_allow_html=True,
            )

        with hB:
            # ───────── ROLE ─────────
            rc = st.radio(
                "สิทธิ์การเข้าถึง",
                ["Admin", "Teacher"],
                horizontal=True,
                key="role_radio",
                index=0 if st.session_state.get("role") == "admin" else 1,
                label_visibility="collapsed",
            )

            new_role = "admin" if "Admin" in rc else "teacher"
            if st.session_state.get("role") != new_role:
                st.session_state["role"] = new_role
                st.rerun()

            # ───────── TEACHER SELECT ─────────
            if st.session_state["role"] == "teacher":
                profs = get_teacher_profiles()
                t_names = [r[0] for r in profs]

                sel_t = st.selectbox(
                    "ยืนยันตัวตนอาจารย์",
                    ["— เลือกชื่ออาจารย์ —"] + t_names,
                    key="login_teacher",
                    label_visibility="collapsed",
                )

                prev = st.session_state.get("active_teacher")

                # 🔥 FIX: sync ค่าให้ตรงทันที
                if sel_t == "— เลือกชื่ออาจารย์ —":
                    st.session_state["active_teacher"] = None
                else:
                    st.session_state["active_teacher"] = sel_t
                    st.session_state["active_course_id"] = None

                    # log เฉพาะตอนเปลี่ยนจริง
                    if prev != sel_t:
                        log_activity(sel_t, "teacher", "LOGIN", f"{sel_t} เข้าสู่ระบบ")

            else:
                st.session_state["active_teacher"] = None


def render_status_badge(is_admin: bool, actor: str | None):
    # 🔥 ดึงค่าจาก selectbox โดยตรง
    sel_t = st.session_state.get("login_teacher")

    if is_admin:
        st.markdown(
            '<div class="status-badge status-admin">ระบบกำลังทำงานในโหมด: <b>Administrator</b></div>',
            unsafe_allow_html=True,
        )

    elif sel_t and sel_t != "— เลือกชื่ออาจารย์ —":
        st.markdown(
            f'<div class="status-badge status-teacher">ยินดีต้อนรับอาจารย์: <b>{sel_t}</b></div>',
            unsafe_allow_html=True,
        )

    else:
        st.markdown(
            '<div class="status-badge status-warning">กรุณาเลือกชื่ออาจารย์ เพื่อเข้าใช้งานระบบ</div>',
            unsafe_allow_html=True,
        )