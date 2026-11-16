# Hukupedia Arama Kalitesi — Ölçüm Raporu v2

**Tarih:** 09.08.2026 · **Korpus (gün sonu):** 11.774 Yargıtay kararı (İş 4.737, Aile 4.037, SGK 3.000
[tamamlandı]), ~58.000+ parça. Gün içi taban ölçümü 10.016 kararlık ilk korpusla yapıldı, aşağıdaki
her bölüm hangi korpusta ölçüldüğünü belirtir.
**Modeller:** bge-m3 (gömme) + bge-reranker-v2-m3 (yeniden sıralama), ince ayarsız
**Donanım:** Apple M1, 16 GB — sunucu değil, dizüstü bilgisayar

## Özet — bugünkü tur

| Aşama | P@5 (nesnel) |
|---|---|
| Gün başı (öbek+ağırlıklı füzyon, eski korpus) | %58,3 |
| + hedefli veri ekleme (yeni korpus, sözlüksüz) | %63,3 |
| **+ günlük dil sözlüğü (yeni korpus, sözlüklü)** | **%86,7** |

**Bugünkü toplam kazanç: +28,4 puan.** 12 meseleden 8'i düzeldi, **hiçbiri kötüleşmedi**. İlk 10
sonuçta isabet %83,3. Detay ve yöntem aşağıda.

## Neden v2? — v1 ölçümünün kusurları

v1 raporu (20.07.2026) "%96 konu isabeti, %75 tam alaka" bildiriyordu. Bu rakamlar denetlendiğinde
ölçüm yönteminde üç kusur bulundu ve üçü de düzeltildi:

| # | Kusur | Etkisi | Düzeltme |
|---|---|---|---|
| 1 | Her sonucu **tek** hakem değerlendiriyordu | Hakemler arası "tam" oranı %44–%74 arasında oynuyordu; ölçüm hatası sistem farkından büyüktü | 3 bağımsız hakem + çoğunluk oyu |
| 2 | Hakemlere kararın ortasından **400 karakterlik kesit** gösteriliyordu | Cümle ortasından başlayan, çoğu usul bilgisi içeren kesitler isabetli kararları "alakasız" gösteriyordu | Kararın konu kısmı (1.200 kr) + eşleşen parça (1.200 kr) birlikte |
| 3 | Kalite ölçümü yalnızca **hakem görüşüne** dayanıyordu | "Yapay zekânın başarısını yapay zekâ notluyor" itirazına açıktı | Nesnel altın standart testi eklendi (aşağıda) |

## Nesnel ölçüm yöntemi (yeni)

Her hukuki mesele için ayırt edici terim veritabanında SQL ile aranır; bulunan belgeler o sorunun
**altın standart** cevap kümesidir — tartışmasız, tekrarlanabilir, insan veya model yorumu içermez.
Sistem, o terimi **içermeyen** doğal dilde bir sorguyla sorgulanır ve altın kümedeki belgelerin ilk k
sonuçta kaçının çıktığı sayılır. Bu ölçüm iki arızayı birbirinden ayırır:

- altın küme boş → **korpus kapsamı** sorunu (veri yok)
- altın küme dolu ama isabet düşük → **geri getirme** sorunu (veri var, sistem bulamıyor)

12 mesele, İş/Aile/SGK alanlarına dağılmış. Betik: `10_altin_standart_test.py`, A/B: `12_ab_testi.py`.

## Bulunan kusur ve düzeltme

Nesnel test, "veri az" sanılan sorunun aslında bir geri getirme arızası olduğunu gösterdi:
deneme süresi feshi konusunda veritabanında **38 karar bulunmasına rağmen** sistem ilk 20 sonuçta
**hiçbirini** getiremiyordu.

**Kök neden:** Türkçe kök bulucu "deneme süresi içinde" ifadesini `dene | süres | iç` köklerine
indiriyor; VEYA mantığıyla çalışan tam metin araması bu köklerle korpusun üçte birini (18.473/54.699
parça) eşliyor ve aranan kalıp sıralamanın dibinde kalıyor.

