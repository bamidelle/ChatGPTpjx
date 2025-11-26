# project_x_singlefile.py
"""
Project X — Single-file Streamlit app (Option A)
- Pipeline Dashboard (Google Ads style look + KPI set requested)
- White app background, pipeline area with glassy dark cards
- KPI: SLA Success %, Qualification Rate, Inspection Scheduling Conversion,
       Estimate-to-Job Win Rate, CPA per Won Job (placeholder), Conversion Velocity
- Pipeline cards arranged in 2 rows x 4 columns
- Priority Leads (Top 8)
- Expandable All Leads with status update, AWARDED allows invoice upload
- Job Value Estimate (USD) creation
- Defensive imports: plotly / joblib optional
- Uses SQLite (SQLAlchemy). No external network calls.
"""
import os
from datetime import datetime, timedelta
import tempfile
import traceback

import streamlit as st
import pandas as pd

# Optional libs; handled defensively
try:
    import plotly.express as px
except Exception:
    px = None

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, inspect
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# ---------------------------
# Config / DB
# ---------------------------
DB_FILE = os.getenv("PROJECT_X_DB", "project_x_singlefile.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# ---------------------------
# Lead statuses & colors
# ---------------------------
class LeadStatus:
    NEW = "New"
    CONTACTED = "Contacted"
    INSPECTION_SCHEDULED = "Inspection Scheduled"
    INSPECTION_COMPLETED = "Inspection Completed"
    ESTIMATE_SUBMITTED = "Estimate Submitted"
    AWARDED = "Awarded"
    LOST = "Lost"

    ALL = [
        NEW,
        CONTACTED,
        INSPECTION_SCHEDULED,
        INSPECTION_COMPLETED,
        ESTIMATE_SUBMITTED,
        AWARDED,
        LOST,
    ]

STAGE_COLORS = {
    LeadStatus.NEW: "#2563eb",
    LeadStatus.CONTACTED: "#eab308",
    LeadStatus.INSPECTION_SCHEDULED: "#f97316",
    LeadStatus.INSPECTION_COMPLETED: "#14b8a6",
    LeadStatus.ESTIMATE_SUBMITTED: "#a855f7",
    LeadStatus.AWARDED: "#22c55e",
    LeadStatus.LOST: "#ef4444",
}

# ---------------------------
# ORM models
# ---------------------------
class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    source = Column(String, default="Unknown")
    source_details = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    property_address = Column(String, nullable=True)
    damage_type = Column(String, nullable=True)
    assigned_to = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    estimated_value = Column(Float, nullable=True)
    status = Column(String, default=LeadStatus.NEW)
    created_at = Column(DateTime, default=datetime.utcnow)
    sla_hours = Column(Integer, default=24)
    sla_entered_at = Column(DateTime, nullable=True)
    # flags
    contacted = Column(Boolean, default=False)
    inspection_scheduled = Column(Boolean, default=False)
    inspection_scheduled_at = Column(DateTime, nullable=True)
    inspection_completed = Column(Boolean, default=False)
    estimate_submitted = Column(Boolean, default=False)
    # awarded / lost
    awarded_comment = Column(Text, nullable=True)
    awarded_date = Column(DateTime, nullable=True)
    awarded_invoice = Column(String, nullable=True)
    lost_comment = Column(Text, nullable=True)
    lost_date = Column(DateTime, nullable=True)
    qualified = Column(Boolean, default=False)

class Estimate(Base):
    __tablename__ = "estimates"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, nullable=False)
    amount = Column(Float, default=0.0)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved = Column(Boolean, default=False)
    lost = Column(Boolean, default=False)

# ---------------------------
# DB helpers
# ---------------------------
def init_db():
    Base.metadata.create_all(bind=engine)
    # safe migration placeholder: ensure table exists
    inspector = inspect(engine)
    if "leads" in inspector.get_table_names():
        return

def get_session():
    return SessionLocal()

