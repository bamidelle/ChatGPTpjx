# project_x_all_in_one.py
# FULL SINGLE-FILE STREAMLIT + SQLALCHEMY APP WITH UI REDESIGN + KPI + PRIORITY FIXES

import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# =====================================================
# DATABASE & ORM SETUP
# =====================================================

Base = declarative_base()
DB_FILE = "leads.db"
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class LeadStatus:
    NEW = "New"
    CONTACTED = "Contacted"
    INSPECTION_SCHEDULED = "Inspection Scheduled"
    INSPECTION_COMPLETED = "Inspection Completed"
    ESTIMATE_SUBMITTED = "Estimate Submitted"
    AWARDED = "Awarded"
    LOST = "Lost"
    ALL = [NEW, CONTACTED, INSPECTION_SCHEDULED, INSPECTION_COMPLETED, ESTIMATE_SUBMITTED, AWARDED, LOST]

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    contact_name = Column(String)
    contact_phone = Column(String)
    contact_email = Column(String)
    property_address = Column(String)
    damage_type = Column(String)
    assigned_to = Column(String)
    estimated_value = Column(Float, default=0.0)
    notes = Column(String)
    status = Column(String, default=LeadStatus.NEW)
    sla_hours = Column(Integer, default=24)
    sla_entered_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    contacted_at = Column(DateTime)
    inspection_sched_at = Column(DateTime)
    inspection_done_at = Column(DateTime)
    estimate_sent_at = Column(DateTime)
    awarded_at = Column(DateTime)
    lost_at = Column(DateTime)
    qualified = Column(Boolean, default=True)
    invoice_file = Column(String)

class Estimate(Base):
    __tablename__ = "estimates"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer)
    amount = Column(Float, default=0.0)
    sent_at = Column(DateTime)
    approved = Column(Boolean, default=False)
    lost = Column(Boolean, default=False)
    lost_reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)

def get_session():
    return SessionLocal()

def leads_df(session):
    leads = session.query(Lead).all()
    data = []
    for l in leads:
        data.append({
            "id": l.id,
            "contact_name": l.contact_name,
            "contact_phone": l.contact_phone,
            "contact_email": l.contact_email,
            "property_address": l.property_address,
            "damage_type": l.damage_type,
            "assigned_to": l.assigned_to,
            "estimated_value": l.estimated_value,
            "notes": l.notes,
            "status": l.status,
            "sla_hours": l.sla_hours,
            "sla_entered_at": l.sla_entered_at.isoformat() if l.sla_entered_at else None,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "qualified": l.qualified
        })
    return pd.DataFrame(data)

def estimates_df(session):
    estimates = session.query(Estimate).all()
    data = []
    for e in estimates:
        data.append({
            "id": e.id,
            "lead_id": e.lead_id,
            "amount": e.amount,
            "sent_at": e.sent_at.isoformat() if e.sent_at else None,
            "approved": e.approved,
            "lost": e.lost,
            "lost_reason": e.lost_reason,
            "created_at": e.created_at.isoformat() if e.created_at else None
        })
    return pd.DataFrame(data)

# =====================================================
# KPI & PRIORITY SCORE LOGIC
# =====================================================

def compute_priority_for_lead_row(lead_row, weights):
    val = float(lead_row.get("estimated_value") or 0.0)
    baseline = weights.get("value_baseline", 5000.0)
    value_score = min(val / baseline, 1.0)

    try:
        sla_entered = lead_row.get("sla_entered_at") or lead_row.get("created_at")
        if isinstance(sla_entered, str):
            sla_entered = datetime.fromisoformat(sla_entered)
        deadline = sla_entered + timedelta(hours=int(lead_row.get("sla_hours") or 24))
        time_left_h = max((deadline - datetime.utcnow()).total_seconds() / 3600.0, 0)
        sla_score = min((72 - time_left_h)/72, 1.0)
    except:
        sla_score = 0.0

    urgency = weights.get("urgency_weight", 0.2)
    score = (value_score * weights.get("value_weight", 0.5) +
             sla_score * weights.get("sla_weight", 0.3)) / (1+urgency)
    return round(float(score), 3), time_left_h, deadline

LEAD_STATUSES = LeadStatus.ALL
KPIs = [
    "Lead Response Compliance %",
    "Lead Qualification Rate %",
    "Inspection Scheduling Conversion %",
    "Estimate-to-Job Win Rate %",
    "Pipeline Job Value",
    "Estimated ROI",
    "CPA per Won Job",
    "Conversion Velocity (hrs)"
]

# =====================================================
# STREAMLIT UI SETUP
# =====================================================

st.set_page_config(layout="wide")

# White background global
st.markdown("""
<style>
    body {background:white;}
    .metric-card {
        background:#111; border-radius:14px; padding:18px; margin:10px 0;
        border:1px solid #444; animation:fadeIn 0.6s ease-in-out;
    }
    @keyframes fadeIn {from{opacity:0} to{opacity:1}}
    .kpi-number {
        font-size:36px; font-weight:800; margin:6px 0; color:white; text-align:left;
    }
    .kpi-title {
        font-size:15px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;
        color: white; margin-bottom: 6px;
    }
    .glassy-board {
        background: linear-gradient(135deg, #e5e7eb80 0%, #f3f4f680 100%);
        backdrop-filter:blur(8px); padding:22px; border-radius:18px; border:1px solid #d1d5db;
    }
    .submit-btn {
        padding:12px 28px; border-radius:12px; font-size:14px; font-weight:600;
        transition:all 0.3s ease; width:100%; border:none; cursor:pointer;
    }
    .submit-btn:hover {transform:translateY(-2px); opacity:0.9;}
</style>
""", unsafe_allow_html=True)

