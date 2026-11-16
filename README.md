# Hukupedia — Semantic Case-Law Search for Turkish Courts

**Hukupedia** is a Turkish legal-search prototype: lawyers ask in natural language and get the most
relevant **Yargıtay (Court of Cassation)** decisions back. It was built as the first phase of an
AI-assisted legal-office automation product prepared for a **TÜBİTAK 1812 BiGG** application
(finalist at stages 1 and 2).

**How it works**

- **Hybrid retrieval:** vector search (`bge-m3` embeddings, pgvector HNSW) + Turkish full-text search
  + phrase search, fused with weighted **Reciprocal Rank Fusion**
- **Cross-encoder reranking** (`bge-reranker-v2-m3`) of the candidate pool
- **Query expansion:** a 121-rule colloquial → legal-term layer ("who keeps the child" → *velayet*)
- **Evaluation-first engineering:** an *objective* gold-standard test (ground truth derived by SQL,
  no LLM/human judgement), A/B tests for every component, 3-judge LLM majority vote with agreement
  reporting, and an honest list of known limits

**Result (12 legal issues, objective P@5):** 58.3 % → **86.7 %** after phrase search, targeted data
and the dictionary layer; 8 of 12 issues improved, none regressed. Full method and caveats:
[pipeline/kalite_raporu_v2.md](pipeline/kalite_raporu_v2.md) (Turkish).

**Stack:** Python · FastAPI · PostgreSQL 16 + pgvector · sentence-transformers / PyTorch · Docker

> The decision corpus is **not** included in this repository (see *Veri* below); the code,
> schema, evaluation scripts and result summaries are.

---

## Türkçe özet

Avukat doğal dille soru soruyor (örn. *"işe iade davasında işverenin geçerli fesih sebebi"*),
sistem üç farklı yöntemle arama yapıp sonuçları birleştiriyor:

1. **Anlam araması (vektör)** — kelime birebir geçmese de anlamca yakın kararları bulur (bge-m3 gömme modeli)
2. **Kelime araması** — klasik Türkçe tam metin araması
3. **Öbek araması** — hukuki kalıpları ("kıdem tazminatı" gibi çok kelimeli terimler) bütün olarak arar

Sonuçlar [Reciprocal Rank Fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) ile
birleştirilir, sonra bir **yeniden sıralayıcı** (cross-encoder) her adayı sorguyla birlikte okuyup
gerçek alakaya göre son sıralamayı yapar. Ayrıca aramadan önce sorgu bir **günlük dil → hukuki
terim sözlüğünden** geçer: "çocuğun kimin yanında kalacağı" gibi bir soru otomatik olarak "velayet"
terimiyle zenginleştirilir.

## Klasör yapısı

```
db/                  PostgreSQL şeması (pgvector uzantılı)
pipeline/            Veri işleme: parçalama, embedding, kalite ölçüm betikleri (pipeline/README.md)
api/                 FastAPI arama servisi (main.py) + günlük dil sözlüğü (sozluk.py)
ui/                  Basit arama arayüzü (index.html)
docker-compose.yml   Veritabanı konteyneri
```

## Nasıl çalıştırılır

```bash
# 0) Ortam değişkenleri
cp .env.example .env          # şifreyi değiştir
set -a; source .env; set +a

# 1) Veritabanını ayağa kaldır
docker compose up -d

# 2) API'yi başlat (aynı zamanda ui/index.html'i http://localhost:8000 üzerinden servis eder)
cd pipeline && uv run --no-sync uvicorn main:app --app-dir ../api --port 8000
```

## Veri

