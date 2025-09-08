# BLE Data Acquisition System — NRF52840 Express

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-production-green.svg)]()

Kurumsal seviye BLE veri toplama uygulaması. NRF52840 Express tabanlı cihazlardan gelen gerçek zamanlı sensör verilerini BLE (NUS) üzerinden alır, gösterir, kaydeder ve dışa aktarır. Performans, güvenlik ve üretim kullanımına uygun kullanıcı deneyimiyle tasarlanmıştır.

- Proje dosyası: main.py — Tkinter GUI tabanlı gerçek zamanlı görselleştirme, zamanlama konfigürasyonu, CSV/JSON dışa aktarımı.
- Hedef platformlar: Windows, macOS, Linux (BlueZ gereksinimleri Linux için geçerlidir).
- Mesaj protokolü: Her BLE bildirimi JSON formatında, 4 kanal için liste: [unit, timestamp, mv, raw_value] şeklinde satır sonu ('\n') ile ayrılmış.

İçindekiler
- [Özet](#özet)
- [Özellikler](#özellikler)
- [Mimari](#mimari)
- [Kurulum](#kurulum)
- [Hızlı Başlangıç (Quick Start)](#hızlı-başlangıç-quick-start)
- [Kullanım & Ekran Görüntüleri](#kullanım--ekran-görüntüleri)
- [Konfigürasyon: LED/Sıralı Zamanlama](#konfigürasyon-ledsıralı-zamanlama)
- [Veri Dışa Aktarım & Formatlar](#veri-dışa-aktarım--formatlar)
- [Üretim ve Dağıtım Notları](#üretim-ve-dağıtım-notları)
- [Güvenlik & Gizlilik](#güvenlik--gizlilik)
- [Sorun Giderme (Troubleshooting)](#sorun-giderme-troubleshooting)
- [Katkıda Bulunma & İletişim](#katkıda-bulunma--iletişim)
- [Lisans](#lisans)

Özet
----
Bu uygulama, NRF52840 Express veya benzeri BLE cihazlarından gelen yüksek frekanslı telemetri verilerini toplamak üzere tasarlanmıştır. Amacımız:
- Düşük gecikmeli gerçek zamanlı gösterim,
- Güvenilir oturum kaydı (session-based logging),
- Kullanıcı dostu zamanlama konfigürasyonu (LED sıralama),
- Kurum içi kullanım için kolay dışa aktarma ve denetim izleri.

Özellikler
---------
- Gerçek zamanlı veri akışı (yaklaşık 60 FPS için optimize edilmiş görselleştirme).
- Çok kanallı (4 kanal) veri işleme ve filtreleme.
- Thread-safe veri kuyruğu (collections.deque + threading.Lock).
- BLE tarama, bağlanma, bildirim dinleme (Bleak kütüphanesi).
- Zengin GUI: canlı grafik, istatistikler, log penceresi, kanal on/off düğmeleri.
- Gelişmiş LED zamanlama/sekans konfigürasyonu (4 girişe kadar).
- CSV ve JSON biçimlerinde dışa aktarım (lokal arşivlemeye uygun).
- Detaylı loglama (logging modülü ile).

Mimari
------
Aşağıdaki diyagramlar repo/docs/images/ altına konulacak görselleri referans eder. Lütfen ilgili PNG/SVG dosyalarını aynı adlarla ekleyin.

- Mimari diyagramı: docs/images/architecture.png
  - BLE cihazlar → BLE Gateway (Bilgisayar) → Uygulama (main.py)
  - Veri akışı: BLE JSON bildirimi → BLEDataManager.notification_handler → veri kuyrukları → GUI güncelleme & session kaydı.

- Veri akışı / zamanlama diyagramı: docs/images/timing_diagram.png

(Ek: Mimari ve akış diyagramlarınıza uygun SVG/PNG'leri docs/images/ içerisine yerleştirin.)

Kurulum
-------
Gereksinimler
- Python 3.9 veya üzeri
- pip
- Sistem BLE desteği:
  - Linux: BlueZ (sudo apt install bluez libbluetooth-dev) ve kullanıcı için bluetooth yetkileri
  - macOS: yerel BLE desteği
  - Windows: uygun BLE sürücüleri

Örnek bağımlılıklar (requirements.txt oluşturunuz):
- bleak
- matplotlib
- numpy

Örnek requirements.txt
```
bleak>=0.20.0
matplotlib>=3.0
numpy>=1.19
```

Yerel geliştirme ortamı
1. Klonlayın:
   git clone https://github.com/bytemounts/ugurhoca.git
2. Sanal ortam oluşturup etkinleştirin:
   python -m venv .venv
   source .venv/bin/activate  (Windows: .venv\Scripts\activate)
3. Bağımlılıkları yükleyin:
   pip install -r requirements.txt
4. Gerekirse GUI kitaplıkları ve sistem BLE ayarlarını doğrulayın.

Hızlı Başlangıç (Quick Start)
-----------------------------
1. Sanal ortamı aktif edin.
2. main.py'yi çalıştırın:
   python main.py
3. Uygulama açıldığında:
   - SCAN tuşuna basın.
   - Uygun cihazı seçin.
   - CONNECT ile bağlanın.
   - START ile kaydı başlatın.
   - STOP ile kaydı durdurun ve EXPORT ile CSV/JSON dışa aktarın.

Kullanım & Ekran Görüntüleri
---------------------------
Lütfen aşağıdaki görselleri docs/images/ klasörüne koyun:

- Gerçek zamanlı grafik: docs/images/screenshot_graph.png
- Zamanlama konfigürasyon ekranı: docs/images/timing_config.png
- Uygulama ana ekranı: docs/images/screenshot_main.png

README içinde referans örneği:
![Canlı Grafik](docs/images/screenshot_graph.png)
![Zamanlama Konfigürasyonu](docs/images/timing_config.png)

Konfigürasyon: LED / Sıralı Zamanlama
------------------------------------
Uygulama birden fazla "Timing Entry" (zamanlama girişi) tanımlamaya izin verir. Her giriş:
- enabled (aktif/pasif)
- time_open_ms: LED açık kalma süresi (ms)
- time_delay_ms: ölçüm başlamadan önce bekleme (ms)
- time_read_ms: ADC okuma süresi (ms)
- target sensor: hangi sensöre atandığı

Sistem toplam döngü süresini hesaplar ve frekansı (Hz) önizleme alanında gösterir. Üretim ortamında:
- Toplam cycle_time düşükse (çok yüksek frekans) BLE bant genişliği/cihaz kaynak kullanımı gözlenmelidir.
- Önerilen başlangıç değerleri: time_open=100 ms, time_delay=50 ms, time_read=10 ms.

Veri Dışa Aktarım & Formatlar
-----------------------------
- CSV: Nokta yerine virgül ayarı, alan ayracı `;` kullanılır (bölgesel uyumluluk amaçlı). Başlık satırı:
  timestamp;datetime;Channel0_(mV);Channel0_raw;Channel1_(mV);Channel1_raw;...
- JSON: session_info, timing_configurations ve sensor_data içeren hiyerarşik çıktı.

Örnek JSON yapısı (kısa):
{
  "session_info": { "export_time": "...", "total_records": 100 },
  "timing_configurations": { "sensor_0": { "timing_entries": [ ... ] } },
  "sensor_data": [ { "timestamp": ..., "datetime": "...", "sensors": { "0": {"raw":..., "real":...} } } ]
}

Üretim ve Dağıtım Notları
------------------------
- GUI uygulaması PyInstaller veya cx_Freeze ile paketlenebilir. PyInstaller kullanıyorsanız matplotlib backend ve Tcl/Tk kaynaklarının paketlendiğinden emin olun.
- Windows hizmeti veya macOS menü çubuğu uygulaması için ayrı dağıtım hedefleri planlayın.
- Uzaktan izleme gerekiyorsa WebSocket veya MQTT tabanlı bir bridge geliştirmeyi düşünün (veri hacmi ve güvenlik gereksinimlerine göre).

Güvenlik & Gizlilik
-------------------
- BLE bağlantıları üretim ortamında yetkilendirme ve cihaz sertifikasyonu ile korunmalıdır.
- Dışa aktarılan veriler hassas olabilir; disk şifreleme ve erişim kontrolleri uygulanmalıdır.
- Loglarda hassas cihaz adresleri veya kullanıcı veri bırakmamaya dikkat edin.

Performans İpuçları
-------------------
- MAX_DATA_POINTS sabitini gereksinime göre ayarlayın. Daha yüksek değer bellek kullanımını artırır.
- ANIMATION_INTERVAL ve plot güncelleme frekansları, GUI yanıtı ile veri bütünlüğü arasında denge sağlar.
- Çok yüksek örnekleme hızlarında veri özetlemeyi (downsample) tercih edin.

Sorun Giderme (Troubleshooting)
-------------------------------
- Cihaz görünmüyor:
  - BLE adapter etkin mi? (Linux: sudo systemctl status bluetooth)
  - Kullanıcı bluetooth grubu üyeliği kontrolü.
- Bağlantı sık kopuyor:
  - Sinyal gücü, cihaz firmware'i ve BLE parametrelerini gözden geçirin.
  - Bleak sürümü ve işletim sistemi BLE sürücülerini güncelleyin.
- Matplotlib gösterimi yavaş:
  - ANIMATION_INTERVAL artırın (ör. 100 ms veya daha).
  - Line çizimlerini basitleştirin (marker kaldırın, linewidth azaltın).

Katkıda Bulunma & İletişim
--------------------------
Kurumsal katkılar için:
1. Yeni özellik/bugfix talebi için issue açın.
2. Değişiklikler için branch → PR akışı kullanın.
3. Kod standartları: yapısal tipler, thread-safe veri erişimi ve kapsamlı loglama ekleyin.
4. CI pipeline önerisi: Python unit tests (pytest), linting (flake8/black), paket oluşturma (GitHub Actions).

Destek: bytemounts GitHub organizasyonu veya proje yöneticisi ile iletişime geçin.

Lisans
------
Bu depo MIT lisansı ile lisanslanmıştır. (LICENSE dosyasını kontrol edin.)

Ek Notlar
---------
- README içindeki resim yollarını repo'nuzdaki gerçekteki dosya isimleriyle eşleştirin: docs/images/*.png
- Üretim için: sistem servisi/daemon, otomatik güncelleme ve merkezi loglama (ELK/Prometheus) entegrasyonlarını planlayın.

İletişim / Sürdürme
-------------------
- Proje sahibi: BytemountsTeam
- Repo: https://github.com/bytemounts/ugurhoca

Teşekkürler — kurumsal dağıtıma uygun hale getirmek isterseniz CI/CD şablonları, paketleme betikleri ve örnek devops dokümanları hazırlayabilirim.