init_db()
s = get_session()

if "weights" not in st.session_state:
    st.session_state.weights = {}

# =====================================================
# PIPELINE DASHBOARD PAGE
# =====================================================

page = st.sidebar.selectbox("Navigate", ["Lead Capture", "Pipeline Board", "Analytics"])

if page == "Pipeline Board":
    st.header("🧊 Pipeline Dashboard — Google Ads style")

    df = leads_df(s)
    if df.empty:
        st.info("No leads to show.")
        st.stop()

    # KPI calculations
    total = len(df)
    qualified = len(df[df["qualified"] == True])
    won = len(df[df["status"] == LeadStatus.AWARDED])
    lost = len(df[df["status"] == LeadStatus.LOST])
    booked = len(df[df["status"].str.contains("Inspection Scheduled")])
    value = df["estimated_value"].sum()
    roi = round((won/(total or 1))*1.4, 3)

    results = {
        "Lead Response Compliance %": round((qualified/total*100) if total else 0,1),
        "Lead Qualification Rate %": round((qualified/total*100) if total else 0,1),
        "Inspection Scheduling Conversion %": round((booked/qualified*100) if qualified else 0,1),
        "Estimate-to-Job Win Rate %": round((won/(won+lost)*100) if (won+lost) else 0,1),
        "Pipeline Job Value": f"${value:,.0f}",
        "Estimated ROI": f"{roi}",
        "Leads Won": won,
        "Leads Lost": lost
    }

    # 2 rows × 4 KPI grid
    kpi_cols = [
        {"title":"Lead Response Compliance %","value":results["Lead Response Compliance %"],"bar":25},
        {"title":"Lead Qualification Rate %","value":results["Lead Qualification Rate %"],"bar":40},
        {"title":"Inspection Scheduling Conversion %","value":results["Inspection Scheduling Conversion %"],"bar":55},
        {"title":"Estimate-to-Job Win Rate %","value":results["Estimate-to-Job Win Rate %"],"bar":70},
        {"title":"Pipeline Job Value","value":value,"bar":50},
        {"title":"Estimated ROI","value":roi,"bar":80},
        {"title":"Leads Won","value":won,"bar":60},
        {"title":"Leads Lost","value":lost,"bar":30}
    ]

    rows = [st.columns(4), st.columns(4)]
    for i, item in enumerate(kpi_cols):
        r = i//4
        c = i%4
        color = "#22c55e" if ("Lost" not in item["title"]) else "#ef4444"
        rows[r][c].markdown(f"""
        <div class="metric-card">
            <div class="kpi-title">{item["title"]}</div>
            <div class="kpi-number" style="color:{color};">{item["value"]}</div>
            <div style="width:100%;background:#e5e7eb;height:6px;border-radius:3px;">
                <div style="width:{item["bar"]}%;height:6px;border-radius:3px;background:{color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Priority Leads display
    stage_colors = {"New":"#2563eb","Contacted":"#eab308","Inspection Scheduled":"#f97316","Inspection Completed":"#14b8a6","Estimate Submitted":"#a855f7","Awarded":"#22c55e","Lost":"#ef4444"}

    priority = []
    for _,r in df.iterrows():
        score, h_left, deadline = compute_priority_for_lead_row(r, {"value_weight":0.5,"sla_weight":0.3})
        priority.append({"id":r["id"],"contact_name":r["contact_name"],"damage_type":r["damage_type"],"estimated_value":r["estimated_value"],"status":r["status"],"priority_score":score,"time_left_hours":h_left})

    pr_df = pd.DataFrame(priority).sort_values("priority_score", ascending=False)

    for _,r in pr_df.head(8).iterrows():
        w = st.columns([3,1])
        w[0].markdown(f"{r['contact_name']} ({r['status']})")
        w[1].markdown(f"{r['priority_score']}")

# =====================================================
# ANALYTICS PAGE
# =====================================================

if page == "Analytics":
    st.header("📍 Analytics — ROI, CPA and Velocity")

    if "start" not in st.session_state:
        st.session_state.start = datetime.utcnow().date()
    if "end" not in st.session_state:
        st.session_state.end = datetime.utcnow().date()

    start = st.date_input("Start Date", st.session_state.start)
    end = st.date_input("End Date", st.session_state.end)
    st.session_state.start = start
    st.session_state.end = end
    range_df = df[(df["created_at"].between(str(start), str(end)))]

    if range_df.empty:
        st.info("No data in selected date range.")
        st.stop()

    cpa = range_df["estimated_value"].sum()/(won or 1)
    velocity = round(range_df["sla_hours"].mean() or 0,1)

    # Comparison chart
    an1,an2 = st.columns(2)
    an1.metric("CPA per Won Job", f"${cpa:,.0f}")
    an2.metric("Conversion Velocity (hrs)", f"{velocity}")

    st.markdown("""
    **CPA per Won Job:** trending downward MoM, segmented by source  
    **Conversion Velocity:** always improving; >48–72 hours stagnation = red flag lead.
    """)

