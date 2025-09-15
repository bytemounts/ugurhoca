#ifndef LEDCONTROLLER_H
#define LEDCONTROLLER_H

#include <Arduino.h>
#include "ledClass.h"

class ledController {
public:
    ledController();
    void begin();
    void update(int index);
    
    // Members
    led leds[5] = {led(4), led(5), led(6), led(7), led(22)};
};

#endif