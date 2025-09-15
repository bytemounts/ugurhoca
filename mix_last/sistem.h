#ifndef sistem_h
#define sistem_h

#include "ads.h"
#include "ledController.h"

enum ChannelState {
  CHANNEL_IDLE,
  DELAY_COUNTING,
  ADC_READING_PHASE,
  CYCLE_COMPLETE
};

struct ChannelData {
  ChannelState state;
  unsigned long startTime;
  unsigned long adcAccumulator;
  int adcReadCount;
  bool processComplete;
};

struct sistem {
  String SisteminAdi;
  String versiyon="version 1.0";
  ads1115 myAds;
  ledController myLeds;
  ChannelData channels[4];
  int currentChannel=0;
  bool systemEnabled=false;
  volatile bool timer1Expired=false;
  volatile bool timer2Expired=false;
  String rxBuffer="";
  bool jsonCallback=false;
};

#endif