# BLE Veri Toplama Sistemi v2.0 - NRF52840 Express

 src="<img width="1915" height="984" alt="image" src="https://github.com/user-attachments/assets/2ae05333-3ad2-461b-adcb-9760e6492c52" />
" />

*Gerçek zamanlı veri görselleştirmesi ve 4 kanal kontrol paneli*

## Genel Bakış

Bu  BLE (Bluetooth Low Energy) veri toplama sistemi, NRF52840 Express mikrokontrolörü ile gerçek zamanlı sensör verilerini toplamak, analiz etmek ve görselleştirmek için geliştirilmiştir. Sistem, endüstriyel kalitede bir kullanıcı arayüzü sunarak, çoklu kanal veri akışını yönetir ve gelişmiş LED zamanlama konfigürasyonları sağlar.

### Ana Özellikler

- **Gerçek Zamanlı Veri Görselleştirme**: 60 FPS ile optimize edilmiş grafik güncellemeleri
- **4 Kanal Eşzamanlı İzleme**: Bireysel kanal kontrolleri ve görünürlük ayarları
- **Gelişmiş LED Zamanlama Sistemi**: Profesyonel timing konfigürasyonu
- **Çoklu Format Dışa Aktarım**: CSV ve JSON format desteği
- **Performans İzleme**: Gerçek zamanlı veri akış hızı göstergesi

## Sistem Arayüzü

### Ana Panel


Yukarıdaki ekran görüntüsü, sistemin ana bileşenlerini göstermektedir:

1. **Üst Header**: Sistem başlığı, tarih/saat bilgisi ve performans göstergesi
2. **Kontrol Paneli**: Renkli butonlarla tüm sistem operasyonları
3. **Gerçek Zamanlı Grafik**: 4 kanallı kombinasyon görünümü
4. **Sağ Panel**: Kanal kontrolleri ve anlık değer gösterimi
5. **Alt Durum Çubuğu**: Bağlantı durumu ve sistem mesajları

### Kanal Kontrol Sistemi
<img width="200" height="795" alt="image" src="https://github.com/user-attachments/assets/266d04bd-1a23-433b-a35f-d968a1619aac" /> <img width="203" height="795" alt="Screenshot 2025-09-12 173051" src="https://github.com/user-attachments/assets/02f49cc2-6820-40c4-b9e5-68d5080c5eac" />



Sağ paneldeki kanal kontrolleri şunları sağlar:
- **Kanal Enable/Disable**: Her kanalı ayrı ayrı etkinleştir
- **Anlık Değer Gösterimi**: mV cinsinden gerçek zamanlı ölçüm
- **Ham Veri Görüntüleme**: 12-bit ADC değerleri
- **Renk Kodlama**: Grafikteki çizgi renkleri ile eşleşen buton renkleri

## Teknik Özellikler

### Sistem Mimarisi
- **Platform**: Python 3.7+ ile geliştirilmiş masaüstü uygulaması
- **BLE İletişim**: Nordic UART Service (NUS) protokolü
- **Gerçek Zamanlı İşleme**: 60 FPS optimizasyonu ile düşük gecikme
- **Veri Formatı**: JSON tabanlı veri akışı
- **Grafik Arayüz**: Tkinter ve Matplotlib entegrasyonu

### Donanım Gereksinimleri
- NRF52840 Express geliştirme kartı
- Bluetooth 5.0 uyumlu bilgisayar
- Windows 10/11, macOS 10.15+, veya Ubuntu 18.04+

### Performans Spesifikasyonları
- **Maksimum Örnekleme Hızı**: 1000 Hz
- **Kanal Sayısı**: 4 eşzamanlı analog kanal
- **Gecikme Süresi**: <16 ms (gerçek zamanlı görselleştirme)
- **Veri Çözünürlüğü**: 12-bit ADC (0-4095)
- **Voltaj Aralığı**: 0-3.3V (mV cinsinden hassasiyet)

## Kurulum

### Gerekli Bağımlılıklar

```bash
pip install -r requirements.txt
```

**requirements.txt**:
```
asyncio
bleak>=0.20.0
matplotlib>=3.5.0
numpy>=1.21.0
tkinter
```

### Sistem Gereksinimleri
- Python 3.7 veya üzeri
- Bluetooth adapter (BLE destekli)
- Minimum 4GB RAM
- 100MB disk alanı

## Kullanım Kılavuzu

