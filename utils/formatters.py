from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

# ===== Helpers numéricos =====

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

def _ts(ms: int) -> str:
    try:
        return datetime.fromtimestamp(int(ms)/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    except Exception:
        return "-"

# ===== Texto de ayuda =====

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

# ===== Colores HTML =====

GREEN = "#27ae60"
RED = "#c0392b"

def html_color(text: str, color: str) -> str:
    return f'<b><span style="color:{color}">{text}</span></b>'

# ===== Formateadores =====

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
        value = pos.get("positionValue", "-")
        liq = pos.get("liquidationPx", "-")
        u_pnl = pos.get("unrealizedPnl", "-")
        lev = pos.get("leverage", {})
        lev_val = lev.get("value", "")
        lev_type = lev.get("type", "")

        szi_d = _to_decimal(szi)
        u_pnl_d = _to_decimal(u_pnl)

        # Long/Short con color
        if szi_d is not None and szi_d > 0:
            side_html = html_color("Long", GREEN)
        elif szi_d is not None and szi_d < 0:
            side_html = html_color("Short", RED)
        else:
            side_html = "<b>Flat</b>"

        # uPnL coloreado
        if u_pnl_d is not None:
            pnl_color = GREEN if u_pnl_d > 0 else RED if u_pnl_d < 0 else "#999"
            u_pnl_f = html_color(fmt_num(u_pnl_d, 2), pnl_color)
        else:
            u_pnl_f = fmt_num(u_pnl, 2)

        # Formatos
        szi_f = fmt_num(szi, 2)
        value_f = fmt_usd(value, 2)
        entry_f = fmt_num(entry, 2)
        liq_f = fmt_num(liq, 2)

        lines.append(
            f"• <b>{coin}</b>: {side_html}  size={szi_f}  ntl={value_f}\n"
            f"  entry={entry_f}  liq={liq_f}  uPnL={u_pnl_f}  lev={lev_val}x {lev_type}"
        )

    ms = state.get("time")
    if ms:
        lines.append(f"<i>Actualizado: {_ts(ms)}</i>")
    return "\n".join(lines)


def format_open_orders_md(orders: list, limit: int = 8) -> str:
    if not orders:
        return "📋 <b>Órdenes abiertas</b>: (ninguna)"
    rows = orders[:limit]
    out = ["📋 <b>Órdenes abiertas</b>"]
    for o in rows:
        coin = o.get("coin", "-")
        side = o.get("side", "-")
        side_txt = "Sell" if side == "A" else ("Buy" if side == "B" else side)
        sz = fmt_num(o.get("sz", o.get("origSz", "-")), 2)
        px = fmt_num(o.get("limitPx", "-"), 2)
        typ = o.get("orderType", "Limit")
        trig = o.get("triggerCondition", "N/A")
        tpx = fmt_num(o.get("triggerPx", "0"), 2)

        side_col = GREEN if side_txt.lower().startswith("b") else RED
        side_html = html_color(side_txt, side_col)

        out.append(f"• <b>{coin}</b> {side_html} {sz}@{px}  ({typ}, trig={trig} {tpx})")

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
        dirn = f.get("dir", "-")
        sz = fmt_num(f.get("sz", "-"), 2)
        px = fmt_num(f.get("px", "-"), 2)
        t = _ts(f.get("time"))

        color = GREEN if "Long" in dirn else RED if "Short" in dirn else "#555"
        dirn_html = html_color(dirn, color)

        out.append(f"• {t} — <b>{coin}</b> {dirn_html} {sz}@{px}")
    return "\n".join(out)
