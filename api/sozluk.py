"""Günlük dil → hukuki terim sözlüğü (v2, 121 kural).

Ölçülen zayıflık: kullanıcı hukuki terimi bilmeden sorunca ("çocuğun kimin yanında
kalacağı") sistem ilgili kararları bulamıyor, çünkü kararlar o terimi ("velayet")
kullanıyor. Sorgu aramadan önce buradan geçer; eşleşen kalıpların hukuki karşılıkları
sorguya eklenir, gerisini öbek ve kelime kolları halleder.

Kural biçimi: (tetikleyici_regex, eklenecek_terimler). Tetikleyiciler küçük harfle
denenir. Sorguda zaten geçen terim tekrar eklenmez. Desenler günlük/halk dilini
hedefler; hukuki terimin kendisini tetikleyici yapmamaya dikkat edilir (teknik
sorgulara dokunulmaz).
"""
import re

KURALLAR = [
    # ================= AİLE — BOŞANMA SÜRECİ =================
    (r"boşan\w+ sonra.{0,30}(evlen|bekle)|tekrar evlen\w+ (için )?(süre|bekle)|yeniden evlenme süre|"
     r"(300|üç ?yüz) gün.{0,20}evlen", ["iddet müddeti"]),
    (r"ayrı yaşama\w*|bir sürel\w+ ayrı|küs\w+ ayrı (ev|yaşa)", ["ayrılık kararı", "ayrılığa karar"]),
    (r"anlaşarak boşan|ikisi de (istiyor|kabul)|tek celsede boşan", ["anlaşmalı boşanma", "protokol"]),
    (r"(eşim|karım|kocam) boşanmak istemiyor|tek taraflı boşan", ["çekişmeli boşanma",
     "evlilik birliğinin temelinden sarsılması"]),
    (r"şiddetli geçimsizlik|anlaşamıyor|geçinemiyor|huzursuzluk", ["evlilik birliğinin temelinden sarsılması"]),
    (r"şiddet (gören|uygulayan|nedeni)|dayak|kötü muamele|darp ed", ["evlilik birliğinin temelinden sarsılması",
     "pek kötü muamele"]),
    (r"hakaret ed\w+ (eş|karı|koca)|aşağıla\w+ eş|onur kırıcı", ["onur kırıcı davranış", "kusur"]),
    (r"terk (etti|eden|edilme)|evi terk|evden (gitti|ayrıldı|kaçtı)", ["terk nedeniyle boşanma", "ihtar"]),
    (r"akıl (sağlığı|hastası)|psikolojik rahatsız\w+ (eş|boşan)|şizofren", ["akıl hastalığı nedeniyle boşanma"]),
    (r"(kumar|içki|alkol|uyuşturucu)\w*.{0,30}(boşan|evlili|eş\w{0,4}den)",
     ["haysiyetsiz hayat sürme", "kusur"]),
    (r"suç işle\w+ (eş|koca|karı)|hapse gir\w+ (eş|boşan)", ["suç işleme nedeniyle boşanma"]),
    (r"(cana kast|öldürmeye çalış)", ["hayata kast"]),
    (r"eş\w{0,4}( beni| onu)? aldat|sadakatsizli|başkasıyla (birlikte|ilişki)|yasak ilişki|ihanet",
     ["zina", "sadakat yükümlülüğü", "manevi tazminat"]),
    (r"kim (suçlu|kusurlu|haklı).{0,20}boşan|boşanmada (suç|kusur) kim", ["kusur belirlemesi", "tam kusur"]),
    (r"boşanma\w* (ne kadar sürer|kaç celse|uzun sür)", ["yargılama süresi", "usul ekonomisi"]),
    (r"(fiilen|yıllardır|uzun süredir) ayrı yaş\w+|ayrı evlerde", ["fiili ayrılık", "eylemli ayrılık"]),
    (r"barış\w+ tekrar (bir araya|birleş)|ortak hayat\w* (yeniden|tekrar) kur",
     ["ortak hayatın yeniden kurulamaması"]),
    (r"düğün (yapılmadan|öncesi)|nişan (boz|at)|söz kesil", ["nişanın bozulması", "hediyelerin iadesi"]),
    # ================= AİLE — ÇOCUK =================
    (r"çocu\w+ (kim\w* yanında|kime verilece|kiminle kalaca)|çocuğun bakımını kim|"
     r"çocuğu (bana|anneye|babaya) ver", ["velayet"]),
    (r"velayet\w* (değiş|geri al|bende|almak)", ["velayetin değiştirilmesi"]),
    (r"(ikimiz|beraber|ortak) (bak|velayet)|ortak velayet", ["ortak velayet"]),
    (r"çocu\w+ (görme|görüş|ziyaret|göster)|çocuğu göster\w+yor|görüştür", ["kişisel ilişki tesisi"]),
    (r"çocu\w+ (masraf|bakım paras|geçim|okul paras)", ["iştirak nafakası"]),
    (r"çocuk kaçır\w+ (eş|anne|baba)|çocuğu (alıp|kaçırıp) (git|kaç)", ["velayet", "çocuğun iadesi"]),
    (r"babası\w* (tanımıyor|kabul etmiyor)|evlilik dışı (çocuk|doğan)|dna test", ["babalık davası", "soybağı"]),
    (r"evlat edin", ["evlat edinme"]),
    (r"çocuğ\w+ soyad", ["çocuğun soyadı", "velayet"]),
    (r"18 yaşın\w+ (küçük|altında).{0,20}evl|küçük yaşta evl", ["evlenme ehliyeti", "yasal temsilci izni"]),
    # ================= AİLE — NAFAKA =================
    (r"boşan\w+ sonra (geçim|para|maaş)|eşten (nafaka|para) al|geçinemem.{0,15}(boşan|sonra)",
     ["yoksulluk nafakası"]),
    (r"dava sürerken (nafaka|geçim|para)|boşanma bitmeden (para|destek)", ["tedbir nafakası"]),
    (r"nafaka\w* (art|yükselt|zam|yeterli değil|yetmiyor)", ["nafakanın artırılması", "uyarlama"]),
    (r"nafaka\w* (kes|kaldır|bitir|iptal|ödemek istemiyor)|nafakadan kurtul",
     ["nafaka yükümlülüğünün kaldırılması"]),
    (r"nafaka öde(n)?m\w+yor|nafakayı vermiyor|nafaka alamıyor", ["nafaka alacağı", "icra takibi"]),
    (r"(çalışmaya başla|evlen|birlikte yaşa)\w*.{0,20}nafaka", ["nafakanın kaldırılması",
     "evlenme ve fiilen evli gibi yaşama"]),
    (r"(anne|baba|çocuk)\w* (bakmak|bakım).{0,20}(zorunda|yükümlü)|yaşlı (anne|baba)ya nafaka",
     ["yardım nafakası"]),
    # ================= AİLE — MAL / EŞYA =================
    (r"evlilik\w* (içinde |sırasında )?(alınan|edinilen) (mal|ev|araba|mülk|birikim)",
     ["edinilmiş mallara katılma", "mal rejiminin tasfiyesi"]),
    (r"mal (paylaşım|bölüş)|mallar nasıl (bölün|paylaş)|evler kime kal", ["mal rejiminin tasfiyesi",
     "katılma alacağı"]),
    (r"(ev|daire) (alırken|alınırken).{0,20}(para verdim|katkı)|birlikte (aldık|ödedik)",
     ["katkı payı alacağı"]),
    (r"düğün\w* takıl\w+ (altın|takı|para)|takılar\w* (geri|iade|kimin)|altınlar\w* (aldı|kimin|geri)",
     ["ziynet eşyası"]),
    (r"çeyiz\w* (geri|iade|aldı)", ["çeyiz eşyalarının iadesi"]),
    (r"oturduk\w+ ev\w* sat[ıi]l|aile\w* yaşadığı ev|eşim evi (satıyor|satmış)|evi habersiz sat",
     ["aile konutu şerhi"]),
    (r"(kredi|borç)\w* (kim|hangi eş) öde|ortak (borç|kredi)", ["evlilik birliğinden doğan borçlar"]),
    (r"evlenmeden önce (sözleşme|anlaşma)|mal ayrılığı (sözleşme|seç)", ["mal ayrılığı rejimi",
     "mal rejimi sözleşmesi"]),
    (r"(eşim|karım|kocam).{0,20}(habersiz|gizli).{0,20}(sattı|devretti|kaçırdı)",
     ["mal kaçırma", "muvazaalı devir", "tasarrufun iptali"]),
    # ================= AİLE — TAZMİNAT =================
    (r"boşan\w+.{0,20}(tazminat|zarar).{0,10}(iste|talep|al)", ["maddi ve manevi tazminat", "TMK 174"]),
    (r"(üzüntü|acı|yıpran)\w*.{0,20}(boşan|tazminat)|manevi (zarar|çöküntü)", ["manevi tazminat"]),
    # ================= İŞ — İŞE GİRİŞ / DENEME =================
    (r"(yeni|henüz) (alın|başla|gir)\w+.{0,30}(çıkar|at[ıi]l|fesih|kovul)|"
     r"ilk (ay|hafta|gün)\w*.{0,30}(çıkar|at[ıi]l|fesih|kovul)|"
     r"(hafta|ay) sonra (çıkar|at[ıi]l|kovul)", ["deneme süresi"]),
    (r"deneme (sürecinde|aşamasında|dönem)", ["deneme süresi"]),
    (r"sözleşme (imzalamadan|yapılmadan) çalış|sözleşmesiz çalış", ["belirsiz süreli iş sözleşmesi",
     "yazılı şekil"]),
    (r"(sezonluk|dönemlik|proje bazlı|geçici) (iş|çalış|sözleşme)", ["belirli süreli iş sözleşmesi"]),
    (r"taşeron|alt firma|aracı şirket", ["alt işveren", "asıl işveren alt işveren ilişkisi", "muvazaa"]),
    (r"kağıt üzerinde (başka|farklı) (şirket|firma)", ["muvazaa", "alt işveren"]),
    # ================= İŞ — ÜCRET =================
    (r"maaş\w*.{0,20}(ödenm|alam[ıa]|gecik|eksik|yatm[ıi]yor|yatır\w{0,4}m[ıi]yor|verm[iı]yor)",
     ["ücret alacağı"]),
    (r"elden (maaş|para|ödeme)|maaş\w* (bir kısmı|yarısı) (elden|kayıt dışı)|bordroda düşük",
     ["gerçek ücretin tespiti", "kayıt dışı ücret"]),
    (r"asgari ücret\w* (altında|az) (öde|çalış)", ["ücret alacağı", "asgari ücret"]),
    (r"(prim|ikramiye|yol paras|yemek paras)\w* (ödenme|kes|vermiyor|alamıyor)",
     ["prim ve ikramiye alacağı", "giydirilmiş ücret"]),
    (r"maaş\w* (düşür|indir|azalt)|zam yapmıyor", ["ücrette esaslı değişiklik",
     "çalışma koşullarında esaslı değişiklik"]),
    (r"mesai\w* (dışında|sonrası|fazla) çalış|geç saatlere kadar|(hafta ?sonu|cumartesi|pazar).{0,15}çalış\w+ (ücret|para)",
     ["fazla mesai", "fazla çalışma ücreti", "hafta tatili ücreti"]),
    (r"fazla mesai\w* (ödenme|vermiyor|alamıyor|kanıt|ispat)", ["fazla çalışma ücreti", "tanıkla ispat"]),
    (r"(bayram|resmi tatil|dini bayram)\w*.{0,15}çalış", ["ulusal bayram ve genel tatil ücreti"]),
    (r"gece (vardiya|çalış)", ["gece çalışması"]),
    (r"izin\w* (kullanmadan|kullanamadan|paras)|kullanılmayan izin|izin vermiyor|yıllık izin\w* (yanar|yandı)",
     ["yıllık izin ücreti"]),
    (r"maaş\w* (ne zamana kadar|kaç yıl geriye)|eski (maaş|alacak)\w* (iste|talep)",
     ["zamanaşımı", "ücret alacağında zamanaşımı"]),
    # ================= İŞ — FESİH / TAZMİNAT =================
    (r"işten (atıl|çıkarıl|kovul)\w+.{0,20}(tazminat|hak|ne yapabilirim|param)", ["kıdem tazminatı",
     "ihbar tazminatı", "işe iade"]),
    (r"kaç yıl.{0,20}tazminat|tazminat\w* nasıl hesap", ["kıdem tazminatı", "giydirilmiş ücret"]),
    (r"haber ver(me|il)\w+ (işten|çıkar)|aniden (işten|kovul)|bir günde (işten|kovul)",
     ["ihbar tazminatı", "usulsüz fesih"]),
    (r"işe geri (dön|al[ıi]n)|geri işe (al|dön)|haksız.{0,20}(çıkarıl|atıl)\w+ geri", ["işe iade",
     "geçersiz fesih"]),
    (r"istifa\w*.{0,30}(tazminat|hak)", ["haklı nedenle fesih", "kıdem tazminatı"]),
    (r"istifaya zorla|istifa (imzalat|ettir)", ["irade fesadı", "istifanın geçersizliği"]),
    (r"karşılıklı anlaş\w+ (ayrıl|işten|son)|anlaşarak işten", ["ikale sözleşmesi", "makul yarar"]),
    (r"emekli ol\w+.{0,40}(tazminat|hak|alacak|ayrıl)|emeklilik.{0,20}(ayrıl|tazminat)",
     ["yaşlılık aylığı", "kıdem tazminatı", "emeklilik nedeniyle fesih"]),
    (r"askere gid\w+.{0,20}(işten|tazminat|hak)|askerlik (nedeni|yüzünden)", ["muvazzaf askerlik",
     "kıdem tazminatı"]),
    (r"evlen\w+.{0,20}(işten ayrıl|tazminat).{0,20}(kadın|kadının)|kadın.{0,15}evlen\w+.{0,15}(ayrıl|tazminat)",
     ["evlilik nedeniyle fesih", "kıdem tazminatı"]),
    (r"işe (gitm|gelm)\w+|rapor bitince gitme", ["devamsızlık"]),
    (r"performans (düşük|yetersiz).{0,20}(çıkar|fesih)|verim (düşük|az).{0,15}(çıkar|at)",
     ["performans düşüklüğü", "geçerli fesih", "savunma alınması"]),
    (r"(küçülme|kriz|ekonomik durum|işler kötü).{0,25}(çıkar|işten|fesih)", ["işletme gerekleri",
     "geçerli fesih", "son çare ilkesi"]),
    (r"(hırsızlık|yolsuzluk|sahtecilik|yalan).{0,25}(iddia|suçla)\w*.{0,20}(işten|çıkar|fesih)",
     ["doğruluk ve bağlılığa aykırı davranış", "haklı fesih"]),
    (r"(küfür|hakaret|kavga)\w*.{0,20}(iş ?yeri|amir|patron|işten)", ["sataşma", "haklı fesih"]),
    (r"(hasta|rapor)\w*.{0,20}(işten (çıkar|at)|fesih)", ["sağlık nedeniyle fesih", "bekleme süresi"]),
    (r"(amir|patron|müdür|iş yerinde).{0,30}(baskı|psikolojik|taciz|yıldır|dışla)",
     ["mobbing", "manevi tazminat", "işçinin haklı feshi"]),
    (r"görev (yeri|tanımı) değiş\w*|başka (şehre|şubeye|pozisyona) (gönder|ata|sür)",
     ["çalışma koşullarında esaslı değişiklik", "nakil"]),
    (r"sendika\w* (üye|katıl)\w+.{0,30}(çıkar|atıl|fesih|baskı)", ["sendikal tazminat", "sendikal fesih"]),
    (r"hamile\w*.{0,25}(işten|çıkar|fesih)|doğum izni.{0,20}(sonra|dönüş).{0,15}(çıkar|işten)",
     ["hamilelik nedeniyle fesih", "kötü niyet tazminatı", "eşit davranma"]),
    (r"ibraname|imzalat\w+ (kağıt|belge)|boş (kağıt|senet) imzala", ["ibra sözleşmesi", "ibranamenin geçerliliği"]),
    (r"işyeri (satıl|devir|el değiştir)|şirket (satıl|birleş)", ["işyeri devri"]),
    (r"(kod|çıkış kodu).{0,15}(yanlış|farklı|29)", ["fesih bildirimi", "SGK çıkış kodu", "haklı fesih ispatı"]),
    (r"boşta (geçen|kaldığım) (süre|dönem)", ["boşta geçen süre ücreti"]),
    (r"işe başlatm\w+yor|geri almadı", ["işe başlatmama tazminatı"]),
    # ================= SGK — İŞ KAZASI / MESLEK HASTALIĞI =================
    (r"iş(yerinde| yerinde|te)? (kaza|yaralan|sakat|düş)", ["iş kazası", "maddi ve manevi tazminat"]),
    (r"çalışırken (öl|hayatını kaybet|vefat|kaza)", ["iş kazası", "destekten yoksun kalma tazminatı"]),
    (r"(öl|vefat)\w+ (işçi|çalışan|eş|baba)\w*.{0,25}(aile|eş|çocuk|tazminat|maaş)",
     ["destekten yoksun kalma tazminatı", "ölüm aylığı"]),
    (r"servis\w* (kaza|devril)|işe (gider|gelir)ken kaza|yolda kaza", ["iş kazası sayılan haller",
     "servis aracı"]),
    (r"(meslek|iş) (yüzünden|nedeniyle|kaynaklı) hastal|tozdan|kimyasaldan|meslek hastalığına yakalan",
     ["meslek hastalığı"]),
    (r"çalışama(z|yacak) (hale|durum)|sakat kal|uzv\w+ (kayb|kopt)|iş göremez",
     ["sürekli iş göremezlik", "maluliyet oranı"]),
    (r"(kaza|olay)da (kim|işveren\w*) (suçlu|sorumlu|kusur)|güvenlik önlemi al[ıi]nma",
     ["kusur oranı", "işverenin sorumluluğu", "iş sağlığı ve güvenliği önlemleri"]),
    (r"(baret|emniyet kemeri|koruyucu)\w* (verilme|yok|takma)", ["iş güvenliği önlemleri", "kusur oranı",
     "müterafik kusur"]),
    (r"kaza\w* (bildirilme|gizle|haber verilme)", ["iş kazasının bildirimi", "Kuruma bildirim"]),
    (r"raporlu\w* (para|ödenek|maaş)|rapor paras|hastalıkta maaş", ["geçici iş göremezlik ödeneği"]),
    (r"sgk (dava aç|para ist|geri ist)\w*.{0,15}(işveren|şirket)", ["rücu davası"]),
    # ================= SGK — SİGORTALILIK / EMEKLİLİK =================
    (r"sigortasız çalış|kayıt dışı çalış|sigorta (yapılma|yatırılma|göster)",
     ["hizmet tespiti", "sigortalılığın tespiti"]),
    (r"prim\w* (ödenme|yatırılma|eksik|az göster)|gün\w* eksik (yatır|bildir)",
     ["prim borcu", "hizmet tespiti", "eksik bildirim"]),
    (r"emekli (olabilir miyim|olma (şart|koşul)|olmak için)|kaç yaşında emekli|ne zaman emekli",
     ["yaşlılık aylığı", "tahsis şartları"]),
    (r"emekli (maaş|aylığ)\w* (bağlanma|kesil|düşük|az)", ["yaşlılık aylığı", "aylık bağlama oranı"]),
    (r"(askerlik|doğum|yurt ?dışı) (borçlan|say[ıi]l|prim)", ["hizmet borçlanması"]),
    (r"malul\w* (sayıl|maaş|aylık|emekli)|hastalıktan emekli", ["malullük aylığı", "maluliyet tespiti"]),
    (r"(engelli|özürlü|rapor)\w*.{0,15}(erken )?emekli", ["malullük aylığı", "engellilik indirimi"]),
    (r"işe giriş\w* (eski|geç|yanlış) (göster|bildir)|ilk işe giriş tarihi", ["sigortalılık başlangıcı",
     "hizmet tespiti"]),
    (r"(ölen|vefat eden) (eş|baba|anne)\w*.{0,15}(maaş|aylık)|dul.{0,10}(maaş|aylık)|yetim (maaş|aylık)|"
     r"(baba|anne|eş|koca|karı)\w{0,3} (öldü|vefat).{0,25}(maaş|aylık)", ["ölüm aylığı", "hak sahipliği"]),
    (r"iki (maaş|aylık) (birden|aynı anda)", ["aylıkların birleşmesi", "hak sahipliği"]),
    (r"işsizlik (maaş|paras|ödeneğ)", ["işsizlik ödeneği"]),
    (r"emekli olduktan sonra çalış", ["sosyal güvenlik destek primi"]),
    # ================= GENEL / USUL =================
    (r"tanık (var|göster|dinlet)|şahit (var|göster)|nasıl (ispat|kanıtla)", ["tanıkla ispat", "ispat yükü"]),
    (r"(whatsapp|mesaj|mail|e-posta|ses kayd|kamera)\w*.{0,30}(delil|kanıt|ispat|mahkemede)",
     ["delil niteliği", "hukuka aykırı delil"]),
    (r"dava (ne kadar sürer|kaç yıl|uzun)", ["makul süre", "yargılama süresi"]),
    (r"dava\w* (nerede|hangi (şehir|mahkeme))|hangi mahkeme", ["görevli ve yetkili mahkeme"]),
    (r"(süre|zaman) (geçti|kaçır|doldu) mu|kaç yıl içinde (dava|başvur)", ["zamanaşımı", "hak düşürücü süre"]),
    (r"önce (arabulucu|uzlaş)", ["zorunlu arabuluculuk", "dava şartı"]),
    (r"avukatsız dava|kendim dava aç", ["davanın açılması", "usul"]),
    (r"faiz\w* (ne zamandan|hangi tarih|işle)", ["faiz başlangıcı", "temerrüt"]),
    (r"karar\w* (itiraz|üst mahkeme|boz)|temyize (git|başvur)", ["istinaf", "temyiz"]),
    (r"(icra|haciz)\w* (gel|koy|başlat)|maaşa haciz", ["icra takibi", "maaş haczi"]),
]

_DERLENMIS = [(re.compile(p, re.IGNORECASE | re.UNICODE), terimler) for p, terimler in KURALLAR]


def genislet(soru: str) -> tuple[str, list[str]]:
    """Sorguyu hukuki terimlerle genişletir. (genişletilmiş_sorgu, eklenen_terimler) döner."""
    kucuk = soru.lower()
    eklenen = []
    for desen, terimler in _DERLENMIS:
        if desen.search(kucuk):
            for t in terimler:
                if t.lower() not in kucuk and t not in eklenen:
                    eklenen.append(t)
    if not eklenen:
        return soru, []
    return f"{soru} ({' '.join(eklenen[:6])})", eklenen[:6]
