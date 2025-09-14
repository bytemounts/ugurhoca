#ifndef sistem_h
#define sistem_h

#include "ads.h"


// sistem.h (veya yeni bir header dosyası, örn. channelStates.h)
enum ChannelState {
  CHANNEL_IDLE,                 // Kanal şu anda aktif değil, bekliyor
  LED_ON,                       // LED açık, time_open süresi sayılıyor
  DELAY_COUNTING,               // LED kapandı, ADC okuma gecikmesi sayılıyor
  ADC_READING_PHASE,            // ADC okuma süresi boyunca örnekler alınıyor
  CYCLE_COMPLETE                // Bir döngü tamamlandı, sonraki kanala geçmeye hazır (veya beklemede)
};

struct prc{
  bool led;
  bool delay;
  bool adc_read;
};

struct sistem{
  String SisteminAdi;
  String versiyon;
  ads1115 myAds;
  ChannelState channelState[4]; // Her kanal için durum
  prc process[4];
  int process_itr = 0;
  int process_pos = 0;
  bool state;
};



#endif