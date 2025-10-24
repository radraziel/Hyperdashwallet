from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

# Python 3.9+ trae zoneinfo en la stdlib
try:
    from zoneinfo import ZoneInfo
    MX_TZ = ZoneInfo("America/Mexico_City")
except Exception:
    MX_TZ = None  # Fallback a UTC si no está disponible

# =========================
# Helpers numéricos
# =========================

def _to_decimal(x):
    if x is None:
        return None
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        return None

def fmt_num(x, decimals: int = 2):
    d = _to_decimal(x)
    if d is None:
        return str(x) if x is not None else "-"
    q = Decimal(10) ** -decimals
    d = d.quantize(q)
    return f"{d:,.{decimals}f}"

def fmt_usd(x, decimals: int = 2):
    d = _to_decimal(x)
    if d is None:
        return str(x) if x is not None else "-"
    q = Decimal(10) ** -decimals
    d = d.quantize(q)
    return f"${d:,.{decimals}f}"

def _offset_str(dt):
    """Devuelve offset como 'GMT-06:00'."""
    try:
        ofs = dt.utcoffset()
        if ofs is None:
            return "GMT+00:00"
        total_min = int(ofs.total_seconds() // 60)
        sign = "+" if total_min >= 0 else "-"
        total_min = abs(total_min)
        hh = total_min // 60
        mm = total_min % 60
        return f"GMT{sign}{hh:02d}:{mm:02d}"
    except Exception:
        return "GMT+00:00"

def _ts_local(ms: int) -> str:
    """
    Convierte timestamp(ms) a America/Mexico_City (GMT-6/-5 según aplique).
    Formato: 'YYYY-MM-DD HH:MM GMT-06:00'
    """
    try:
        dt_utc = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        if MX_TZ is not None:
            dt_local = dt_utc.astimezone(MX_TZ)
        else:
            dt_local = dt_utc  # fallback UTC
        return f"{dt_local.strftime('%Y-%m-%d %H:%M')} {_offset_str(dt_local)}"
    except Exception:
        return "-"

# =========================
# Texto de ayuda (HTML)
# =========================

def usage_instructions_md() -> str:
    return (
        "👋 <b>HyperdashWallet Bot</b>\n\n"
        "Usa este bot para ver <b>posiciones</b>, <b>órdenes abiertas</b> y <b>fills recientes</b> "
        "de un wallet de Hyperliquid.\n\n"
        "• Comando principal:\n"
        "<code>/wallet &lt;address&gt;</code>\n"
        "Ejemplo:\n"
        "<code>/wallet 0xc2a30212a8ddac9e123944d6e29faddce994e5f2</code>\n\n"
        "También puedes pegar una URL de HyperDash y detectaremos el address automáticamente.\n\n"
        "<i>Tip:</i> puedes re-ejecutar /wallet con otra dirección para cambiar de seguimiento."
    )

# =========================
# Emojis / Visual
# =========================
LONG_EMOJI = "🟢"
SHORT_EMOJI = "🔴"
NEUTRAL_EMOJI = "⚪️"

def side_html(szi_decimal: Decimal | None) -> str:
    if szi_decimal is None or szi_decimal == 0:
        return f"{NEUTRAL_EMOJI} <b>Flat</b>"
    return f"{LONG_EMOJI} <b>Long</b>" if szi_decimal > 0 else f"{SHORT_EMOJI} <b>Short</b>"

def pnl_html(u_pnl_decimal: Decimal | None, formatted_value: str) -> str:
    if u_pnl_decimal is None or u_pnl_decimal == 0:
        return f"{NEUTRAL_EMOJI} <b>{formatted_value}</b>"
    return f"{LONG_EMOJI} <b>{formatted_value}</b>" if u_pnl_decimal > 0 else f"{SHORT_EMOJI} <b>{formatted_value}</b>"

# =========================
# Formateadores (lista)
# =========================

def format_positions_md(state: dict) -> str:
    if not state or "assetPositions" not in state:
        return "📌 <b>Posiciones</b>: (sin datos)"

    assets = state.get("assetPositions", [])
    if not assets:
        return "📌 <b>Posiciones abiertas</b>: (ninguna)"

    lines = ["📌 <b>Posiciones abiertas</b>"]
    for ap in assets:
        pos = ap.get("position") or {}
        coin = pos.get("coin", "-")
        szi = pos.get("szi", "0")
        entry = pos.get("entryPx", "-")
        liq = pos.get("liquidationPx", "-")
        u_pnl = pos.get("unrealizedPnl", "-")
        ntl = pos.get("positionValue", "-")
        lev = pos.get("leverage", {})
        lev_val = lev.get("value", "")
        lev_type = lev.get("type", "")

        szi_d = _to_decimal(szi)
        u_pnl_d = _to_decimal(u_pnl)

        side = side_html(szi_d)
        szi_f = fmt_num(szi, 2)
        entry_f = fmt_num(entry, 2)
        liq_f = fmt_num(liq, 2)
        pnl_f = fmt_num(u_pnl, 2)
        ntl_f = fmt_usd(ntl, 2)
        pnl_badge = pnl_html(u_pnl_d, pnl_f)

        # Formato de lista (el que te gustaba), con etiquetas en español
        lines.append(
            f"• <b>{coin}</b>: {side}  Tamaño Crypto={szi_f}  Valor de posición={ntl_f}\n"
            f"  Precio de entrada={entry_f}  Liquidación={liq_f}  P&L={pnl_badge}  Apalancamiento={lev_val}x {lev_type}"
        )

    ms = state.get("time")
    if ms:
        lines.append(f"<i>Actualizado: {_ts_local(ms)}</i>")
    return "\n".join(lines)

def format_open_orders_md(orders: list, limit: int = 8) -> str:
    if not orders:
        return "📋 <b>Órdenes abiertas</b>: (ninguna)"
    rows = orders[:limit]
    out = ["📋 <b>Órdenes abiertas</b>"]
    for o in rows:
        coin = o.get("coin", "-")
        side = o.get("side", "-")
        side_txt = "Sell" if side == "A" else ("Buy" if side == "B" else str(side))
        # Emoji de lado
        side_html_badge = f"{LONG_EMOJI} <b>{side_txt}</b>" if side_txt.lower().startswith("b") \
                          else f"{SHORT_EMOJI} <b>{side_txt}</b>" if side_txt.lower().startswith("s") \
                          else f"{NEUTRAL_EMOJI} <b>{side_txt}</b>"
        sz = fmt_num(o.get("sz", o.get("origSz", "-")), 2)
        px = fmt_num(o.get("limitPx", "-"), 2)
        typ = o.get("orderType", "Limit")
        trig = o.get("triggerCondition", "N/A")
        tpx_raw = o.get("triggerPx", "0")
        tpx = fmt_num(tpx_raw, 2) if tpx_raw not in (None, "0", 0) else "0.00"

        out.append(
            f"• <b>{coin}</b> {side_html_badge} {sz}@{px}  ({typ}, trig={trig} {tpx})"
        )
    if len(orders) > limit:
        out.append(f"<i>…y {len(orders)-limit} más</i>")
    return "\n".join(out)

def format_recent_fills_md(fills: list, limit: int = 5) -> str:
    if not fills:
        return "🧾 <b>Fills recientes</b>: (sin actividad)"
    rows = fills[:limit]
    out = ["🧾 <b>Fills recientes</b>"]
    for f in rows:
        coin = f.get("coin", "-")
        dirn = f.get("dir", "-") or "-"
        dlow = dirn.lower()
        emoji = LONG_EMOJI if "long" in dlow else SHORT_EMOJI if "short" in dlow else NEUTRAL_EMOJI
        sz = fmt_num(f.get("sz", "-"), 2)
        px = fmt_num(f.get("px", "-"), 2)
        t = _ts_local(f.get("time"))

        out.append(f"• {t} — <b>{coin}</b> {emoji} <b>{dirn}</b> {sz}@{px}")
    return "\n".join(out)
