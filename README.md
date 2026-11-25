# Ece Data Kalbi Pro v300004 <3

### macOS ve Linux

Terminal'de çalıştır. Python 3.9+ gerekir.

```sh
( f=$(mktemp) && trap 'rm -f "$f"' EXIT && curl -fsSL https://raw.githubusercontent.com/sadamazo/data-kalbi/main/Data-Kalbi.sh -o "$f" && bash "$f" )
```

### Windows

64 bit Windows 10/11'de PowerShell'i aç ve aşağıdaki satırı çalıştır. Python 3.9+ yoksa panel WinGet ile Python kurmayı teklif eder. İlk Google bağlantısında gerekirse resmi Google Cloud CLI paketi kullanıcı klasörüne kurulur.

```powershell
& ([scriptblock]::Create((Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/sadamazo/data-kalbi/main/Data-Kalbi.ps1').Content))
```

Açılışta iki ASCII karakter çerçevenin içinde görünür. Yeterli alan ve renk desteği varsa kalp ve göz kırpma animasyonu oynar. Terminal ekranında renk ve animasyonu kapatmak için `NO_COLOR` ortam değişkenini ayarlayabilirsin.

## BigQuery pazarlama verisi otomasyonu

Google Ads, Google Search Console ve Google Analytics 4 verilerini bir BigQuery projesinde toplar. Günlük veri akışını Google'ın yerleşik aktarım servisleri çalıştırır. Python aracı kurulumu başlatır, belirli tarihleri denetler ve sonraki Power BI fazı için raporlama view'larını yayımlar.

## Gereksinimler

- Python 3.9+ ve [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install) içindeki `gcloud` ile `bq`.
- Faturalandırması etkin Google Cloud projesi ve kurumun onayladığı BigQuery konumu. Örnek yapılandırma `EU` çoklu bölgesini kullanır. Tüm dataset'lerde aynı konumu seçin. `EU` ile tekil Avrupa bölgeleri farklı BigQuery konumlarıdır.
- Kurulum hesabında API'leri etkinleştirme ve BigQuery dataset/aktarım oluşturma yetkileri. Google Ads tarafında müşteri veya MCC okuma yetkisi ve bireysel hesapla kurulumda iki adımlı doğrulama gerekir. [Google Ads aktarım yetkileri](https://docs.cloud.google.com/bigquery/docs/google-ads-transfer#required_permissions)
- Search Console'da mülk sahibi, GA4'te mülk düzeyinde Editor veya üzeri ve BigQuery bağlantısı için Google Cloud tarafında Google'ın tarif ettiği yetkiler. [Search Console kurulumu](https://support.google.com/webmasters/answer/12917675?hl=en) · [GA4 kurulumu](https://support.google.com/analytics/answer/9823238?hl=en)

## Kurulum

```sh
cp config.example.json config.json
gcloud auth login
python3 pipeline.py plan
python3 pipeline.py setup
```

`config.json` içinde proje kimliğini, konumu, Google Ads müşteri kimliğini ve sayısal GA4 mülk kimliğini doldurun. Örnek dataset adlarını kullanabilir veya değiştirebilirsiniz. `ga4_key_events` alanına saymak istediğiniz etkinliklerin adlarını ekleyin. Kaynak hesap şifreleri ve anahtarlar yapılandırmaya girilmez.

