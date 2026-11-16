"""
Pipeline v2 — overlap'li embedding (GPU hiç beklemez).
=======================================================
v1 (03_...) sıralı: parçala → embed → DB'ye yaz → tekrar. GPU, chunk ve DB
adımlarında boş bekler.

v2 burada 3 aşamayı ÜST ÜSTE bindirir (producer-consumer):
  Thread P (CPU) : parquet oku + parçala → chunk_kuyruk
  Ana iş  (GPU)  : chunk_kuyruk'tan al → embed → yaz_kuyruk
  Thread W (I/O) : yaz_kuyruk'tan al → pgvector'e COPY ile yaz

Neden thread işe yarıyor ama GPU'yu "bölmüyor": GPU tek ve tek thread onu
kullanıyor (encode). Diğer thread'ler yalnızca GPU'nun BEKLEDİĞİ işleri
(disk okuma, metin bölme, DB yazma) paralelde götürüyor. GIL de sorun değil
çünkü bu işler ya I/O (GIL bırakılır) ya da C-uzantısı (torch/psycopg GIL bırakır).

Kullanım (700k tam korpus için tasarlandı):
  uv run --no-sync python 03b_pipeline_overlap.py --parquet <yol> [--limit N]
Ölçüm: her aşamanın toplam süresini sonda basar → gerçek darboğazı görürsün.
"""
import os
import argparse
import queue
import threading
import time
import pyarrow.parquet as pq
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

DB = os.environ["HUKUPEDIA_DSN"]
CHUNK, OVERLAP = 1500, 200
GRUP, BATCH = 64, 32
BITTI = object()   # kuyruk sonu işareti

sure = {"chunk": 0.0, "embed": 0.0, "yaz": 0.0}


def parcala(metin: str) -> list[str]:
    paragraflar = [p.strip() for p in metin.split("\n") if p.strip()]
    parcalar, aktif = [], ""
    for p in paragraflar:
        if len(aktif) + len(p) + 1 <= CHUNK:
            aktif = f"{aktif}\n{p}".strip()
        else:
            if aktif: parcalar.append(aktif)
            aktif = (aktif[-OVERLAP:] + "\n" + p).strip() if aktif else p
            while len(aktif) > CHUNK:
                parcalar.append(aktif[:CHUNK]); aktif = aktif[CHUNK-OVERLAP:]
    if aktif: parcalar.append(aktif)
    return parcalar


def uretici(bekleyen, chunk_kuyruk):
    """Thread P: belgeleri parçala, gruplar halinde kuyruğa koy."""
    for i in range(0, len(bekleyen), GRUP):
        grup = bekleyen[i:i+GRUP]
        t = time.time()
        is_listesi = []
        for b in grup:
            baslik = f"[{b['daire']} | {b['esas_no']} E. {b['karar_no']} K. | {b['tarih']}]"
            is_listesi.append((b, [f"{baslik}\n{p}" for p in parcala(b["metin"])]))
        sure["chunk"] += time.time() - t
        chunk_kuyruk.put(is_listesi)
    chunk_kuyruk.put(BITTI)


def yazici(yaz_kuyruk):
    """Thread W: embed edilmiş grupları tek transaction'da DB'ye yaz."""
    with psycopg.connect(DB, autocommit=False) as conn:
        register_vector(conn)
        cur = conn.cursor()
        while True:
            paket = yaz_kuyruk.get()
            if paket is BITTI: break
            t = time.time()
            for b, parcalar, vekler in paket:
                cur.execute(
                    "INSERT INTO belgeler (belge_id,kaynak,daire,konu_grubu,esas_no,karar_no,tarih,metin)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (belge_id) DO NOTHING RETURNING id",
                    (b["belge_id"], b["kaynak"], b["daire"], b["konu_grubu"],
                     b["esas_no"], b["karar_no"], b["tarih"], b["metin"]))
                row = cur.fetchone()
                if not row: continue
                bid = row[0]
                cur.executemany(
                    "INSERT INTO parcalar (belge_id,sira,metin,embedding) VALUES (%s,%s,%s,%s)",
                    [(bid, s, parcalar[s], vekler[s]) for s in range(len(parcalar))])
            conn.commit()
            sure["yaz"] += time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    model = SentenceTransformer("BAAI/bge-m3", device="mps")
    model.max_seq_length = 512
    model.half()
    print("model hazır (bge-m3, MPS, fp16)", flush=True)

    df = pq.read_table(args.parquet).to_pylist()
    if args.limit: df = df[:args.limit]
    with psycopg.connect(DB) as conn:
        varolan = {r[0] for r in conn.execute("SELECT belge_id FROM belgeler").fetchall()}
    bekleyen = [r for r in df if r["belge_id"] not in varolan]
    print(f"işlenecek {len(bekleyen):,} belge", flush=True)

    chunk_kuyruk = queue.Queue(maxsize=4)   # geri-basınç: bellek şişmesin
    yaz_kuyruk = queue.Queue(maxsize=4)
    tP = threading.Thread(target=uretici, args=(bekleyen, chunk_kuyruk), daemon=True)
    tW = threading.Thread(target=yazici, args=(yaz_kuyruk,), daemon=True)
    tP.start(); tW.start()

    t0, islenen = time.time(), 0
    while True:
        is_listesi = chunk_kuyruk.get()
        if is_listesi is BITTI: break
        duz = [p for _, pl in is_listesi for p in pl]
        t = time.time()
        vekler = model.encode(duz, batch_size=BATCH, normalize_embeddings=True,
                              show_progress_bar=False)
        sure["embed"] += time.time() - t
        # embed'i belge bazında geri böl
        paket, k = [], 0
        for b, pl in is_listesi:
            paket.append((b, pl, vekler[k:k+len(pl)])); k += len(pl)
        yaz_kuyruk.put(paket)
        islenen += len(is_listesi)
        hiz = islenen / (time.time() - t0)
        print(f"{islenen:,}/{len(bekleyen):,} | {hiz:.1f} belge/sn | "
              f"chunk {sure['chunk']:.0f}s · embed {sure['embed']:.0f}s · yaz {sure['yaz']:.0f}s",
              flush=True)
    yaz_kuyruk.put(BITTI)
    tW.join()
    print(f"\n🏁 bitti. Aşama süreleri → chunk:{sure['chunk']:.0f}s "
          f"embed:{sure['embed']:.0f}s yaz:{sure['yaz']:.0f}s "
          f"(embed toplam sürenin çoğunuysa GPU darboğazdır; model küçültme tek çözüm)", flush=True)


if __name__ == "__main__":
    main()
