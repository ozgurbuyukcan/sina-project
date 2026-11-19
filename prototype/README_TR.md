# SINA Prototype 1 — Hidrolik İzleme ve Olay İnceleme Prototipi

**Yayımlanan adı SINA Prototype 1 olan bu uygulama, SINA Fresh 0.2 kaynak kodundan türetilmiş teknik 0.2.1 sağlamlaştırma sürümünü kullanır. Eski 0.2 ZIP dosyası değiştirilmemiştir.** Önceki v2–v6 modelleri, model ağırlıkları veya başarı iddiaları kullanılmaz. Bu sürümün amacı: ölçümü güvenli biçimde kaydetmek, incelenmesi gereken olayları düzenlemek ve operatörün kaydettiği doğrulanmış gözlemleri eğitim için *aday* veri hâline getirmektir.

## 0.2.1 neyi düzeltir?

- ASSESS grafiğindeki yanlış yere kayabilen dikey olay işaretçisi artık UTC ISO8601 tarih türüyle çizilir. Olay çevresi ±5 dakika sabit görüntü aralığıdır.
- Seri gateway bağlantı kurma/kopma/yeniden deneme durumları yerel SQLite'da izlenir; ekrandaki `Gateway health` durumu en son alınış saatine göre yeniden hesaplanır. Bu bir donanım kalibrasyon testi değildir.
- SQLite inceleme kararlarının, audit izlerinin ve dondurulmuş olay kesitinin uygulama yeniden açıldığında korunduğu doğrulanır.
- SCAN'den LEARNING DATA'ya kadar otomatik zincir testleri ve sahte seri port ile bağlantı kopma/hatalı paket testleri bulunur.
- **Orijinal 0.2 klasörünü silmeyin.** Eski yerel verilerinizi taşımak isterseniz, her iki uygulamayı kapattıktan sonra `MIGRATE_FROM_0_2_WINDOWS.bat` ile eski 0.2 klasörünü gösterin. Eski veritabanına dokunmaz; yeni klasörde aynı veritabanı zaten varsa kopyalamayı reddeder. Önce ayrıca yedek alın.
- `RUN_0_2_1_TESTS_WINDOWS.bat` ile otomatik testleri çalıştırabilirsiniz (gerekirse pytest'i kurar).

## Windows'ta başlatma

1. ZIP dosyasının tamamını çıkarın. Python **3.10 64-bit** kurulu olsun.
2. `run_windows.bat` çalıştırın. İlk açılışta `.venv` içinde Streamlit, scikit-learn, pandas, Plotly ve pyserial kurulur.
3. SINA arayüzü `http://127.0.0.1:8501` adresinde açılır. Sadece kendi bilgisayarınızdan erişilir.
4. `Synthetic demo (offline)` ile SCAN → IDENTIFY → NAVIGATE → ASSESS → LEARNING DATA sekmelerini deneyin.
5. Gerçek saha CSV'nizi `Upload measured CSV` üzerinden içe aktarabilirsiniz. Dosyanın gerçekliğini uygulama bağımsız olarak doğrulamaz.
6. Canlı sensor akışı için **ayrı bir komut penceresinde** `start_serial_windows.bat` çalıştırın. Arduino'nun gerçek COM portunu (örneğin COM3) yazın. Arduino IDE'deki Serial Monitor'u kapatın.
7. Arayüzde `Live sensor gateway` → `field-01` seçin. Her yeni gözlem kümesi için **Refresh live snapshot** düğmesine basın. Arayüz otomatik kendiliğinden yenilenmez; ağ geçidi arka planda ölçümleri almaya devam eder.

### Seri port / Arduino veri sözleşmesi

Seri port: varsayılan **115200 baud**. Her satır bir JSON nesnesi veya CSV kaydı olmalıdır:

```text
2026-11-18T12:00:00Z,LINE-1,12.50,0.34
,LINE-1,12.50,
```

İkinci örnekte Arduino'nun gerçek zaman saati ve basınç sensörü yoktur: **timestamp bilgisayarın UTC alım saatiyle atanır, basınç boş bırakılır**. JSON örneği:

```json
{"timestamp":"2026-11-18T12:00:00Z","line_id":"LINE-1","flow_lpm":12.50,"pressure_bar":0.34}
```

Sütunlar: `timestamp` ISO8601 (varsa açık saat dilimi), `line_id`, `flow_lpm` (**L/dk**), `pressure_bar` (**bar**, opsiyonel). Cihaz saati yoksa `timestamp` alanını boş bırakın. Birimler *asla* otomatik tahmin edilmez. Kaydedilen her ölçüm `source_id`, hat, zaman, alım zamanı, timestamp kökeni ve kaynak özet kimliğiyle SQLite'a yazılır. Aynı kaynak/hat/zaman çakışmasında farklı değer gelirse **ilk ölçüm korunur, yeni paket reddedilir ve hata günlüğüne yazılır**. Girişte kabul edilen geniş fiziksel sınırlar bir sensör kalibrasyonu değildir.

Örnek Arduino kodu: `arduino_examples/FlowPulse_Input_Only.ino` yalnızca **uyumlu bir darbeli debimetre varsa ve PULSES_PER_LITER sizin tarafınızdan kalibre edilirse** kullanılabilir. Varsayılan `0.0` değeriyle ölçüm göndermez. Elektriksel gerilim ve girişleri cihazın veri sayfasına göre kontrol edin; 12 V çıkışı Arduino 5 V pinlerine doğrudan bağlamayın. Röle, pompa, vana kontrolü bulunmaz.

### Yerel HTTP sensör girişi (alternatif)

`start_http_windows.bat` rastgele, uzun bir token üretir; komut penceresinde token gösterilir. HTTP ağ geçidi sadece **127.0.0.1:8765** adresini dinler. Ağdaki başka bilgisayarların bağlantısını kabul etmez; TLS veya uzaktan erişim altyapısı değildir.

Örnek PowerShell (token'ı komut penceresinde gösterilen değerle değiştirin):

```powershell
$token = 'GATEWAY_PENCERESINDEKI_UZUN_TOKEN'
$body = @{timestamp='2026-11-18T12:00:00Z'; line_id='LINE-1'; flow_lpm=12.5; pressure_bar=0.34} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/v1/measurements' -ContentType 'application/json' -Headers @{Authorization="Bearer $token"} -Body $body
```

**Güvenlik:** SINA'yı ve ağ geçidini doğrudan İnternet'e açmayın. Gateway token'ını paylaşmayın. HTTP'nin yerel ağ dışında uzaktan kullanılabilmesi için ayrıca güvenli ve doğrulanmış bir iletişim katmanı geliştirilmelidir.

### Donanım olmadan canlı kayıt yolunun sınanması

```powershell
.venv\Scripts\python.exe live_gateway.py --mode replay --source demo-replay-01 --input sample_data\synthetic_sensor_replay.jsonl
```

Kaynak `OFFLINE_REPLAY` olarak kaydedilir; gerçek bir seri bağlantıyla **aynı kaynak kimliğine** yazılmasına izin verilmez. Bu veri yalnızca entegrasyon testidir. Tekrarlanan kayıtlar tekrar eklenmez.

## Beş aşama

| Aşama | 0.2'de uygulanan özellik |
| --- | --- |
| **SCAN** | Eski CSV QA + kalıcı, kaynak kimlikli sensör alımı; geçersiz/reddedilen paket günlüğü; aynı zamanlı çakışmaların önlenmesi |
| **IDENTIFY** | Önceki v0.1'deki, ilk N ölçümün sağlıklı olduğu **varsayımıyla** eğitilen Isolation Forest + nedensel robust debi özellikleri korunur |
| **NAVIGATE** | Filtrelenebilir, önceliğe göre sıralanabilir hidrolik olaylar ve ayrı veri kalitesi olayları; deterministik olay kimliği |
| **ASSESS** | Olay çevresinde ±5 dakika grafiği ve ham ölçümler, kullanıcı raporları, inceleme yöntemi, notlar, audit geçmişi, değişmez ilk-inceleme ölçüm kesiti |
| **LEARNING DATA** | Kapalı + fiziksel kontrolü bildirilen + kanıt notu olan ve demo/replay olmayan olaylardan **operatör-onaylı aday veri** arşivi |

### Gerçek olayların doğrulanması

1. `04 · ASSESS` sekmesinde olayı seçin.
2. Gerçek saha kontrolünü yapın; kontrol sonucunu **Operator-reported finding** olarak seçin.
3. Fiziksel olarak denetledinizse **I inspected and physically verified** kutusunu işaretleyin ve delil/denetim yöntemini yazın. İş akışını `closed` yapın. Aksi hâlde böyle işaretlemeyin.
4. `Save review + immutable measurement snapshot` düğmesine basın.
5. `05 · LEARNING DATA` bölümünde uygun olayları ve `Export verified event candidates (ZIP)` seçeneğini görün.

`candidate_manifest.json`, `operator_verified_events.csv` ve `event_context_samples.csv` ZIP içinde birlikte verilir. SHA-256 özetleri, ham veri kimliği, kaynak kökeni, zaman, olay kimliği ve etiket durumu tutulur. **Bunlar operatör beyanıdır, bağımsızca doğrulanmış bilimsel ground truth değildir.** Gözetimli model otomatik eğitilmez. *Tek bir anomali tespit anı, fiziksel sızıntının gerçek başlangıç zamanı değildir.* Olay çevresindeki beş dakikalık pencere gelecekteki değerleri de içerir; ancak yalnızca **geriye dönük olay incelemesi** içindir, gerçek zamanlı modele doğrudan girdi yapılamaz. Kısa ve birbirine yakın örnek pencerelerini rastgele train/test bölmek bilimsel sızıntı bilgisi üretmez.

### Veritabanı ve gizlilik

- `user_data/live_measurements.sqlite3`: alınmış sensör ölçümleri; `source_registry` ve `ingestion_errors` tabloları.
- `user_data/operator_feedback.sqlite3`: inceleme formları, append-only audit geçmişi ve ilk incelemede dondurulan olay kesitleri.
- Dosyalar **sadece yerel diskinizde** saklanır; varsayılan kurulumda buluta yüklenmez. Yedeklemek ve erişimi korumak kullanıcının sorumluluğundadır.
- Sistemde kullanıcı hesapları/rol izinleri bulunmaz; bu nedenle **çok kullanıcılı, internete açık üretim sistemi değil**, yerel operatör prototipidir.
- Arayüzün `Refresh live snapshot` butonu anlık yeniden analiz başlatır. İlk `baseline` ölçümleri gelmeden tespit başlatılamaz.
- Silme/retention işlemleri otomatik değildir; veritabanı büyüdüğünde yerel arşiv ve daha güçlü depolama mekanizması gerekir.

## Testler

```powershell
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest -q
```

Testler seri paket doğrulaması, eşsiz ve idempotent kayıt, kaynak türü izolasyonu, HTTP auth, değişmez olay görüntüsü, doğrulanmamış etiketlerin dışlanması ve v0.1 analiz regresyonunu kapsar. **Gerçek Arduino bağlantısı bu çalışma ortamında fiziksel olarak sınanmadı.**

## Bilimsel sınırlamalar

- Anomali ≠ sızıntı. Fiziksel kök neden teşhisi otomatik değildir.
- İlk N satırın sağlıklı olduğu **varsayılır**, gerçekten sağlıklı oldukları bilinmez.
- Cihaz kalibrasyonu, ağ topolojisi ve gerçek fiziksel akış testleri henüz doğrulanmamıştır.
- Eğitime aday olayların onaylı olması, fiziksel yerinde bağımsız kanıt veya model doğruluğu garantisi değildir.
- Basınç ve debi yalnızca sağlanan birimleriyle kullanılır; başka sensör türleri için yeni bağlayıcı gerekir.
- Pompa veya vanalara asla otomatik kumanda gönderilmez.


## Sahada doğrulama listesi

`STABILIZATION_CHECKLIST_TR.md` dosyasında ASSESS dikey çizgisi, yeniden açıldıktan sonra operatör kayıtları ve gerçek USB port davranışları için adım adım kontrol listesi bulunmaktadır. Gerçek sensör testi bitmeden üretim sistemi veya doğrulanmış kaçak dedektörü iddiası yapılmaz.