### 1. Uygulama Başlatma

```bash
python ble_data_acquisition.py
```

### 2. Cihaz Bağlantısı

<img width="395" height="91" alt="image" src="https://github.com/user-attachments/assets/3f931e3c-d812-4bbe-a733-c13ab5a30617" />


1. **SCAN** butonuna tıklayın (mor renk)
2. Uyumlu cihazları açılan listeden seçin
3. **CONNECT** butonuna tıklayın (mavi renk)
4. Bağlantı durumu sağ alt köşede "Connected" olarak görüntülenir

### 3. Veri Toplama

<img width="505" height="80" alt="image" src="https://github.com/user-attachments/assets/16e61be0-af23-46d8-bde2-8277101e1492" />


1. **START** butonu (yeşil) ile kayıt başlatın
2. Gerçek zamanlı grafik güncellenir
3. **STOP** (kırmızı) ile kaydı durdurun
4. **EXPORT** (mor) ile verileri kaydedin

### 4. Kanal Yönetimi

Sağ paneldeki kanal butonları ile:
- **ENABLED/DISABLED**: Kanalları etkinleştir/devre dışı bırak
- **Value**: Anlık mV değerlerini görüntüle
- **Raw**: Ham ADC verilerini izle

Her kanal farklı renk koduna sahiptir:
- **Kanal 0**: Kırmızı (#e74c3c)
- **Kanal 1**: Mavi (#3498db)
- **Kanal 2**: Yeşil (#2ecc71)
- **Kanal 3**: Turuncu (#f39c12)

## LED Zamanlama Konfigürasyonu


<img width="995" height="778" alt="image" src="https://github.com/user-attachments/assets/da1492a1-38fb-4d7a-a565-efc0c21be1a2" /> 


**TIMING** butonu ile erişilen  konfigürasyon paneli:

### Zamanlama Parametreleri
- **Time Open (ms)**: LED açık kalma süresi (1-10000 ms)
- **Time Delay (ms)**: Ölçüm öncesi gecikme (1-10000 ms)
- **Time Read (ms)**: ADC okuma süresi (1-10000 ms)
- **Target Sensor**: Hedef sensör seçimi (0-3)

### Performans Hesaplamaları
- **Toplam Döngü Süresi**: Tüm aşamaların toplamı + 10ms buffer
- **Sistem Frekansı**: 1000 / Toplam Döngü Süresi (Hz)
- **Saniyedeki Örnek**: Frekans × Aktif Sekans Sayısı

### Zamanlama Örnekleri

| Konfigürasyon | Time Open | Time Delay | Time Read | Döngü Süresi | Frekans |
|---------------|-----------|------------|-----------|--------------|---------|
| Hızlı         | 50 ms     | 10 ms      | 5 ms      | 75 ms        | 13.3 Hz |
| Standart      | 100 ms    | 50 ms      | 10 ms     | 170 ms       | 5.9 Hz  |
| Hassas        | 200 ms    | 100 ms     | 50 ms     | 360 ms       | 2.8 Hz  |

### Konfigürasyon Özeti Paneli
Zamanlama panelinin alt kısmında gerçek zamanlı hesaplamalar görüntülenir:
```
Configuration Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Active Sequences: 2/4
Total Cycle Time: 340 ms
System Frequency: 2.94 Hz
Samples/Second: 5.9

Sensor Distribution:
  • Sensor 0: 1 sequence(s)
  • Sensor 1: 1 sequence(s)
```

### 5. State Butonu


<img width="132" height="62" alt="image" src="https://github.com/user-attachments/assets/1d6d4e5e-401e-4449-a265-833c348f6863" /> <img width="125" height="53" alt="image" src="https://github.com/user-attachments/assets/8499d32c-b864-4db6-a2b7-0402f162d186" />


### Genel Bakış

**STATE** (Durum) butonu, **nRF52840** sisteminin genel durumunu **BLE Veri Toplama Sistemi** grafik arayüzünden kontrol etmenizi sağlar. Bu buton, sistemi uzaktan etkinleştirme veya devre dışı bırakma için doğrudan bir kontrol sunar.

### Özellikler

#### Buton Durumları

  - **STATE ON** (Açık) (Yeşil `#1abc9c`): Sistem etkin.
  - **STATE OFF** (Kapalı) (Kırmızı `#e74c3c`): Sistem devre dışı.
  - **Devre Dışı** (Gri `#95a5a6`): Bluetooth bağlantısı yok.

#### Davranış

**Bluetooth Bağlantısı Kurulduğunda:**

  - Buton otomatik olarak etkinleşir.
  - Varsayılan durum **ON**'dur (etkin).
  - nRF52840 sistemi, başlangıç durumunu anında alır.

**Durum Değiştirme:**

  - Tek tıklama: Sistem durumunu değiştirir (**ON** ↔ **OFF**).
  - Görsel değişiklik: Butonun rengi ve metni anında güncellenir.
  - Otomatik iletim: Durum, Bluetooth üzerinden nRF52840'a gönderilir.

**Bağlantı Kesildiğinde:**

  - Buton devre dışı kalır (grileşir).
  - Durum, bir sonraki bağlantı için bellekte saklanır.

### İletişim Formatı

nRF52840'a gönderilen **JSON** mesajları:

  - **Sistem etkin:**
    ```json
    {
      "state": true
    }
    ```
  - **Sistem devre dışı:**
    ```json
    {
      "state": false
    }
    ```

#### İletim Protokolü

  - **Taşıyıcı:** BLE UART Hizmeti (NUS).
  - **Kodlama:** UTF-8.
  - **Sonlandırma:** Yeni satır karakteri (`\n`).
  - **Parçalama:** Uzun mesajlar 20 baytlık parçalara bölünür.
  - **Onay:** Kullanıcı arayüzündeki kayıtlar (loglar) aracılığıyla.

### Kullanıcı Arayüzü

#### Konum

**STATE** butonu, ana kontrol çubuğunda, **CLEAR** (Temizle) butonundan sonra yer alır.

#### Görsel Göstergeler

  - **Yeşil renk:** **ON** durumu - Sistem çalışıyor.
  - **Kırmızı renk:** **OFF** durumu - Sistem duraklatıldı.
  - **Gri renk:** Buton devre dışı - Bağlantı yok.

#### Kayıt Mesajları (Log Mesajları)

  - `System state changed to: ON/OFF` - Yerel değişiklik.
  - `✓ State ON/OFF sent to nRF52840` - Başarılı iletim.
  - `✗ Failed to send state to nRF52840` - İletim hatası.
  - `✗ State send error: [details]` - Teknik hata.

### Pratik Kullanım

#### Tipik Kullanım Durumları

  - **Sistemi duraklatma:** Bağlantıyı kesmeden ölçümleri geçici olarak durdurma.
  - **Bakım modu:** Bakım veya kalibrasyon için LED'leri durdurma.
  - **Enerji tasarrufu:** nRF52840'ın tüketimini azaltma.
  - **Deneysel kontrol:** Deneylerin başlangıç/bitişini senkronize etme.

#### Önerilen İş Akışı

1.  Bluetooth üzerinden nRF52840'a bağlanın.
2.  Sistem otomatik olarak **ON** durumunda başlar.
3.  İhtiyaçlara göre veri alımını kontrol etmek için **STATE** butonunu kullanın.
4.  Durum değiştirildiğinde, devam eden veriler korunur.
5.  Bağlantı kesildiğinde buton otomatik olarak devre dışı kalır.

### Hata Yönetimi

#### İletim Hataları

  - Gönderim başarısız olursa, yerel durum geri yüklenir.
  - Kayıtlarda bir hata mesajı görünür.
  - Arayüz, sistemin gerçek durumuyla tutarlı kalır.

#### Bağlantı Kaybı

  - Buton otomatik olarak devre dışı kalır.
  - Durum, yeniden bağlantı için saklanır.
  - Kullanıcıdan herhangi bir işlem gerekmez.

### Sistem Entegrasyonu

#### Bağımlılıklar

  - nRF52840 ile aktif Bluetooth bağlantısı.
  - Çalışır durumda olan NUS (Nordic UART Service) hizmeti.
  - BLE Veri Toplama Sistemi v2.0 arayüzü.

#### Uyumluluk

  - Tüm LED zamanlama modlarıyla uyumludur.
  - Devam eden veri alımına müdahale etmez.
  - Sensör yapılandırmalarından bağımsız çalışır.

### Teknik Notlar

#### Performans

  - İletim neredeyse anlıktır (\< 100ms).
  - Gerçek zamanlı veri alımı üzerinde hiçbir etkisi yoktur.
  - Bluetooth iletişimlerinin eş zamansız (asenkron) yönetimi.

#### Güvenlik

  - Göndermeden önce bağlantı kontrolü.
  - İletim zaman aşımlarının yönetimi.
  - Başarısızlık durumunda otomatik geri yükleme.

#### Ölçeklenebilirlik

  - Gelecekteki özellikler için genişletilebilir JSON yapısı.
  - Daha karmaşık durumlara uygun mimari.
  - Gelişmiş sistem komutlarına hazır arayüz.


## Veri Formatları

### CSV Dışa Aktarım
```csv
timestamp;datetime;Channel_0_(mV);Channel_0_raw;Channel_1_(mV);Channel_1_raw;...
1641234567.123;2024-01-03T10:30:45.123456;1234,56;2048;2345,67;3072;...
```

### JSON Dışa Aktarım
```json
{
  "session_info": {
    "export_time": "2024-01-03T10:30:45.123456",
    "total_records": 10000,
    "duration_seconds": 300.45
  },
  "timing_configurations": {
    "sensor_0": {
      "name": "Channel 0",
      "unit": "mV",
      "timing_entries": [
        {
          "index": 1,
          "state": true,
          "time_open_ms": 100,
          "time_delay_ms": 50,
          "time_read_ms": 10,
          "pin": 1,
          "enabled": true,
          "cycle_time_ms": 170,
          "frequency_hz": 5.88
        }
      ]
    }
  },
  "sensor_data": [...]
}
```

## İstatistik ve Log Sistemi

### İstatistik Sekmesi
<img width="1195" height="366" alt="image" src="https://github.com/user-attachments/assets/5731de7b-fb75-4a7e-8c99-80a9383a8643" />


Ana arayüzün **Statistics** sekmesinde her kanal için:
- **Current (mV)**: Anlık değer
- **Min (mV)**: Minimum değer
- **Max (mV)**: Maksimum değer
- **Avg (mV)**: Ortalama değer
- **Count**: Toplam örnek sayısı

### Log Sistemi


**Log** sekmesinde sistem mesajları gerçek zamanlı görüntülenir:
```
[11:51:51.123] System Ready - Real-time Mode
[11:51:55.456] Scanning for BLE devices...
[11:52:00.789] Found compatible device: NRF52840_Device
[11:52:02.345] Connected to NRF52840_Device - Real-time mode enabled
[11:52:05.678] Recording started
```

## Sistem Mimarisi

### Sınıf Yapısı

#### `BLEDataManager`
- BLE iletişim yönetimi
- Veri tamponu optimizasyonu
- Thread-safe veri erişimi
- Performans izleme

#### `SensorConfig`
- Sensör konfigürasyon yönetimi
- Kalibrasyon parametreleri
- LED zamanlama ayarları

#### `TimingEntry`
- LED kontrol sekansları
- Zamanlama hesaplamaları
- Frekans optimizasyonu

#### `BLEDataAcquisitionGUI`
- Kullanıcı arayüz yönetimi
- Gerçek zamanlı görselleştirme
- Veri dışa aktarım işlemleri

### Veri Akış Diyagramı

```
NRF52840 → BLE → PC → JSON Parser → Data Manager → GUI Components
    ↑                                         ↓              ↓
LED Control ←─────────── Timing Config   Real-time Plot  Statistics
Sequences                                   Channel Controls  Logs
```

## Performans Optimizasyonları

### Gerçek Zamanlı İşleme
- 16ms güncelleme aralığı (~60 FPS)
- Thread-safe veri yapıları
- Minimal gecikme için optimize edilmiş buffer yönetimi
- Batch işleme ile CPU kullanımı azaltma

### Bellek Yönetimi
- Döngüsel buffer (maksimum 100 veri noktası/kanal)
- Otomatik bellek temizliği
- Garbage collection optimizasyonu

### Performans İzleme
Ana ekranın sağ üst köşesinde gerçek zamanlı performans göstergeleri:
- **Data Rate**: Saniyede alınan örnek sayısı
- **Connection Status**: Bağlantı durumu
- **System Time**: Güncel tarih ve saat

## Hata Ayıklama

### Yaygın Sorunlar

#### Bağlantı Problemleri
```python
# Log çıktısı örneği:
[10:30:45.123] Scanning for BLE devices...
[10:30:50.456] Found compatible device: NRF52840_Device (XX:XX:XX:XX:XX:XX)
[10:30:52.789] Connected to NRF52840_Device - Real-time mode enabled
```

#### Veri Formatı Hataları
- **JSON decode errors**: Veri bütünlüğünü kontrol edin
- **Buffer overflow**: Bağlantı hızını optimize edin  
- **Threading issues**: Concurrent access loglarını inceleyin

### Debug Modu Etkinleştirme
```python
# Kod başında logging seviyesini değiştirin:
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
```

### Sistem Durumu Kontrolü
Durum çubuğunda şu bilgiler görüntülenir:
- **Sol**: Sistem durumu mesajları
- **Sağ**: Bağlantı durumu (Yeşil: Connected, Kırmızı: Disconnected)

## API Referansı

### Ana Metodlar

#### `BLEDataManager.connect(device)`
```python
async def connect(self, device) -> bool:
    """
    BLE cihazına bağlantı kurar
    
    Args:
        device: BleakScanner tarafından bulunan cihaz
        
    Returns:
        bool: Bağlantı durumu
    """
```

#### `TimingEntry.cycle_time_ms`
```python
@property
def cycle_time_ms(self) -> int:
    """Toplam döngü süresi hesaplama"""
    return self.time_open_ms + self.time_delay_ms + self.time_read_ms + 10
```

#### `BLEDataAcquisitionGUI.toggle_channel(channel)`
```python
def toggle_channel(self, channel):
    """
    Belirtilen kanalın görünürlüğünü değiştirir
    
    Args:
        channel (int): Kanal numarası (0-3)
    """
```

## Güvenlik ve Uyumluluk

### Veri Güvenliği
- Thread-safe veri erişimi
- Memory leak koruması
- Exception handling kapsamı

### Bluetooth Güvenliği
- Secure pairing desteği
- Connection timeout yönetimi
- Error recovery mekanizmaları

### Performans Garantileri
- Maksimum 16ms gecikme süresi
- Buffer overflow koruması
- Real-time thread priority

## Lisans ve Telif Hakları

Bu yazılım MIT lisansı altında dağıtılmaktadır. Ticari kullanım için lütfen lisans koşullarını inceleyin.

```
MIT License

Copyright (c) 2024 BLE Data Acquisition System

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software")...
```

## Teknik Destek

### Sistem Gereksinimleri Kontrolü
```python
import sys
import platform
print(f"Python sürümü: {sys.version}")
print(f"Platform: {platform.system()} {platform.release()}")
print(f"Mimari: {platform.machine()}")
```

### Log Dosyası Konumu
- **Windows**: `%APPDATA%/BLE_Data_Acquisition/logs/`
- **macOS**: `~/Library/Application Support/BLE_Data_Acquisition/logs/`
- **Linux**: `~/.local/share/BLE_Data_Acquisition/logs/`

### Destek Kanalları
- **Teknik Dokümantasyon**: Bu README dosyası
- **Issue Tracking**: GitHub Issues sistemi
- **Debug Logs**: Log sekmesinden sistem mesajları

## Versiyon Geçmişi

### v2.0.0 (Mevcut Sürüm)
- ✅ Gerçek zamanlı optimizasyon (60 FPS)
- ✅ 4 Kanallı eşzamanlı görselleştirme
- ✅ Gelişmiş LED zamanlama sistemi (maksimum 4 sekans)
- ✅ Profesyonel kullanıcı arayüzü
- ✅ Çoklu format dışa aktarım (CSV/JSON)
- ✅ Kanal görünürlük kontrolleri
- ✅ Performans izleme sistemi
- ✅ İstatistik ve log panelleri

### v1.x.x
- ⭐ Temel BLE bağlantısı
- ⭐ Basit veri görselleştirme
- ⭐ CSV dışa aktarım

## Ekran Görüntüleri Rehberi

### Gerekli Ekran Görüntüleri
README'de referans verilen görüntüleri oluşturmak için:

1. **screenshot_main_interface.png**: Ana uygulama ekranı (tam görünüm)
2. **screenshot_control_panel.png**: Üst kontrol paneli yakın çekim
3. **screenshot_channel_controls.png**: Sağ panel kanal kontrolleri
4. **screenshot_connection.png**: Cihaz bağlantısı süreci
5. **screenshot_timing_config.png**: LED zamanlama konfigürasyonu
6. **screenshot_statistics.png**: İstatistik sekmesi
7. **screenshot_logs.png**: Log sekmesi
---
