#include "ads.h"
#include "sistem.h"
extern sistem mysistem;




ads1115::ads1115() {
  for (int i = 0; i < 4; i++) {
    adc[i] = 0;
    adc_readtime[i] = 0;
    adc_delay[i] = 0;
    read_state[i]=false;
    
  }
  this->is_adc_started=false;
}

void ads1115::begin() {
  Wire.begin();
  int gecikme=5000,previous = millis();
  if (!ads.begin()) {
    Serial.println("ADS1115 bulunamadi!");
    while(millis()-previous <= gecikme){//5 SANİYE 
      //Serial.println("ADS1115 aranıyor...");
      if(ads.begin()){
        this->is_adc_started = true;
        Serial.println("ADS1115 tekrar bulundu!");
        //this->ads.setDataRate(RATE_ADS1115_860SPS);//475 SPS - 2.105 ms, 860 SPS(max) - 1.163 ms, varsayılan olarak 128 SPS - 7.8125 ms
        break;
      }
      delay(20);
    }
  }else{
    this->is_adc_started = true;
    //this->ads.setDataRate(RATE_ADS1115_860SPS);
  }
  if(this->is_adc_started){
    ads.setGain(GAIN_ONE);
    Serial.println("ADS1115 Baslatildi.");
  }else{
    Serial.println("ADS1115 5 saniye boyunca bulunamadi!");
  }
}


void ads1115::devam(int i){//milisaniye cinsinden
  unsigned long baslangiczamani=millis(); //baslangic zamanı
  while(millis()- baslangiczamani < this->adc_readtime[i]){//readtime kadar okur
    this->adc[i] = ads.readADC_SingleEnded(i);
  }
}


void ads1115::devam() {
  // First read all ADC values
  for (int i = 0; i < 4; i++) {
    this->adc[i] = ads.readADC_SingleEnded(i);
  }
}

