"""Nesnel geri-getirme testi (Recall@k) — LLM hakem YOK, insan yorumu YOK.

Yöntem: her hukuki mesele için ayırt edici terimi veritabanında SQL ile ararız;
bulunan belgeler o sorunun "altın standart" cevap kümesidir (kesin doğru, tartışmasız).
Sonra sistemi, o terimi İÇERMEYEN doğal dilde bir sorguyla sorgular ve altın kümedeki
belgelerin ilk k sonuçta kaçının çıktığını sayarız.

Bu ölçüm iki soruyu ayırır:
  - altın küme boş  → korpus kapsamı sorunu (veri yok)
  - altın küme dolu ama recall düşük → geri getirme sorunu (veri var, sistem bulamıyor)
"""
import os
import json, urllib.request
import psycopg

DB = os.environ["HUKUPEDIA_DSN"]
API = "http://127.0.0.1:8000/ara"

# (doğal dil sorgusu, altın standardı belirleyen regex, açıklama)
# Sorgu, regex terimini birebir içermemeli — anlamsal aramayı sınamak için.
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

K_LISTESI = (5, 10, 20)


def altin_kume(conn, regex):
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT b.belge_id FROM parcalar p JOIN belgeler b ON b.id=p.belge_id "
        "WHERE p.metin ~* %s", (regex,)).fetchall()}


def ara(soru, limit):
    v = json.dumps({"soru": soru, "mod": "hibrit", "limit": limit}).encode()
    r = urllib.request.Request(API, data=v, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=180) as resp:
        return [s["belge_id"] for s in json.loads(resp.read())["sonuclar"]]


rapor = []
with psycopg.connect(DB) as conn:
    for soru, regex, aciklama in MESELELER:
        altin = altin_kume(conn, regex)
        bulunan = ara(soru, max(K_LISTESI))
        satir = {"soru": soru, "mesele": aciklama, "altin_kume_buyuklugu": len(altin)}
        for k in K_LISTESI:
            isabet = len(altin & set(bulunan[:k]))
            satir[f"isabet@{k}"] = isabet
            satir[f"precision@{k}"] = round(isabet / k, 3)
            satir[f"recall@{k}"] = round(isabet / len(altin), 4) if altin else None
        rapor.append(satir)
        print(f"{aciklama:22s} altın={len(altin):4d} | ilk5={satir['isabet@5']} "
              f"ilk10={satir['isabet@10']} ilk20={satir['isabet@20']} | P@5=%{100*satir['precision@5']:.0f}",
              flush=True)

kapsam_var = [r for r in rapor if r["altin_kume_buyuklugu"] > 0]
ozet = {
    "mesele_sayisi": len(rapor),
    "korpusta_karsiligi_olan": len(kapsam_var),
    "ort_precision@5": round(sum(r["precision@5"] for r in kapsam_var) / len(kapsam_var), 3),
    "ort_precision@10": round(sum(r["precision@10"] for r in kapsam_var) / len(kapsam_var), 3),
    "hic_bulamadigi_mesele": [r["mesele"] for r in kapsam_var if r["isabet@20"] == 0],
}
json.dump({"ozet": ozet, "meseleler": rapor},
          open("altin_standart_sonuc.json", "w"),
          ensure_ascii=False, indent=2)
print("\n" + json.dumps(ozet, ensure_ascii=False, indent=2))
