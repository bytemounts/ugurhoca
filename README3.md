# nRF52840 ProMicro Ardunio Ide Kurulumu #
- Adafruit nRF52 Board paketi,
- Adafruit ADS1X15 kütüphanesi,
- Adafruit LittleFS kütüphanesi,
- Adafruit nRFCrypto kütüphanelerini yükleyiniz.
- Uygun variant.h dosyası için Adafruit Feather nRF52840 isimli board'ı kullanacağız,kaynak dosyalara erişeceğiz: **windows + r** tuşuna aynı anda basınız.
``` 
%localappdata%
```
- **~\Arduino15\packages\adafruit\hardware\nrf52\1.7.0\variants\feather_nrf52840_express**      dosyasına gidin.
- https://github.com/bytemounts/ugurhoca/tree/main/variants dosyasında bulunan variant dosyalarını bir önceki adımdaki dosya uzantısına yerleştirin.

# Pinlerin Tanımı
Ledler ve I2C için:
- P0_17 (D2) **SDA**
- P0_20 (D3) **SCL**
- P0_22 (D4) LED0
- P0_24 (D5) LED1
- P1_00 (D6) LED2
- P0_11 (D7) LED3

<img width="722" height="527" alt="image" src="https://github.com/user-attachments/assets/5825c977-8d7b-46f6-bff0-e1cac47dffbb" />

# Özellikler
-4 Kanallı Veri Toplama: ADS1115 ADC ile 4 farklı kanaldan yüksek hassasiyetli analog veri okuma(I2C)
-Zamanlanmış Ölçüm: Her kanal için bağımsız zamanlama kontrolü
-BLE İletişimi: Toplanan verilerin JSON formatında kablosuz iletilmesi
-Donanım Zamanlayıcılar: nRF52840'nin dahili timer'ları ile kesin zamanlama kontrolü
-ADS1115 hiç bağlanmadıysa kırmızı led yanıp söner.
-ADS1115 bağlantısı sağlanıp bluetooth bağlantısı sağlanamadıysa LED sürekli yanar.
# Ana Modüller
### 1.ADS1115 Sürücüsü (ads.h, ads.cpp)
- I2C İletişimi sağlanmıştır.
- ADC veri okuyucularının belirlenen indeksi ve belirlenen süresi için kaç ms okuma yapacağı sınıfın içinde tutulmuştur.
- Bluetooth'dan her veri geldiğinde kesme yapılır ve ilgili fonksiyona subroutine yapılır. Burada ise gelen veri kutusuna göre işlemler yapılır.
### 2.Led Kontrol Sistemi(ledClass.h, ledClass.cpp, ledController.h, ledController.cpp)
- Ledlerin kontrolü zamanlayıcı ISR(interrupt subroutine) ile yapılmıştır.
- Bilgisayardan BLE ile mikroişlemciye gönderilen veri kutusundaki verilere göre gelen pin numarasına tanımlı olan led'in timer süresi değiştirilir ve timer başlatılır(eğer state true ise).
### 3.BLE İletişimi (mix_last.ino)
- Json formatında veri paketleme ve açma.
- BLE bağlantı yönetimi (alma ve gönderme).
- Ana yapılandırma dosyası mix_last.ino içerisindedir.
### 4.Sistem Yapılandırılması(sistem.h, sistem.cpp)
- Genel sistem yapısının tanımlanması.
- Global mysistem burada tanımlanmıştır, diğer dosyalardan bu değişkene erişim için extern ifadesi için ilgili dosyalarla tanımlama yapılmıştır.
