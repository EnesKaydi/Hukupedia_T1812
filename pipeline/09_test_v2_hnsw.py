"""Kalite ölçümü v2: 95 sorgu (80 konu + 15 tuzak), Precision@5 ön-verisi + gecikme (saniye).
Çıktı: test_v2_hnsw_sonuclari.json → LLM hakem değerlendirmesine girer."""
import os
import json, time, urllib.request

API = "http://127.0.0.1:8000/ara"

IS_HUKUKU = [
    "kıdem tazminatının hesaplanmasında giydirilmiş ücret",
    "işe iade davasında işverenin geçerli fesih sebebi",
    "fazla mesai ücretinin tanıkla ispatı",
    "işçinin haklı nedenle derhal fesih hakkı",
    "ihbar tazminatı ödenmemesi",
    "işyerinde mobbing nedeniyle manevi tazminat",
    "belirli süreli iş sözleşmesinin niteliği",
    "sendikal nedenle fesih ve sendikal tazminat",
    "yıllık izin ücreti alacağının ispatı",
    "ücret alacağında zamanaşımı süresi",
    "işverenin eşit davranma borcuna aykırılık",
    "asıl işveren alt işveren ilişkisinde muvazaa",
    "işçinin devamsızlığı nedeniyle fesih",
    "performans düşüklüğü nedeniyle iş akdinin feshi",
    "ikale sözleşmesinin geçerlilik şartları",
    "işçilik alacaklarında faiz başlangıcı",
    "hafta tatili çalışması ücreti",
    "ulusal bayram ve genel tatil ücreti alacağı",
    "iş sözleşmesinin ahlak ve iyi niyet kurallarına aykırılıktan feshi",
    "kötü niyet tazminatının koşulları",
    "işyeri devrinin iş sözleşmesine etkisi",
    "deneme süresi içinde fesih",
    "işçinin sadakat borcuna aykırı davranışı",
    "prim ve ikramiye alacağının ödenmemesi",
    "işe başlatmama tazminatının hesabı",
    "boşta geçen süre ücreti",
    "emeklilik nedeniyle kıdem tazminatı talebi",
    "askerlik nedeniyle iş sözleşmesinin feshi",
    "işçinin istifası halinde kıdem tazminatı",
    "geçersiz fesihte işe iade kararının sonuçları",
    "işveren vekilinin iş güvencesi kapsamı",
    "zorlayıcı nedenle iş sözleşmesinin askıya alınması",
    "işçiye ödenen avansın mahsubu",
    "gece çalışması ve fazla mesai sınırı",
    "tazminat hesabında tavan ücret uygulaması",
]
AILE = [
    "anlaşmalı boşanma protokolünün geçerliliği",
    "çocuğun velayetinin değiştirilmesi şartları",
    "yoksulluk nafakasının artırılması",
    "düğünde takılan ziynet eşyalarının iadesi",
    "edinilmiş mallara katılma alacağı hesabı",
    "boşanmada tam kusur belirlemesi",
    "tedbir nafakasına hükmedilmesi",
    "iştirak nafakasının belirlenmesi",
    "çocukla kişisel ilişki kurulması",
    "evlilik birliğinin temelinden sarsılması",
    "terk nedeniyle boşanma ihtar şartı",
    "boşanmada maddi tazminat talebi",
    "mal rejiminin tasfiyesinde katkı payı alacağı",
    "aile konutu şerhi ve eşin rızası",
    "nafaka yükümlülüğünün kaldırılması",
    "velayetin anneye verilmesi çocuğun üstün yararı",
    "boşanma davasında ekonomik şiddet",
    "eşlerin ortak hayatın yeniden kurulamaması",
    "yoksulluk nafakasında kusur değerlendirmesi",
    "çeyiz eşyalarının aynen iadesi talebi",
    "babalık davası ve nafaka",
    "boşanma sonrası kadının bekleme süresi",
    "fiili ayrılık nedeniyle boşanma",
    "ortak velayet talebi",
    "nafakanın uyarlanması ekonomik durum değişikliği",
    "akıl hastalığı nedeniyle boşanma",
    "haysiyetsiz hayat sürme nedeniyle boşanma",
    "evlilik birliğinden doğan yükümlülüklerin ihlali",
    "boşanma davasında tanık beyanlarının değerlendirilmesi",
    "ayrılık kararı verilmesinin koşulları",
]
SGK = [
    "iş kazası sonucu maddi ve manevi tazminat",
    "sürekli iş göremezlik derecesi tespiti",
    "destekten yoksun kalma tazminatı hesabı",
    "iş kazasında işverenin kusur oranı",
    "meslek hastalığının tespiti",
    "hizmet tespiti davasının koşulları",
    "sigortalılık başlangıç tarihinin tespiti",
    "iş kazasının Kuruma bildirilmemesi",
    "rücu davasında işverenin sorumluluğu",
    "iş göremezlik ödeneğinin hesaplanması",
    "iş kazasında kaçınılmazlık faktörü",
    "yaşlılık aylığı bağlanma koşulları",
    "prim borcunun işverenden tahsili",
    "iş kazasında müteselsil sorumluluk",
    "malullük aylığı tahsis şartları",
]
TUZAK = [
    "kira bedelinin tespiti ve tahliye davası",
    "ithalatta katma değer vergisi ziyaı cezası",
    "imar planına karşı iptal davası",
    "tüketicinin ayıplı mal iadesi hakkı",
    "kasten adam öldürme suçunda haksız tahrik",
    "marka hakkına tecavüz ve tazminat",
    "kamulaştırma bedelinin tespiti",
    "trafik kazasında değer kaybı tazminatı",
    "miras ortaklığının giderilmesi izale-i şuyu",
    "çek iptali ve istirdat davası",
    "anonim şirkette genel kurul kararının iptali",
    "eser sözleşmesinde ayıplı ifa",
    "ipoteğin fekki davası",
    "uyuşturucu madde ticareti etkin pişmanlık",
    "idari para cezasına itiraz süresi",
]