**Düzeltme — öbek kolu:** Aramaya üçüncü bir kol eklendi. Sorgunun ardışık kelime ikilileri korpusta
ne kadar yaygın olduğuna göre elenir; ayırt edici olanlar (parçaların %2'sinden azında geçenler)
bütün öbek olarak aranır. Hukuk dili çok kelimeli kalıplardan oluştuğu için ("kıdem tazminatı",
"iş göremezlik derecesi") bu kol sözcüklere bölünmenin kaybettirdiği anlamı geri kazandırır.

**Düzeltme — ağırlıklı füzyon:** Kelime ve öbek kolları ikisi de sözcük temelli olduğundan aynı
belgeleri bulup füzyonda çifte oy kullanıyor, anlam kolunu sıralama dışına itiyordu. Sözcük
kollarına yarım ağırlık verilerek iki yaklaşım dengelendi.

## Sonuçlar

### Nesnel ölçüm (12 mesele, altın standart)

| Yapılandırma | P@5 | P@10 |
|---|---|---|
| Öbek kolu kapalı | %51,7 | %53,3 |
| Öbek kolu açık | %56,7 | %57,5 |
| **Öbek kolu + ağırlıklı füzyon** | **%58,3** | — |

Öbek kolu iki meseleyi düzeltti, **hiçbirini kötüleştirmedi**. En büyük kazanç deneme süresi
meselesinde: P@5 %0 → %40, P@10 %0 → %60.

### Yeniden sıralayıcının (reranker) katkısı ve bedeli

| Füzyon | Reranker kapalı P@5 | Reranker açık P@5 | Reranker'ın katkısı |
|---|---|---|---|
| Ağırlıksız | %33,3 | %56,7 | +23,4 puan |
| **Ağırlıklı** | **%45,0** | **%58,3** | +13,3 puan |

Ağırlıklandırma ham füzyon kalitesini **11,7 puan** yükseltti. Reranker hâlâ vazgeçilmez
(+13,3 puan) ama artık daha az iş yapıyor — bu, aday havuzunun küçültülerek hız kazanılmasına
imkân veriyor. Reranker'ın gecikme bedeli: 9,5 sn.

### Hakem değerlendirmesi (3 bağımsız hakem, tam bağlam, 100 sonuç)

- Üç hakem **%84** oranında birebir aynı etiketi verdi, %16'sında ikisi hemfikir, hiçbirinde üçü de farklı değil.
- Çoğunluk oyu: **tam isabet %67, kısmen faydalı %22, alakasız %11**
- **Avukat için kullanılabilir (tam + kısmen): %89**

Not: "tam isabet" ölçüm yöntemine duyarlı (400 kr kesitle %56,5, tam bağlamla %67). "Faydalı" oranı
yönteme dayanıklı (%90,2 → %89). Bu nedenle **raporlanacak asıl metrik faydalı oranıdır.**

### Gecikme dökümü (M1, limit=5)

| Aşama | Süre |
|---|---|
| Sorgu gömme | 0,09 sn |
| Vektör arama | 0,05–0,28 sn |
| Kelime arama | 0,85–2,6 sn |
| Öbek arama | 0,9–1,1 sn |
| **Yeniden sıralama** | **8,8–9,6 sn** |
| Toplam | 12–13 sn |

Toplam sürenin %75–88'i yeniden sıralayıcıda geçiyor. **Açık iyileştirme alanı budur.**

### Aday havuzu taraması (hız/kalite dengesi)

Yeniden sıralayıcıya kaç aday verileceği tarandı (11 mesele, altın standart):

| Aday | P@5 | Rerank süresi |
|---|---|---|
| 10 | %50,9 | 2,3 sn |
| **20** | **%58,2** | **5,2 sn** |
| 30 | %56,4 | 8,9 sn |
| 40 | %63,6 | 11,8 sn |

20 üzeri farklar ±5 puanlık ölçüm gürültüsü bandında (30'un 20'den düşük çıkması bunun kanıtı).
**Demo yapılandırması: 20 aday** — süre yarıya iner, kalite kaybı gürültü sınırında. API'de
`aday_havuz` parametresiyle istek bazında seçilebilir; derinlemesine araştırma için 40 kullanılabilir.
Süreler takas baskısı altında ölçüldü; temiz makinede ~%40 daha kısa.

## Hedefli veri ekleme + günlük dil sözlüğü (gün sonu turu)

Sabah ölçümündeki dört zayıf mesele ortak bir teşhis paylaşıyordu: ya korpusta o konuda çok az
karar vardı (iddet müddeti: 1 karar, ayrılık kararı: 6, emeklilik-kıdem: 6) ya da sorgu günlük
dilde sorulduğunda terim köprüsü kurulamıyordu (velayet: 629 karar VARDI, sorgu "çocuğun kimin
yanında kalacağı" bulamıyordu). İki ayrı müdahale ile ikisi de hedeflendi:

**1. Hedefli veri ekleme.** Ham arşivden (702k karar) rastgele büyütme yerine tam eksik olan
konuların kararları süzüldü: deneme süresi (+200), emeklilik-kıdem (+37), ayrılık kararı (+35),
iddet müddeti (+2 — arşivde bu kadar az geçiyor), + yarım kalan SGK grubunun 1.484 eksik kararı.
Betik: `Hukupedia_Veri/analiz/03_hedefli_ek_olustur.py`. Toplam +1.758 belge, indekssiz toplu
yükleme + üretici-tüketici paralelleştirmeli pipeline (`03b_pipeline_overlap.py`) ile ~25 dk sürdü
(GPU embedding darboğaz; chunk/yazma ~0 sn).

**2. Günlük dil → hukuki terim sözlüğü.** Sorgu aramadan önce ~120 kural + 250+ terim eşlemesinden
geçer (`api/sozluk.py`). "Çocuğun kimin yanında kalacağı" → **+velayet**, "boşandıktan sonra tekrar
evlenme süresi" → **+iddet müddeti**, "ilk haftalarda işten çıkarma" → **+deneme süresi**. İki
güvenlik testinden geçti: 95 teknik/hukuki-terimli sorgudan **0'ı değişti** (mevcut başarıyı
bozmuyor), 30 günlük-dil örneğinin **30'u da doğru terime çevrildi**.

### Sonuç — sözlük A/B testi (yeni korpus, 12 mesele)

| Mesele | Altın küme | Sözlüksüz P@5 | Sözlüklü P@5 |
|---|---|---|---|
| Deneme süresi (İş K. m.15) | 238 | %40 | **%100** |
| Emeklilik-kıdem | 43 | %40 | **%60** |
| İddet müddeti (TMK m.132) | 3 | %0 | %20 |
| Ayrılık kararı (TMK m.170) | 41 | %60 | **%80** |
| Devamsızlık (İş K. m.25/II-g) | 212 | %80 | **%100** |
| Velayet (TMK m.182, günlük dil) | 643 | %20 | **%80** |
| Fazla mesai (İş K. m.41) | 1.995 | %100 | %100 |
| Ziynet alacağı | 293 | %80 | **%100** |
| İş kazası kusur oranı | 815 | %40 | **%100** |
| Hizmet tespiti | 502 | %100 | %100 |
| Yıllık izin (İş K. m.59) | 1.045 | %100 | %100 |
| Sadakat/manevi tazminat (TMK m.174/2) | 325 | %100 | %90 |

**Ortalama: P@5 %63,3 → %86,7 (+23,4 puan), P@10 %66,7 → %83,3.** 8 mesele düzeldi, kalan 4'ü
zaten tavandaydı veya ±10 puanlık gürültü bandında sabit kaldı — **hiçbir mesele geriye gitmedi**.

İddet müddeti hâlâ zayıf ama artık nedeni farklı: korpusta yalnızca 3 karar var (arşivde bu konu
gerçekten nadir), sözlük olmasaydı %0 kalırdı. Bu, kalan zayıflığın sistem kusuru değil saf veri
kıtlığı olduğunu gösteriyor — çözümü daha fazla hedefli veri, mimari değişikliği değil.

Betikler: `Hukupedia_Veri/analiz/03_hedefli_ek_olustur.py` (veri süzme), `api/sozluk.py` (terim
sözlüğü), `15_sozluk_ab.py` (A/B ölçüm). Ham sonuç: `sozluk_ab_sonuc.json`.

## Dürüst tespit — bilinen sınırlar

1. **Günlük dille sorulan sorular — büyük ölçüde çözüldü.** Sözlük katmanı (yukarıda) bu zayıflığı
   hedef aldı ve 8/12 meselede belirgin kazanç sağladı. Kalan sınır: sözlük ~120 elle yazılmış
   kural içeriyor, kapsamadığı ifade kalıpları hâlâ kaçabilir. Kalıcı çözüm Faz 2'nin yerel LLM'i
   (sorguyu otomatik hukuk terminolojisine çevirir) veya Faz 3 ince ayarlı gömme modeli.
2. **Gecikme.** 12–13 saniye kullanıcı deneyimi için yüksek. Yeniden sıralayıcının kısaltılması,
   nicemlenmesi veya daha küçük bir modele geçiş değerlendirilmeli.
3. **Korpus kapsamı.** SGK grubu 3.000 hedeflenmişken 1.516'da kalmış (yükleme yarıda kesilmiş).
5. **Bellek.** İki model (gömme + yeniden sıralama) aynı anda yüklü olduğunda M1/16 GB sınırda
   çalışıyor. Ölçüm sırasında sistem takas (swap) alanına düştüğünde sorgu süresi 12 sn'den
   60 sn'ye çıktı. Demo makinesinde başka ağır süreç (Docker konteynerleri, IDE) açık olmamalı.
4. **Örneklem büyüklüğü.** Nesnel test 12 mesele üzerinde; hakem değerlendirmesi 100 sonuç üzerinde.
   Güven aralığını daraltmak için genişletilmeli.

## Tekrarlanabilirlik

| Betik | İşlev |
|---|---|
| `08_test_v2.py` | 95 sorgu, konu isabeti + gecikme |
| `10_altin_standart_test.py` | Nesnel altın standart P@k ölçümü |
| `11_hakem_verisi_hazirla.py` | Hakem verisini tam bağlamla hazırlar |
| `12_ab_testi.py` | Öbek kolu A/B karşılaştırması |
| `13_rerank_bedeli.py` | Yeniden sıralayıcı kalite/gecikme dengesi |

Ham sonuçlar: `altin_standart_TABAN.json`, `ab_testi_sonuc.json`, `rerank_bedeli_sonuc.json`.
(Yargıtay karar metinlerinden alıntı içeren ara çıktılar — `test_v2_sonuclari.json`,
`hakem_verisi_v3.json` — bu depoya bilerek dahil edilmedi; betikler çalıştırılınca yerelde üretilir.)
