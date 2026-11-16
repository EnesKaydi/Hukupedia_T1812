"""Aday havuzu taraması: reranker'a kaç aday verilirse kalite/hız dengesi en iyi olur?

Gecikme dökümü toplam sürenin %75-88'inin yeniden sıralayıcıda geçtiğini gösterdi; süre
doğrudan aday sayısıyla orantılı. Füzyon ağırlıklandırmasından sonra adaylar iyileştiği
için havuzun küçültülmesi kaliteyi düşürmeyebilir. Bu betik her havuz boyutu için altın
standart P@5 ile ortalama süreyi birlikte ölçer.
"""
import os
import json, urllib.request

import psycopg

DB = os.environ["HUKUPEDIA_DSN"]
API = "http://127.0.0.1:8000/ara"
K = 5
HAVUZLAR = (10, 20, 30, 40)

MESELELER = [
    ("işe yeni alınan personelin ilk aylarda çıkarılması", "deneme süresi", "İş K. m.15"),
    ("emekli olan çalışanın tazminat hakkı", "yaşlılık aylığ\\w*.{0,80}kıdem tazminat", "emeklilik-kıdem"),
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


def ara(soru, havuz):
    v = json.dumps({"soru": soru, "mod": "hibrit", "limit": K, "aday_havuz": havuz}).encode()
    r = urllib.request.Request(API, data=v, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=180) as resp:
        d = json.loads(resp.read())
    return [s["belge_id"] for s in d["sonuclar"]], d["sure"]["toplam"], d["sure"].get("rerank", 0)


altin_kumeler = {}
with psycopg.connect(DB) as conn:
    for soru, regex, ad in MESELELER:
        altin_kumeler[ad] = {r[0] for r in conn.execute(
            "SELECT DISTINCT b.belge_id FROM parcalar p JOIN belgeler b ON b.id=p.belge_id "
            "WHERE p.metin ~* %s", (regex,)).fetchall()}

sonuc = {}
for havuz in HAVUZLAR:
    puanlar, sureler, rr_sureler = [], [], []
    for soru, regex, ad in MESELELER:
        bulunan, sn, rr = ara(soru, havuz)
        puanlar.append(len(altin_kumeler[ad] & set(bulunan)) / K)
        sureler.append(sn)
        rr_sureler.append(rr)
    sonuc[havuz] = {
        "P@5": round(sum(puanlar) / len(puanlar), 3),
        "ort_sn": round(sum(sureler) / len(sureler), 2),
        "rerank_sn": round(sum(rr_sureler) / len(rr_sureler), 2),
    }
    print(f"havuz={havuz:3d} → P@5=%{100*sonuc[havuz]['P@5']:.1f} | toplam {sonuc[havuz]['ort_sn']:.1f} sn "
          f"(rerank {sonuc[havuz]['rerank_sn']:.1f} sn)", flush=True)

json.dump(sonuc, open("havuz_taramasi_sonuc.json", "w"),
          ensure_ascii=False, indent=2)
print("\n→ havuz_taramasi_sonuc.json")
