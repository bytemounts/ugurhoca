

// ledController.h
#ifndef LEDCONTROLLER_H
#define LEDCONTROLLER_H

#include <Arduino.h>
#include "ledClass.h"
class ledController {
public:
    // Singleton örneğini kullanabilmek için ctor public olabilir
    // (ama instance pointer her zaman son oluşturulan objeyi gösterir)
    ledController();

    void begin();
    void update(int itr);
    void pauseAllExcept(int activeIndex);
    void resumeAll();
    void handleTimerEvent(int timerIdx);
    void adsBaglanmadiLedBildir();

    // Üyeler
    static const int pinNos[5];
    static volatile bool toggleFlag[5];

    led leds[5]={led(4),led(5),led(6),led(7),led(22)};

    // Singleton erişimi (ISR'lerden kullanılacak)
    static ledController* instance;
};

#endif