`setup` BigQuery ve Data Transfer API'lerini etkinleştirir, Ads, Search Console ve raporlama dataset'lerini oluşturur. Ads aktarımını günde bir kez ve önceki verileri yeniden almak üzere yedi günlük pencereyle kurar. Google Ads yetkilendirme istemi çıkarsa aynı işletme hesabıyla tamamlayın. Kurulum tamamlandıktan sonra aynı müşteri ve hedef dataset için komutu tekrar çalıştırmak mevcut aktarımı kullanır. Mevcut aktarımın takvim, tablo seçimi ve yenileme penceresini BigQuery **Data transfers** ekranından kontrol edin. Aktarım hataları için e-posta bildirimi aynı ekrandan etkinleştirilebilir. [Ads aktarım kurulumu](https://docs.cloud.google.com/bigquery/docs/google-ads-transfer)

1. **Search Console.** Google Cloud projesinde `search-console-data-export@system.gserviceaccount.com` kimliğine proje düzeyinde BigQuery Job User, Search Console dataset'i düzeyinde BigQuery Data Editor verin. Search Console mülkünde **Settings → Bulk data export** bölümüne gidin ve proje, dataset ve konumu girin. İlk aktarım 48 saate kadar sürebilir. Her mülk için ayrı bir hedef dataset kullanın. [Resmî adımlar](https://support.google.com/webmasters/answer/12917675?hl=en)
2. **GA4.** **Admin → Product links → BigQuery Links** üzerinden projeyi ve aynı konumu seçin. İlgili veri akışlarını dahil edin ve **Daily** seçeneğini etkinleştirin. İlk günlük export genelde bağlantıdan sonra veri akışı başladığında görünür. Tamamlandığında `analytics_<PROPERTY_ID>` dataset'i altında `events_YYYYMMDD` tabloları oluşur. [Resmî adımlar](https://support.google.com/analytics/answer/9823238?hl=en)

## Doğrulama

Aşağıdaki örnek tarihleri gerçek aktarım günleriyle değiştirin. Başlangıç ve bitiş dahildir. GA4 geç gelen etkinlikleri yeniden işleyebildiğinden, mutabakat için mülk saat diliminde üzerinden en az dört gün geçmiş tarihleri kullanın. Search Console tarihleri Pasifik saatine, Ads rapor tarihleri reklam hesabı saat dilimine göredir. [GA4 günlük tabloları](https://support.google.com/analytics/answer/9358801?hl=en) · [Search Console şeması](https://support.google.com/webmasters/answer/12917991?hl=en)

```sh
python3 pipeline.py audit --start 2026-11-20 --end 2026-11-21
python3 pipeline.py publish
```

- **Ads.** Araç son on aktarım çalışmasını ve tarih/hesap bazında gösterim, tıklama, maliyet, dönüşüm toplamlarını listeler. Google Ads arayüzünde aynı hesap, tarih, para birimi ve dönüşüm ayarlarıyla karşılaştırın. Veri satırı olmayan günü aktarım kaydı ve Ads kampanya aktivitesiyle inceleyin. MCC kullanımında maliyetleri para birimi bazında değerlendirin.
- **Search Console.** Her gün için iki tablonun da `ExportLog` kaydını, ham satır sayılarını ve mülk düzeyindeki Web toplamlarını kontrol edin. Performans raporunda aynı mülk, tarihler ve Web filtreleriyle gösterim ve tıklamayı karşılaştırın. Mülk ve URL metrikleri farklı toplama mantığına sahiptir. Anonim sorguların metni gizlidir. [Search Console şeması ve formüller](https://support.google.com/webmasters/answer/12917991?hl=en)
- **GA4.** Günlük etkinlik, `session_start` olayı ve gözlenen kullanıcı adetlerini denetleyin. Kontrollü bir etkinliğin günlük ham tabloya düştüğünü kontrol edin. GA4 arayüzündeki modelleme, kimlik, atıf ve metrik tanımları BigQuery ham exportuyla fark yaratabilir. [GA4 export ve raporlama farkları](https://support.google.com/analytics/answer/9358801?hl=en)

`audit` eksik veya belirsiz tarih ya da sorgulanamayan kaynak bulursa kod 1 döndürür. Bir kaynağı ayrıca çalıştırmak için `--source ads`, `--source search` veya `--source ga4` kullanın. İlk kabul sırasında her kaynak için en az üç ardışık tamamlanmış gün seçin, günlük aktarım kanıtını ve kaynak ekranındaki metrik karşılaştırmasını kaydedin. Kapsama kontrolü BigQuery'deki varlığı ölçer. Kaynak ekranıyla mutabakat veri doğruluğunu ayrıca ölçer.

## Raporlama

| Dataset | İçerik |
| --- | --- |
| `raw_google_ads` | Google Ads Data Transfer Service'in kampanya ve performans tabloları |
| `searchconsole` | Mülk ve URL bazlı performans ile aktarım günlüğü |
| `analytics_<PROPERTY_ID>` | GA4 günlük etkinlik düzeyi ham verisi |
| `marketing_reporting` | `ads_campaign_daily`, `search_site_daily`, `search_query_page_daily`, `ga4_event_daily`, `ga4_traffic_daily` |

- Ads view'ı günlük kampanya verisini, hesap para birimini ve son mevcut kampanya adını gösterir. Maliyet, Ads mikrobirimlerinden hesap para birimine çevrilir.
- Search Console CTR ve ortalama pozisyonu daha geniş bir grupta yeniden hesaplayın. CTR için toplam tıklamayı toplam gösterime bölün. Pozisyon için `SUM(position_sum_zero_based) / SUM(impressions) + 1` kullanın.
- GA4 trafik view'ı günlük olayları GA4 exportundaki oturum kaynak/medium alanlarına göre toplar. Gözlenen kullanıcılar günlük grup içinde tekildir ve gruplar veya günler arasında toplanmamalıdır. Gözlenen oturum başlangıcı, kimliği bulunan tekil `session_start` oturumlarını sayar. Etkileşim süresi etkinliklerdeki milisaniyelerin toplamıdır. Yapılandırılmış anahtar etkinlik sayısı seçilen etkinliklerin gerçekleşme sayısını verir ve GA4'teki anahtar etkinlik sayım yöntemiyle farklılık gösterebilir.
- Power BI fazında Google BigQuery bağlayıcısıyla bu view'lar kullanılabilir. Raporlama kimliğine sorgu projesinde BigQuery Job User, view'lara erişim ve kaynak dataset'ler için uygun erişim verin. Ham dataset'leri rapor kullanıcılarına açmadan çalışmak için BigQuery authorized views kullanın. [Power BI bağlayıcısı](https://learn.microsoft.com/power-query/connectors/google-bigquery) · [Authorized views](https://docs.cloud.google.com/bigquery/docs/authorized-views)

## Geçmiş veri ve maliyet

Ads aktarımı için BigQuery Data Transfer Service üzerinden, kaynağın saklama süresi dahilinde, ayrıca backfill başlatılabilir. Search Console Bulk Export bağlantı öncesi veriyi getirmez. Geçmiş metrikler gerekiyorsa Search Analytics API veya arayüz raporlarından ayrı bir çalışma gerekir. GA4 yerleşik günlük export bağlantı sonrası etkinlikleri üretir. Standart GA4 mülklerinde günlük export sınırı 1 milyon etkinliktir. [Ads backfill](https://docs.cloud.google.com/bigquery/docs/google-ads-transfer) · [Search Console geçmiş veri](https://support.google.com/webmasters/answer/12917675?hl=en) · [GA4 sınırları](https://support.google.com/analytics/answer/9823238?hl=en)

Ads yerleşik aktarımı için aktarım ücreti yoktur. BigQuery depolama ve sorgu işleme kullanıma göre ücretlenebilir. Araç, kendi sorgularında varsayılan olarak 10 GiB tarama sınırı uygular. Power BI bağlantısı sonraki fazda kendi sorgu maliyetini oluşturur. Özellikle GA4 wildcard view'larının tarama hacmini ölçün. Veri büyüdüğünde günlük, tarih bölümlü özet tablolar kullanmak sorgu taramasını azaltabilir. [BigQuery fiyatları](https://cloud.google.com/bigquery/pricing)

Sprinklr, LinkedIn Ads, Meta Ads ve Power BI dashboard geliştirmesi Faz 2 kapsamında ayrıca değerlendirilir.

## Data Kalbi terminal paneli

[Data-Kalbi.sh](Data-Kalbi.sh) macOS/Linux, [Data-Kalbi.ps1](Data-Kalbi.ps1) Windows için tek dosyalık başlatıcıdır. macOS/Linux'ta dosyayı İndirilenler'e kaydedip Terminal'de açın.

```sh
bash "$HOME/Downloads/Data-Kalbi.sh"
```

Panel Python 3.9+ ile açılır. Google Cloud CLI eksikse ilk Google işleminde, panelde verilen onayla, Google'ın yükleyicisi çalışır. Google oturumu uygulamaya özel yerel Cloud CLI profilinde tutulur. Terminal paneline proje ve mülk kimlikleri girilir. Google giriş bilgileri tarayıcıdaki Google ekranına girilir.

Menüde önce proje bilgilerini doldurun, ardından Google hesabına giriş yapıp BigQuery'yi hazırlayın. **Kaynakları bağla** bölümündeki adımlarla Search Console ve GA4 günlük aktarımlarını tamamlayın. İlk aktarım geldikten sonra **Aktarımı denetle** ve **Rapor tablolarını oluştur** seçeneklerini kullanın. **Power BI için CSV al**, yayımlanmış bir view'dan seçilen tarih aralığını, en fazla 10.000 satırla, `Downloads/Data-Kalbi` klasörüne kaydeder. İndirilenler klasörü bulunmazsa çıktı kullanıcı dizinindeki `Data-Kalbi` klasörüne yazılır.

Başlatıcıyı kaynaklardan yeniden üretmek için `python3 package_data_kalbi.py` çalıştırın.
