# Gece Çalışma Planı — Production Öncesi Sertleştirme

## Mevcut durum ve kanıt

- M14 güvenlik sertleştirmesi tamamlanmış; son kaydedilen offline doğrulama 108 testtir
  (`docs/PROGRESS.md`, 2026-09-08).
- Rol-temelli model yönlendirme, kalıcı sonuç cache'i, bütçe kaydı, RSS/Gmail/YouTube
  akışları, scheduler için günlük claim ve Search/Ask için sınırlandırılmış aday bağlamı
  halihazırda vardır (`docs/MODEL_ROUTING.md`, `docs/PIPELINES.md`).
- Başlangıç çalışma ağacı zaten değiştirilmiş durumdadır. Bu çalışma mevcut değişiklikleri
  geri almayacak veya sırf biçimsel nedenlerle yeniden yazmayacaktır.

## En yüksek etkili maliyet iyileştirmeleri

1. Tüm ana akışlarda "yeni kalıcı çıktı yoksa briefing editor çağrısı yok" kuralını ve
   run-bazlı provider/cache sayaçlarını tek bir güvenli toplama noktasından denetlemek.
2. Cache/dedup/post-LLM blok/retry kararlarını RSS, Gmail, YouTube ve Ask için aynı
   "tekrar provider çağrısı yapma" semantiğine yaklaştırmak; başarısızlık kategorilerini
   yalnızca güvenli operasyon metadatası olarak kaydetmek.
3. Prompt ve retrieval girdilerini konfigüre edilmiş üst sınırlarla sınırlamak; role/fallback/
   budget kararlarının model kimliklerini iş mantığına sabitlemeden kaldığını test etmek.
4. Bilinmeyen sağlayıcı maliyetini sıfır yerine `unavailable` olarak taşımaya devam edip
   görünür run özetlerinde netleştirmek.

## En yüksek etkili performans/dayanıklılık iyileştirmeleri

1. Manual run, scheduler ve açık retry'nin aynı iş üzerinde çakışma/çifte maliyet
   yaratmadığını akış sınırlarında doğrulamak ve eksikse tekil claim/koordinasyon eklemek.
2. Dış kaynak timeout'u, kısmi akış hatası ve yeniden başlatma senaryolarında diğer
   akışların çalışmaya devam etmesini; sonuçların RSS, Gmail, YouTube, Search/Ask ve
   briefing editor olarak ayrıştırılmasını sağlamak.
3. Gerçek sorgu yollarını inceleyip yalnızca kanıtlanabilir faydası olan ileri-yönlü
   indeks/sorgu ve sayfalama limitlerini eklemek. Tüm geçmişi çeken Admin/arama yollarını
   sınırlandırmak.
4. Güvenli, aggregate-only gözlemlenebilirliği güçlendirmek; secret, token, ham e-posta
   ve transcript asla run sonucu veya hata metnine eklenmeyecek.

## Bu gece kapsam dışı bırakılan küçük işler

- Küçük UI metni/sayaç düzenlemeleri, yeni dashboard parçaları ve yeni kullanıcı özelliği.
- Yeni sağlayıcı entegrasyonu, gerçek RSS/Gmail/YouTube/OpenRouter çağrısı veya deployment.
- Ses-STT fallback, Gmail Pub/Sub, Qdrant, genel web tarama ve kapsamlı UI tasarımı.

## Final doğrulama planı

1. Yeni veya güncellenen offline fixture'larla RSS, Gmail, YouTube, retry, scheduler ve
   Search/Ask'ın kritik maliyet/çakışma/kısmi-hata senaryolarını kapsa.
2. Tam offline `pytest`, `ruff check .`, `alembic upgrade head --sql` ve `git diff --check`
   çalıştır.
3. Sonuçları, değişen dosyaları ve kalan riskleri `docs/PROGRESS.md`ye dürüstçe kaydet;
   canlı sağlayıcı veya kullanıcı verisi kullanma.
