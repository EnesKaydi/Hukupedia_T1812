"""Arama kalite testi: gerçekçi sorguları API'den geçir, sonuçları JSON'a yaz.
Sonraki adım (workflow) bu JSON'u LLM hakemlere değerlendirtir."""
import os
import json, urllib.request

API = "http://127.0.0.1:8000/ara"

# (sorgu, beklenen_konu_grubu | None=tuzak/elimizde-yok)
SORGULAR = [
    # --- İŞ HUKUKU (elimizde 4500) ---
    ("kıdem tazminatının hesaplanmasında giydirilmiş ücret", "IS_HUKUKU"),
    ("işe iade davasında işverenin geçerli fesih sebebi", "IS_HUKUKU"),
    ("fazla mesai ücretinin tanıkla ispatı", "IS_HUKUKU"),
    ("işçinin haklı nedenle derhal fesih hakkı", "IS_HUKUKU"),
    ("ihbar tazminatı ödenmemesi", "IS_HUKUKU"),
    ("işyerinde mobbing nedeniyle manevi tazminat", "IS_HUKUKU"),
    ("belirli süreli iş sözleşmesinin niteliği", "IS_HUKUKU"),
    ("sendikal nedenle fesih ve sendikal tazminat", "IS_HUKUKU"),
    # --- AİLE (elimizde 4000) ---
    ("anlaşmalı boşanma protokolünün geçerliliği", "AILE"),
    ("çocuğun velayetinin değiştirilmesi şartları", "AILE"),
    ("yoksulluk nafakasının artırılması", "AILE"),
    ("düğünde takılan ziynet eşyalarının iadesi", "AILE"),
    ("edinilmiş mallara katılma alacağı hesabı", "AILE"),
    ("eşin aldatması nedeniyle manevi tazminat", "AILE"),
    ("boşanmada tam kusur belirlemesi", "AILE"),
    ("tedbir nafakasına hükmedilmesi", "AILE"),
    # --- SGK / İŞ KAZASI (elimizde 1516) ---
    ("iş kazası sonucu maddi ve manevi tazminat", "SGK_ISKAZASI"),
    ("sürekli iş göremezlik derecesi tespiti", "SGK_ISKAZASI"),
    ("destekten yoksun kalma tazminatı hesabı", "SGK_ISKAZASI"),
    ("iş kazasında işverenin kusur oranı", "SGK_ISKAZASI"),
    ("meslek hastalığının tespiti", "SGK_ISKAZASI"),
    # --- TUZAK: elimizde olmayan konular (sistem dürüst olmalı) ---
    ("kira bedelinin tespiti ve tahliye davası", None),
    ("ithalatta katma değer vergisi ziyaı cezası", None),
    ("imar planına karşı iptal davası", None),
    ("tüketicinin ayıplı mal iadesi hakkı", None),
    ("kasten adam öldürme suçunda haksız tahrik", None),
]


def ara(soru, mod="hibrit", limit=5):
    veri = json.dumps({"soru": soru, "mod": mod, "limit": limit}).encode()
    req = urllib.request.Request(API, data=veri, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


cikti = []
for soru, beklenen in SORGULAR:
    d = ara(soru)
    sonuclar = d["sonuclar"]
    # otomatik konu-eşleşme oranı (ilk 5'te beklenen konudan kaç tane)
    if beklenen:
        eslesen = sum(1 for s in sonuclar if s["konu_grubu"] == beklenen)
        oto = f"{eslesen}/{len(sonuclar)} beklenen konu ({beklenen})"
    else:
        oto = "tuzak — ideal: zayıf/boş"
    cikti.append({
        "soru": soru, "beklenen_konu": beklenen, "oto_kontrol": oto,
        "sonuclar": [{
            "daire": s["daire"], "konu": s["konu_grubu"], "esas_no": s["esas_no"],
            "eslesme": s.get("eslesme"), "skor": s.get("skor"),
            "ozet": (s["parca"] or "")[:400],
        } for s in sonuclar],
    })
    print(f"✓ {soru[:45]:45s} | {oto}", flush=True)

json.dump(cikti, open("test_sonuclari.json", "w"),
          ensure_ascii=False, indent=2)
print(f"\n→ {len(cikti)} sorgu test_sonuclari.json'a yazıldı")
