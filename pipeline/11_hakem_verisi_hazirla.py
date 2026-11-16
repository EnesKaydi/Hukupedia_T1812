"""Hakem değerlendirmesi için veri hazırlar — v1'deki iki ölçüm kusurunu giderir.

Kusur 1: hakemlere kararın ortasından kesilmiş 400 karakterlik parça gösteriliyordu;
         cümle ortasından başlayan, çoğu zaman usul bilgisi içeren bu kesit yüzünden
         isabetli kararlar "alakasız" etiketlenebiliyordu.
Kusur 2: her sonucu tek hakem değerlendiriyordu; hakemler arası "tam" oranı %44-%74
         arasında değişiyordu, yani ölçümün hata payı sistemin farkından büyüktü.

Bu betik her sonuç için (a) kararın konusunu içeren baş kısmını ve (b) sorguyla eşleşen
parçayı birlikte verir. Aynı veri 3 bağımsız hakeme gönderilir, çoğunluk oyu alınır ve
hakemler arası uyum ayrıca raporlanır.
"""
import os
import json

import psycopg

DB = os.environ["HUKUPEDIA_DSN"]
GIRDI = "test_v2_sonuclari.json"
CIKTI = "hakem_verisi_v3.json"
BAS_UZUNLUK = 1200      # kararın konusunu anlatan baş kısmı
PARCA_UZUNLUK = 1200    # sorguyla eşleşen parça


def temizle(s):
    return " ".join((s or "").split())


d = json.load(open(GIRDI))
cikti = []
with psycopg.connect(DB) as conn:
    for si, q in enumerate(d["sorgular"]):
        if not q["beklenen_konu"]:      # tuzak sorgular ayrı değerlendirilir
            continue
        kayitlar = []
        for ri, s in enumerate(q["sonuclar"]):
            r = conn.execute("SELECT metin FROM belgeler WHERE esas_no=%s LIMIT 1",
                             (s["esas_no"],)).fetchone()
            tam_metin = temizle(r[0]) if r else ""
            kayitlar.append({
                "sonuc_idx": ri,
                "daire": s["daire"],
                "esas_no": s["esas_no"],
                "kararin_basi": tam_metin[:BAS_UZUNLUK],
                "eslesen_parca": temizle(s["ozet"])[:PARCA_UZUNLUK],
            })
        cikti.append({"soru_idx": si, "soru": q["soru"], "sonuclar": kayitlar})

json.dump(cikti, open(CIKTI, "w"), ensure_ascii=False, indent=1)
print(f"→ {len(cikti)} sorgu × 5 sonuç, tam bağlamla {CIKTI} dosyasına yazıldı")
print(f"   (karar başı {BAS_UZUNLUK} kr + eşleşen parça {PARCA_UZUNLUK} kr)")
