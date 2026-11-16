"""
Arama kalitesi ölçümü — 290 altın QA (mtntasci/turkish-legal-rag) ile.
Her soru için mevzuat indeksinde arama yapar; doğru kanun+madde ilk K sonuçta
mı diye bakar. Çıktı: Recall@1/5/10, MRR ve kanun bazlı kırılım → kalite_raporu.md
Bu sayılar TÜBİTAK raporundaki "RAG ve Semantik Arama Başarı Kriteri"nin kanıtıdır.
ÖN KOŞUL: 04_mevzuat_indeksle.py tamamlanmış olmalı.
"""
import os
import re
import pandas as pd
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

QA = os.environ.get("HUKUPEDIA_VERI", "../data") + "/ham_arsiv/turkish-legal-rag/qa_benchmark_gold.csv"
DB = os.environ["HUKUPEDIA_DSN"]
K = 10

def maddeler(s):
    """'3-' / '8-|9-' → {'3'} / {'8','9'}"""
    return {m for m in re.findall(r"\d+", str(s or ""))}

qa = pd.read_csv(QA)
if "is_active" in qa.columns:
    qa = qa[qa["is_active"].astype(str).str.lower().isin(["true", "1"])]
qa = qa.dropna(subset=["soru", "kaynak"]).to_dict("records")
print(f"{len(qa)} altın soru ile ölçülüyor", flush=True)

model = SentenceTransformer("BAAI/bge-m3", device="mps")
model.max_seq_length = 512
model.half()
vekler = model.encode([r["soru"] for r in qa], batch_size=32,
                      normalize_embeddings=True, show_progress_bar=True)

hit_at, rr_toplam = {1: 0, 5: 0, 10: 0}, 0.0
kanun_kirilim = {}
with psycopg.connect(DB) as conn:
    register_vector(conn)
    for r, v in zip(qa, vekler):
        satirlar = conn.execute(
            "SELECT b.daire, b.karar_no FROM parcalar p JOIN belgeler b ON b.id=p.belge_id "
            "WHERE b.kaynak='mevzuat' ORDER BY p.embedding <=> %s LIMIT %s",
            (v, K)).fetchall()
        dogru_kanun = str(r["kaynak"]).strip().lower()
        dogru_madde = maddeler(r.get("madde_nolari_context") or r.get("madde_no"))
        sira = None
        for j, (kanun, madde) in enumerate(satirlar, 1):
            if str(kanun).strip().lower() == dogru_kanun and (maddeler(madde) & dogru_madde):
                sira = j
                break
        kk = kanun_kirilim.setdefault(r["kaynak"], {"n": 0, "hit10": 0})
        kk["n"] += 1
        if sira:
            rr_toplam += 1 / sira
            kk["hit10"] += 1
            for k in hit_at:
                if sira <= k:
                    hit_at[k] += 1

n = len(qa)
rapor = [
    "# Hukupedia Arama Kalitesi Raporu (bge-m3, mevzuat indeksi)",
    f"Soru sayısı: {n}",
    f"- **Recall@1:  {hit_at[1]/n:.1%}**",
    f"- **Recall@5:  {hit_at[5]/n:.1%}**",
    f"- **Recall@10: {hit_at[10]/n:.1%}**",
    f"- **MRR@10:    {rr_toplam/n:.3f}**",
    "", "## Kanun bazlı kırılım (Recall@10)",
]
for kanun, kk in sorted(kanun_kirilim.items(), key=lambda x: -x[1]["n"]):
    rapor.append(f"- {kanun}: {kk['hit10']}/{kk['n']} ({kk['hit10']/kk['n']:.0%})")
metin = "\n".join(rapor)
print("\n" + metin)
open("kalite_raporu.md", "w").write(metin + "\n")
print("\n→ kalite_raporu.md yazıldı", flush=True)
