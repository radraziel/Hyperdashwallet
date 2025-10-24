from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

# Zona horaria local (CDMX)
try:
    from zoneinfo import ZoneInfo
    MX_TZ = ZoneInfo("America/Mexico_City")
except Exception:
    MX_TZ = None  # Fallback a UTC

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

def fmt_num(x, decimals: int = 2, show_sign: bool = False):
    """Formatea número con comas, decimales y signo opcional (+ para positivos)."""
    d = _to_decimal(x)
    if d is None:
        return str(x) if x is not None else "-"
    q = Decimal(10) ** -decimals
    d = d.quantize(q)
    sign = "+" if show_sign and d > 0 else ""
    return f"{sign}{d:,.{decimals}f}"

def fmt_usd(x, decimals: int = 2, bold: bool = False, emoji: bool = False):
    """Permite poner en negritas y agregar emoji 💰 si emoji=True."""
    d = _to_decimal(x)
    if d is None:
        val = str(x) if x is not None else "-"
    else:
        q = Decimal(10) ** -decimals
        d = d.quantize(q)
        val = f"${d:,.{decimals}f}"
    if emoji:
        val = f"💰 {val}"
    return f"<b>{val}</b>" if bold else val

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
    try:
        dt_utc = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        dt_local = dt_utc.astimezone(MX_TZ) if MX_TZ else dt_utc
        return f"{dt_local.strftime('%Y-%m-%d %H:%M')} {_offset_str(dt_local)}"
    except Exception:
        return "-"

def _ts_local_short(ms: int) -> str:
    try:
        dt_utc = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        dt_local = dt_utc.astimezone(MX_TZ) if MX_TZ else dt_utc
        return dt_local.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return "-"

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
    """Agrega emoji según signo al P&L ya formateado con +/-."""
    if u_pnl_decimal is None or u_pnl_decimal == 0:
        return f"{NEUTRAL_EMOJI} {formatted_value}"
    return f"{LONG_EMOJI} {formatted_value}" if u_pnl_decimal > 0 else f"{SHORT_EMOJI} {formatted_value}"

# =========================
# Formateadores
# =========================

def format_positions_md(state: dict) -> str:
    if not state or "assetPositions" not in state:
        return "📌 <b>Posiciones</b>: (sin datos)"

    assets = state.get("assetPositions", [])
    if not assets:
        return "📌 <b>Posiciones abiertas</b>: (ninguna)"

    out = ["📌 <b>Posiciones abiertas</b>"]
    lines = []

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
        pnl_f = fmt_num(u_pnl, 2, show_sign=True)
        # 💰 bold + emoji
        ntl_f = fmt_usd(ntl, 2, bold=True, emoji=True)
        pnl_badge = pnl_html(u_pnl_d, pnl_f)

        block = [
            f"• <b>{coin}</b>: {side}  Tamaño Crypto={szi_f}",
            f"Valor de posición={ntl_f}",
            f"Precio de entrada={entry_f}",
            f"Liquidación={liq_f}",
            f"P&L={pnl_badge}",
            f"Apalancamiento={lev_val}x {lev_type}",
            ""
        ]
        lines.extend(block)

    ms = state.get("time")
    if ms:
        lines.append(f"<i>Actualizado: {_ts_local(ms)}</i>")

    out.append("\n".join(lines))
    return "\n".join(out)

def format_open_orders_md(orders: list, limit: int = 8) -> str:
    if not orders:
        return "📋 <b>Órdenes abiertas</b>: (ninguna)"
    out = ["📋 <b>Órdenes abiertas</b>"]
    for o in orders[:limit]:
        coin = o.get("coin", "-")
        side = o.get("side", "-")
        side_txt = "Sell" if side == "A" else ("Buy" if side == "B" else str(side))
        side_badge = (
            f"{LONG_EMOJI} <b>{side_txt}</b>" if side_txt.lower().startswith("b")
            else f"{SHORT_EMOJI} <b>{side_txt}</b>" if side_txt.lower().startswith("s")
            else f"{NEUTRAL_EMOJI} <b>{side_txt}</b>"
        )
        sz = fmt_num(o.get("sz", o.get("origSz", "-")), 2)
        px = fmt_num(o.get("limitPx", "-"), 2)
        typ = o.get("orderType", "Limit")
        trig = o.get("triggerCondition", "N/A")
        tpx_raw = o.get("triggerPx", "0")
        tpx = fmt_num(tpx_raw, 2) if tpx_raw not in (None, "0", 0) else "0.00"

        out.append(f"• <b>{coin}</b> {side_badge} {sz}@{px}  ({typ}, trig={trig} {tpx})")

    if len(orders) > limit:
        out.append(f"<i>…y {len(orders)-limit} más</i>")
    return "\n".join(out)

def format_recent_fills_md(fills: list, limit: int = 5) -> str:
    if not fills:
        return "🧾 <b>Fills recientes</b>: (sin actividad)"
    out = ["🧾 <b>Fills recientes</b>"]
    for f in fills[:limit]:
        coin = f.get("coin", "-")
        dirn = f.get("dir", "-") or "-"
        dlow = dirn.lower()
        emoji = LONG_EMOJI if "long" in dlow else SHORT_EMOJI if "short" in dlow else NEUTRAL_EMOJI
        sz = fmt_num(f.get("sz", "-"), 2)
        px = fmt_num(f.get("px", "-"), 2)
        t = _ts_local_short(f.get("time"))
        out.append(f"• {t} — <b>{coin}</b> {emoji} <b>{dirn}</b> {sz}@{px}")
    return "\n".join(out)
