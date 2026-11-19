# SINA Fresh 0.2.1 — Sağlamlaştırma sürümü

**Temel:** SINA Fresh 0.2 (silinecek / üzerine yazılacak bir dosya yok). Yeni AI modeli yoktur.

## Düzeltilenler

1. **ASSESS UTC zaman çizgisi:** Olay dikey işaretçisi artık epoch-millis sayısı olarak değil `UTC ISO8601` tarih değeri olarak çizilir. Olay çevresinin ±5 dakikalık UTC görünüm sınırları açıkça tanımlanır. Tarihler aynı anı farklı UTC offsetleriyle gösterse de işaretçi aynı konuma gelir. Ayrıntı: `sina/plots.py`.
2. **ASSESS kartı:** Uzun `HYDRAULIC_ANOMALY` adı daha okunur `Hydraulic anomaly` olarak gösterilir; alttaki gerçek olay tablosundaki teknik tür değiştirilmez.
3. **Bağlantı durumu görünürlüğü:** Seri port `CONNECTED`, `DISCONNECTED`, `RETRYING`, `STOPPED` olayları yerel SQLite `gateway_events` tablosuna yazılır. Arayüz son ölçümün alım zamanına göre `RECEIVING / STALE / NO_RECORDS / DISCONNECTED / RECONNECTING / OFFLINE_REPLAY` durumlarını gösterir. Bu durumlar donanım kalibrasyon doğrulaması **değildir**.
4. **Seri port kurtarma testi:** Giriş döngüsü testte sahte cihaz takılarak kopma/yeniden bağlanma/hatalı paket senaryolarını çalıştırabilecek biçimde ayrıştırıldı. Üretimde aynı pyserial yolunu kullanır; pompa/vanaya hiçbir komut göndermez.
5. **SQLite kalıcılığı:** Operatör değerlendirmesi, audit satırları ve değişmez ilk olay kesitinin yeniden açıldığında kaybolmadığı test edildi.
6. **Tam modül zinciri:** CSV/sentetik + sentetik canlı paket → SCAN → IDENTIFY → NAVIGATE → ASSESS → LEARNING DATA yazılım entegrasyon testleri eklendi. Gerçek etiketli saha sızıntı doğrulaması değildir.
7. **Veri taşıma:** `migrate_from_02.py` eski sürümün iki SQLite veritabanını tutarlı yedekle (backup API) yeni klasöre kopyalar; eskiyi değiştirmez ve hedefin üzerine yazmaz.
8. **Windows doğrulama:** `RUN_0_2_1_TESTS_WINDOWS.bat` isteğe bağlı otomatik testleri çalıştırır.

## Değişmeyenler

- SCAN, IDENTIFY, NAVIGATE, ASSESS, LEARNING DATA sözleşmeleri
- Başlangıç normal veri varsayımı ve deneysel Isolation Forest model mantığı
- İnsan beyanının bağımsız saha kanıtı sayılamaması
- Demo/replay etiketlerinin gerçek eğitim-adayı olarak dışlanması
- Canlı akışın manuel arayüz yenilemesi ve sadece yerel HTTP erişim sınırı
- Otomatik vana/pompa müdahalesinin veya kendi kendini eğitmenin bulunmaması

## Kapsam sınırı

33 otomatik test geçti. Streamlit uygulamasının tarayıcı üzerinden tam testi ve gerçek Arduino port testi mevcut ortamda gerçekleştirilemedi. Bütün yeni donanım senaryoları sahte bir seri taşıyıcıyla kontrol edildi.
