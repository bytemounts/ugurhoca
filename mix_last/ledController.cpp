#include "ledController.h"

ledController::ledController() {
  // Constructor
}

void ledController::begin() {
  for(int i = 0; i < 5; i++) {
    pinMode(leds[i].pinNo, OUTPUT);
    digitalWrite(leds[i].pinNo, LOW);
  }
}

void ledController::update(int index) {
  // Update specific LED if needed
}