// ledController.cpp (örnek)
#include "ledClass.h"
#include "ledController.h"
#include "sistem.h"

extern sistem mysistem;
extern bool dongu_led[4];
// Pin tanımı
const int ledController::pinNos[5] = {4, 5, 6, 7, 22};
volatile bool ledController::toggleFlag[5] = {false, false, false, false, false};

// Singleton pointer (ISR'lerden erişmek için)
ledController* ledController::instance = nullptr;

ledController::ledController() {
  // Singleton olarak kaydet
  instance = this;
}

void ledController::begin() {
  // Pinleri çıkış yap
  for (int i = 0; i < 5; i++) {
    pinMode(pinNos[i], OUTPUT);
    digitalWrite(pinNos[i], LOW);
  }

  

}

void ledController::update(int i) {
  if (toggleFlag[i]) digitalWrite(pinNos[i], HIGH);
  else digitalWrite(pinNos[i], LOW);
  
}

void ledController::adsBaglanmadiLedBildir(){
  if(leds[4].counter==4){
    digitalWrite(22,LOW);
    leds[4].counter=0;
  } 
}
