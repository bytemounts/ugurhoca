# Grafik Arayüzü Bileşenleri

## Gerçek Zamanlı Görselleştirme

### Birleşik Çok Kanallı Ekran
Ana grafik, aşağıdaki özelliklere sahip eş zamanlı 4 sensör kanalını görüntüler:

- **Zaman Serisi Grafiği**: Gerçek zamanlı voltaj ölçümleri (mV) zamana karşı
- **Renk Kodlu Kanallar**: 
  - Kanal 0: Kırmızı (#e74c3c)
  - Kanal 1: Mavi (#3498db)
  - Kanal 2: Yeşil (#2ecc71)
  - Kanal 3: Turuncu (#f39c12)
- **Performans Optimize Edilmiş**: 100 noktalık yuvarlak pencere ile 60 FPS rendering
- **Etkileşimli Lejant**: Kanalları tek tek görünür/görünmez yapabilme

### Kanal Kontrol Paneli
Sağ tarafta konumlanmış, bireysel kanal yönetimi sağlar:

- **Etkinleştir/Devre Dışı Bırak**: Grafikteki kanal görünürlüğünü kontrol eder
- **Gerçek Zamanlı Değer Görüntüsü**: mV cinsinden mevcut voltaj okuma
- **Ham ADC Değerleri**: Dijital dönüştürücü çıkışı (0-4095 aralığı)
- **Görsel Durum Göstergeleri**: Renk kodlu etkin/devre dışı durumlar

### İstatistikler Sekmesi
Kapsamlı ölçüm analitikleri sağlar:

| Metrik | Açıklama |
|--------|----------|
| Güncel | En son ölçüm değeri |
| Minimum | Oturumda kaydedilen en düşük değer |
| Maksimum | Oturumda kaydedilen en yüksek değer |
| Ortalama | Tüm ölçümlerin ortalama değeri |
| Sayım | Toplanan toplam veri noktası sayısı |

## Grafik Özellikleri

### Görselleştirme Kontrolleri
- **Kanal Geçişi**: Her kanalı bağımsız olarak etkinleştirme/devre dışı bırakma
- **Renk Koordinasyonu**: Her kanal için tutarlı renk şeması
- **Dinamik Ölçeklendirme**: Veriye göre otomatik Y ekseni ayarı
- **Zaman Penceresi**: Son 100 ölçümün kayan penceresi

### Performans Göstergeleri
- **Veri Alma Hızı**: Saniye başına örnek sayısı görüntüsü
- **Bağlantı Durumu**: Gerçek zamanlı bağlantı durumu göstergesi
- **Sistem Gecikmesi**: Veri işleme performans metrikleri
- **Bellek Kullanımı**: Optimize edilmiş kaynak yönetimi

### Etkileşim Özellikleri
- **Anlık Değer Gösterimi**: Her kanal için güncel ölçüm değerleri
- **Ham Veri Erişimi**: ADC okuma değerlerine doğrudan erişim
- **Durum Göstergeleri**: Görsel geri bildirim ile sistem durumu
- **Gerçek Zamanlı Güncellemeler**: Kesintisiz veri akışı görselleştirmesi