SORGULAR = ([(s, "IS_HUKUKU") for s in IS_HUKUKU] + [(s, "AILE") for s in AILE]
            + [(s, "SGK_ISKAZASI") for s in SGK] + [(s, None) for s in TUZAK])


def ara(soru, mod="hibrit", limit=5):
    veri = json.dumps({"soru": soru, "mod": mod, "limit": limit}).encode()
    req = urllib.request.Request(API, data=veri, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()), time.perf_counter() - t0


cikti, sureler = [], []
for i, (soru, beklenen) in enumerate(SORGULAR):
    d, sn = ara(soru)
    sonuclar = d["sonuclar"]
    if i > 0:
        sureler.append(sn)
    if beklenen:
        eslesen = sum(1 for s in sonuclar if s["konu_grubu"] == beklenen)
        oto = f"{eslesen}/{len(sonuclar)}"
    else:
        oto = "tuzak"
    cikti.append({
        "soru": soru, "beklenen_konu": beklenen, "oto_kontrol": oto, "sure_sn": round(sn, 3),
        "sonuclar": [{
            "daire": s["daire"], "konu": s["konu_grubu"], "esas_no": s["esas_no"],
            "eslesme": s.get("eslesme"), "skor": s.get("skor"),
            "ozet": (s["parca"] or "")[:400],
        } for s in sonuclar],
    })
    print(f"{i+1:3d}. {soru[:50]:50s} | {oto:6s} | {sn:.2f} sn", flush=True)

sureler.sort()
n = len(sureler)
ozet = {
    "sorgu_sayisi": len(SORGULAR),
    "ilk_sorgu_isinma_sn": cikti[0]["sure_sn"],
    "ort_sn": round(sum(sureler) / n, 3),
    "p50_sn": round(sureler[n // 2], 3),
    "p95_sn": round(sureler[int(n * 0.95)], 3),
    "max_sn": round(sureler[-1], 3),
}
json.dump({"ozet": ozet, "sorgular": cikti},
          open("test_v2_hnsw_sonuclari.json", "w"),
          ensure_ascii=False, indent=2)
print(f"\nGecikme: ort {ozet['ort_sn']} sn | p50 {ozet['p50_sn']} | p95 {ozet['p95_sn']} | max {ozet['max_sn']}")
print(f"→ test_v2_hnsw_sonuclari.json ({len(cikti)} sorgu)")
