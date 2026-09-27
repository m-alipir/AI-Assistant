# Koordinasyon notları

- Deploy komut dersi: git stash pop hash değil stash reflog referansı bekler; oluşturulan
  stash'i doğrulayıp stash@{0} ile pop et. SSH stdin üzerinden bash çalıştırırken Docker
  exec/run stdin'i tüketebilir; noninteractive komutlara </dev/null ver. Ham çıktı özel
  dosyada kalsın; yalnız aşama sonuçları gösterilsin. Env byte karşılaştırmasıyla korunmayı doğrula.

- Net tek yürütme emri sonrası fixer uygulama, migration ve son 398/398 offline test
  finalini REPORT ile teslim etti. Kanıt alındığında görevi kapat; atıl follow-up/ACK
  gönderip yeni tur açma. Yerel kabulü CI/VDS/canlı Gmail kabulünden ayrı kaydet.

- Son follow-up tekrar idle/hazırlık finaline döndü. Final teslimi bir kez başarılı oldu
  diye sonraki görevin yürütüldüğünü varsayma. Atama başında doğrudan "şimdi kodu değiştir
  ve test et; yeni görev bekleme" de; tek kalan somut işi ver. Başlatıldı bilgisini yalnız
  active durumuyla sınırlı tut; gerçek uygulama/test kanıtıyla ayrı doğrula.

- Yeniden atamada CURRENT EXECUTION başa taşındı ve eski bekle talimatı açıkça iptal
  edildi; fixer bu kez uygulama ve REPORT teslim etti. Odaklı test başarısı DB migration
  başarısızlığını kapatmaz. Eski suite sonucu ile son değişikliklerin doğrulamasını ayır;
  yalnız somut kalan kabul boşluğunu aynı ajana ver, otomatik reviewer döngüsü açma.

- 2026-09-27 tekrar: worker kod incelemesine başladı; contextCompaction sonrası eski
  hazırlık/bekle mesajına döndü. Bu turda değişiklik/test/REPORT kanıtı yok; finaldeki
  "kod/test açmadım" yürütme iziyle çelişti. Önceki düzeltmeyi kalıcı saymak hataydı.
  Yürütme emrini brief başına taşı, eski bekle talimatını geçersiz kıl; geniş araştırmayı
  tekrarlatma. Atama gönderildi diye işi yürütülüyor/tamamlandı sayma; final veya gerçek
  engel teslimini doğrula. Özetleme sonrası aktif göreve devam etmesini açıkça belirt.

- Gmail UX ders: araştırma normal Google readonly OAuth akışını ve uygulama sahibine ait client/API/redirect kurulumunu doğruladı. Telegram butonu kodlandı ama üretimde client/encryption girdileri eksikti; uçtan uca hazır değildi. `Kurulumu biz yaparız, kullanıcı sadece giriş yapar` demeden mevcut OAuth client/operatör erişimi ve yapılandırma hazırlığını güvenli var/yok kanıtıyla netleştir. Uygulama kullanıcısı ve işletmecisi aynı kişi olsa da sorumlulukları ayır. Kullanıcı Cloud Console işi istemiyorsa aynı kurulum listesini tekrar verme; mevcut client'ı yeniden kullanma, yetkili operatör kurulumu veya güvenilir broker seçeneğini araştır, kaçınılmaz erişim/credential engelini açıkça söyle. Kod/test/health başarısı canlı giriş başarısı değildir; gerçek kullanıcı akışındaki engeli baştan bildir. Yapamayacağını gizleyip görevi kullanıcıya devretme veya erişim olmadan yapacağın sözü verme.

- Test tekrarı sınırını koşullu yaz: başarılı gate gereksiz tekrarlanmaz; tam paket başarısızsa düzeltmeden sonra yeniden çalıştırılır. `Bir kez` talimatı fixer tarafından düzeltme sonrası doğrulamayı da engeller diye yorumlandı; acceptance için full green gerektiğini açıkça belirt.

Kısa operasyon belleği; görev durumu PROGRESS.md, mevcut kapsam AGENT_BRIEF.md içinde tutulur.

- 2026-09-27 kullanıcı düzeltmesi: YouTube'da önce mevcut yt-dlp ayarını/çağrısını incelet;
  sistemi değiştirme. Telegram maddesi sonunda kısa doğrulanmış kaynak adı (TRT Haber)
  göster; kaynak URL'si gösterme. Önceki "görünür kaynak yok" kararı bu ad istisnasıyla güncellendi.

- Araştırma teslimi ders: mevcut final/belgeleri tekrar geniş inceletme; yalnız eksik sözleşme
  için dar kaynak izi iste. İlk REPORT geldiğinde bitmiş göreve atıl ek talimat gönderme;
  sırada bekleyen mesaj yeni tur açabilir. Actions gibi bağımsız eski kapsamın izin sorusunu
  güncel plan teslimine engel yapma; açık kalem olarak tut, onaysız yeni komut isteme.

- Ücretli yeni API/servis/test veya maliyeti artıracak işlem öncesinde amacı, tahmini maliyeti
  ve harcama tavanını kullanıcıya söyle; tam ücretli kapsam onayı olmadan başlatma. Mevcut
  API anahtarı veya araştırma izni harcama izni değildir. Bunu ajan atamasına da taşı.
