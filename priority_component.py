import streamlit as st
from datetime import datetime, timedelta

# =====================================================
#  PRIORITY LEADS COMPONENT (STANDALONE)
# =====================================================

def render_priority_leads(priority_df, stage_colors):
    """
    Renders the Priority Leads (Top 8) section.
    priority_df must be a pandas DataFrame containing:
    id, contact_name, status, estimated_value, damage_type,
    priority_score, time_left_hours
    """

    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Comfortaa:wght@600&display=swap');

        .priority-card {
            background: #111111;
            padding: 18px;
            border-radius: 14px;
            margin-bottom: 14px;
            border: 1px solid #333;
            font-family: 'Poppins', sans-serif;
        }
        .priority-label {
            font-size: 14px;
            font-weight: 700;
        }
        .priority-score {
            font-size: 28px;
            font-weight: 800;
            text-align: right;
        }
        .priority-meta {
            font-size: 11px;
            color: #777;
            text-transform: uppercase;
            text-align: right;
        }
        .stage-badge {
            padding: 5px 10px;
            border-radius: 14px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

    if priority_df.empty:
        st.info("No priority leads available.")
        return

    # Loop through top 8 priority leads
    for _, r in priority_df.head(8).iterrows():

        score = float(r["priority_score"])
        status = r["status"]
        color = stage_colors.get(status, "#888")
        name = r["contact_name"] or "No Name"
        est = float(r.get("estimated_value") or 0.0)
        dmg = (r.get("damage_type") or "Unknown").title()
        time_left = float(r.get("time_left_hours") or 0)

        # Priority label logic
        if score >= 0.7:
            p_color = "#ef4444"
            p_label = "🔴 CRITICAL"
        elif score >= 0.45:
            p_color = "#f97316"
            p_label = "🟠 HIGH"
        else:
            p_color = "#22c55e"
            p_label = "🟢 NORMAL"

        # SLA
        if time_left <= 0:
            sla_html = "<span style='color:#ef4444; font-weight:700;'>❗ OVERDUE</span>"
        else:
            h = int(time_left)
            m = int((time_left * 60) % 60)
            sla_html = f"<span style='color:#ef4444; font-weight:700;'>⏳ {h}h {m}m left</span>"

        # Render card
        st.markdown(f"""
        <div class="priority-card">

            <div style="display:flex; justify-content:space-between; align-items:center;">

                <div style="flex:1;">
                    <div style="margin-bottom:6px;">
                        <span class="priority-label" style="color:{p_color};">{p_label}</span>
                        <span class="stage-badge" 
                              style="background:{color}20; color:{color}; border:1px solid {color}40;">
                            {status}
                        </span>
                    </div>

                    <div style="font-size:20px; font-weight:700; color:white;">
                        #{int(r["id"])} — {name}
                    </div>

                    <div style="font-size:13px; color:#aaa; margin-top:4px;">
                        {dmg} | Est: <span style="color:#22c55e; font-weight:700;">
                        ${est:,.0f}</span>
                    </div>

                    <div style="margin-top:6px; font-size:13px;">
                        {sla_html}
                    </div>
                </div>

                <div style="padding-left:20px;">
                    <div class="priority-score" style="color:{p_color};">{score:.2f}</div>
                    <div class="priority-meta">Priority</div>
                </div>

            </div>

        </div>
        """, unsafe_allow_html=True)

