from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

# ===== Helpers de formato numérico =====

def _to_decimal(x):
    if x is None:
        return None
    try:
        # Hyperliquid suele mandar números como str o numérico
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        return None

def fmt_num(x, decimals: int = 2):
    """
    Formatea con comas y decimales fijos. Si no es numérico, devuelve el valor tal cual.
    """
    d = _to_decimal(x)
    if d is None:
        return str(x) if x is not None else "-"
    q = Decimal(10) ** -decimals
    d = d.quantize(q)  # redondeo a 'decimals'
    # Usamos formato con miles
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

def usage_instructions_md() -> str:
    return (
        "👋 *HyperdashWallet Bot*\n\n"
        "Usa este bot para ver *posiciones*, *órdenes abiertas* y *fills recientes* de un wallet de Hyperliquid.\n\n"
        "• Comando principal:\n"
        "`/wallet <address>`\n"
        "Ejemplo:\n"
        "`/wallet 0xc2a30212a8ddac9e123944d6e29faddce994e5f2`\n\n"
        "También puedes pegar una URL de HyperDash y detectaremos el address automáticamente.\n\n"
        "_Tip:_ puedes re-ejecutar `/wallet` con otra dirección para cambiar de seguimiento."
    )

# ===== Formateadores de bloques =====

def format_positions_md(state: dict) -> str:
    if not state or "assetPositions" not in state:
        return "📌 *Posiciones*: (sin datos)"

    assets = state.get("assetPositions", [])
    if not assets:
        return "📌 *Posiciones*: (no hay posiciones abiertas)"

    lines = ["📌 *Posiciones abiertas*"]
    for ap in assets:
        pos = ap.get("position") or {}
        coin = pos.get("coin", "-")
        szi = pos.get("szi", "0")
        try:
            side = "Long" if Decimal(str(szi)) > 0 else ("Short" if Decimal(str(szi)) < 0 else "Flat")
        except Exception:
            side = "?"

        entry = pos.get("entryPx", "-")
        value = pos.get("positionValue", "-")
        liq = pos.get("liquidationPx", "-")
        u_pnl = pos.get("unrealizedPnl", "-")
        lev = pos.get("leverage", {})
        lev_val = lev.get("value", "")
        lev_type = lev.get("type", "")

        # Aplicamos formato con comas y 2 decimales
        szi_f = fmt_num(szi, 2)
        value_f = fmt_usd(value, 2)
        entry_f = fmt_num(entry, 2)
        liq_f = fmt_num(liq, 2)
        u_pnl_f = fmt_num(u_pnl, 2)

        lines.append(
            f"• {coin}: *{side}*  size={szi_f}  ntl={value_f}\n"
            f"  entry={entry_f}  liq={liq_f}  uPnL={u_pnl_f}  lev={lev_val}x {lev_type}"
        )

    ms = state.get("time")
    if ms:
        lines.append(f"_Actualizado: {_ts(ms)}_")
    return "\n".join(lines)

def format_open_orders_md(orders: list, limit: int = 8) -> str:
    if not orders:
        return "📋 *Órdenes abiertas*: (ninguna)"
    rows = orders[:limit]
    out = ["📋 *Órdenes abiertas*"]
    for o in rows:
        coin = o.get("coin", "-")
        side = o.get("side", "-")
        side_txt = "Sell" if side == "A" else ("Buy" if side == "B" else side)
        sz = o.get("sz", o.get("origSz", "-"))
        px = o.get("limitPx", "-")
        typ = o.get("orderType", "Limit")
        trig = o.get("triggerCondition", "N/A")
        tpx = o.get("triggerPx", "0")

        sz_f = fmt_num(sz, 2)
        px_f = fmt_num(px, 2)
        tpx_f = fmt_num(tpx, 2) if tpx not in (None, "0", 0) else "0.00"

        out.append(f"• {coin} {side_txt} {sz_f}@{px_f}  ({typ}, trig={trig} {tpx_f})")
    if len(orders) > limit:
        out.append(f"_…y {len(orders)-limit} más_")
    return "\n".join(out)

def format_recent_fills_md(fills: list, limit: int = 5) -> str:
    if not fills:
        return "🧾 *Fills recientes*: (sin actividad)"
    rows = fills[:limit]
    out = ["🧾 *Fills recientes*"]
    for f in rows:
        coin = f.get("coin", "-")
        dirn = f.get("dir", "-")
        sz = f.get("sz", "-")
        px = f.get("px", "-")
        t = _ts(f.get("time"))

        sz_f = fmt_num(sz, 2)
        px_f = fmt_num(px, 2)

        out.append(f"• {t} — {coin} {dirn} {sz_f}@{px_f}")
    return "\n".join(out)