def add_lead(session, **kwargs):
    lead = Lead(
        source=kwargs.get("source", "Unknown"),
        source_details=kwargs.get("source_details"),
        contact_name=kwargs.get("contact_name"),
        contact_phone=kwargs.get("contact_phone"),
        contact_email=kwargs.get("contact_email"),
        property_address=kwargs.get("property_address"),
        damage_type=kwargs.get("damage_type"),
        assigned_to=kwargs.get("assigned_to"),
        notes=kwargs.get("notes"),
        estimated_value=float(kwargs.get("estimated_value") or 0.0),
        sla_hours=int(kwargs.get("sla_hours") or 24),
        sla_entered_at=datetime.utcnow(),
        qualified=bool(kwargs.get("qualified", False)),
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead

def create_estimate(session, lead_id, amount, details=""):
    est = Estimate(lead_id=lead_id, amount=float(amount), details=details)
    session.add(est)
    session.commit()
    session.refresh(est)
    # mark lead accordingly
    lead = session.query(Lead).filter(Lead.id == lead_id).first()
    if lead:
        lead.estimate_submitted = True
        lead.estimate_submitted_at = datetime.utcnow()
        lead.status = LeadStatus.ESTIMATE_SUBMITTED
        session.add(lead)
        session.commit()
    return est

def save_uploaded_file(uploaded_file, prefix="file"):
    if uploaded_file is None:
        return None
    folder = os.path.join(os.getcwd(), "uploaded_files")
    os.makedirs(folder, exist_ok=True)
    fname = f"{prefix}_{int(datetime.utcnow().timestamp())}_{uploaded_file.name}"
    path = os.path.join(folder, fname)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path

def leads_df(session):
    rows = session.query(Lead).all()
    data = []
    for r in rows:
        data.append({
            "id": r.id,
            "source": r.source,
            "source_details": r.source_details,
            "contact_name": r.contact_name,
            "contact_phone": r.contact_phone,
            "contact_email": r.contact_email,
            "property_address": r.property_address,
            "damage_type": r.damage_type,
            "assigned_to": r.assigned_to,
            "notes": r.notes,
            "estimated_value": float(r.estimated_value or 0.0),
            "status": r.status,
            "created_at": r.created_at,
            "sla_hours": r.sla_hours or 24,
            "sla_entered_at": r.sla_entered_at or r.created_at,
            "contacted": bool(r.contacted),
            "inspection_scheduled": bool(r.inspection_scheduled),
            "inspection_scheduled_at": r.inspection_scheduled_at,
            "inspection_completed": bool(r.inspection_completed),
            "estimate_submitted": bool(r.estimate_submitted),
            "awarded_date": r.awarded_date,
            "awarded_invoice": r.awarded_invoice,
            "lost_date": r.lost_date,
            "qualified": bool(r.qualified),
        })
    df = pd.DataFrame(data)
    # ensure columns exist
    expected = ["id","source","contact_name","contact_phone","contact_email","property_address","damage_type",
                "assigned_to","notes","estimated_value","status","created_at","sla_hours","sla_entered_at",
                "contacted","inspection_scheduled","inspection_scheduled_at","inspection_completed","estimate_submitted",
                "awarded_date","awarded_invoice","lost_date","qualified"]
    for c in expected:
        if c not in df.columns:
            df[c] = pd.NA
    return df

def estimates_df(session):
    rows = session.query(Estimate).all()
    data = []
    for e in rows:
        data.append({
            "id": e.id,
            "lead_id": e.lead_id,
            "amount": e.amount,
            "details": e.details,
            "created_at": e.created_at,
            "approved": bool(e.approved),
            "lost": bool(e.lost),
        })
    return pd.DataFrame(data)

# ---------------------------
# Priority scoring & SLA utilities
# ---------------------------
def compute_priority_for_lead_row(lead_row, weights):
    # returns score 0..1 and time_left_hours
    try:
        val = float(lead_row.get("estimated_value") or 0.0)
    except Exception:
        val = 0.0
    baseline = float(weights.get("value_baseline", 5000.0))
    value_score = min(1.0, val / max(1.0, baseline))
    sla_entered = lead_row.get("sla_entered_at") or lead_row.get("created_at") or datetime.utcnow()
    if isinstance(sla_entered, str):
        try:
            sla_entered = datetime.fromisoformat(sla_entered)
        except:
            sla_entered = datetime.utcnow()
    try:
        deadline = sla_entered + timedelta(hours=int(lead_row.get("sla_hours") or 24))
        time_left_h = max((deadline - datetime.utcnow()).total_seconds() / 3600.0, 0.0)
    except Exception:
        time_left_h = 9999.0
    sla_score = max(0.0, (72.0 - min(time_left_h, 72.0)) / 72.0)
    contacted_flag = 0.0 if bool(lead_row.get("contacted")) else 1.0
    inspection_flag = 0.0 if bool(lead_row.get("inspection_scheduled")) else 1.0
    estimate_flag = 0.0 if bool(lead_row.get("estimate_submitted")) else 1.0
    urgency_component = (contacted_flag * weights.get("contacted_w", 0.6)
                        + inspection_flag * weights.get("inspection_w", 0.5)
                        + estimate_flag * weights.get("estimate_w", 0.5))
    total_weight = (weights.get("value_weight", 0.5)
                   + weights.get("sla_weight", 0.35)
                   + weights.get("urgency_weight", 0.15))
    if total_weight <= 0:
        total_weight = 1.0
    score = (value_score * weights.get("value_weight", 0.5)
            + sla_score * weights.get("sla_weight", 0.35)
            + urgency_component * weights.get("urgency_weight", 0.15)) / total_weight
    score = max(0.0, min(1.0, score))
    return score, time_left_h

# ---------------------------
# UI CSS (white app + pipeline dark cards)
# ---------------------------
APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&family=Comfortaa:wght@700&display=swap');

:root{
  --bg: #ffffff;
  --text: #0b0f13;
  --muted: #6b7280;
  --glass-bg: rgba(17,24,39,0.85); /* dark glassy for pipeline cards */
  --glass-opaque: rgba(255,255,255,0.06);
  --radius: 12px;
  --money: #16a34a;
}

body, .stApp {
  background: var(--bg);
  color: var(--text);
  font-family: 'Poppins', sans-serif;
}

/* header style */
.header { font-family: 'Comfortaa', cursive; font-size:22px; font-weight:700; color:var(--text); padding:10px 0; }

/* KPI card */
.kpi-card {
  border-radius: 12px;
  padding: 14px;
  margin: 6px;
  color: #fff;
  min-height: 86px;
  box-shadow: 0 6px 18px rgba(15,23,42,0.06);
  transition: transform .18s ease, box-shadow .18s ease;
}
.kpi-card:hover { transform: translateY(-6px); box-shadow: 0 14px 30px rgba(15,23,42,0.12); }

/* pipeline stage card (glassy dark) */
.stage-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.015));
  border-radius: 10px;
  padding: 12px;
  color: #fff;
  box-shadow: 0 6px 18px rgba(2,6,23,0.06);
}

