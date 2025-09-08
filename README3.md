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

# nRF52840 ProMicro'ya bağlı LED pin yerleri ve I2C iletişimi için SDA SCL pinlerinin tanımı
Ledler ve I2C için:
- P0_17 (D2) **SDA**
- P0_20 (D3) **SCL**
- P0_22 (D4) LED0
- P0_24 (D5) LED1
- P1_00 (D6) LED2
- P0_11 (D7) LED3


<img width="722" height="527" alt="image" src="https://github.com/user-attachments/assets/5825c977-8d7b-46f6-bff0-e1cac47dffbb" />


