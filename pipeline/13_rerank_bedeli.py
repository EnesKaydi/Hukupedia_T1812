"""Reranker'ın kalite katkısı ile gecikme bedelini birlikte ölçer.

Gecikme dökümü reranker'ın toplam sürenin %80'inden fazlasını harcadığını gösterdi.
Bu betik aynı altın standart üzerinde rerank açık/kapalı P@5 farkını ve saniye
farkını yan yana koyar; demoda hangi ayarla çıkılacağına bu tabloya bakarak karar verilir.
"""
import os
import json, urllib.request

import psycopg

DB = os.environ["HUKUPEDIA_DSN"]
API = "http://127.0.0.1:8000/ara"
K = 5

MESELELER = [
    ("işe yeni alınan personelin ilk aylarda çıkarılması", "deneme süresi", "İş K. m.15"),
    ("emekli olan çalışanın tazminat hakkı", "yaşlılık aylığ\\w*.{0,80}kıdem tazminat", "emeklilik-kıdem"),
    ("kadının boşandıktan sonra tekrar evlenebilmesi için geçmesi gereken süre",
     "iddet müddeti|iddet süresi", "TMK m.132"),
    ("eşlerin bir süreliğine ayrı yaşamasına hükmedilmesi", "ayrılığa karar|ayrılık karar", "TMK m.170"),
    ("çalışanın işe gelmemesi sebebiyle sözleşmenin sona erdirilmesi", "devamsızlık", "İş K. m.25/II-g"),
    ("evlilik sona erdiğinde çocuğun kimin yanında kalacağı", "velayet", "TMK m.182"),
    ("çalışanın mesai saatleri dışında çalıştırılması karşılığı", "fazla mesai|fazla çalışma", "İş K. m.41"),
    ("gelinin düğünde takılan altınlarının geri istenmesi", "ziynet", "ziynet alacağı"),
    ("iş yerinde meydana gelen olayda işverenin sorumluluk payı", "kusur oran|kusur derece", "iş kazası kusur"),
    ("sigortalı çalışmanın mahkeme yoluyla ispatlanması", "hizmet tespit", "hizmet tespiti"),
    ("işten ayrılan çalışana ödenmesi gereken kullanılmamış izin bedeli",
     "yıllık izin ücret|izin alacağ", "İş K. m.59"),
    ("eşin sadakatsizliği sebebiyle talep edilen manevi zarar", "sadakat|aldat", "TMK m.174/2"),
]


def ara(soru, rerank):
    v = json.dumps({"soru": soru, "mod": "hibrit", "limit": K, "rerank": rerank}).encode()
    r = urllib.request.Request(API, data=v, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=180) as resp:
        d = json.loads(resp.read())
    return [s["belge_id"] for s in d["sonuclar"]], d["sure"]["toplam"]


rapor, sure = [], {"kapali": [], "acik": []}
with psycopg.connect(DB) as conn:
    for soru, regex, ad in MESELELER:
        altin = {r[0] for r in conn.execute(
            "SELECT DISTINCT b.belge_id FROM parcalar p JOIN belgeler b ON b.id=p.belge_id "
            "WHERE p.metin ~* %s", (regex,)).fetchall()}
        satir = {"mesele": ad, "altin": len(altin)}
        for etiket, rr in (("kapali", False), ("acik", True)):
            bulunan, sn = ara(soru, rr)
            satir[f"P@5_{etiket}"] = round(len(altin & set(bulunan)) / K, 3)
            sure[etiket].append(sn)
        rapor.append(satir)
        print(f"{ad:22s} | rerank kapalı P@5=%{100*satir['P@5_kapali']:3.0f} "
              f"| açık P@5=%{100*satir['P@5_acik']:3.0f}", flush=True)


def ort(x):
    return round(sum(x) / len(x), 3)


ozet = {
    "rerank_kapali": {"P@5": ort([r["P@5_kapali"] for r in rapor]), "ort_sn": ort(sure["kapali"])},
    "rerank_acik": {"P@5": ort([r["P@5_acik"] for r in rapor]), "ort_sn": ort(sure["acik"])},
}
ozet["kalite_farki_puan"] = round(100 * (ozet["rerank_acik"]["P@5"] - ozet["rerank_kapali"]["P@5"]), 1)
ozet["gecikme_bedeli_sn"] = round(ozet["rerank_acik"]["ort_sn"] - ozet["rerank_kapali"]["ort_sn"], 2)
json.dump({"ozet": ozet, "meseleler": rapor},
          open("rerank_bedeli_sonuc.json", "w"),
          ensure_ascii=False, indent=2)
print("\n" + json.dumps(ozet, ensure_ascii=False, indent=2))
