"""
Hukupedia API — Faz 1: semantik emsal arama.
Çalıştırma:  cd pipeline && uv run uvicorn main:app --app-dir ../api --port 8000
UI:          http://localhost:8000  (ui/index.html buradan servis edilir)
"""
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
import torch
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pgvector.psycopg import register_vector
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder

from sozluk import genislet

DB = os.environ["HUKUPEDIA_DSN"]
UI_KLASORU = Path(__file__).resolve().parent.parent / "ui"
model = None       # embedding (bge-m3)
reranker = None    # cross-encoder (bge-reranker-v2-m3) — sıralama düzeltici


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, reranker
    cihaz = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer("BAAI/bge-m3", device=cihaz)
    model.max_seq_length = 512
    if cihaz == "mps":
        model.half()
    print(f"arama modeli hazır ({cihaz})", flush=True)
    try:
        reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", device=cihaz, max_length=512)
        print(f"reranker hazır ({cihaz})", flush=True)
    except Exception as e:
        reranker = None
        print(f"reranker yüklenemedi ({e}) — rerank'siz devam", flush=True)
    yield


app = FastAPI(title="Hukupedia API", version="0.1", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(  # önizleme paneli / farklı origin'lerden erişim için
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AramaIstek(BaseModel):
    soru: str
    kaynaklar: list[str] = []        # ör. ["yargitay","danistay"] — boş = hepsi
    konu_gruplari: list[str] = []    # ör. ["AILE"] — boş = hepsi
    limit: int = 10
    mod: str = "hibrit"              # hibrit | vektor | kelime
    rerank: bool = True             # cross-encoder ile yeniden sırala (hibrit/vektör)
    obek: bool = True               # öbek kolu (A/B ölçümü için kapatılabilir)
    aday_havuz: int = 0             # rerank aday sayısını elle ayarla (0 = varsayılan)
    sozluk: bool = True             # günlük dil → hukuki terim genişletmesi


@app.get("/saglik")
def saglik():
    with psycopg.connect(DB) as conn:
        nb = conn.execute("SELECT count(*) FROM belgeler").fetchone()[0]
        np_ = conn.execute("SELECT count(*) FROM parcalar").fetchone()[0]
        gruplar = dict(conn.execute(
            "SELECT konu_grubu, count(*) FROM belgeler GROUP BY 1 ORDER BY 2 DESC").fetchall())
        kaynaklar = dict(conn.execute(
            "SELECT kaynak, count(*) FROM belgeler GROUP BY 1").fetchall())
    return {"durum": "ok", "belge": nb, "parca": np_,
            "gruplar": gruplar, "kaynaklar": kaynaklar}


ZAYIF_ESIK = 0.55    # saf vektör modu: kosinüs <0.55 çoğunlukla alakasız
RERANK_ZAYIF = 0.40  # rerank modu: cross-encoder skoru <0.40 → ilgisiz olabilir
RRF_K = 60           # Reciprocal Rank Fusion sabiti (literatür standardı)
OBEK_YAYGINLIK_ORANI = 0.02  # parçaların %2'sinden fazlasında geçen öbek ayırt edici değil
OBEK_AZAMI = 4               # en nadir kaç öbek kullanılsın
RERANK_AZAMI = 60            # cross-encoder'a verilecek azami aday (M1'de ~60 çift ≈ 3 sn)
RRF_AGIRLIK = {"vektor": 1.0, "kelime": 0.5, "obek": 0.5}  # sözcük kolları toplamda anlam koluna eşit

# ortak filtre parçası (kaynak + konu grubu)
_FILTRE = ("(cardinality(%s::text[]) = 0 OR b.kaynak = ANY(%s::text[])) "
           "AND (cardinality(%s::text[]) = 0 OR b.konu_grubu = ANY(%s::text[]))")


def aday(istek):
    """Her arama kolunun çekeceği aday sayısı: istenen sonucun ~4 katı (füzyon payı),
    en az 40, en çok 400. limit büyüdükçe aday havuzu da büyür."""
    return max(40, min(400, istek.limit * 4))


def _vektor_ara(conn, vek, istek):
    """Anlamsal arama → [(belge_id, satır_sözlüğü, kosinüs_benzerliği), ...] sıralı."""
    sql = f"""
      SELECT b.belge_id,b.kaynak,b.daire,b.konu_grubu,b.esas_no,b.karar_no,b.tarih,p.metin,
             1 - (p.embedding <=> %s) AS skor
      FROM parcalar p JOIN belgeler b ON b.id=p.belge_id
      WHERE {_FILTRE}
      ORDER BY p.embedding <=> %s LIMIT %s"""
    return conn.execute(sql, (vek, istek.kaynaklar, istek.kaynaklar,
                              istek.konu_gruplari, istek.konu_gruplari, vek, aday(istek))).fetchall()


def _kelime_ara(conn, istek):
    """Türkçe tam-metin arama (OR mantığı) → ts_rank'e göre sıralı satırlar.
    plainto_tsquery 'a & b & c' üretir (hepsi şart); '&'→'|' ile 'a | b | c'
    yaparız: herhangi bir terim eşleşen parçalar gelir, ts_rank alaka sırasını verir."""
    # sorgudan güvenli OR-tsquery türet (kullanıcı metni doğrudan tsquery'ye girmez)
    q = conn.execute(
        "SELECT replace(plainto_tsquery('turkish',%s)::text,' & ',' | ')", (istek.soru,)).fetchone()[0]
    if not q:                                          # sorguda anlamlı terim yoksa
        return []
    sql = f"""
      SELECT b.belge_id,b.kaynak,b.daire,b.konu_grubu,b.esas_no,b.karar_no,b.tarih,p.metin,
             ts_rank(to_tsvector('turkish',p.metin), %s::tsquery) AS skor
      FROM parcalar p JOIN belgeler b ON b.id=p.belge_id
      WHERE to_tsvector('turkish',p.metin) @@ %s::tsquery AND {_FILTRE}
      ORDER BY skor DESC LIMIT %s"""
    return conn.execute(sql, (q, q, istek.kaynaklar, istek.kaynaklar,
                              istek.konu_gruplari, istek.konu_gruplari, aday(istek))).fetchall()


def _obek_ara(conn, istek):
    """Öbek kolu: sorgunun ardışık ikili öbeklerinden yaygın olanları eleyip kalanları arar.

    Gerekçe: Türkçe kök bulucu 'deneme süresi içinde' ifadesini 'dene|süres|iç' köklerine
    indiriyor ve OR araması korpusun üçte birini eşliyor; aranan kalıp listenin dibinde kalıyor.
    Hukuk dili çok kelimeli kalıplardan oluştuğu için ('kıdem tazminatı', 'iş göremezlik
    derecesi') öbeği bütün olarak aramak gerekiyor. Yaygınlık eşiği, tesadüfen bitişen
    dolgu ikililerini ('süresi içinde') eler."""
    kelimeler = [k for k in re.findall(r"\w+", istek.soru.lower(), re.UNICODE) if len(k) > 2]
    ikililer = [f"{a} {b}" for a, b in zip(kelimeler, kelimeler[1:])]
    if not ikililer:
        return []
    # her ikilinin korpusta kaç parçada geçtiğini say, yaygın olanları at
    sayim = conn.execute(
        "SELECT o, (SELECT count(*) FROM parcalar WHERE to_tsvector('turkish',metin) "
        "@@ phraseto_tsquery('turkish', o)) FROM unnest(%s::text[]) AS o", (ikililer,)).fetchall()
    tavan = max(50, int(_parca_sayisi(conn) * OBEK_YAYGINLIK_ORANI))
    secilen = [o for o, c in sorted(sayim, key=lambda x: x[1]) if 0 < c <= tavan][:OBEK_AZAMI]
    if not secilen:
        return []
    tq = " || ".join(["phraseto_tsquery('turkish', %s)"] * len(secilen))
    sql = f"""
      SELECT b.belge_id,b.kaynak,b.daire,b.konu_grubu,b.esas_no,b.karar_no,b.tarih,p.metin,
             ts_rank(to_tsvector('turkish',p.metin), ({tq})) AS skor
      FROM parcalar p JOIN belgeler b ON b.id=p.belge_id
      WHERE to_tsvector('turkish',p.metin) @@ ({tq}) AND {_FILTRE}
      ORDER BY skor DESC LIMIT %s"""
    return conn.execute(sql, (*secilen, *secilen, istek.kaynaklar, istek.kaynaklar,
                              istek.konu_gruplari, istek.konu_gruplari, aday(istek))).fetchall()


_parca_onbellek = {}


def _parca_sayisi(conn):
    if "n" not in _parca_onbellek:
        _parca_onbellek["n"] = conn.execute("SELECT count(*) FROM parcalar").fetchone()[0]
    return _parca_onbellek["n"]


def _satir_sozluk(r):
    a = ["belge_id","kaynak","daire","konu_grubu","esas_no","karar_no","tarih","parca"]
    d = dict(zip(a, r[:8]))
    d["skor"] = round(float(r[8]), 4)
    return d


@app.post("/ara")
def ara(istek: AramaIstek):
    sure, t0 = {}, time.perf_counter()

    def olc(ad):
        nonlocal t0
        sure[ad] = round(time.perf_counter() - t0, 3)
        t0 = time.perf_counter()

    orijinal_soru = istek.soru
    eklenen_terimler = []
    if istek.sozluk:
        istek.soru, eklenen_terimler = genislet(istek.soru)

    with psycopg.connect(DB) as conn:
        register_vector(conn)
        vek_satir = kel_satir = obek_satir = []
        olc("baglanti")
        if istek.mod in ("hibrit", "vektor"):
            vek = model.encode([istek.soru], normalize_embeddings=True)[0]
            olc("sorgu_embedding")
            vek_satir = _vektor_ara(conn, vek, istek)
            olc("vektor_arama")
        if istek.mod in ("hibrit", "kelime"):
            kel_satir = _kelime_ara(conn, istek)
            olc("kelime_arama")
            if istek.obek:
                obek_satir = _obek_ara(conn, istek)
                olc("obek_arama")

    # RRF: her listede belgenin en iyi sırasını al, ağırlık/(k+sıra) puanlarını topla.
    # Ağırlık gerekçesi: kelime ve öbek kolları ikisi de sözcük temelli olduğu için aynı
    # belgeleri bulup çifte oy kullanıyor ve anlam kolunu sıralamadan dışarı itiyorlardı.
    # Sözcük kollarına yarım ağırlık verilerek iki yaklaşım dengelenir.
    puan, veri, kaynak_liste = {}, {}, {}
    for etiket, satirlar in (("vektor", vek_satir), ("kelime", kel_satir), ("obek", obek_satir)):
        agirlik = RRF_AGIRLIK[etiket]
        gorulen = set()
        for sira, r in enumerate(satirlar, 1):
            bid = r[0]
            if bid not in gorulen:                    # belge başına ilk (en iyi) parça
                gorulen.add(bid)
                puan[bid] = puan.get(bid, 0.0) + agirlik / (RRF_K + sira)
                kaynak_liste.setdefault(bid, []).append(etiket)
                if bid not in veri:                   # kartta gösterilecek satır
                    veri[bid] = _satir_sozluk(r)

    # RRF sıralaması: rerank varsa daha geniş aday havuzu al (limit*4), yoksa direkt limit
    if istek.rerank and reranker and istek.mod != "kelime":
        havuz_n = istek.aday_havuz or min(istek.limit * 8, RERANK_AZAMI)
    else:
        havuz_n = istek.limit
    aday_bid = sorted(puan, key=lambda b: -puan[b])[:havuz_n]

    rerank_uygula = istek.rerank and reranker and istek.mod != "kelime" and len(aday_bid) > 1
    if rerank_uygula:
        # cross-encoder: (sorgu, aday_parça) çiftlerini gerçek alaka üzerinden puanla
        ciftler = [(istek.soru, veri[b]["parca"] or "") for b in aday_bid]
        olc("rrf_fuzyon")
        rr = reranker.predict(ciftler)
        olc("rerank")
        sirali = [b for _, b in sorted(zip(rr, aday_bid), key=lambda x: -x[0])][:istek.limit]
        rr_puan = dict(zip(aday_bid, (float(x) for x in rr)))
    else:
        sirali = aday_bid[:istek.limit]
        rr_puan = {}

    sonuclar = []
    for bid in sirali:
        d = veri[bid]
        d["rrf"] = round(puan[bid], 4)
        d["eslesme"] = kaynak_liste[bid]              # ["vektor","kelime"] = ikisinde de → en güçlü
        if bid in rr_puan:
            d["rerank_skor"] = round(rr_puan[bid], 3)
            d["zayif"] = rr_puan[bid] < RERANK_ZAYIF       # cross-encoder güveni düşük
        else:
            d["zayif"] = (istek.mod == "vektor" and d["skor"] < ZAYIF_ESIK)
        sonuclar.append(d)
    sure["toplam"] = round(sum(sure.values()), 3)
    return {"soru": orijinal_soru, "genisletilmis": istek.soru if eklenen_terimler else None,
            "eklenen_terimler": eklenen_terimler, "mod": istek.mod, "rerank": rerank_uygula,
            "sure": sure, "aday_sayisi": len(aday_bid), "sonuclar": sonuclar,
            "guclu": sum(1 for s in sonuclar if not s["zayif"]),
            "zayif": sum(1 for s in sonuclar if s["zayif"])}


@app.get("/belge/{belge_id}")
def belge(belge_id: str):
    with psycopg.connect(DB) as conn:
        r = conn.execute(
            "SELECT belge_id,kaynak,daire,konu_grubu,esas_no,karar_no,tarih,metin "
            "FROM belgeler WHERE belge_id=%s", (belge_id,)).fetchone()
    if not r:
        return {"hata": "belge bulunamadı"}
    alanlar = ["belge_id","kaynak","daire","konu_grubu","esas_no","karar_no","tarih","metin"]
    return dict(zip(alanlar, r))


# Faz 2'de doldurulacak uçlar (iskelet hazır dursun)
@app.post("/sohbet")
def sohbet():
    return {"durum": "faz-2", "mesaj": "RAG sohbet Faz 2'de eklenecek (Ollama/Qwen)"}

@app.post("/dilekce")
def dilekce():
    return {"durum": "faz-2", "mesaj": "Dilekçe taslağı Faz 2'de eklenecek"}


app.mount("/", StaticFiles(directory=str(UI_KLASORU), html=True), name="ui")