- YouTube ders: caption_access_error altyazı yok demek değildir. Önce mevcut çekme yolunun
  erişim/rate-limit/timeout/parse nedenini kanıtla. API'nin video desteklemesi bu iş için
  optimize çözüm olduğunu kanıtlamaz; konuşma özeti için ölçülmemiş görsel fallback önerme.
  Kullanıcı düzeltmesiyle video analizi aktif plandan çıkarıldı.

- Araştırmada yeni entegrasyon önermeden mevcut gateway'in doğru modalite/provider yolunu
  doğrula: OpenRouter video_url + Gemini AI Studio YouTube URL destekliyor; düz metin URL ve
  Vertex AI aynı şey değil. Ayrı Google adapter'ı ancak mevcut yol ölçülen ihtiyacı karşılamazsa.
  Daha açıklayıcı hata mesajı kök neden onarımı değildir; bütçe/erişim sorunu kapanmış sayılmaz.

- Ajanlar depolama hakkında çeliştiğinde belge varsayımını büyütme: optimizer compact_summary
  alanını doğruladı; önce cache/briefing snapshot okuma-yazma sözleşmesini kontrol ettir.
  Alanın varlığı Türkçe ve sürümlü içeriğin kullanıma hazır olduğunu kanıtlamaz. Plan incelemesini
  tüm repo araştırmasına dönüştürme; mevcut kanıtla kısa düzeltmeler ve açık kapılar yeterli.

- Küçük ve bağlantılı işleri tek görevde tut; yalnız bağımsız büyük işleri paralelleştir. En fazla üç mevcut ajanı yeniden kullan.
- Çalışan ajana sonraki bağımsız görevi erken gönderme; önce mevcut final raporunu al. Ek istekleri koordinatörde beklet, önceki iş bittikten sonra ayrı ata. Kişisel Gmail giriş sadeleştirmesi şu an beklemede.
- OAuth turunda kod dosyaları değiştiği hâlde bağlam özetlemesi sonrası final eski `hazırım/görev bekliyorum` talimatına döndü, REPORT gönderilmedi. Kesin sonuç: teslim ve görev devamlılığı başarısız; özetleme kaynaklı görev kayması olası neden. Aktif brief'in başında tek güncel görev/durum olsun; eski hazırlık mesajını açıkça geçersiz kıl. Final gelmezse bir kez durum+dosya adlarını kontrol et; kod yok/tamamlandı varsayma. Yeniden başlatırken mevcut değişiklikleri korut ve test/final mesaj teslimini kabul koşulu yap.
- Düzeltme işe yaradı: tek güncel uygulama talimatı ve finalin hem koordinatöre gönderilmesi hem sohbette verilmesi açıkça istendiğinde worker OAuth kodunu/testlerini tamamlayıp REPORT gönderdi. Yeni görev vermeden önce bu teslimi doğrula.
- Atamada sonuç, sahip olunan alan, yasaklar ve kabul kanıtını belirt. Reviewer için yalnız değişen delta; önce kabul edilmiş alanları yeniden taratma.
- Rutin işte kod ajanının odaklı testleri ve final kanıtı yeterli; otomatik kod → reviewer döngüsü kurma. Reviewer özel kullanıcı isteği, somut çözülemeyen risk veya önemli bağımsız inceleme ihtiyacında kullanılır.
- Sentetik örnek gerçek üretim yolunu kaçırdı: RSS sıralama regresyonu doğrudan yeni işlenen girişleri kullanmalı. Tarihsiz kaynak ve beşten fazla aday önemli sınırlar.
- Ortak sıralama yalnız bölüm/tarih ile yeterli değil: eşit anahtarlı adayların farklı giriş sıralarında aynı sonucu verdiğini de sınat; kararlı kimlik tie-break kullan.
- Reviewer eski hazırlık/CI talimatına döndü ve son inceleme kararını vermedi. Yeni mesajda aktif görev önceliğini ve gerekli final kararını açıkça belirt; başarısız bir komutu kanıt sayma.
- Yalnız final REPORT veya engelleyici NEEDS_DECISION al; otomatik rapor gelmezse final çıktıyı bir kez kontrol et.
- Hassas terminal çıktısı için tam komut ve okuma izni al. Sunucu ayarlarını yedekle; yalnız ilgili takip edilen değişiklikleri stash et, fast-forward güncelle, stash pop çatışırsa dur. .env ve secrets değerlerini okuma veya Git'e ekleme.
- Kullanıcı commit/push, sunucuda stash/pull/pop çıktıları ile yalnız pass/fail ve sağlık sonucu veren kontrollerin okunmasına izin verdi. Bu izin env/secrets veya ham uygulama loglarına yayılmaz. PowerShell'den SSH betik aktarımında CRLF taşımamak için UTF-8/base64 kullan; Compose servis adını tahmin etme.
- Yerel test geçişi canlı Telegram, Actions veya VDS kabulü değildir. Gerekli kabul kanıtı tamamlanmadan dağıtma; dağıtım sonrası güvenli sağlık kontrolü ve kullanıcı denemesi ayrı kanıttır.
