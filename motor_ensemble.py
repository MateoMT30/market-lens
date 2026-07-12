"""
Market Lens - Motor ENSEMBLE + cripto (version nube / GitHub Actions).
======================================================================
Ensemble de 3 estrategias (momentum sectores + Faber + dual momentum),
MAS un sleeve pequeno de cripto por momentum (10%), que incluye Bitcoin,
Ethereum, Litecoin, XRP y Bitcoin Cash. El sleeve tiene la moneda mas
fuerte del momento, o se va a efectivo si ninguna sube.

Medido (2018-2026): añadir 10% de cripto subio el retorno de ~11% a ~14%
y el Sharpe de 0.69 a 0.78, con la caida pasando de -15% a -17%.

Seguro para repos publicos: el token de Telegram se lee de variables de
entorno (GitHub Secrets), nunca del codigo.
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
MONEDAS = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "LTC-USD": "Litecoin",
           "XRP-USD": "XRP", "BCH-USD": "Bitcoin Cash"}
CRIPTO_W = 0.10

NOMBRES = dict(SECTORES, **MONEDAS, SPY="Acciones EE.UU. (S&P 500)",
               EFA="Acciones internacionales", AGG="Bonos (refugio)", SHY="Efectivo (T-bills)")
ROLES = {"SPY": "Crecimiento · mercado EE.UU.", "EFA": "Crecimiento · internacional",
         "AGG": "Refugio · bonos", "SHY": "Refugio · efectivo"}
for _s in SECTORES:
    ROLES[_s] = "Crecimiento · sector fuerte"
for _c in MONEDAS:
    ROLES[_c] = "Cripto · momentum (alto riesgo)"

CASH = "SHY"
LB = 12
SMA_M = 10

TRACK = {
    "ensemble": {"nombre": "Ensemble + cripto (tu app)", "cagr": 13.9, "sharpe": 0.78, "maxdd": -17.1},
    "mercado": {"nombre": "Comprar S&P 500", "cagr": 11.1, "sharpe": 0.66, "maxdd": -50.8},
    "momentum": {"nombre": "Ensemble sin cripto", "cagr": 10.8, "sharpe": 0.69, "maxdd": -14.7},
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


def alloc_cripto(px, i):
    moms = {c: px[c][i] / px[c][i - LB] - 1 for c in MONEDAS}
    best = max(moms, key=lambda c: moms[c])
    return best if moms[best] > 0 else CASH


def ret_serie(px, alloc_fn, tickers):
    N = len(px["SPY"])
    out = []
    for i in range(LB, N - 1):
        w = alloc_fn(px, i)[0]
        out.append(sum(w.get(k, 0) * (px[k][i + 1] / px[k][i] - 1) for k in tickers))
    return out


def calcular():
    stk = list(SECTORES) + ["SPY", "EFA", "AGG", CASH]
    tickers = stk + list(MONEDAS)
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
    rA, rB, rC = ret_serie(px, alloc_A, stk), ret_serie(px, alloc_B, stk), ret_serie(px, alloc_C, stk)
    vols = [std(r[-12:]) or 1e-4 for r in (rA, rB, rC)]
    inv = [1 / v for v in vols]
    s = sum(inv)
    pesos = [x / s for x in inv]

    ens = {}
    for w, pe in ((wa, pesos[0]), (wb, pesos[1]), (wc, pesos[2])):
        for etf, frac in w.items():
            ens[etf] = ens.get(etf, 0) + frac * pe

    cripto_pick = alloc_cripto(px, i)

    final = {k: v * (1 - CRIPTO_W) for k, v in ens.items()}
    final[cripto_pick] = final.get(cripto_pick, 0) + CRIPTO_W
    final = {k: v for k, v in final.items() if v >= 0.02}
    tot = sum(final.values())
    final = {k: v / tot for k, v in final.items()}
    orden = sorted(final, key=lambda k: final[k], reverse=True)

    # momentum a 12 meses de CADA activo (para mostrarlo en su grafica)
    momentos = {}
    for a in list(SECTORES) + ["SPY", "EFA"] + list(MONEDAS):
        if a in px and len(px[a]) > LB:
            momentos[a] = round((px[a][i] / px[a][i - LB] - 1) * 100, 1)

    return {"moms": moms, "picks": picks, "pick_b": pick_b, "pick_c": pick_c,
            "cripto": cripto_pick, "pesos": pesos, "final": final, "orden": orden,
            "momentos": momentos}


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
    cripto_txt = ("con %s en la parte cripto" % NOMBRES.get(c["cripto"], c["cripto"])) \
        if c["cripto"] != CASH else "sin cripto este mes (ninguna moneda con momentum)"
    pasos = [
        "Este mes, tu cartera objetivo es: " + mezcla + ".",
        "Traducido: %d%% en crecimiento y %d%% en refugio; %s." % (round(crec * 100), round(refu * 100), cripto_txt),
        "Si empiezas de cero: compra esos ETF/monedas en esos porcentajes con un broker/exchange.",
        "Si ya estabas invertido: solo mueve lo necesario para acercarte a esos porcentajes (rebalanceo).",
        "No hagas nada mas hasta el proximo mes o hasta que te llegue una alerta de cambio.",
    ]
    return pasos, round(crec * 100), round(refu * 100)


def main():
    print("Market Lens (nube) - motor ENSEMBLE + cripto")
    c = calcular()
    pasos, crec, refu = plan_accion(c)
    alloc = [{"etf": e, "nombre": NOMBRES.get(e, e), "rol": ROLES.get(e, ""),
              "pct": round(c["final"][e] * 100)} for e in c["orden"]]
    sect = [{"tk": s, "nombre": SECTORES[s], "mom": round(c["moms"][s] * 100, 1), "sel": s in c["picks"]}
            for s in sorted(SECTORES, key=lambda k: c["moms"][k], reverse=True)]
    payload = {
        "fecha": datetime.now().strftime("%d %b %Y"), "modo": "ensemble+cripto",
        "asignacion": alloc, "crecimiento_pct": crec, "refugio_pct": refu, "plan": pasos,
        "sub": {"sectores": c["picks"] or ["(ninguno: mercado debil)"], "faber": c["pick_b"],
                "gem": c["pick_c"], "cripto": NOMBRES.get(c["cripto"], "Efectivo"),
                "pesos": {"Momentum sectores": round(c["pesos"][0] * 100),
                          "Faber tendencia": round(c["pesos"][1] * 100),
                          "Dual momentum": round(c["pesos"][2] * 100)}},
        "sectores_mom": sect, "track": TRACK, "momentos": c["momentos"],
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
        link = "\n\n\U0001F4F1 Tablero: https://mateomt30.github.io/market-lens/"
        enviar_telegram("\U0001F4CA <b>Market Lens · Cartera del mes</b>\n" + mezcla +
                        "\n\n%d%% crecimiento · %d%% refugio (incluye ~10%% cripto)" % (crec, refu) + link +
                        "\n\n<i>Historial: 13.9%/año, caída máx −17% (2018-2026). Cripto = alto riesgo. No es consejo financiero.</i>")
    elif "--alert" in sys.argv:
        print("[i] Sin cambios: no se alerta.")
    json.dump({"firma": firma, "ts": datetime.now().isoformat()},
              open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
