"""
Market Lens - Motor ENSEMBLE (version nube / GitHub Actions).
=============================================================
Igual que el motor local, pero:
  - El token de Telegram se lee de variables de entorno (GitHub Secrets),
    NUNCA va escrito en el codigo -> seguro para repos publicos.
  - Escribe el tablero en docs/motor_data.json (lo que publica GitHub Pages).
  - Guarda el estado en estado.json (se versiona en el repo) para detectar
    cambios entre corridas.

Corre solo en la nube cada dia via GitHub Actions. No necesita tu PC.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

OUT_JSON = os.path.join("docs", "motor_data.json")
STATE_FILE = "estado.json"

SECTORES = {
    "XLK": "Tecnologia", "XLF": "Financiero", "XLE": "Energia", "XLV": "Salud",
    "XLI": "Industrial", "XLP": "Consumo basico", "XLY": "Consumo discrecional",
    "XLU": "Servicios publicos", "XLB": "Materiales",
}
NOMBRES = dict(SECTORES, SPY="Acciones EE.UU. (S&P 500)", EFA="Acciones internacionales",
               AGG="Bonos (refugio)", SHY="Efectivo (T-bills)")
ROLES = {"SPY": "Crecimiento · mercado EE.UU.", "EFA": "Crecimiento · internacional",
         "AGG": "Refugio · bonos", "SHY": "Refugio · efectivo"}
for _s in SECTORES:
    ROLES[_s] = "Crecimiento · sector fuerte"

CASH = "SHY"
LB = 12
SMA_M = 10

TRACK = {
    "ensemble": {"nombre": "Ensemble (tu app)", "cagr": 10.2, "sharpe": 0.77, "maxdd": -16.1},
    "mercado": {"nombre": "Comprar S&P 500", "cagr": 11.1, "sharpe": 0.66, "maxdd": -50.8},
    "momentum": {"nombre": "Solo momentum sectores", "cagr": 11.4, "sharpe": 0.66, "maxdd": -24.6},
}


def http_get(url, timeout=30, retries=4):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MarketLens)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def fetch_monthly(symbol):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" +
           urllib.parse.quote(symbol) + "?range=5y&interval=1mo")
    j = json.loads(http_get(url))
    res = j["chart"]["result"][0]
    ts, adj = res["timestamp"], res["indicators"].get("adjclose")
    vals = adj[0]["adjclose"] if adj else res["indicators"]["quote"][0]["close"]
    return [v for v in vals if v is not None]


def mean(a):
    return sum(a) / len(a) if a else 0.0


def std(a):
    if len(a) < 2:
        return 0.0
    m = mean(a)
    return (sum((x - m) ** 2 for x in a) / (len(a) - 1)) ** 0.5


def sma(seq, n):
    return mean(seq[-n:]) if len(seq) >= n else None


def alloc_A(px, i):
    moms = {s: px[s][i] / px[s][i - LB] - 1 for s in SECTORES}
    picks = [s for s in sorted(SECTORES, key=lambda k: moms[k], reverse=True)[:2] if moms[s] > 0]
    w = {}
    for s in picks:
        w[s] = w.get(s, 0) + 0.5
    if 2 - len(picks):
        w["AGG"] = w.get("AGG", 0) + (2 - len(picks)) / 2
    return w, moms, picks


def alloc_B(px, i):
    s = sma(px["SPY"][:i + 1], SMA_M)
    return ({"SPY": 1.0}, "SPY") if (s and px["SPY"][i] > s) else ({CASH: 1.0}, "Efectivo")


def alloc_C(px, i):
    ms = px["SPY"][i] / px["SPY"][i - LB] - 1
    me = px["EFA"][i] / px["EFA"][i - LB] - 1
    mc = px[CASH][i] / px[CASH][i - LB] - 1
    tk = ("SPY" if ms >= me else "EFA") if ms > mc else "AGG"
    return {tk: 1.0}, tk


def ret_serie(px, alloc_fn, tickers):
    N = len(px["SPY"])
    out = []
    for i in range(LB, N - 1):
        w = alloc_fn(px, i)[0]
        out.append(sum(w.get(k, 0) * (px[k][i + 1] / px[k][i] - 1) for k in tickers))
    return out


def calcular():
    tickers = list(SECTORES) + ["SPY", "EFA", "AGG", CASH]
    px = {}
    for tk in tickers:
        px[tk] = fetch_monthly(tk)
        time.sleep(0.35)
    n = min(len(v) for v in px.values())
    px = {k: v[-n:] for k, v in px.items()}
    i = n - 1
    wa, moms, picks = alloc_A(px, i)
    wb, pick_b = alloc_B(px, i)
    wc, pick_c = alloc_C(px, i)
    rA, rB, rC = ret_serie(px, alloc_A, tickers), ret_serie(px, alloc_B, tickers), ret_serie(px, alloc_C, tickers)
    vols = [std(r[-12:]) or 1e-4 for r in (rA, rB, rC)]
    inv = [1 / v for v in vols]
    s = sum(inv)
    pesos = [x / s for x in inv]
    final = {}
    for w, pe in ((wa, pesos[0]), (wb, pesos[1]), (wc, pesos[2])):
        for etf, frac in w.items():
            final[etf] = final.get(etf, 0) + frac * pe
    final = {k: v for k, v in final.items() if v >= 0.02}
    tot = sum(final.values())
    final = {k: v / tot for k, v in final.items()}
    orden = sorted(final, key=lambda k: final[k], reverse=True)
    return {"moms": moms, "picks": picks, "pick_b": pick_b, "pick_c": pick_c,
            "pesos": pesos, "final": final, "orden": orden}


def enviar_telegram(texto):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[i] Sin TELEGRAM_TOKEN/CHAT_ID en el entorno: no se envia alerta.")
        return
    url = "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_TOKEN
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": texto,
                                   "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15).read()
        print("[i] Alerta enviada a Telegram.")
    except Exception as e:
        print("[!] Telegram:", e)


def plan_accion(c):
    mezcla = ", ".join("%d%% %s" % (round(c["final"][e] * 100), e) for e in c["orden"])
    crec = sum(v for k, v in c["final"].items() if k not in ("AGG", "SHY"))
    refu = 1 - crec
    pasos = [
        "Este mes, tu cartera objetivo es: " + mezcla + ".",
        "Traducido: %d%% en crecimiento (sectores/acciones) y %d%% en refugio (bonos/efectivo)."
        % (round(crec * 100), round(refu * 100)),
        "Si empiezas de cero: compra esos ETF en esos porcentajes con un broker que de acceso a EE.UU.",
        "Si ya estabas invertido: solo mueve lo necesario para acercarte a esos porcentajes (rebalanceo).",
        "No hagas nada mas hasta el proximo mes o hasta que te llegue una alerta de cambio.",
    ]
    return pasos, round(crec * 100), round(refu * 100)


def main():
    print("Market Lens (nube) - motor ENSEMBLE")
    c = calcular()
    pasos, crec, refu = plan_accion(c)
    alloc = [{"etf": e, "nombre": NOMBRES.get(e, e), "rol": ROLES.get(e, ""),
              "pct": round(c["final"][e] * 100)} for e in c["orden"]]
    sect = [{"tk": s, "nombre": SECTORES[s], "mom": round(c["moms"][s] * 100, 1), "sel": s in c["picks"]}
            for s in sorted(SECTORES, key=lambda k: c["moms"][k], reverse=True)]
    payload = {
        "fecha": datetime.now().strftime("%d %b %Y"), "modo": "ensemble",
        "asignacion": alloc, "crecimiento_pct": crec, "refugio_pct": refu, "plan": pasos,
        "sub": {"sectores": c["picks"] or ["(ninguno: mercado debil)"], "faber": c["pick_b"],
                "gem": c["pick_c"],
                "pesos": {"Momentum sectores": round(c["pesos"][0] * 100),
                          "Faber tendencia": round(c["pesos"][1] * 100),
                          "Dual momentum": round(c["pesos"][2] * 100)}},
        "sectores_mom": sect, "track": TRACK,
    }
    os.makedirs("docs", exist_ok=True)
    json.dump(payload, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("-> docs/motor_data.json actualizado.")

    firma = "|".join("%s:%d" % (e, round(c["final"][e] * 100)) for e in c["orden"])
    prev = {}
    if os.path.exists(STATE_FILE):
        try:
            prev = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            prev = {}
    cambio = prev.get("firma") != firma
    if "--alert" in sys.argv and (cambio or not prev):
        mezcla = "\n".join("• %d%% %s (%s)" % (round(c["final"][e] * 100), NOMBRES.get(e, e), e) for e in c["orden"])
        enviar_telegram("\U0001F4CA <b>Market Lens · Cartera del mes</b>\n" + mezcla +
                        "\n\n%d%% crecimiento · %d%% refugio" % (crec, refu) +
                        "\n\n<i>Historial: 10.2%/año, caída máx −16% (2004-2026). No es consejo financiero.</i>")
    elif "--alert" in sys.argv:
        print("[i] Sin cambios: no se alerta.")
    json.dump({"firma": firma, "ts": datetime.now().isoformat()},
              open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
