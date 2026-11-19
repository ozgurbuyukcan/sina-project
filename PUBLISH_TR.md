# SINA GitHub Pages — Türkçe yayımlama rehberi

Bu ZIP **yalnızca herkese açık web sitesini** içerir. SINA'nın özel program kodu, veri tabanı, sensör anahtarı veya yerel kullanıcı kayıtları eklenmedi.

## Kurulum
1. [GitHub](https://github.com/) hesabında **New repository** seçeneğine tıkla.
2. Depoya örneğin **sina-project** adını ver, **Public** seç ve oluştur. (Kendi adı istediğin gibi değiştirebilirsin.)
3. ZIP'i aç. İçindeki `docs/` klasörünü, `README.md` ve `.gitignore` dosyalarını depoya yükle. GitHub web arayüzünde **Add file → Upload files** kullanabilirsin. `docs` klasör yapısı korunmalı. GitHub tarayıcı sürükle-bırak desteklemiyorsa dosyaları GitHub Desktop ile ekle.
4. `Settings → Pages → Build and deployment` bölümüne git; `Source: Deploy from a branch`, `Branch: main`, `Folder: /docs` seç ve **Save** yap.
5. Birkaç dakika sonra Pages kısmında gerçek site adresi görünür. Örnek biçim: `https://KULLANICIADIN.github.io/sina-project/`. Kullanıcı adını bilmediğim için bu bir *örnek* bağlantıdır.
6. Siteyi telefonda ve masaüstünde dene; beş sekmeyi tıklayıp görselleri kontrol et. Sonra adresi Xylem Freestyle Section metnindeki bağlantı düğmesiyle ekle.

## Free Section için önerilen metin
**Explore SINA — Technical Project Showcase**

Explore our working hydraulic monitoring and decision-support prototype, including the SCAN → IDENTIFY → NAVIGATE → ASSESS workflow, the LEARNING DATA research module, real but unlabeled irrigation measurements, software-test evidence, and the limitations of our current validation. The interface images demonstrate simulated data; no field leak-detection accuracy is claimed.

**Project website:** [Buraya GitHub Pages adresini link olarak ekle]

## Yayın öncesi kontrol
- Tam SINA kaynak kodunu GitHub'a açmak isteyip istemediğini ayrıca kararlaştır.
- `docs/assets/` içindeki görüntülerin çevrimiçi yayımlanmasını onayla; hepsi gönderdiğin arayüz ekranlarıdır.
- Gizli sensör kimlikleri, tokenlar, kişisel veriler, SQLite dosyaları veya kullanıcı CSV'lerini GitHub'a yükleme.
- Sitedeki teknik test raporunun 33 software test sonucu ile fiziksel saha doğrulamasını karıştırma.
- Ekran görüntüleri **sentetik demoya**, 911 ölçümlük grafik **gerçek fakat etiketlenmemiş araştırma verisine** ait. Ayrı deneylerdir.
- Siteyi GitHub Pages'te etkinleştirmek sitenin **herkes tarafından görülebilir** olması demektir.
- Xylem'e başvuru için gereken **sesli sunum + demo videosunun yerine geçmez**; destekleyici bağlantıdır.
