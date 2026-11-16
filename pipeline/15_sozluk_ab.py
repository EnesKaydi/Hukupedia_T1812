"""Sözlük katmanı A/B testi — altın standart üzerinde sözlük açık/kapalı karşılaştırması.

Veri ekleme ile sözlük aynı anda devreye girdiği için ikisinin etkisini ayrıştırmak
gerekir; bu betik aynı korpusta yalnız sözlük bayrağını değiştirerek ölçer.
"""
import os
import json, urllib.request

import psycopg

DB = os.environ["HUKUPEDIA_DSN"]
API = "http://127.0.0.1:8000/ara"
K_LISTESI = (5, 10)

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


def ara(soru, limit, sozluk):
    v = json.dumps({"soru": soru, "mod": "hibrit", "limit": limit, "sozluk": sozluk}).encode()
    r = urllib.request.Request(API, data=v, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=180) as resp:
        d = json.loads(resp.read())
    return [s["belge_id"] for s in d["sonuclar"]], d.get("eklenen_terimler", [])


rapor = []
with psycopg.connect(DB) as conn:
    for soru, regex, ad in MESELELER:
        altin = {r[0] for r in conn.execute(
            "SELECT DISTINCT b.belge_id FROM parcalar p JOIN belgeler b ON b.id=p.belge_id "
            "WHERE p.metin ~* %s", (regex,)).fetchall()}
        satir = {"mesele": ad, "altin": len(altin)}
        for etiket, bayrak in (("kapali", False), ("acik", True)):
            for k in K_LISTESI:
                bulunan, terimler = ara(soru, k, bayrak)
                satir[f"{etiket}_P@{k}"] = round(len(altin & set(bulunan)) / k, 3)
            if bayrak:
                satir["eklenen"] = terimler
        rapor.append(satir)
        print(f"{ad:22s} altın={len(altin):4d} | kapalı P@5=%{100*satir['kapali_P@5']:3.0f} "
              f"P@10=%{100*satir['kapali_P@10']:3.0f} || açık P@5=%{100*satir['acik_P@5']:3.0f} "
              f"P@10=%{100*satir['acik_P@10']:3.0f} | {satir.get('eklenen') or ''}", flush=True)


def ort(alan):
    return round(sum(r[alan] for r in rapor) / len(rapor), 3)


ozet = {
    "sozluk_kapali": {"P@5": ort("kapali_P@5"), "P@10": ort("kapali_P@10")},
    "sozluk_acik": {"P@5": ort("acik_P@5"), "P@10": ort("acik_P@10")},
    "iyilesen": [r["mesele"] for r in rapor if r["acik_P@5"] > r["kapali_P@5"]],
    "kotulesen": [r["mesele"] for r in rapor if r["acik_P@5"] < r["kapali_P@5"]],
}
json.dump({"ozet": ozet, "meseleler": rapor},
          open("sozluk_ab_sonuc.json", "w"),
          ensure_ascii=False, indent=2)
print("\n" + json.dumps(ozet, ensure_ascii=False, indent=2))
