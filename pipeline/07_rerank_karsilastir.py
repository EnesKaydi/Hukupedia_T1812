"""Rerank açık vs kapalı: konu-eşleşme oranını tüm test sorgularında karşılaştır."""
import json, urllib.request
from collections import Counter

API = "http://127.0.0.1:8000/ara"

# 06'daki sorgu listesini yeniden kullan
import importlib.util
spec = importlib.util.spec_from_file_location("t6", "06_test_sorgulari.py")
# 06 modülü import'ta API'ye istek atıyor; onun yerine sorgu listesini elle alalım
SORGULAR = None
for line in open("06_test_sorgulari.py", encoding="utf-8"):
    pass
# basitçe 06'dan SORGULAR'ı çek
import ast, re
src = open("06_test_sorgulari.py", encoding="utf-8").read()
m = re.search(r"SORGULAR = (\[.*?\n\])", src, re.S)
SORGULAR = ast.literal_eval(m.group(1))


def ara(soru, rerank):
    veri = json.dumps({"soru": soru, "mod": "hibrit", "rerank": rerank, "limit": 5}).encode()
    req = urllib.request.Request(API, data=veri, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


print(f"{'SORGU':50s} {'kapalı':>8s} {'AÇIK':>8s}")
print("-" * 70)
top_kapali = top_acik = n_konu = 0
for soru, beklenen in SORGULAR:
    if not beklenen:
        continue  # tuzakları ayrı değerlendireceğiz
    n_konu += 1
    dk = ara(soru, False); da = ara(soru, True)
    ek = sum(1 for s in dk["sonuclar"] if s["konu_grubu"] == beklenen)
    ea = sum(1 for s in da["sonuclar"] if s["konu_grubu"] == beklenen)
    top_kapali += ek; top_acik += ea
    ok = "↑" if ea > ek else ("↓" if ea < ek else " ")
    print(f"{soru[:50]:50s} {ek:>6d}/5 {ea:>6d}/5 {ok}")

print("-" * 70)
print(f"{'TOPLAM konu-eşleşme':50s} {top_kapali:>6d}/{n_konu*5} {top_acik:>6d}/{n_konu*5}")
print(f"Oran: rerank kapalı %{100*top_kapali/(n_konu*5):.0f}  →  rerank AÇIK %{100*top_acik/(n_konu*5):.0f}")

# Tuzak sorgular: en iyi skor ne kadar düşük? (düşük = sistem dürüst)
print("\n=== TUZAK sorgular (elimizde olmayan konu — skor düşük olmalı) ===")
for soru, beklenen in SORGULAR:
    if beklenen:
        continue
    d = ara(soru, True)
    ust = d["sonuclar"][0] if d["sonuclar"] else {}
    rr = ust.get("rerank_skor", "?")
    print(f"  {soru[:45]:45s} en üst rerank_skor={rr}  konu={ust.get('konu_grubu','-')}")
