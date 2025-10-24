from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

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

def _ts(ms: int) -> str:
    try:
        return datetime.fromtimestamp(int(ms)/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")
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

def side_emoji_text(szi_decimal: Decimal | None) -> str:
    if szi_decimal is None or szi_decimal == 0:
        return f"{NEUTRAL_EMOJI} Flat"
    return f"{LONG_EMOJI} Long" if szi_decimal > 0 else f"{SHORT_EMOJI} Short"

def pnl_emoji_text(u_pnl_decimal: Decimal | None, formatted_value: str) -> str:
    if u_pnl_decimal is None or u_pnl_decimal == 0:
        return f"{NEUTRAL_EMOJI} {formatted_value}"
    return f"{LONG_EMOJI} {formatted_value}" if u_pnl_decimal > 0 else f"{SHORT_EMOJI} {formatted_value}"

# =========================
# Helpers de tabla monoespaciada
# =========================

def pad(s: str, width: int) -> str:
    s = str(s)
    return s[:width].ljust(width)

def row_join(cols: list[str]) -> str:
    # separador uniforme
    return "  ".join(cols)

# =========================
# Formateadores
# =========================

def format_positions_md(state: dict) -> str:
    if not state or "assetPositions" not in state:
        return "📌 <b>Posiciones</b>: (sin datos)"

    assets = state.get("assetPositions", [])
    if not assets:
        return "📌 <b>Posiciones abiertas</b>: (ninguna)"

    lines = []
    # Encabezado visible
    lines.append("📌 <b>Posiciones abiertas</b>")

    # Cabecera de tabla (monoespaciado)
    header = row_join([
        pad("COIN", 5),
        pad("SIDE", 12),
        pad("SIZE", 14),
        pad("ENTRY", 12),
        pad("LIQ", 12),
        pad("UPNL", 16),
        pad("LEV", 8),
        pad("NTL", 16),
    ])
    sep = "-" * len(header)

    body_rows = []
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

        side_txt = side_emoji_text(szi_d)
        u_pnl_txt = pnl_emoji_text(u_pnl_d, fmt_num(u_pnl, 2))

        row = row_join([
            pad(coin, 5),
            pad(side_txt, 12),
            pad(fmt_num(szi, 2), 14),
            pad(fmt_num(entry, 2), 12),
            pad(fmt_num(liq, 2), 12),
            pad(u_pnl_txt, 16),
            pad(f"{lev_val}x {lev_type}".strip(), 8),
            pad(fmt_usd(ntl, 2), 16),
        ])
        body_rows.append(row)

    ms = state.get("time")
    ts = _ts(ms) if ms else None

    table = "<pre>\n" + header + "\n" + sep + "\n" + "\n".join(body_rows) + "\n</pre>"
    if ts:
        table += f"\n<i>Actualizado: {ts}</i>"

    lines.append(table)
    return "\n".join(lines)

def format_open_orders_md(orders: list, limit: int = 8) -> str:
    if not orders:
        return "📋 <b>Órdenes abiertas</b>: (ninguna)"

    out = ["📋 <b>Órdenes abiertas</b>"]

    header = row_join([
        pad("COIN", 5),
        pad("SIDE", 8),
        pad("SZ", 12),
        pad("PX", 12),
        pad("TYPE", 8),
        pad("TRIG", 6),
        pad("TPX", 10),
    ])
    sep = "-" * len(header)

    rows = []
    for o in orders[:limit]:
        coin = o.get("coin", "-")
        side = o.get("side", "-")
        side_txt = "Buy" if side == "B" else "Sell" if side == "A" else str(side)
        side_txt = f"{LONG_EMOJI} {side_txt}" if side_txt.lower().startswith("b") else f"{SHORT_EMOJI} {side_txt}" if side_txt.lower().startswith("s") else f"{NEUTRAL_EMOJI} {side_txt}"
        sz = fmt_num(o.get("sz", o.get("origSz", "-")), 2)
        px = fmt_num(o.get("limitPx", "-"), 2)
        typ = o.get("orderType", "Limit")
        trig = o.get("triggerCondition", "N/A")
        tpx_raw = o.get("triggerPx", "0")
        tpx = fmt_num(tpx_raw, 2) if tpx_raw not in (None, "0", 0) else "0.00"

        rows.append(row_join([
            pad(coin, 5),
            pad(side_txt, 8),
            pad(sz, 12),
            pad(px, 12),
            pad(typ, 8),
            pad(trig, 6),
            pad(tpx, 10),
        ]))

    table = "<pre>\n" + header + "\n" + sep + "\n" + "\n".join(rows) + "\n</pre>"
    if len(orders) > limit:
        table += f"\n<i>…y {len(orders)-limit} más</i>"

    out.append(table)
    return "\n".join(out)

def format_recent_fills_md(fills: list, limit: int = 5) -> str:
    if not fills:
        return "🧾 <b>Fills recientes</b>: (sin actividad)"

    out = ["🧾 <b>Fills recientes</b>"]

    header = row_join([
        pad("TIME (UTC)", 17),
        pad("COIN", 5),
        pad("DIR", 12),
        pad("SZ@PX", 22),
    ])
    sep = "-" * len(header)

    rows = []
    for f in fills[:limit]:
        coin = f.get("coin", "-")
        dirn = f.get("dir", "-") or "-"
        dlow = dirn.lower()
        dir_emoji = LONG_EMOJI if "long" in dlow else SHORT_EMOJI if "short" in dlow else NEUTRAL_EMOJI
        sz = fmt_num(f.get("sz", "-"), 2)
        px = fmt_num(f.get("px", "-"), 2)
        t = _ts(f.get("time"))

        rows.append(row_join([
            pad(t, 17),
            pad(coin, 5),
            pad(f"{dir_emoji} {dirn}", 12),
            pad(f"{sz}@{px}", 22),
        ]))

    table = "<pre>\n" + header + "\n" + sep + "\n" + "\n".join(rows) + "\n</pre>"
    out.append(table)
    return "\n".join(out)
