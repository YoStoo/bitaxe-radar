"""Mining earnings estimates for Bitaxe Radar. Stdlib only.

Inputs come from mempool.space at build time (network hashrate, recent fees, BTC/USD) and are cached in
data/network.json so a failed fetch falls back to the last good values. Values older than STALE_HOURS are not shown.
All figures are estimates and are labelled as such on the site.
"""
import json
import math
import urllib.request
from datetime import datetime, timezone

SUBSIDY_BTC = 3.125          # block subsidy since the April 2024 halving (next halving ~2028)
BLOCKS_PER_DAY = 144
DAYS_PER_MONTH = 365 / 12
POOL_FEE = 0.02              # typical pool fee
HAIRCUT = 0.10               # conservative cut so the estimate sits a little under the theoretical figure
POWER_RATE = 0.15            # $/kWh used for the power-cost line (stated on the page)
STALE_HOURS = 48
API = "https://mempool.space/api"


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "bitaxeradar-build/1.0 (+https://bitaxeradar.com)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_network(now=None):
    """Live inputs from mempool.space. Raises on any failure or implausible value."""
    now = now or datetime.now(timezone.utc)
    hr = _get(f"{API}/v1/mining/hashrate/3d")
    prices = _get(f"{API}/v1/prices")
    rew = _get(f"{API}/v1/mining/reward-stats/144")
    hashrate = float(hr["currentHashrate"])                       # H/s
    blocks = int(rew["endBlock"]) - int(rew["startBlock"]) + 1
    fees_btc = int(rew["totalFee"]) / 1e8 / max(blocks, 1)          # average fees per block, recent ~day
    usd = float(prices["USD"])
    if not (1e20 < hashrate < 1e23 and 1000 < usd < 10_000_000 and 0 <= fees_btc < 5):
        raise ValueError("implausible network data")
    return {"network_hashrate_hs": hashrate, "difficulty": float(hr.get("currentDifficulty") or 0),
            "subsidy_btc": SUBSIDY_BTC, "avg_fees_btc": round(fees_btc, 8), "btc_usd": usd,
            "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "mempool.space"}


def load_network(path, *, fetch=fetch_network, now=None):
    """Fetch fresh inputs and cache them; on failure use the cached file. Returns (data or None, fresh_enough)."""
    now = now or datetime.now(timezone.utc)
    data = None
    try:
        data = fetch(now=now)
        path.write_text(json.dumps(data, indent=1) + "\n")
    except Exception as e:  # network down, API change: fall back to the last good values
        print("network data fetch failed, using cache:", type(e).__name__, e)
        try:
            data = json.loads(path.read_text())
        except Exception:
            return None, False
    age_h = (now - datetime.strptime(data["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600
    return data, age_h <= STALE_HOURS


def block_btc(net):
    return net["subsidy_btc"] + net["avg_fees_btc"]


def share(hashrate_ths, net):
    return hashrate_ths * 1e12 / net["network_hashrate_hs"]


def floor_to(x, step):
    return round(math.floor(x / step + 1e-9) * step, 2)


def pool_estimate(hashrate_ths, net, *, fee=POOL_FEE, haircut=HAIRCUT):
    """Expected pool payout: share of network x 144 blocks x block reward, minus pool fee, minus a conservative haircut."""
    btc_day = share(hashrate_ths, net) * BLOCKS_PER_DAY * block_btc(net) * (1 - fee) * (1 - haircut)
    usd_day = btc_day * net["btc_usd"]
    usd_month = usd_day * DAYS_PER_MONTH
    return {"btc_day": btc_day, "usd_day": usd_day, "usd_month": usd_month,
            "usd_day_shown": floor_to(usd_day, 0.01), "usd_month_shown": round_down_money(usd_month)}


def round_down_money(x):
    """Round down: to the cent under $10, to the dollar above."""
    return floor_to(x, 0.01) if x < 10 else float(math.floor(x))


def power_cost_month(watts, rate=POWER_RATE):
    return watts / 1000 * 24 * DAYS_PER_MONTH * rate


# ---- "your electricity price" calculator. site/calc.js mirrors these line for line (tests/test_calc_parity.py). ----
def round_up_money(x):
    """Round up (the conservative direction for a cost): to the cent under $10, to the dollar above."""
    return math.ceil(x * 100 - 1e-9) / 100 if x < 10 else float(math.ceil(x - 1e-9))


def fmt_rate(rate):
    s = f"{math.floor(rate * 1000 + 0.5) / 1000:.3f}"
    return "$" + (s[:-1] if s.endswith("0") else s)


def net_month(hashrate_ths, watts, net, rate=POWER_RATE):
    """Pool estimate (already rounded down) minus the power bill. Negative = costs more than it earns."""
    return pool_estimate(hashrate_ths, net)["usd_month_shown"] - power_cost_month(watts, rate)


def net_words(hashrate_ths, watts, net, rate=POWER_RATE):
    n = net_month(hashrate_ths, watts, net, rate)
    r = fmt_rate(rate)
    if abs(n) < 0.01:
        return f"About breaks even at {r}"
    if n > 0:
        return f"Earns about {fmt_usd(round_down_money(n))}/mo more than its power costs at {r}"
    return f"Costs about {fmt_usd(round_up_money(-n))}/mo more than it earns at {r}"


def net_short(hashrate_ths, watts, net, rate=POWER_RATE):
    """Signed form for tables: '+$1.20' or '−$0.81' (same rounding as net_words)."""
    n = net_month(hashrate_ths, watts, net, rate)
    if abs(n) < 0.01:
        return "$0.00"
    return ("+" + fmt_usd(round_down_money(n))) if n > 0 else ("−" + fmt_usd(round_up_money(-n)))


def breakeven_rate(hashrate_ths, watts, net):
    """Power price ($/kWh) where the conservative pool estimate equals the power bill, rounded down to 0.1 cent."""
    kwh_month = watts / 1000 * 24 * DAYS_PER_MONTH
    return math.floor(pool_estimate(hashrate_ths, net)["usd_month"] / kwh_month * 1000 + 1e-9) / 1000


def power_shown(watts, rate=POWER_RATE):
    """Power bill as shown on the site: rounded up, the conservative direction for a cost."""
    return round_up_money(power_cost_month(watts, rate))


def heat_value_month(watts, rate=POWER_RATE):
    """What a space heater of the same wattage would cost to run 24/7: the heat you'd pay for anyway."""
    return round_down_money(power_cost_month(watts, rate))


def solo_odds(hashrate_ths, net):
    """Chance of finding a block solo: 1 in N per day and per year, plus the block's dollar value."""
    p_day = share(hashrate_ths, net) * BLOCKS_PER_DAY
    p_year = 1 - (1 - p_day) ** 365
    return {"one_in_day": 1 / p_day, "one_in_year": 1 / p_year, "block_usd": block_btc(net) * net["btc_usd"]}


def fmt_usd(x):
    return f"${x:,.2f}" if x < 10 else f"${x:,.0f}"


def fmt_big(n):
    """Plain 'about' number: 6,100,000 -> '6.1 million', 16,700 -> '17,000'."""
    if n >= 1e9:
        return f"{n / 1e9:.2g} billion" if n < 1e10 else f"{n / 1e9:,.0f} billion"
    if n >= 1e6:
        return f"{n / 1e6:.2g} million" if n < 1e7 else f"{n / 1e6:,.0f} million"
    if n >= 100:
        return f"{float(f'{n:.2g}'):,.0f}"
    return f"{n:,.0f}"
