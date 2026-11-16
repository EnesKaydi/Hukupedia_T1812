# pipeline/ — veri hattı ve kalite ölçüm betikleri

Tüm betikler **bu klasörden** çalıştırılır (`cd pipeline`) ve `HUKUPEDIA_DSN` ortam değişkenini
bekler (bkz. `../.env.example`). Karar korpusu depoda yoktur; `HUKUPEDIA_VERI` (varsayılan `../data`)
altına kendi veri setinizi koyarak `03_*` ile yükleyebilirsiniz.

```bash
set -a; source ../.env; set +a      # HUKUPEDIA_DSN ve POSTGRES_PASSWORD yüklenir
uv run --no-sync python 03_parcala_embedle_yukle.py
```

| Betik | Ne yapar |
|---|---|
| `03_parcala_embedle_yukle.py` | Kararları parçalar, bge-m3 ile gömer, pgvector'e yükler; kesintiye dayanıklı (kaldığı yerden devam), sonda HNSW indeksi kurar |
| `03b_pipeline_overlap.py` | Aynı işin producer-consumer sürümü: parçalama (CPU), gömme (GPU) ve DB yazımı (I/O) üst üste biner, GPU boş beklemez |
| `04_mevzuat_indeksle.py` | 25 temel kanunun maddelerini ([turkish-legal-rag](https://huggingface.co/datasets/mtntasci/turkish-legal-rag) veri setinden) indeksler |
| `05_kalite_olc.py` | 290 soruluk altın QA ile Recall@1/5/10 ve MRR ölçer → `kalite_raporu.md` |
| `06`–`09` | Gerçekçi sorgularla ilk kalite testleri, rerank açık/kapalı karşılaştırması, HNSW ayarı |
| `10_altin_standart_test.py` | **Nesnel** geri-getirme testi: doğru cevap kümesi SQL ile belirlenir, LLM/insan yorumu karışmaz |
| `11_hakem_verisi_hazirla.py` | 3 bağımsız LLM hakem için tam bağlamlı değerlendirme verisi hazırlar |
| `12_ab_testi.py` | Öbek (phrase) aramasının etkisini aynı koşullarda A/B ölçer |
| `13_rerank_bedeli.py` | Yeniden sıralayıcının kalite katkısı ile gecikme bedelini yan yana koyar |
| `14_havuz_taramasi.py` | Reranker'a kaç aday verilirse kalite/hız dengesinin en iyi olduğunu tarar |
| `15_sozluk_ab.py` | Günlük dil sözlüğü katmanının etkisini ayrıştırır |

Sonuç özetleri (`*_sonuc.json`, `kalite_raporu*.md`) depoda; Yargıtay karar metni içeren ham ara
çıktılar depoya dahil değildir ve betikler çalıştırılınca yerelde üretilir.
