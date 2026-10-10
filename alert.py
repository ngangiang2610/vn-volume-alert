#!/usr/bin/env python3
"""Cảnh báo cổ phiếu VN có KL trong ngày vượt RATIO x KLGD trung bình 20 phiên."""
import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

RATIO = float(os.environ.get("RATIO", "0.5"))
MIN_AVG_VOL = int(os.environ.get("MIN_AVG_VOL", "200000"))
WINDOW = ("09:30", "11:00")
EXCHANGES = ("hose", "hnx")
VN_TZ = timezone(timedelta(hours=7))
HERE = Path(__file__).parent
AVG_FILE = HERE / "avg20.json"
STATE_FILE = HERE / "state.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://iboard.ssi.com.vn",
    "Referer": "https://iboard.ssi.com.vn/",
}


def get_json(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1 + i)


def fetch_snapshot():
    """Ảnh chụp hiện tại của cả 3 sàn: {symbol: row}."""
    out = {}
    for ex in EXCHANGES:
        data = get_json(f"https://iboard-query.ssi.com.vn/stock/exchange/{ex}")["data"]
        for s in data:
            if s.get("stockType") == "s":
                out[s["stockSymbol"]] = s
    return out


def fetch_avg20(symbol, today):
    """TB KL 20 phiên đã kết thúc (bỏ phiên hôm nay nếu đã có)."""
    now = int(time.time())
    url = ("https://iboard-api.ssi.com.vn/statistics/charts/history"
           f"?symbol={symbol}&resolution=1D&from={now - 60 * 86400}&to={now}")
    d = get_json(url)["data"]
    bars = [(datetime.fromtimestamp(t, VN_TZ).strftime("%Y%m%d"), v)
            for t, v in zip(d.get("t", []), d.get("v", []))]
    vols = [v for day, v in bars if day != today][-20:]
    return sum(vols) / len(vols) if len(vols) >= 10 else 0


def load_avg20(snapshot, today):
    if AVG_FILE.exists():
        cached = json.loads(AVG_FILE.read_text())
        if cached.get("date") == today:
            return cached["avg"]
    print(f"Tính TB20 cho {len(snapshot)} mã...", file=sys.stderr)

    def one(sym):
        try:
            return sym, fetch_avg20(sym, today)
        except Exception as e:
            print(f"  lỗi {sym}: {e}", file=sys.stderr)
            return sym, 0

    with ThreadPoolExecutor(16) as ex:
        avg = dict(ex.map(one, snapshot))
    AVG_FILE.write_text(json.dumps({"date": today, "avg": avg}))
    return avg


def load_state(today):
    if STATE_FILE.exists():
        s = json.loads(STATE_FILE.read_text())
        if s.get("date") == today:
            return s
    return {"date": today, "alerted": []}


def format_messages(hits):
    lines = [f"{h['sym']:<5} {h['vol']/1e6:6.2f}M ({h['ratio']:.2f}x)  "
             f"{h['price']:,.0f}  {h['pct']:+.1f}%" for h in hits]
    head = f"🔔 KL ≥ {RATIO}x TB20 ({datetime.now(VN_TZ):%H:%M})\n"
    msgs, cur = [], head + "```\n"
    for line in lines:
        if len(cur) + len(line) + 5 > 1900:
            msgs.append(cur + "```")
            cur = "```\n"
        cur += line + "\n"
    msgs.append(cur + "```")
    return msgs


def notify(text):
    url = os.environ["DISCORD_WEBHOOK_URL"]
    req = urllib.request.Request(
        url, data=json.dumps({"content": text}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "vn-volume-alert"})
    urllib.request.urlopen(req, timeout=20).read()


def in_window():
    now = datetime.now(VN_TZ)
    return now.weekday() < 5 and WINDOW[0] <= f"{now:%H:%M}" <= WINDOW[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="in ra, không gửi, không lưu state")
    ap.add_argument("--any-time", action="store_true", help="bỏ qua kiểm tra khung giờ")
    ap.add_argument("--test", action="store_true", help="gửi 1 tin thử rồi thoát")
    args = ap.parse_args()

    if args.test:
        notify("✅ vn-volume-alert: kết nối Discord OK")
        return

    if not (args.any_time or in_window()):
        print("Ngoài khung giờ, bỏ qua.")
        return

    snap = fetch_snapshot()
    today = next(iter(snap.values()))["tradingDate"]
    avg = load_avg20(snap, today)
    state = load_state(today)

    hits = []
    for sym, row in snap.items():
        a = avg.get(sym, 0)
        if a < MIN_AVG_VOL or sym in state["alerted"]:
            continue
        vol = row.get("nmTotalTradedQty") or row.get("stockVol") or 0
        if vol >= RATIO * a:
            hits.append({"sym": sym, "vol": vol, "ratio": vol / a,
                         "price": row.get("matchedPrice") or row.get("refPrice") or 0,
                         "pct": row.get("priceChangePercent") or 0})
    hits.sort(key=lambda h: -h["ratio"])
    universe = sum(1 for a in avg.values() if a >= MIN_AVG_VOL)
    print(f"{today}: {universe} mã đủ thanh khoản, {len(hits)} mã mới vượt {RATIO}x")
    if not hits:
        return

    msgs = format_messages(hits)
    if args.dry_run:
        print("\n".join(msgs))
        return
    for m in msgs:
        notify(m)
    state["alerted"] += [h["sym"] for h in hits]
    STATE_FILE.write_text(json.dumps(state))


if __name__ == "__main__":
    main()
