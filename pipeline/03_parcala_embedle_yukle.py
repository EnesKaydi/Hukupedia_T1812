"""
Faz 1 çekirdeği: 50k test grubunu parçala → bge-m3 ile embedle (Apple GPU) → pgvector'e yükle.
Kesintiye dayanıklı: DB'de olan belgeler atlanır, istediğin zaman durdur/yeniden başlat.
Sonda HNSW indeksi kurulur.
"""
import os
import sys
import time
import pyarrow.parquet as pq
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

PARQUET = sys.argv[1] if len(sys.argv) > 1 else \
    os.environ.get("HUKUPEDIA_VERI", "../data") + "/analiz/testgrubu_50k.parquet"
DB = os.environ["HUKUPEDIA_DSN"]
CHUNK, OVERLAP = 1500, 200          # karakter cinsinden
GRUP = 64                            # kaç belge birlikte işlenir (embed+commit)
BATCH = 32                           # GPU batch

def parcala(metin: str) -> list[str]:
    """Paragraf sınırlarına saygılı kayan pencere."""
    paragraflar = [p.strip() for p in metin.split("\n") if p.strip()]
    parcalar, aktif = [], ""
    for p in paragraflar:
        if len(aktif) + len(p) + 1 <= CHUNK:
            aktif = f"{aktif}\n{p}".strip()
        else:
            if aktif: parcalar.append(aktif)
            aktif = (aktif[-OVERLAP:] + "\n" + p).strip() if aktif else p
            while len(aktif) > CHUNK:            # tek paragraf devasa ise böl
                parcalar.append(aktif[:CHUNK])
                aktif = aktif[CHUNK-OVERLAP:]
    if aktif: parcalar.append(aktif)
    return parcalar

print("model yükleniyor (ilk seferde ~2.3GB iner)...", flush=True)
model = SentenceTransformer("BAAI/bge-m3", device="mps")
model.max_seq_length = 512
model.half()                         # fp16: MPS'te ~2x hız, bellek yarıya
print("model hazır (bge-m3, MPS, fp16)", flush=True)

df = pq.read_table(PARQUET).to_pylist()
with psycopg.connect(DB, autocommit=False) as conn:
    register_vector(conn)
    cur = conn.cursor()
    cur.execute("SELECT belge_id FROM belgeler")
    varolan = {r[0] for r in cur.fetchall()}
    bekleyen = [r for r in df if r["belge_id"] not in varolan]
    print(f"toplam {len(df):,} | DB'de {len(varolan):,} | işlenecek {len(bekleyen):,}", flush=True)

    t0, islenen, parca_toplam = time.time(), 0, 0
    for i in range(0, len(bekleyen), GRUP):
        grup = bekleyen[i:i+GRUP]
        # 1) parçala
        is_listesi = []               # (belge, [parça metinleri])
        for b in grup:
            baslik = f"[{b['daire']} | {b['esas_no']} E. {b['karar_no']} K. | {b['tarih']}]"
            pl = [f"{baslik}\n{p}" for p in parcala(b["metin"])]
            is_listesi.append((b, pl))
        duz = [p for _, pl in is_listesi for p in pl]
        # 2) embedle (GPU)
        vekler = model.encode(duz, batch_size=BATCH, normalize_embeddings=True,
                              show_progress_bar=False)
        # 3) tek transaction'da yaz
        k = 0
        for b, pl in is_listesi:
            cur.execute(
                "INSERT INTO belgeler (belge_id,kaynak,daire,konu_grubu,esas_no,karar_no,tarih,metin) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (b["belge_id"], b["kaynak"], b["daire"], b["konu_grubu"],
                 b["esas_no"], b["karar_no"], b["tarih"], b["metin"]))
            bid = cur.fetchone()[0]
            cur.executemany(
                "INSERT INTO parcalar (belge_id,sira,metin,embedding) VALUES (%s,%s,%s,%s)",
                [(bid, s, pl[s], vekler[k+s]) for s in range(len(pl))])
            k += len(pl)
        conn.commit()
        islenen += len(grup); parca_toplam += len(duz)
        hiz = islenen / (time.time() - t0)
        kalan_dk = (len(bekleyen) - islenen) / hiz / 60 if hiz > 0 else 0
        print(f"{islenen:,}/{len(bekleyen):,} belge | {parca_toplam:,} parça | "
              f"{hiz:.1f} belge/sn | kalan ~{kalan_dk:.0f} dk", flush=True)

    print("HNSW indeksi kuruluyor (birkaç dakika)...", flush=True)
    cur.execute("SET maintenance_work_mem = '512MB'")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_parcalar_hnsw ON parcalar "
                "USING hnsw (embedding vector_cosine_ops)")
    cur.execute("ANALYZE parcalar; ANALYZE belgeler;")
    conn.commit()
    cur.execute("SELECT count(*) FROM belgeler"); nb = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM parcalar"); np_ = cur.fetchone()[0]
    print(f"🏁 TAMAM: {nb:,} belge, {np_:,} parça indekslendi.", flush=True)
