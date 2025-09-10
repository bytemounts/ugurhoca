#ifndef sistem_h
#define sistem_h

#include "ads.h"

struct prc{
  bool led;
  bool delay;
  bool adc_read;
};

struct sistem{
  String SisteminAdi;
  String versiyon;
  ads1115 myAds;
  prc process[4];
  int process_itr = 0;
  int process_pos = 0;
  bool state;
};



#endif