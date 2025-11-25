
# priority_component_fixed.py

def render_priority_lead_card(r, stage_colors):
    """
    Clean HTML version WITHOUT dangling </div> tags.
    """
    score = r.get("priority_score", 0)
    status_color = stage_colors.get(r.get("status"), "#000")

    # Priority levels
    if score >= 0.7:
        priority_color = "#ef4444"
        priority_label = "🔴 CRITICAL"
    elif score >= 0.45:
        priority_color = "#f97316"
        priority_label = "🟠 HIGH"
    else:
        priority_color = "#22c55e"
        priority_label = "🟢 NORMAL"

    # SLA
    remaining_hours = r.get("time_left_hours", 0)
    if remaining_hours <= 0:
        sla_html = "<span style='color:#ef4444;font-weight:700;'>❗ OVERDUE</span>"
    else:
        h = int(remaining_hours)
        m = int((remaining_hours * 60) % 60)
        sla_html = f"<span style='color:#ef4444;font-weight:700;'>⏳ {h}h {m}m left</span>"

    html = f"""
<div style="background:#111; padding:18px; border-radius:14px; margin-bottom:12px; border:1px solid #333;">
  <div style="display:flex; justify-content:space-between; align-items:center;">

    <div style="flex:1;">
      <div style="margin-bottom:8px;">
        <span style="color:{priority_color}; font-weight:700; font-size:14px;">{priority_label}</span>
        <span style="background:{status_color}20; color:{status_color}; border:1px solid {status_color}40; padding:4px 10px; border-radius:14px; font-size:11px; font-weight:600; margin-left:8px;">
          {r.get('status')}
        </span>
      </div>

      <div style="font-size:20px; font-weight:700; color:white;">#{int(r.get('id'))} — {r.get('contact_name')}</div>

      <div style="font-size:13px; color:#aaa; margin-top:4px;">
        {r.get('damage_type').title()} | Est:
        <span style="color:#22c55e; font-weight:700;">${r.get('estimated_value'):,.0f}</span>
      </div>

      <div style="margin-top:6px; font-size:13px;">{sla_html}</div>
    </div>

    <div style="text-align:right; padding-left:20px;">
      <div style="font-size:28px; font-weight:800; color:{priority_color};">{score:.2f}</div>
      <div style="font-size:11px; color:#777; text-transform:uppercase;">Priority</div>
    </div>

  </div>
</div>
"""
    return html
