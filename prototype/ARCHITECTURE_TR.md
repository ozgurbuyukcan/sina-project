# SINA Fresh 0.2 — Gerçekleşmiş teknik mimari

```text
Arduino / Serial JSONL,CSV            Local HTTP (Bearer token)
          |                                      |
          +-------> live_gateway.py <-----------+
                               |
                 Validate source & readings
                   [rejection reason audit]
                               |
             SQLite measurements append-only
                      [provenance/time]
                               |
                 Snapshot on UI refresh
                               |
                   SCAN (schema, QA)
                               |
                IDENTIFY (0.1 ML core)
                               |
               NAVIGATE (triage queue)
                               |
                 ASSESS (event detail)
                               |
          Human review + immutable context
                               |
                 SQLite review audit
                               |
                LEARNING DATA EXPORT
                 [candidates, no fit]
```

## Değiştirilen / eklenen dosyalar

- `app.py`: 5 sekmeli Streamlit arayüzü; kaynak türü, canlı kayıtların manuel yenilenmesi, olayların detaylı incelemesi.
- `live_gateway.py`: seri port, sadece localhost HTTP ve kaynak türü işaretli offline replay girişleri.
- `sina/live.py`: paket normlama; sonlu sayısal değerler; kaynak türünü sabitleme; append-only SQLite; duplicate/conflict ayrımı; stabil canlı olay kimlikleri.
- `sina/feedback.py`: immutable ilk olay veri kesiti, review-verified aday kümesi, manifest + SHA-256 doğrulama, demo/replay dışlama.
- `sina/{detect,pipeline,quality,events,schema,store}.py`: v0.1 çekirdek işleyişi korunmuştur; pipeline sürüm kimliği 0.2'ye güncellenmiştir.
- `tests/test_live_and_feedback.py`: yeni bağımsız entegrasyon ve geriye uyumluluk testleri.

## Kimlikler

- CSV: ilk içerik SHA-256'nın ilk 20 karakteri değişmeyen `dataset_id`.
- Live: `live-<source_id>` aynı kaynaktaki büyüyen kayıtlarla sabit kalır.
- Live event: `SHA256(source_id, line_id, event_kind, first active timestamp)` üzerinden 14 karakter.
- Kayıt kimliği: `source_id + line_id + timestamp` benzersiz anahtarı; farklı değerli tekrar reddedilir.
- Review snapshot: bir olayın ilk operatör incelemesindeki ±5 dakika bağlamı SHA-256 ile dondurulur, daha sonraki ek ölçümlerle geriye dönük değişmez.

## Özellik/kanıt sınırları

- Streamlit ekranı periyodik otomatik yenileme yapmaz. Canlı ingestion işlemi ayrıdır; ekran `Refresh live snapshot` ile yenilenir.
- Event data immutable snapshot, **geriye dönük açıklama** içindir; online modele gelecekteki değer aktarmaz.
- İnsan onayı ile doğrulanmış bir olay, uygulama tarafından bağımsızca doğrulanmış değildir. Etiketler `operator_physically_verified_claim` şeklinde aktarılır.
- Sinyal ayrımı, neden analizi ve koruyucu müdahale otomatik yapılmaz. Ek sensörler ve hidrolik model gerektiğinde ayrı modül gerekir.
- Yerel HTTP girişine token gerekir, uzak erişime kapalıdır; ayrı kullanıcı oturum/rol yönetimi henüz yoktur.

## 0.2.1 ek güvenilirlik katmanı

- `sina/plots.py`: görsel gösterim dışında bağımsız sınanabilen UTC/Plotly olay grafiği. `add_shape` olay anını ISO tarih değeri olarak alır; ±5 dakika pencere yalnızca değerlendirme içindir.
- `sina/live.py`: artan tablo `gateway_events`, `source_connection_health` ile alınış saati temelli tazelik ve bağlantı geçmişi. Ağ geçidi fiziksel olarak kalibre edilmiş sensör tanıması yapmaz.
- `live_gateway.py`: `collect_serial` fonksiyonu yeniden deneme döngüsünü test edilebilir kılar. Seri port hiç açılmasa bile kaynak ölçümleri silinmez.
- `migrate_from_02.py`: 0.2 operatör/veri depolarının SQLite backup ile kopyası; hedef veritabanının üzerine yazma yok.
- `tests/test_021_regressions.py`: zaman çizgisi, veri kalıcılığı, canlı giriş ve tüm beş aşamanın otomatik kontrolleri.

Bu sürümde model algoritması, sızıntı doğruluğu iddiaları ve denetim kaydından eğitim davranışı değiştirilmemiştir.
