"""
Mevzuat maddelerini (25 temel kanun, mtntasci/turkish-legal-rag) indeksle.
Karar korpusunun yanına kaynak='mevzuat' olarak eklenir → arama "kanun maddesi
+ emsal karar" birlikte dönebilir; 05_kalite_olc.py bu indeks üzerinde ölçüm yapar.
NOT: 03 koşusu bitince çalıştır (GPU'yu paylaşmasınlar).
"""
import os
import time
import pandas as pd
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

CSV = os.environ.get("HUKUPEDIA_VERI", "../data") + "/ham_arsiv/turkish-legal-rag/statute_chunks.csv"
DB = os.environ["HUKUPEDIA_DSN"]
BATCH = 64

df = pd.read_csv(CSV)
df = df.dropna(subset=["context", "context_key"]).drop_duplicates(subset=["context_key"])
print(f"{len(df):,} mevzuat parçası indekslenecek", flush=True)

model = SentenceTransformer("BAAI/bge-m3", device="mps")
model.max_seq_length = 512
model.half()

with psycopg.connect(DB) as conn:
    register_vector(conn)
    cur = conn.cursor()
    cur.execute("SELECT belge_id FROM belgeler WHERE kaynak='mevzuat'")
    varolan = {r[0] for r in cur.fetchall()}
    bekleyen = df[~("mevzuat_" + df["context_key"]).isin(varolan)].to_dict("records")
    print(f"DB'de {len(varolan):,} var, işlenecek {len(bekleyen):,}", flush=True)

    t0 = time.time()
    for i in range(0, len(bekleyen), BATCH):
        grup = bekleyen[i:i+BATCH]
        metinler = [str(r.get("retrieval_text") or r["context"]) for r in grup]
        vekler = model.encode(metinler, batch_size=32, normalize_embeddings=True,
                              show_progress_bar=False)
        for r, v in zip(grup, vekler):
            cur.execute(
                "INSERT INTO belgeler (belge_id,kaynak,daire,konu_grubu,esas_no,karar_no,tarih,metin) "
                "VALUES (%s,'mevzuat',%s,'MEVZUAT',%s,%s,'',%s) RETURNING id",
                (f"mevzuat_{r['context_key']}", str(r["kaynak"]),
                 str(r.get("kanun_no") or ""), str(r.get("madde_no") or ""),
                 str(r["context"])))
            bid = cur.fetchone()[0]
            cur.execute("INSERT INTO parcalar (belge_id,sira,metin,embedding) VALUES (%s,0,%s,%s)",
                        (bid, str(r.get("retrieval_text") or r["context"]), v))
        conn.commit()
        hiz = (i + len(grup)) / (time.time() - t0)
        print(f"{i+len(grup):,}/{len(bekleyen):,} | {hiz:.0f} parça/sn", flush=True)
    print("🏁 mevzuat indekslendi", flush=True)
