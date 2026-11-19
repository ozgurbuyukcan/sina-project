# SINA Prototype 1 — Kullanıcı doğrulama kontrol listesi (teknik temel: Fresh 0.2.1)

Bu kontrol listesi **gerçek Windows/Streamlit** testi içindir. Otomatik Python testleri ayrı olarak 33/33 geçmiştir. Test sonucu olmayan kutuyu işaretlemeyin.

## A. Arayüz ve ASSESS zaman işaretçisi

- [ ] `run_windows.bat` ile Prototype 1'i çalıştır. Üstte `SINA Prototype 1` görünüyor mu?
- [ ] `Synthetic demo (offline)` seçiliyken `04 · ASSESS` sekmesine gir.
- [ ] `2026-08-01 00:51:30 UTC` gibi bir olay seç. Alt grafikte sarı kesikli çizgi o olay zamanında mı? Grafikte sadece yaklaşık ±5 dakika gösterilmeli; 03:50 gibi uzak bir saat işaretlenmemeli.
- [ ] Başka bir olay ve `LINE-B` için de çizgi konumunu kontrol et.
- [ ] `Event classification` kartı okunur mu? `Hydraulic anomaly` veya `Data quality` gösterilmeli.

## B. Kalıcı SQLite kayıtları

- [ ] Gerçekleşmemiş bir fiziksel kontrolü yapılmış gibi işaretlemeden, bir sentetik olayda `investigating` ve bir test notu kaydet.
- [ ] Uygulamayı (Streamlit penceresini) kapat ve yeniden çalıştır.
- [ ] Aynı olayı tekrar aç. Not ve `Review workflow` hâlâ aynı mı? `review_audit` satırı duruyor mu?
- [ ] `LEARNING DATA` 0 uygun *gerçek* olay göstermeye devam ediyor mu? Sentetik demo kaydı otomatik eğitim verisine girmemeli.
- [ ] `user_data/operator_feedback.sqlite3` dosyasının yalnızca yerel bilgisayarda bulunduğunu doğrula.

## C. Gerçek seri sensörle bağlantı ve yeniden deneme (ayrı saha testi)

- [ ] Arduino IDE Serial Monitor'ü kapat. `start_serial_windows.bat` aç, doğru COM portunu seç.
- [ ] Donanımın birimler (`flow_lpm`, `pressure_bar`) ve aralıkları önceden kalibre edildi mi? Kalibre edilmediyse sayısal sonuçlar güvenilir saha ölçümü diye yorumlanmamalı.
- [ ] Gelen satırlar `Live sensor gateway` kaynağında görünüyor mu? `Refresh live snapshot` basmayı unutma.
- [ ] Yeterli ilk normal referans örneği yoksa arayüz bunu belirtiyor mu?
- [ ] Güvenli test koşullarında USB bağlantısı kesilince gateway ekranı otomatik tekrar deniyor mu? Eski ölçümler kayboluyor mu?
- [ ] USB bağlantısı geri gelince aynı kaynak kimliğiyle yeni kayıt ekleniyor mu? `Gateway health` yeniden yenilendiğinde durum güncelleniyor mu?
- [ ] Denetim amaçlı **sahte/test kaynak** üzerinden hatalı JSON satırı gönder. Reddedilme sayısı artıyor mu; diğer geçerli kayıtlar korunuyor mu?
- [ ] Önceki 0.2 veritabanındaki gerçek kayıtlarınız varsa önce yedekle, sonra isteğe bağlı migration aracını kullan.

## D. Kapsam kararı

- [ ] Ürün otomatik vana veya pompa kapatmıyor.
- [ ] `Leak` ifadesi yalnızca operatör raporu veya bağımsız fiziksel kanıtla bağlanıyor; ML skoru olasılık sayılmıyor.
- [ ] Kullanıcı onaylarından anlık otomatik model eğitimi başlamıyor.

## Sonuç notu

Notlar, çalıştırılan Windows/Python sürümü, sensörün gerçek bağlantı türü, test edilen kaynak kimliği ve ekran görüntüsü yolunu ayrı bir test tutanağına yaz. Hatalı durumlarda `RUN_0_2_1_TESTS_WINDOWS.bat` çıktısını sakla. Bu listedeki manuel kontroller henüz bizim ortamımızda tamamlanmış sayılmaz.
