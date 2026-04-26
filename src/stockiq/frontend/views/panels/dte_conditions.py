"""0DTE Conditions Meter panel — evaluates live signals and suggests a trade."""

import pandas as pd
import streamlit as st

from stockiq.backend.services.spy_service import get_spy_options_analysis


def render_dte_conditions(
    current_price: float,
    vix_snapshot: dict | None,
    rsi: float | None,
    pc_data: dict | None,
) -> None:
    try:
        seed      = get_spy_options_analysis(expiration="", current_price=current_price)
        max_pain  = seed["max_pain"]               if seed else None
        gex_df    = seed.get("gex_df", pd.DataFrame()) if seed else pd.DataFrame()
        total_gex = gex_df["gex"].sum()            if not gex_df.empty else None
    except Exception:
        seed = None
        max_pain = total_gex = None

    signals, call_pts, put_pts = _evaluate_signals(
        current_price, vix_snapshot, rsi, pc_data, max_pain, total_gex
    )

    net    = call_pts - put_pts
    scored = call_pts + put_pts
    v_label, v_color, v_icon, v_note = _verdict(net)
    trade_html = _trade_suggestion(net, seed, current_price, max_pain) if net != 0 and seed else ""
    badges_html = _badges(signals)
    right_panel = trade_html or _neutral_panel()

    st.html(
        f'<div style="margin-bottom:8px">'
        f'<span style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        f'text-transform:uppercase">0DTE Conditions Meter</span>'
        f'<span style="font-size:9px;color:#475569;margin-left:10px">'
        f'Based on 0DTE guide thresholds · not financial advice'
        f'</span>'
        f'</div>'
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
        f'border-radius:12px;padding:18px 20px">'
        f'<div style="display:flex;align-items:flex-start;gap:20px">'
        f'<div style="min-width:220px;flex-shrink:0">'
        f'<div style="font-size:32px;font-weight:900;color:{v_color};line-height:1;'
        f'letter-spacing:-.5px">{v_icon} {v_label}</div>'
        f'<div style="font-size:11px;color:{v_color};font-weight:600;margin-top:5px">'
        f'{call_pts} call &nbsp;·&nbsp; {put_pts} put &nbsp;·&nbsp; {5 - scored} neutral'
        f'</div>'
        f'<div style="font-size:9px;color:#64748B;margin-top:5px;line-height:1.4">{v_note}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:12px">{badges_html}</div>'
        f'</div>'
        f'<div style="width:1px;background:#1E293B;align-self:stretch;flex-shrink:0"></div>'
        f'<div style="width:230px;flex-shrink:0">{right_panel}</div>'
        f'</div>'
        f'</div>'
    )


# ── Signal evaluation ──────────────────────────────────────────────────────────

