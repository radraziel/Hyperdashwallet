from datetime import datetime, timezone

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
        # szi > 0: Long, < 0: Short
        try:
            side = "Long" if float(szi) > 0 else ("Short" if float(szi) < 0 else "Flat")
        except Exception:
            side = "?"
        entry = pos.get("entryPx", "-")
        value = pos.get("positionValue", "-")
        liq = pos.get("liquidationPx", "-")
        u_pnl = pos.get("unrealizedPnl", "-")
        lev = pos.get("leverage", {})
        lev_val = lev.get("value", "")
        lev_type = lev.get("type", "")
        lines.append(
            f"• {coin}: *{side}*  size=`{szi}`  ntl=`${value}`\n"
            f"  entry=`{entry}`  liq=`{liq}`  uPnL=`{u_pnl}`  lev=`{lev_val}x {lev_type}`"
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
        out.append(f"• {coin} {side_txt} {sz}@{px}  ({typ}, trig={trig} {tpx})")
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
        out.append(f"• {t} — {coin} {dirn} {sz}@{px}")
    return "\n".join(out)
