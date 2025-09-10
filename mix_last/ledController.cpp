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

  // Timer0..4 ayarları (her biri için ayrı)
  // Not: PRESCALER/ MODE/ BITMODE ayarını kopyaladım; donanım datasheet'ine göre doğrula
  
  NRF_TIMER1->TASKS_STOP = 1;
  NRF_TIMER1->PRESCALER = 4;
  NRF_TIMER1->MODE = TIMER_MODE_MODE_Timer;
  NRF_TIMER1->BITMODE = TIMER_BITMODE_BITMODE_32Bit;

  NRF_TIMER2->TASKS_STOP = 1;
  NRF_TIMER2->PRESCALER = 4;
  NRF_TIMER2->MODE = TIMER_MODE_MODE_Timer;
  NRF_TIMER2->BITMODE = TIMER_BITMODE_BITMODE_32Bit;

  NRF_TIMER3->TASKS_STOP = 1;
  NRF_TIMER3->PRESCALER = 4;
  NRF_TIMER3->MODE = TIMER_MODE_MODE_Timer;
  NRF_TIMER3->BITMODE = TIMER_BITMODE_BITMODE_32Bit;

  NRF_TIMER4->TASKS_STOP = 1;
  NRF_TIMER4->PRESCALER = 4;
  NRF_TIMER4->MODE = TIMER_MODE_MODE_Timer;
  NRF_TIMER4->BITMODE = TIMER_BITMODE_BITMODE_32Bit;

  NRF_TIMER1->EVENTS_COMPARE[0] = 0;
  NRF_TIMER2->EVENTS_COMPARE[0] = 0;
  NRF_TIMER3->EVENTS_COMPARE[0] = 0;
  NRF_TIMER4->EVENTS_COMPARE[0] = 0;

  // Interrupt maskelerini her timer için ayrı ayarla (COMPARE0 örneği)
  NRF_TIMER1->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
  NRF_TIMER2->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
  NRF_TIMER3->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
  NRF_TIMER4->INTENSET = TIMER_INTENSET_COMPARE0_Msk;

  // NVIC IRQ'leri etkinleştir
  NVIC_EnableIRQ(TIMER1_IRQn);
  NVIC_EnableIRQ(TIMER2_IRQn);
  NVIC_EnableIRQ(TIMER3_IRQn);
  NVIC_EnableIRQ(TIMER4_IRQn);

  NRF_TIMER1->TASKS_STOP = 1;
  NRF_TIMER2->TASKS_STOP = 1;
  NRF_TIMER3->TASKS_STOP = 1;
  NRF_TIMER4->TASKS_STOP = 1;
}

void ledController::update() {
  for (int i = 0; i < 5; i++) {
    if (toggleFlag[i]) {
      toggleFlag[i] = false;
      digitalWrite(pinNos[i], !digitalRead(pinNos[i]));
    }
  }
}

void ledController::resumeAll() {
  NRF_TIMER1->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
  NRF_TIMER2->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
  NRF_TIMER3->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
  NRF_TIMER4->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
}

// Timer olaylarını işleyen non-static üye fonksiyon
void ledController::handleTimerEvent(int timerIdx) {
  switch (timerIdx) {
    case 0:
      if (NRF_TIMER1->EVENTS_COMPARE[0]) {
        Serial.print("cp5\n");
        NRF_TIMER1->EVENTS_COMPARE[0] = 0; // Clear event
        NRF_TIMER1->INTENCLR = TIMER_INTENCLR_COMPARE0_Msk;//kesmeyi kapatır, .ino'da timer_start_handle fonksiyonu tekrar açar.
        toggleFlag[timerIdx]=true;
        dongu_led[timerIdx]=true;
      }
      break;
    case 1:
      if (NRF_TIMER2->EVENTS_COMPARE[0]) {
        Serial.print("cp5\n");
        NRF_TIMER2->EVENTS_COMPARE[0] = 0; // Clear event
        NRF_TIMER2->INTENCLR = TIMER_INTENCLR_COMPARE0_Msk;
        toggleFlag[timerIdx]=true;
        dongu_led[timerIdx]=true;
      }
      break;
    case 2:
      if (NRF_TIMER3->EVENTS_COMPARE[0]) {
        Serial.print("cp5\n");
        NRF_TIMER3->EVENTS_COMPARE[0] = 0; // Clear event
        NRF_TIMER3->INTENCLR = TIMER_INTENCLR_COMPARE0_Msk;
        toggleFlag[timerIdx]=true;
        dongu_led[timerIdx]=true;
        
      }
      break;
    case 3:
      if (NRF_TIMER4->EVENTS_COMPARE[0]) {
        Serial.print("cp5\n");
        NRF_TIMER4->EVENTS_COMPARE[0] = 0; // Clear event
        NRF_TIMER4->INTENCLR = TIMER_INTENCLR_COMPARE0_Msk;
        toggleFlag[timerIdx]=true;
        dongu_led[timerIdx]=true;
      }
      break;
    default:
    break;
  }
}

  void ledController::adsBaglanmadiLedBildir(){
    if(leds[4].counter==4){
      digitalWrite(22,LOW);
      leds[4].counter=0;
    } 
  }

// C ISR'leri sınıfın singleton örneğine yönlendirir
extern "C" void TIMER1_IRQHandler(void) {
  if (ledController::instance) ledController::instance->handleTimerEvent(0);
}
extern "C" void TIMER2_IRQHandler(void) {
  if (ledController::instance) ledController::instance->handleTimerEvent(1);
}
extern "C" void TIMER3_IRQHandler(void) {
  if (ledController::instance) ledController::instance->handleTimerEvent(2);
}
extern "C" void TIMER4_IRQHandler(void) {
  if (ledController::instance) ledController::instance->handleTimerEvent(3);
}
