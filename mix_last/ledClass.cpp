#include "ledClass.h"

led::led(int pinNo){
  this->pinNo = pinNo;
  this->kalansure=0;
  this->counter = 0;
  pinMode(pinNo,OUTPUT);
}
