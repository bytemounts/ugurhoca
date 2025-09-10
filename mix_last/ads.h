#include <cstdint>
#ifndef ADS_H
#define ADS_H

#include "Arduino.h"
#include <Wire.h>
#include <Adafruit_ADS1X15.h>

class ads1115 {
    public:
    Adafruit_ADS1115 ads;
    int adc[4];
    uint16_t adc_readtime[4];
    uint32_t adc_delay[4];
    bool is_adc_started;
    bool read_state[4];

    ads1115();      // constructor
    void begin();   // başlat
    void devam();   // ölçüm for all döngüsü
    void devam(int i);
};

#endif