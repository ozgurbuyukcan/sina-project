# SINA Fresh 0.2 — Değişiklikler

**0.1 üzerine eklendi; 0.1 analitik çekirdeği korundu.**

1. **Canlı sensör alımı:** Arduino/USB seri satırları (JSONL veya CSV), yalnızca localhost çalışan Bearer-token HTTP giriş noktası; veri saklama ve hata günlüğü SQLite üzerinde.
2. **Veri kökeni ve bütünlük:** ölçüm kaynağı türü (SERIAL/HTTP/OFFLINE_REPLAY) kalıcıdır; yeniden oynatma ve gerçek ağ geçidi aynı kaynak adına karıştırılamaz; zaman damgası kökeni, aynı ölçümün tekrarı ve çelişkili kayıtlar ayrılır.
3. **Olay inceleme merkezi:** filtrelenebilir olay kuyruğu; seçilen olay için beş dakika önce/sonra ölçümler, işaretler, açıklama, kullanıcı notu, fiziksel denetim beyanı ve audit geçmişi.
4. **Eğitim adayı kümesi:** fiziksel inceleme yapıldığı beyan edilmiş, kapatılmış, kanıtlı olaylar ile ilk-inceleme kesiti; kaynak hash'i, denetim kaydı ve değişmez bağlam özeti; CSV+manifest ZIP dışa aktarımı. Sentetik/tekrar oynatma kaynakları dışlanır.
5. **Geriye uyumluluk:** 0.1'in CSV sözleşmesi, model ayarları, ilk N sağlıklı varsayımı ve IDENTIFY çıktıları korunur.

**Yok / henüz doğrulanmadı:** Gerçek Arduino'ya bağlanarak fiziksel donanım testi, uzaktan güvenli IoT protokolü, otomatik ekran yenileme, kullanıcı yetki yönetimi, fiziksel arızanın modelce kesin tanısı, yeniden eğitim, gerçek saha doğruluğu, sahada su tasarrufu.
