# Projeyi anlatırken

Bu notlar ezberlenecek bir konuşma metni değil. Her cevabı kodu açarak açıklayabilmek için bir çalışma rehberi.

**Proje hangi soruya cevap veriyor?**
Müşterilerin şikâyetlerinde hangi ürün/sorun temalarının bulunduğu ve hangi haftalarda beklenenden fazla kayıt oluştuğu. Bir alarmın gerçek bir operasyon sorunu olduğunu kanıtlamıyor.

**Neden New York ve 2024?**
İndirilebilir, tekrar üretilebilir ve tam haftalardan oluşan bir pilot kapsam oluşturmak için. Sonuçlar Türkiye'ye veya bütün ABD'ye doğrudan genellenemez. Bu bir örnekleme temsiliyeti iddiası değil.

**Gerçek veri mi?**
Evet. Canlı CFPB metadatası ve kurumun resmî anlatım arşivi kullanılıyor. Yanlış alarm deneyi ise ayrı ve sentetik; bu iki sonucu karıştırmamak gerekir.

**Veri indirirken ne sorun çıktı?**
API artık anlatım alanını vermiyordu: Eylül 2026 değişikliği. Resmî arşivler bulundu ve ID ile eşleştirildi. Ayrıca API'nin tarih üst sınırı beklenenden farklı davrandığı için 48 kayıt yerel filtreyle çıkarıldı. Kaynak dosyaların hash'leri saklandı.

**Neden TF-IDF + lojistik regresyon?**
2.527 eğitim anlatımı için anlaşılır bir başlangıç modeli. Kelime/kelime çifti ağırlıkları incelenebiliyor; eğitimi ve yerel çalıştırması kolay. Transformer'ın üstün olduğunu ölçmeden iddia etmiyoruz.

**Neyi tahmin ediyor?**
Metinden ürün grubu ve tüketicinin seçtiği sorun etiketi. Bu etiketler de hatalı veya belirsiz olabilir. Şikâyetin doğruluğunu tahmin etmiyor.

**Veri sızıntısını nasıl sınırladınız?**
Kronolojik train/validation/test ayrımı, eğitimde öğrenilen sözlük ve IDF, eğitimde belirlenen sınıflar, erken kaydı tutan tekrar temizliği. Benzer ama birebir olmayan metinler kalabileceği için sızıntının tamamen yok olduğunu söylemiyoruz.

**Neden accuracy tek başına yeterli değil?**
Sık sınıfı seçmek accuracy'yi yükseltebilir. Macro-F1 her sınıfa eşit ağırlık verir. Sorun modeli accuracy yaklaşık %51,0 iken macro-F1 0,324; seyrek sınıflarda zayıflık var. Çoğunluk baseline'ının macro-F1'i 0,036.

**0,324 macro-F1 iyi mi?**
Otomatik sorun yönlendirme için güçlü bir sonuç değil. Baseline'dan daha iyi ama sınırlı. Bunu insan incelemesini destekleyen bir başlangıç modeli olarak sunmak doğru. Daha ayrıntılı hata analizi ve alan etiketlemesi gerekiyor.

**%88,2 doğruluk nereden geliyor?**
Sadece model skoru 0,60 ve üzerinde olan test alt kümesinden. Bu grup tüm testin yaklaşık %9,9'u. Tüm modelin doğruluğuymuş gibi kullanılamaz. Eşik testte değil validation'da seçildi.

**Skor %80 ise tahmin kesin %80 doğru mu?**
Hayır. Skorlar ayrıca kalibre edilmedi. ECE ve Brier bunun değerlendirilmesi için raporlanıyor. Kalibrasyon ileri bir çalışma olarak kalıyor.

**NMF ne yapıyor?**
TF-IDF matrisini pozitif bileşenlere ayırarak birlikte görülen kelime temalarını buluyor. Konu sayısı 8 bir tasarım seçimi; temaların gerçek operasyon nedenlerini temsil ettiğini iddia etmiyoruz.

**Alarm neden yalnızca yüzde artışa bakmıyor?**
1 kayıttan 3'e çıkmak %200 artış ama az veri var. Sayı tabanı, beklenen hacim, değişkenlik ve aynı anda kontrol edilen seri sayısı önemli. Burada en az sayı, lift, standartlaştırılmış sapma ve düzeltilmiş kuyruk skoru birlikte kullanılıyor.

**Neden negatif binom?**
Şikâyet sayılarındaki varyans ortalamadan büyük olabilir. Poisson eşit ortalama/varyans varsayımıyla fazla alarm üretebilir. Negatif binom aşırı yayılımı karşılayabilir; parametre tahmini ve otokorelasyon yine sınırlama.

**Benjamini–Hochberg ne işe yarıyor?**
Aynı haftada birçok ürün/sorun serisini kontrol etmenin çoklu karşılaştırma etkisini azaltıyor. Fakat tahmini ve bağımlı kuyruk skorları nedeniyle gerçek hayatta kesin %5 yanlış keşif garantisi verilmiyor.

**Yanlış alarm oranını gerçek veride ölçtünüz mü?**
Hayır; doğrulanmış olay etiketleri yok. %0,99 sentetik durağan serilerde işaretlenen seri-hafta oranı. Gerçek kayıtlardaki dört sinyalin hangilerinin gerçek olay olduğunu bilmiyoruz.

**Neden Temmuz'dan önce alarm yok?**
İzlenecek seri ailesi Ocak–Haziran ile belirleniyor. Bu aileyi kullanarak Nisan'da alarm verdiğimizi iddia etmek geleceğe bakmak olurdu. İlk altı ay geliştirme, sonraki altı ay izleme dönemi.

**CUSUM bir olayın tarihini kanıtlıyor mu?**
Hayır. Art arda pozitif sapmaların birikimini gösteren ek izleme sinyali. Kesin değişim tarihi veya neden bulma yöntemi olarak sunulmuyor.

**Gerçek bankaya taşımak için ne gerekir?**
Türkçe ve banka içi etiketler, müşterilerin/işlemlerin sayısı gibi paydalar, ilk görülme zamanı, insan tarafından doğrulanmış olaylar, güvenlik ve erişim yönetimi, düzenli yeniden değerlendirme.

**Katkını nasıl anlatmalısın?**
Gerçekte yaptığın kararları, incelemeleri ve değişiklikleri anlat. AI araçlarının geliştirmedeki rolü sorulursa doğru bilgi ver. Bu dosyada anlatılan bir yöntemi henüz açıklayamıyorsan önce ilgili küçük fonksiyonu ve testini incele; kendi başına tasarladığını varsayma.
