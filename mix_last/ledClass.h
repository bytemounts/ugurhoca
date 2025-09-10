#ifndef ledClass_h
#define ledClass_h

#include "Arduino.h"

class led{
  private:
  int pinNo;

  public:
  int kalansure;
  int counter;
  
  led(int pinNo);
};





#endif