Yargıtay karar korpusu bu depoda **yoktur**. Veritabanı boşsa önce kendi veri setinizi
`HUKUPEDIA_VERI` (varsayılan `../data`) altına koyup `pipeline/03_parcala_embedle_yukle.py` ile
yüklemek gerekir — bkz. [pipeline/README.md](pipeline/README.md). Mevzuat tarafındaki 290 soruluk
altın QA, herkese açık [turkish-legal-rag](https://huggingface.co/datasets/mtntasci/turkish-legal-rag)
veri setinden gelir.

**Önemli:** İki yapay zekâ modeli (gömme + yeniden sıralayıcı) aynı anda RAM'de yükleniyor.
16 GB'lık makinelerde başka ağır uygulama açıkken sistem takas alanına düşebiliyor — sorgu süresi
12 saniyeden 60 saniyeye çıkabilir.

## Güncel durum (09.08.2026, yazarın dizüstü bilgisayarında ölçüldü)

| | |
|---|---|
| **Korpus** | 11.774 Yargıtay kararı — İş Hukuku (4.737), Aile (4.037), SGK/İş Kazası (3.000) |
| **Nesnel isabet (P@5)** | **%86,7** — bkz. [pipeline/kalite_raporu_v2.md](pipeline/kalite_raporu_v2.md) |
| **Avukata faydalı oran** | %89 (3 bağımsız hakem, çoğunluk oyu) |
| **Sorgu süresi** | ~6-7 sn (temiz makinede, 20 aday havuzuyla, Apple M1 16 GB) |

Bu üç alan, Türkiye'deki dava hacminin en yüksek dilimleri oldukları için bilinçli seçildi.

### Bugüne kadarki yolculuk

1. **Faz 1 çekirdeği** — pgvector + embedding pipeline + arama API/UI kuruldu
2. **İlk kalite ölçümü** — 26 sorgu, tek LLM hakem → "%96 konu isabeti" (bu rakam sonradan
   sorgulandı, bkz. madde 4)
3. **Hibrit arama + reranker eklendi** — vektör + kelime + cross-encoder yeniden sıralama
4. **Ölçüm yöntemi denetlendi ve düzeltildi** — tek hakem yerine 3 bağımsız hakem + çoğunluk oyu,
   kesik alıntı yerine tam bağlam, ve en önemlisi: **nesnel bir altın standart testi** eklendi
   (doğru cevaplar SQL ile kesin belirlenir, model/insan yorumu karışmaz). Bu test "veri az"
   sanılan bir zayıflığın aslında bir **arama motoru kusuru** olduğunu ortaya çıkardı: Türkçe kök
   bulucunun aşırı kırpması yüzünden bazı sorgular korpusun üçte birini eşleyip aranan kararı
   listenin dibine gömüyordu. **Öbek araması + ağırlıklı füzyon** ile düzeltildi.
5. **Hedefli veri ekleme + günlük dil sözlüğü** — zayıf çıkan meseleler için ham arşivden hedefli
   karar eklendi (rastgele büyütme değil), ve günlük dille sorulan sorular hukuki terime çeviren
   ~120 kurallık bir sözlük katmanı eklendi. **Nesnel isabet %58,3 → %86,7'ye çıktı, 12 meseleden
   8'i düzeldi, hiçbiri kötüleşmedi.**

Detaylı yöntem, ölçülen her sayının nasıl üretildiği ve bilinen sınırlar için:
**[pipeline/kalite_raporu_v2.md](pipeline/kalite_raporu_v2.md)**

## Bilinen sınırlar (dürüst liste)

- Sorgu gecikmesi (~6-13 sn, makine yüküne göre değişir) — yeniden sıralayıcı sürenin çoğunu yiyor
- Sözlük ~120 elle yazılmış kural içeriyor; kapsamadığı ifade kalıpları kaçabilir (Faz 2'de LLM
  ile otomatikleştirilecek)
- Çok nadir hukuki konularda (örn. iddet müddeti) korpusta yeterli örnek yok
- 16 GB RAM'de iki model aynı anda sınırda çalışıyor

## Sıradaki fazlar

- **Faz 2** — RAG tabanlı sohbet ve dilekçe taslağı (`/sohbet`, `/dilekce` uçları şu an iskelet),
  yerel LLM (Ollama/Qwen) ile sorgu zenginleştirme
- **Faz 3** — Türk hukuk diline ince ayarlı embedding modeli (GPU/TRUBA gerektirir)

## Lisans

[Boost Software License 1.0](LICENSE)