/* rounded action button */
.round-btn {
  display:inline-block;
  padding:10px 18px;
  border-radius:999px;
  font-weight:600;
  cursor:pointer;
  border:none;
}

/* make submit buttons medium-long and animated */
button.stButton>button, .stButton>button {
  min-width: 170px;
  padding: 10px 18px;
  border-radius: 10px;
  font-weight:700;
  transition: transform .12s ease;
}
button.stButton>button:hover { transform: translateY(-3px); }

.small-muted { font-size:13px; color:var(--muted); }
.big-number { font-size:28px; font-weight:800; letter-spacing:-0.5px; }
.title-white { color:#ffffff; font-size:14px; font-weight:700; }
"""

# ---------------------------
# App start
# ---------------------------
st.set_page_config(page_title="Project X — Pipeline", layout="wide")
init_db()
st.markdown(f"<style>{APP_CSS}</style>", unsafe_allow_html=True)
st.markdown("<div class='header'>Project X — Sales & Pipeline</div>", unsafe_allow_html=True)

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    page = st.radio("Go to", ["Leads / Capture", "Pipeline Board", "Analytics & SLA", "Exports"], index=1)
    st.markdown("---")
    if "weights" not in st.session_state:
        st.session_state.weights = {
            "value_weight": 0.5,
            "sla_weight": 0.35,
            "urgency_weight": 0.15,
            "contacted_w": 0.6,
            "inspection_w": 0.5,
            "estimate_w": 0.5,
            "value_baseline": 5000.0
        }
    st.markdown("### Priority tuning")
    st.session_state.weights["value_weight"] = st.slider("Estimate value weight", 0.0, 1.0, float(st.session_state.weights["value_weight"]), step=0.05)
    st.session_state.weights["sla_weight"] = st.slider("SLA urgency weight", 0.0, 1.0, float(st.session_state.weights["sla_weight"]), step=0.05)
    st.session_state.weights["urgency_weight"] = st.slider("Flags urgency weight", 0.0, 1.0, float(st.session_state.weights["urgency_weight"]), step=0.05)
    st.session_state.weights["value_baseline"] = st.number_input("Value baseline", min_value=100.0, value=float(st.session_state.weights["value_baseline"]), step=100.0)

    st.markdown("---")
    if st.button("Add Demo Lead"):
        s = get_session()
        add_lead(s,
                 source="Google Ads",
                 source_details="gclid=demo",
                 contact_name="Demo Customer",
                 contact_phone="+15550000",
                 contact_email="demo@example.com",
                 property_address="100 Demo Ave",
                 damage_type="water",
                 assigned_to="Alex",
                 estimated_value=4500,
                 notes="Demo lead",
                 sla_hours=24,
                 qualified=True)
        st.success("Demo lead added to DB (Demo)")

# ---------------------------
# Page: Lead Capture
# ---------------------------
if page == "Leads / Capture":
    st.header("📇 Lead Capture")
    with st.form("lead_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            source = st.selectbox("Lead Source", ["Google Ads", "Organic Search", "Referral", "Phone", "Insurance", "Other"])
            source_details = st.text_input("Source details (UTM / notes)", placeholder="utm_source=google")
            contact_name = st.text_input("Contact name", placeholder="John Doe")
            contact_phone = st.text_input("Contact phone", placeholder="+1-555-0123")
            contact_email = st.text_input("Contact email", placeholder="name@example.com")
        with c2:
            property_address = st.text_input("Property address")
            damage_type = st.selectbox("Damage type", ["water","fire","mold","contents","reconstruction","other"])
            assigned_to = st.text_input("Assigned to")
            qualified_choice = st.selectbox("Is the Lead Qualified?", ["No","Yes"], index=1)
            sla_hours = st.number_input("SLA hours (first response)", min_value=1, value=24)
        notes = st.text_area("Notes")
        est_val = st.number_input("Estimated job value (USD)", min_value=0.0, value=0.0, step=100.0)
        submitted = st.form_submit_button("Create Lead")
        if submitted:
            s = get_session()
            lead = add_lead(
                s,
                source=source,
                source_details=source_details,
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_email=contact_email,
                property_address=property_address,
                damage_type=damage_type,
                assigned_to=assigned_to,
                notes=notes,
                sla_hours=int(sla_hours),
                qualified=(qualified_choice == "Yes"),
                estimated_value=float(est_val or 0.0)
            )
            st.success(f"Lead created (ID: {lead.id})")

    st.markdown("---")
    s = get_session()
    df_all = leads_df(s)
    if df_all.empty:
        st.info("No leads yet. Create one above.")
    else:
        st.subheader("Recent leads (table)")
        st.dataframe(df_all.sort_values("created_at", ascending=False).head(50))

# ---------------------------
# Page: Pipeline Board
# ---------------------------
elif page == "Pipeline Board":
    st.header("🧭 Pipeline Dashboard — Google Ads style (glassy cards)")

    s = get_session()
    leads = s.query(Lead).order_by(Lead.created_at.desc()).all()
    if not leads:
        st.info("No leads yet. Create one from Lead Capture.")
    else:
        df = leads_df(s)
        weights = st.session_state.weights

        # ------- KPIs (new requested KPIs) -------
        # 1. SLA Success % (contacts within SLA)
        def compute_sla_metrics(df):
            rows = []
            for _, r in df.iterrows():
                sla_entered = r.get("sla_entered_at") or r.get("created_at") or datetime.utcnow()
                if isinstance(sla_entered, str):
                    try:
                        sla_entered = datetime.fromisoformat(sla_entered)
                    except:
                        sla_entered = datetime.utcnow()
                sla_hours = int(r.get("sla_hours") or 24)
                deadline = sla_entered + timedelta(hours=sla_hours)
                # time to first contact unknown if not contacted
                # We'll approximate: if contacted True and inspection/estimate set, else mark as breach if now > deadline and not contacted
                breached = (datetime.utcnow() > deadline) and not bool(r.get("contacted"))
                # time-to-first-contact: if contacted True we can't get timestamp here; approximate 0
                rows.append({
                    "id": r.get("id"),
                    "contacted": bool(r.get("contacted")),
                    "breached": breached,
                    "sla_hours": sla_hours
                })
            total = len(rows)
            if total == 0:
                return {"sla_success_pct": 0.0, "sla_breach_rate": 0.0, "avg_time_to_first_contact": 0.0}
            contacted_count = sum(1 for x in rows if x["contacted"])
            breached_count = sum(1 for x in rows if x["breached"])
            sla_success_pct = (contacted_count / total) * 100.0
            sla_breach_rate = (breached_count / total) * 100.0
            # avg time-to-first-contact is not tracked precisely; placeholder = avg SLA/2 for contacted
            avg_time_to_first_contact = sum(x["sla_hours"] for x in rows if x["contacted"]) / max(1, contacted_count) / 2.0
            return {
                "sla_success_pct": sla_success_pct,
                "sla_breach_rate": sla_breach_rate,
                "avg_time_to_first_contact": avg_time_to_first_contact
            }

        sla_metrics = compute_sla_metrics(df)

        # 2. Lead Qualification Rate
        qual_total = df.shape[0]
        qual_count = int(df[df["qualified"] == True].shape[0]) if qual_total else 0
        qual_rate = (qual_count / qual_total * 100) if qual_total else 0.0

        # 3. Inspection Scheduling Conversion (% booked)
        inspected_booked = int(df[df["inspection_scheduled"] == True].shape[0])
        inspection_conversion = (inspected_booked / qual_count * 100) if qual_count else 0.0

        # 4. Estimate-to-Job Win Rate (% Won) — using awarded vs estimates
        # We'll approximate: awarded_count / estimate_submitted_count
        est_sub_count = int(df[df["estimate_submitted"] == True].shape[0])
        awarded_count = int(df[df["status"] == LeadStatus.AWARDED].shape[0])
        estimate_win_rate = (awarded_count / est_sub_count * 100) if est_sub_count else 0.0

        # 5. CPA per Won Job — requires spend data; we'll show placeholder and allow user to paste CPA later
        # For now set as N/A (0) unless a user-provided mapping exists.
        cpa_per_won = 0.0

        # 6. Conversion Velocity — average time from created -> awarded (hours)
        times = []
        for _, row in df.iterrows():
            if row.get("status") == LeadStatus.AWARDED and row.get("awarded_date") is not None:
                created = row.get("created_at")
                if isinstance(created, str):
                    try:
                        created = datetime.fromisoformat(created)
                    except:
                        created = datetime.utcnow()
                awd = row.get("awarded_date")
                if isinstance(awd, str):
                    try:
                        awd = datetime.fromisoformat(awd)
                    except:
                        awd = datetime.utcnow()
                delta_h = max(0.0, (awd - created).total_seconds() / 3600.0)
                times.append(delta_h)
        conv_velocity = (sum(times) / len(times)) if times else 0.0

        # KPI cards 2 rows x 4 columns; provide colors and left-aligned big numbers
        KPI_ITEMS = [
            ("#2563eb", "SLA Success %", f"{sla_metrics['sla_success_pct']:.1f}%", "SLA - contacts within SLA"),
            ("#a855f7", "Qualification Rate", f"{qual_rate:.1f}%", "Leads marked qualified"),
            ("#f97316", "Inspection Booked %", f"{inspection_conversion:.1f}%", "Qualified → Inspection"),
            ("#22c55e", "Estimate → Win %", f"{estimate_win_rate:.1f}%", "Estimates that convert"),
            ("#ef4444", "Awarded (count)", f"{awarded_count}", "Jobs Won"),
            ("#0ea5a4", "Avg Time-to-Contact (hrs)", f"{sla_metrics['avg_time_to_first_contact']:.1f}", "Approx avg"),
            ("#0f172a", "CPA per Won Job", f"${cpa_per_won:.2f}", "Placeholder (add spend data)"),
            ("#0f172a", "Conversion Velocity (hrs)", f"{conv_velocity:.1f}", "Lead→Won avg hours"),
        ]

        # two rows of 4 (use inline blocks for stable layout)
        st.markdown("<div style='display:flex; flex-wrap:wrap; gap:10px;'>", unsafe_allow_html=True)
        for color, label, val, note in KPI_ITEMS:
            safe_val = val
            st.markdown(f"""
                <div class="kpi-card" style="background: linear-gradient(90deg, {color}, {color}); width:24%;">
                    <div style="text-align:left;">
                        <div style="color:white; font-size:13px; font-weight:700;">{label}</div>
                        <div style="color:white; margin-top:6px;">
                            <span class="big-number" style="font-size:30px;">{safe_val}</span>
                        </div>
                        <div style="color:rgba(255,255,255,0.9); margin-top:6px; font-size:12px;">{note}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")

        # Pipeline Stage Cards (2 rows x 4)
        st.markdown("### 📈 Pipeline Stages")
        statuses = LeadStatus.ALL.copy()
        row1 = statuses[:4]
        row2 = statuses[4:8]

        def render_stage_row(row_statuses):
            cols = st.columns(len(row_statuses))
            for i, status in enumerate(row_statuses):
                cnt = int(df[df["status"] == status].shape[0])
                pct = (cnt / len(df) * 100) if len(df) else 0.0
                color = STAGE_COLORS.get(status, "#111111")
                with cols[i]:
                    st.markdown(f"""
                        <div class="stage-card" style="background:var(--glass-bg);">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div style="color:#fff; font-weight:700;">{status}</div>
                                <div style="font-weight:800; font-size:22px; color:{color};">{cnt}</div>
                            </div>
                            <div style="margin-top:8px;">
                                <div class="progress-bar" style="background: rgba(255,255,255,0.08); border-radius:8px; height:10px; overflow:hidden;">
                                    <div class="progress-fill" style="width:{pct}%; height:100%; background:{color};"></div>
                                </div>
                                <div style="text-align:center; margin-top:8px; color:rgba(255,255,255,0.8); font-size:12px;">{pct:.1f}% of pipeline</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

        render_stage_row(row1)
        render_stage_row(row2)
        st.markdown("---")

        # Priority Leads (Top 8)
        st.markdown("### 🎯 Priority Leads (Top 8)")
        priority_list = []
        for _, row in df.iterrows():
            try:
                score, time_left_h = compute_priority_for_lead_row(row, weights)
            except Exception:
                score, time_left_h = 0.0, 9999.0
            sla_entered = row.get("sla_entered_at") or row.get("created_at") or datetime.utcnow()
            if isinstance(sla_entered, str):
                try:
                    sla_entered = datetime.fromisoformat(sla_entered)
                except:
                    sla_entered = datetime.utcnow()
            deadline = sla_entered + timedelta(hours=int(row.get("sla_hours") or 24))
            remaining = deadline - datetime.utcnow()
            overdue = remaining.total_seconds() <= 0
            priority_list.append({
                "id": int(row["id"]),
                "contact_name": row.get("contact_name") or "No name",
                "estimated_value": float(row.get("estimated_value") or 0.0),
                "time_left_hours": float(max(0.0, (deadline - datetime.utcnow()).total_seconds()/3600.0)),
                "priority_score": score,
                "status": row.get("status"),
                "sla_overdue": overdue,
                "sla_deadline": deadline,
                "damage_type": row.get("damage_type", "Unknown")
            })
        pr_df = pd.DataFrame(priority_list).sort_values("priority_score", ascending=False)

        if pr_df.empty:
            st.info("No priority leads to display.")
        else:
            # render priority cards (vertical list)
            for _, r in pr_df.head(8).iterrows():
                score = r["priority_score"]
                status = r["status"]
                status_color = STAGE_COLORS.get(status, "#ffffff")
                if score >= 0.7:
                    priority_color = "#ef4444"
                    priority_label = "🔴 CRITICAL"
                elif score >= 0.45:
                    priority_color = "#f97316"
                    priority_label = "🟠 HIGH"
                else:
                    priority_color = "#22c55e"
                    priority_label = "🟢 NORMAL"
                # SLA red for time-left
                if r["sla_overdue"]:
                    sla_html = f"<span style='color:#ef4444;font-weight:700;'>❗ OVERDUE</span>"
                else:
                    hours_left = int(r['time_left_hours'])
                    mins_left = int((r['time_left_hours']*60) % 60)
                    sla_html = f"<span style='color:#ef4444;font-weight:700;'>⏳ {hours_left}h {mins_left}m left</span>"

                st.markdown(f"""
                    <div style="background:linear-gradient(180deg, rgba(0,0,0,0.03), rgba(0,0,0,0.02)); padding:12px; border-radius:10px; margin-bottom:8px;">
                       <div style="display:flex; justify-content:space-between; align-items:center;">
                         <div style="flex:1;">
                             <div style="margin-bottom:6px;">
                                 <span style="color:{priority_color}; font-weight:800;">{priority_label}</span>
                                 <span style="display:inline-block; margin-left:10px; padding:6px 10px; border-radius:16px; background:{status_color}22; color:{status_color}; font-weight:700;">{status}</span>
                             </div>
                             <div style="font-size:16px; font-weight:800; color:var(--text);">#{int(r['id'])} — {r['contact_name']}</div>
                             <div style="color:var(--muted); margin-top:6px;">{r['damage_type'].title()} | Est: <span style='color:var(--money); font-weight:800;'>${r['estimated_value']:,.0f}</span></div>
                             <div style="margin-top:8px;">{sla_html}</div>
                         </div>
                         <div style="text-align:right; padding-left:18px;">
                             <div style="font-size:28px; font-weight:800; color:{priority_color};">{score:.2f}</div>
                             <div style="font-size:11px; color:var(--muted); text-transform:uppercase;">Priority</div>
                         </div>
                       </div>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # All Leads (expandable) with edit form
        st.markdown("### 📋 All Leads (expand a card to edit / change status)")
        for lead in leads:
            est_val_display = f"${lead.estimated_value:,.0f}" if lead.estimated_value else "$0"
            card_title = f"#{lead.id} — {lead.contact_name or 'No name'} — {lead.damage_type or 'Unknown'} — {est_val_display}"
            with st.expander(card_title, expanded=False):
                colA, colB = st.columns([3,1])
                with colA:
                    st.markdown(f"**Source:** {lead.source or '—'}   •   **Assigned:** {lead.assigned_to or '—'}")
                    st.markdown(f"**Address:** {lead.property_address or '—'}")
                    st.markdown(f"**Notes:** {lead.notes or '—'}")
                    st.markdown(f"**Created:** {lead.created_at.strftime('%Y-%m-%d %H:%M') if lead.created_at else '—'}")
                with colB:
                    entered = lead.sla_entered_at or lead.created_at or datetime.utcnow()
                    if isinstance(entered, str):
                        try:
                            entered = datetime.fromisoformat(entered)
                        except:
                            entered = datetime.utcnow()
                    deadline = entered + timedelta(hours=(lead.sla_hours or 24))
                    remaining = deadline - datetime.utcnow()
                    if remaining.total_seconds() <= 0:
                        sla_status_html = "<div style='color:#ef4444;font-weight:700;'>❗ OVERDUE</div>"
                    else:
                        hours = int(remaining.total_seconds() // 3600)
                        mins = int((remaining.total_seconds() % 3600) // 60)
                        sla_status_html = f"<div style='color:#ef4444;font-weight:700;'>⏳ {hours}h {mins}m</div>"
                    st.markdown(f"""
                        <div style="text-align:right;">
                          <div style="display:inline-block; padding:6px 12px; border-radius:16px; background:{STAGE_COLORS.get(lead.status,'#111')}22; color:{STAGE_COLORS.get(lead.status,'#111')}; font-weight:800;">{lead.status}</div>
                          <div style="margin-top:10px;">{sla_status_html}</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")

                # Quick contact buttons row
                qc1, qc2, qc3, qc4 = st.columns([1,1,1,4])
                phone = (lead.contact_phone or "").strip()
                email = (lead.contact_email or "").strip()
                if phone:
                    with qc1:
                        st.markdown(f"<a href='tel:{phone}'><button class='round-btn' style='background:#2563eb;color:white;'>📞 Call</button></a>", unsafe_allow_html=True)
                    with qc2:
                        wa_number = phone.lstrip("+").replace(" ", "").replace("-", "")
                        wa_link = f"https://wa.me/{wa_number}?text=Hi%2C%20following%20up%20on%20your%20restoration%20request."
                        st.markdown(f"<a href='{wa_link}' target='_blank'><button class='round-btn' style='background:#25D366;color:#000;'>💬 WhatsApp</button></a>", unsafe_allow_html=True)
                else:
                    qc1.write(" "); qc2.write(" ")
                if email:
                    with qc3:
                        st.markdown(f"<a href='mailto:{email}?subject=Follow%20up'><button class='round-btn' style='background:#ffffff;color:#000;border:1px solid #e5e7eb;'>✉️ Email</button></a>", unsafe_allow_html=True)
                else:
                    qc3.write(" ")
                qc4.write("")

                st.markdown("---")

                # Edit form
                with st.form(f"update_lead_{lead.id}"):
                    st.markdown("#### Update Lead")
                    lcol1, lcol2 = st.columns(2)
                    with lcol1:
                        new_status = st.selectbox("Status", LeadStatus.ALL, index=LeadStatus.ALL.index(lead.status) if lead.status in LeadStatus.ALL else 0, key=f"status_{lead.id}")
                        new_assigned = st.text_input("Assigned to", value=lead.assigned_to or "", key=f"assign_{lead.id}")
                        contacted_flag = st.checkbox("Contacted", value=bool(lead.contacted), key=f"contacted_{lead.id}")
                    with lcol2:
                        insp_sched = st.checkbox("Inspection Scheduled", value=bool(lead.inspection_scheduled), key=f"insp_sched_{lead.id}")
                        insp_comp = st.checkbox("Inspection Completed", value=bool(lead.inspection_completed), key=f"insp_comp_{lead.id}")
                        est_sub = st.checkbox("Estimate Submitted", value=bool(lead.estimate_submitted), key=f"est_sub_{lead.id}")
                    new_notes = st.text_area("Notes", value=lead.notes or "", key=f"notes_{lead.id}")
                    new_est_val = st.number_input("Job Value Estimate (USD)", value=float(lead.estimated_value or 0.0), min_value=0.0, step=100.0, key=f"estval_{lead.id}")

                    # AWARDED -> upload invoice
                    awarded_invoice_file = None
                    awarded_comment = ""
                    lost_comment = ""
                    if new_status == LeadStatus.AWARDED:
                        st.markdown("**Award details**")
                        awarded_comment = st.text_area("Award comment", key=f"award_comment_{lead.id}")
                        awarded_invoice_file = st.file_uploader("Upload Invoice File (optional)", type=["pdf","jpg","jpeg","png","xlsx","csv"], key=f"award_inv_{lead.id}")
                    elif new_status == LeadStatus.LOST:
                        st.markdown("**Lost details**")
                        lost_comment = st.text_area("Lost comment", key=f"lost_comment_{lead.id}")

                    if st.form_submit_button("💾 Update Lead"):
                        try:
                            db_lead = s.query(Lead).filter(Lead.id == lead.id).first()
                            if db_lead:
                                db_lead.status = new_status
                                db_lead.assigned_to = new_assigned
                                db_lead.contacted = bool(contacted_flag)
                                db_lead.inspection_scheduled = bool(insp_sched)
                                db_lead.inspection_completed = bool(insp_comp)
                                db_lead.estimate_submitted = bool(est_sub)
                                db_lead.notes = new_notes
                                db_lead.estimated_value = float(new_est_val or 0.0)
                                if db_lead.sla_entered_at is None:
                                    db_lead.sla_entered_at = datetime.utcnow()
                                if new_status == LeadStatus.AWARDED:
                                    db_lead.awarded_date = datetime.utcnow()
                                    db_lead.awarded_comment = awarded_comment
                                    if awarded_invoice_file is not None:
                                        path = save_uploaded_file(awarded_invoice_file, prefix=f"lead_{db_lead.id}_inv")
                                        db_lead.awarded_invoice = path
                                if new_status == LeadStatus.LOST:
                                    db_lead.lost_date = datetime.utcnow()
                                    db_lead.lost_comment = lost_comment
                                # if status changed to a stage, update flags accordingly
                                s.add(db_lead)
                                s.commit()
                                st.success(f"Lead #{db_lead.id} updated.")
                            else:
                                st.error("Lead not found.")
                        except Exception as e:
                            st.error("Failed to update lead.")
                            st.write(traceback.format_exc())

                # Estimates block (create Job Value Estimate)
                st.markdown("#### 💰 Job Value Estimate (USD)")
                lead_estimates = s.query(Estimate).filter(Estimate.lead_id == lead.id).all()
                if lead_estimates:
                    for est in lead_estimates:
                        est_status = "✅ Approved" if est.approved else ("❌ Lost" if est.lost else "⏳ Pending")
                        est_color = "#22c55e" if est.approved else ("#ef4444" if est.lost else "#f97316")
                        st.markdown(f"<div style='padding:8px;border-radius:8px;background:rgba(0,0,0,0.02);'><strong style='color:{est_color};'>{est_status}</strong> — ${est.amount:,.0f} • {est.created_at.strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
                else:
                    st.info("No estimates yet for this lead.")

                with st.form(f"create_estimate_{lead.id}"):
                    new_amount = st.number_input("Amount (USD)", min_value=0.0, step=100.0, key=f"est_amt_{lead.id}")
                    new_details = st.text_area("Details", key=f"est_det_{lead.id}")
                    if st.form_submit_button("➕ Create Job Value Estimate"):
                        try:
                            create_estimate(s, lead.id, new_amount, new_details)
                            st.success("Estimate created.")
                        except Exception:
                            st.error("Failed to create estimate.")
                            st.write(traceback.format_exc())

# ---------------------------
# Page: Analytics & SLA
# ---------------------------
elif page == "Analytics & SLA":
    st.header("📈 Funnel Analytics & SLA (Donut)")

    s = get_session()
    df = leads_df(s)
    if df.empty:
        st.info("No leads yet.")
    else:
        # Pie/donut chart of statuses
        status_counts = df["status"].value_counts().reindex(LeadStatus.ALL, fill_value=0)
        pie_df = pd.DataFrame({"status": status_counts.index, "count": status_counts.values})
        if px is not None:
            colors = [STAGE_COLORS[s] for s in LeadStatus.ALL]
            fig = px.pie(pie_df, names="status", values="count", hole=0.45, color="status", color_discrete_sequence=colors)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(margin=dict(t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.bar_chart(pie_df.set_index("status")["count"])

        st.markdown("---")
        st.subheader("SLA / Overdue Leads")
        overdue = []
        for _, row in df.iterrows():
            sla_entered_at = row.get("sla_entered_at") or row.get("created_at") or datetime.utcnow()
            if isinstance(sla_entered_at, str):
                try:
                    sla_entered_at = datetime.fromisoformat(sla_entered_at)
                except:
                    sla_entered_at = datetime.utcnow()
            sla_hours = int(row.get("sla_hours") or 24)
            deadline = sla_entered_at + timedelta(hours=sla_hours)
            remaining = deadline - datetime.utcnow()
            overdue_flag = remaining.total_seconds() <= 0
            overdue.append({
                "id": row.get("id"),
                "contact": row.get("contact_name"),
                "status": row.get("status"),
                "deadline": deadline,
                "overdue": overdue_flag
            })
        df_overdue = pd.DataFrame(overdue)
        if not df_overdue.empty:
            st.dataframe(df_overdue.sort_values("deadline"))
        else:
            st.info("No SLA overdue leads.")

# ---------------------------
# Page: Exports
# ---------------------------
elif page == "Exports":
    st.header("📤 Export / Downloads")
    s = get_session()
    df_leads = leads_df(s)
    if df_leads.empty:
        st.info("No leads to export.")
    else:
        csv = df_leads.to_csv(index=False).encode("utf-8")
        st.download_button("Download leads.csv", csv, file_name="leads.csv", mime="text/csv")
    df_est = estimates_df(s)
    if not df_est.empty:
        st.download_button("Download estimates.csv", df_est.to_csv(index=False).encode("utf-8"), file_name="estimates.csv", mime="text/csv")

# End of file