def _evaluate_signals(current_price, vix_snapshot, rsi, pc_data, max_pain, total_gex):
    signals: list[tuple] = []
    call_pts = put_pts = 0

    vix_val = vix_snapshot.get("current") if vix_snapshot else None
    if vix_val is not None:
        if vix_val < 16:
            signals.append(("VIX", f"{vix_val:.1f}", "CALL", "Cheap options — good day to buy directional calls", "#22C55E")); call_pts += 1
        elif vix_val > 25:
            signals.append(("VIX", f"{vix_val:.1f}", "PUT",  "Fear elevated — sell spreads or fade bounces", "#EF4444")); put_pts += 1
        else:
            signals.append(("VIX", f"{vix_val:.1f}", "NEUTRAL", "Mid-range — no strong options-price edge", "#94A3B8"))
    else:
        signals.append(("VIX", "N/A", "—", "Unavailable", "#475569"))

    if pc_data:
        r = pc_data["ratio"]
        if r < 0.80:
            signals.append(("P/C Ratio", f"{r:.3f}", "CALL", "More calls than puts — market leans bullish", "#22C55E")); call_pts += 1
        elif r > 1.10:
            signals.append(("P/C Ratio", f"{r:.3f}", "PUT",  "Fear/hedging dominant — put volume heavy", "#EF4444")); put_pts += 1
        else:
            signals.append(("P/C Ratio", f"{r:.3f}", "NEUTRAL", "Balanced put/call positioning", "#94A3B8"))
    else:
        signals.append(("P/C Ratio", "N/A", "—", "Unavailable", "#475569"))

    if max_pain:
        dist = (current_price - max_pain) / max_pain * 100
        if dist > 1.0:
            signals.append(("Max Pain", f"${max_pain:,.0f}", "CALL", f"Price {dist:+.1f}% above — bullish price action", "#22C55E")); call_pts += 1
        elif dist < -1.0:
            signals.append(("Max Pain", f"${max_pain:,.0f}", "PUT",  f"Price {dist:+.1f}% below — bearish gravitational pull", "#EF4444")); put_pts += 1
        else:
            signals.append(("Max Pain", f"${max_pain:,.0f}", "NEUTRAL", f"Pinned near pain ({dist:+.1f}%) — sideways expected", "#94A3B8"))
    else:
        signals.append(("Max Pain", "N/A", "—", "Unavailable", "#475569"))

    if total_gex is not None:
        gb = total_gex / 1e9
        if total_gex >= 0:
            signals.append(("GEX", f"{gb:+.1f}B", "CALL", "Dealers buy dips & sell rips — market pinned up", "#22C55E")); call_pts += 1
        else:
            signals.append(("GEX", f"{gb:+.1f}B", "PUT",  "Dealers amplify moves — drops can accelerate", "#EF4444")); put_pts += 1
    else:
        signals.append(("GEX", "N/A", "—", "Unavailable", "#475569"))

    if rsi is not None:
        if rsi >= 55:
            signals.append(("RSI (1d)", f"{rsi:.1f}", "CALL", "Above 55 — bullish daily momentum", "#22C55E")); call_pts += 1
        elif rsi <= 45:
            signals.append(("RSI (1d)", f"{rsi:.1f}", "PUT",  "Below 45 — bearish daily momentum", "#EF4444")); put_pts += 1
        else:
            signals.append(("RSI (1d)", f"{rsi:.1f}", "NEUTRAL", "45–55 choppy zone — no directional edge", "#94A3B8"))
    else:
        signals.append(("RSI (1d)", "N/A", "—", "Unavailable", "#475569"))

    return signals, call_pts, put_pts


def _verdict(net: int) -> tuple:
    if net >= 3:
        return "CALL BIAS",  "#22C55E", "▲", "Strong conditions for call buying or bull spreads"
    if net >= 1:
        return "MILD CALL",  "#86EFAC", "↗", "Slight upside lean — size smaller, defined risk only"
    if net <= -3:
        return "PUT BIAS",   "#EF4444", "▼", "Strong conditions for put buying or bear spreads"
    if net <= -1:
        return "MILD PUT",   "#FCA5A5", "↘", "Slight downside lean — size smaller, defined risk only"
    return "NEUTRAL", "#F59E0B", "↔", "No clear edge — consider iron condors or stay flat"


# ── Trade suggestion ───────────────────────────────────────────────────────────

def _trade_suggestion(net: int, seed: dict, current_price: float, max_pain: float | None) -> str:
    oi_df    = seed.get("oi_df", pd.DataFrame())
    em_s     = seed.get("expected_move")
    em_move  = em_s["move"] if em_s else 3.0

    call_wall = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"]) if not oi_df.empty else None
    put_wall  = float(oi_df.loc[oi_df["put_oi"].idxmax(), "strike"])  if not oi_df.empty else None
    atm       = round(current_price)

    if net > 0:
        tgt_price, tgt_label = _best_target_call(current_price, em_move, call_wall, max_pain)
        reward    = tgt_price - current_price
        stp_price, stp_label = _best_stop_call(current_price, em_move, reward, put_wall)
        risk = max(current_price - stp_price, 0.5)
        clr, bg, direction = "#22C55E", "rgba(34,197,94,0.12)", "call"
    else:
        tgt_price, tgt_label = _best_target_put(current_price, em_move, put_wall, max_pain)
        reward    = current_price - tgt_price
        stp_price, stp_label = _best_stop_put(current_price, em_move, reward, call_wall)
        risk = max(stp_price - current_price, 0.5)
        clr, bg, direction = "#EF4444", "rgba(239,68,68,0.12)", "put"

    rr      = reward / risk
    rr_clr  = "#22C55E" if rr >= 2.0 else "#F59E0B" if rr >= 1.2 else "#EF4444"
    stp_clr = "#F59E0B"

    return (
        f'<div style="font-size:9px;color:#64748B;font-weight:700;letter-spacing:.06em;'
        f'text-transform:uppercase;margin-bottom:8px">Suggested Trade</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 12px">'
        f'<div><div style="font-size:8px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Entry</div>'
        f'<div style="font-size:15px;font-weight:800;color:{clr}">${atm:,} {direction}</div></div>'
        f'<div><div style="font-size:8px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Stop</div>'
        f'<div style="font-size:15px;font-weight:800;color:{stp_clr}">${stp_price:,}</div></div>'
        f'<div><div style="font-size:8px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Target</div>'
        f'<div style="font-size:15px;font-weight:800;color:{clr}">${tgt_price:,}</div></div>'
        f'<div><div style="font-size:8px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">R / R</div>'
        f'<div style="font-size:15px;font-weight:800;color:{rr_clr}">1 : {rr:.1f}</div></div>'
        f'</div>'
        f'<div style="font-size:8px;color:#475569;margin-top:6px;line-height:1.5">'
        f'Target: {tgt_label} &nbsp;·&nbsp; Stop: {stp_label}'
        f'</div>'
        f'<div style="font-size:8px;color:#475569;margin-top:6px;padding-top:6px;'
        f'border-top:1px solid #1E293B;line-height:1.5">'
        f'&#9200; Enter 9:45–11:30 AM &nbsp;·&nbsp; Exit by 3:00 PM'
        f'</div>'
    )


