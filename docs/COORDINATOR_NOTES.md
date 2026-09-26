# Koordinasyon notları

Kısa operasyon belleği; görev durumu PROGRESS.md, mevcut kapsam AGENT_BRIEF.md içinde tutulur.

- Küçük ve bağlantılı işleri tek görevde tut; yalnız bağımsız büyük işleri paralelleştir. En fazla üç mevcut ajanı yeniden kullan.
- Çalışan ajana sonraki bağımsız görevi erken gönderme; önce mevcut final raporunu al. Ek istekleri koordinatörde beklet, önceki iş bittikten sonra ayrı ata. Kişisel Gmail giriş sadeleştirmesi şu an beklemede.
- Atamada sonuç, sahip olunan alan, yasaklar ve kabul kanıtını belirt. Reviewer için yalnız değişen delta; önce kabul edilmiş alanları yeniden taratma.
- Rutin işte kod ajanının odaklı testleri ve final kanıtı yeterli; otomatik kod → reviewer döngüsü kurma. Reviewer özel kullanıcı isteği, somut çözülemeyen risk veya önemli bağımsız inceleme ihtiyacında kullanılır.
- Sentetik örnek gerçek üretim yolunu kaçırdı: RSS sıralama regresyonu doğrudan yeni işlenen girişleri kullanmalı. Tarihsiz kaynak ve beşten fazla aday önemli sınırlar.
- Ortak sıralama yalnız bölüm/tarih ile yeterli değil: eşit anahtarlı adayların farklı giriş sıralarında aynı sonucu verdiğini de sınat; kararlı kimlik tie-break kullan.
- Reviewer eski hazırlık/CI talimatına döndü ve son inceleme kararını vermedi. Yeni mesajda aktif görev önceliğini ve gerekli final kararını açıkça belirt; başarısız bir komutu kanıt sayma.
- Yalnız final REPORT veya engelleyici NEEDS_DECISION al; otomatik rapor gelmezse final çıktıyı bir kez kontrol et.
- Hassas terminal çıktısı için tam komut ve okuma izni al. Sunucu ayarlarını yedekle; yalnız ilgili takip edilen değişiklikleri stash et, fast-forward güncelle, stash pop çatışırsa dur. .env ve secrets değerlerini okuma veya Git'e ekleme.
- Kullanıcı commit/push, sunucuda stash/pull/pop çıktıları ile yalnız pass/fail ve sağlık sonucu veren kontrollerin okunmasına izin verdi. Bu izin env/secrets veya ham uygulama loglarına yayılmaz. PowerShell'den SSH betik aktarımında CRLF taşımamak için UTF-8/base64 kullan; Compose servis adını tahmin etme.
- Yerel test geçişi canlı Telegram, Actions veya VDS kabulü değildir. Gerekli kabul kanıtı tamamlanmadan dağıtma; dağıtım sonrası güvenli sağlık kontrolü ve kullanıcı denemesi ayrı kanıttır.
