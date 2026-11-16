"""Öbek kolu A/B testi — nesnel geri-getirme ölçümü, aynı koşullarda karşılaştırma.

10_altin_standart_test.py'deki iki kusuru giderir:
  1. Tek bir limit=20 sorgusundan P@5 türetiyordu; oysa reranker aday havuzu limit'e
     bağlı, dolayısıyla ölçülen davranış gerçek limit=5 sorgusundan farklıydı.
     Burada her k için ayrı sorgu atılır.
  2. Öbek kolunun etkisi ancak API yeniden başlatılarak ölçülebiliyordu; artık
     istekteki `obek` bayrağıyla aynı koşuşta A/B yapılır.
"""
import os
import json, time, urllib.request

import psycopg

DB = os.environ["HUKUPEDIA_DSN"]
API = "http://127.0.0.1:8000/ara"
K_LISTESI = (5, 10)

# 10_altin_standart_test.py ile aynı mesele listesi (bağımsız çalışsın diye kopyalandı)
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


def ara(soru, limit, obek):
    v = json.dumps({"soru": soru, "mod": "hibrit", "limit": limit, "obek": obek}).encode()
    r = urllib.request.Request(API, data=v, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(r, timeout=180) as resp:
        d = json.loads(resp.read())
    return [s["belge_id"] for s in d["sonuclar"]], time.perf_counter() - t0


rapor, sureler = [], {"obeksiz": [], "obekli": []}
with psycopg.connect(DB) as conn:
    for soru, regex, ad in MESELELER:
        altin = {r[0] for r in conn.execute(
            "SELECT DISTINCT b.belge_id FROM parcalar p JOIN belgeler b ON b.id=p.belge_id "
            "WHERE p.metin ~* %s", (regex,)).fetchall()}
        satir = {"mesele": ad, "soru": soru, "altin": len(altin)}
        for etiket, obek in (("obeksiz", False), ("obekli", True)):
            for k in K_LISTESI:
                bulunan, sn = ara(soru, k, obek)
                satir[f"{etiket}_P@{k}"] = round(len(altin & set(bulunan)) / k, 3)
                sureler[etiket].append(sn)
        rapor.append(satir)
        print(f"{ad:22s} altın={len(altin):4d} | öbeksiz P@5=%{100*satir['obeksiz_P@5']:3.0f} "
              f"P@10=%{100*satir['obeksiz_P@10']:3.0f} || öbekli P@5=%{100*satir['obekli_P@5']:3.0f} "
              f"P@10=%{100*satir['obekli_P@10']:3.0f}", flush=True)


def ort(alan):
    return round(sum(r[alan] for r in rapor) / len(rapor), 3)


def gecikme(e):
    s = sorted(sureler[e])
    return {"ort_sn": round(sum(s) / len(s), 2), "p50_sn": round(s[len(s) // 2], 2),
            "p95_sn": round(s[int(len(s) * 0.95)], 2)}


ozet = {
    "mesele_sayisi": len(rapor),
    "obeksiz": {"P@5": ort("obeksiz_P@5"), "P@10": ort("obeksiz_P@10"), **gecikme("obeksiz")},
    "obekli": {"P@5": ort("obekli_P@5"), "P@10": ort("obekli_P@10"), **gecikme("obekli")},
    "iyilesen": [r["mesele"] for r in rapor if r["obekli_P@5"] > r["obeksiz_P@5"]],
    "kotulesen": [r["mesele"] for r in rapor if r["obekli_P@5"] < r["obeksiz_P@5"]],
}
json.dump({"ozet": ozet, "meseleler": rapor},
          open("ab_testi_sonuc.json", "w"),
          ensure_ascii=False, indent=2)
print("\n" + json.dumps(ozet, ensure_ascii=False, indent=2))