def _best_target_call(price, em, call_wall, max_pain):
    cands = []
    if call_wall and price + 0.5 < call_wall <= price + em * 1.3:
        cands.append(("call wall", call_wall))
    if max_pain and price + 0.5 < max_pain <= price + em * 1.3:
        cands.append(("max pain", max_pain))
    cands.append(("exp. move ×0.6", price + em * 0.6))
    label, val = cands[0]
    return round(val), label


def _best_stop_call(price, em, reward, put_wall):
    cands = []
    if put_wall and price - em < put_wall < price - 0.5:
        if (price - put_wall) <= reward * 1.5:
            cands.append(("put wall", put_wall))
    cands.append(("1:2 R/R", price - reward / 2))
    label, val = cands[0]
    return round(val), label


def _best_target_put(price, em, put_wall, max_pain):
    cands = []
    if put_wall and price - em * 1.3 <= put_wall < price - 0.5:
        cands.append(("put wall", put_wall))
    if max_pain and price - em * 1.3 <= max_pain < price - 0.5:
        cands.append(("max pain", max_pain))
    cands.append(("exp. move ×0.6", price - em * 0.6))
    label, val = cands[0]
    return round(val), label


def _best_stop_put(price, em, reward, call_wall):
    cands = []
    if call_wall and price + 0.5 < call_wall < price + em:
        if (call_wall - price) <= reward * 1.5:
            cands.append(("call wall", call_wall))
    cands.append(("1:2 R/R", price + reward / 2))
    label, val = cands[0]
    return round(val), label


# ── HTML helpers ───────────────────────────────────────────────────────────────

_BIAS_ICON = {"CALL": "▲", "PUT": "▼", "NEUTRAL": "→"}
_BIAS_BG   = {
    "CALL":    "rgba(34,197,94,0.15)",
    "PUT":     "rgba(239,68,68,0.15)",
    "NEUTRAL": "rgba(148,163,184,0.08)",
}


def _badges(signals: list) -> str:
    def _badge(label, value, bias, clr):
        bg   = _BIAS_BG.get(bias, "rgba(71,85,105,0.08)")
        icon = _BIAS_ICON.get(bias, "·")
        txt  = clr if bias in ("CALL", "PUT") else "#64748B"
        return (
            f'<span style="display:inline-flex;align-items:center;gap:3px;background:{bg};'
            f'border:1px solid rgba(255,255,255,0.05);border-radius:20px;'
            f'padding:3px 9px;font-size:9px;font-weight:600;color:{txt};white-space:nowrap">'
            f'{label}&nbsp;{value}&nbsp;{icon}'
            f'</span>'
        )
    return " ".join(_badge(s[0], s[1], s[2], s[4]) for s in signals)


def _neutral_panel() -> str:
    return (
        '<div style="font-size:11px;color:#F59E0B;font-weight:600;margin-bottom:6px">'
        'No directional edge today</div>'
        '<div style="font-size:9px;color:#64748B;line-height:1.6">'
        'Consider: iron condor or iron fly<br>'
        'Sell premium, let theta work for you<br>'
        '<span style="margin-top:5px;display:block">&#9200; Avoid new positions after 2:00 PM</span>'
        '</div>'
    )
