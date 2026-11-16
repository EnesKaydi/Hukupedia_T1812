# Hukupedia Arama Kalitesi — Test & Düzeltme Raporu

**Tarih:** 20.07.2026 · **Korpus:** 10.016 Yargıtay kararı (İş Hukuku 4.500, Aile 4.000, SGK/İş Kazası 1.516), 54.699 parça · **Modeller:** bge-m3 (embedding) + bge-reranker-v2-m3 (reranker), ince ayarsız (off-the-shelf).

## Yöntem
26 gerçekçi sorgu (21 elimizdeki 3 konuda + 5 "tuzak" = elimizde olmayan konular). İki ölçüm:
1. **Otomatik konu eşleşmesi** — ilk 5 sonuç beklenen konu grubundan mı (kaba vekil ölçü).
2. **LLM hakem alaka** — 21 paralel uzman-hakem ajanı, her sonucu sorunun *hukuki meselesini* karşılıyor mu diye değerlendirdi (tam / kısmen / alakasız).

## Bulunan sorunlar ve düzeltmeler (test → teşhis → çözüm)

| # | Bulgu | Kök neden | Düzeltme | Etki |
|---|---|---|---|---|
| 1 | "anlaşmalı boşanma" sorgusu 0/5 doğru sonuç | HNSW `ef_search=40` yaklaşık arama gerçek en yakın komşuları ıskalıyor | `ALTER DATABASE ... hnsw.ef_search=200` | 0/5 → 2/5 |
| 2 | Vektör skorları 0.63'e sıkışık, konu ayrımı zayıf | bge-m3 Türkçe hukuk metninde düşük kontrastlı | Cross-encoder **reranker** eklendi (aday havuzunu gerçek alaka ile yeniden sırala) | Konu isabeti %89 → **%96** |
| 3 | Elimizde olmayan konularda yüksek güvenle yanlış sonuç | Rerank skoru güven sinyali olarak kullanılmıyordu | rerank_skor < 0.40 → "zayıf eşleşme" işareti | Tuzakların 4/5'i dürüstçe "zayıf" |

## Nihai sonuçlar (LLM hakem, 21 sorgu × 5 = 105 sonuç)

- **Tam alakalı: %75** (79/105) — karar sorunun meselesini doğrudan karşılıyor
- **Avukata faydalı (tam + kısmen): %97** (102/105) — aynı hukuk alanında, işe yarar
- **Alakasız: %3** (3/105) — tamamı tek bir sorguda ("aldatma manevi tazminat")

Otomatik konu eşleşmesi: **%96** (101/105, reranker açık).

## Kalan zayıf noktalar (dürüst tespit)

1. **Konular-arası ortak kavramlar** — "manevi tazminat" hem aile hem SGK'da geçtiği için "eşin aldatması nedeniyle manevi tazminat" sorgusunda 3/5 sonuç iş kazası kararı çıktı (reranker bile ayıramadı). En ciddi tek hata. **Çözüm yolu:** (a) tam veri kapsamı — konu çeşitliliği arttıkça reranker daha iyi aday görür; (b) Türk hukukuna ince ayarlı reranker/embedding (Faz 3).
2. **İnce hukuki ayrım** — "işçinin haklı feshi (İş K. m.24)" ile "işverenin haklı feshi (m.25)" ayrımı yapılamıyor; hepsi "fesih" olarak geliyor (0 tam, 5 kısmen). Alt-mesele ayrımı domain fine-tune gerektirir.
3. **"kira" tuzağı** — reranker bir aile kararına 0.862 verdi (yanlış güven); KIRA_ALACAK grubu indekslenince gerçek eşleşme oluşup düzelmesi beklenir.

## Sonuç
İnce ayarsız açık modellerle, 10k kararlık örneklemde **%97 faydalı sonuç oranı** fizibiliteyi kanıtlıyor: mimari (hibrit arama + RRF + reranker + güven eşiği) çalışıyor. Kalan hatalar ya veri kapsamıyla ya da alan-özel fine-tune (Faz 3) ile kapanacak sınıfta — mimari değişikliği gerektirmiyor.

*Tekrarlanabilirlik: `06_test_sorgulari.py` (sorguları çalıştır), `07_rerank_karsilastir.py` (rerank a/b), workflow `arama-alaka-hakem` (LLM hakem). Test sorguları ve sonuçları `test_sonuclari.json`.*
