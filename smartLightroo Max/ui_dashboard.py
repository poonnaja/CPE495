import streamlit as st
from database import get_summary


def render_dashboard():
    st.markdown('<div class="dashboard-header">System Overview</div>', unsafe_allow_html=True)
    st.markdown("""
    <style>
    .kpi-card {
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    </style>
    """, unsafe_allow_html=True)

    total, avg_sv, mode_counts, proj_cnt, tot_saved = get_summary()

    with st.container():
        cols = st.columns(4, gap="medium")

        with cols[0]:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">การวิเคราะห์ทั้งหมด</div>
                    <div class="kpi-val green">{total} <span style="font-size:0.9rem; font-weight:400;">ครั้ง</span></div>
                </div>
            """, unsafe_allow_html=True)

        with cols[1]:
            saving_color = "green" if avg_sv >= 30 else "yellow"
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">ประหยัดเฉลี่ย</div>
                    <div class="kpi-val {saving_color}">{avg_sv}%</div>
                    <div style="font-size:0.7rem; color:#555; margin-top:4px;">Target: 30%</div>
                </div>
            """, unsafe_allow_html=True)

        with cols[2]:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">เปิดโปรเจกเตอร์</div>
                    <div class="kpi-val red">{proj_cnt} <span style="font-size:0.9rem; font-weight:400;">ครั้ง</span></div>
                </div>
            """, unsafe_allow_html=True)

        with cols[3]:
            val_display = f"{tot_saved/1000:.2f} k" if tot_saved > 9999 else tot_saved
            unit = "kW" if tot_saved > 9999 else "W"
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">พลังงานที่ประหยัดได้</div>
                    <div class="kpi-val green">{val_display} <span style="font-size:0.9rem; font-weight:400;">{unit}</span></div>
                </div>
            """, unsafe_allow_html=True)