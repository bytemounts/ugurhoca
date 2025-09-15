#include "ads.h"
#include "sistem.h"
#include <bluefruit.h>
#include <ArduinoJson.h>

// BLE Services
BLEDfu bledfu;
BLEDis bledis;
BLEUart bleuart;
BLEBas blebas;

sistem mysistem;

void setup() {
  Serial.begin(9600);
  while (!Serial)
    ;
  Serial.println("Program basladi");

  // Initialize BLE
  Bluefruit.autoConnLed(true);
  Bluefruit.configPrphBandwidth(BANDWIDTH_MAX);
  Bluefruit.begin();
  Bluefruit.setTxPower(4);
  Bluefruit.Periph.setConnectCallback(connect_callback);
  Bluefruit.Periph.setDisconnectCallback(disconnect_callback);

  bledfu.begin();
  bledis.setManufacturer("Adafruit Industries");
  bledis.setModel("Bluefruit Feather52");
  bledis.begin();

  bleuart.begin();
  bleuart.setRxCallback(uart_rx_callback);

  blebas.begin();
  blebas.write(100);

  startAdv();
  timer1_init();
  timer2_init();

  // Initialize system components
  mysistem.myLeds.begin();
  mysistem.myAds.begin();
  
  // Initialize system state
  for (int i = 0; i < 4; i++) {
    mysistem.channels[i].state = CHANNEL_IDLE;
    mysistem.channels[i].processComplete = false;
  }
}

void loop() {
  if (!mysistem.myAds.is_adc_started) {
    mysistem.myAds.begin();
  }

  if (Bluefruit.connected()) {
    handleBleMessages();
    digitalWrite(22, LOW);  // Bluetooth connected indicator

    if (mysistem.systemEnabled) {
      processCurrentChannel();
    }
  } else {
    if (mysistem.myAds.is_adc_started) {
      digitalWrite(LED_BUILTIN, HIGH);
    }
    handleChill();
    // Bluetooth not connected
    
  }
}

void processCurrentChannel() {
  ChannelData& current = mysistem.channels[mysistem.currentChannel];

  if (!mysistem.myAds.read_state[mysistem.currentChannel]) {
    advanceToNextChannel();
    return;
  }

  switch (current.state) {
    case CHANNEL_IDLE:
      startChannelProcessing(current);
      break;

    case DELAY_COUNTING:
      handleDelayCounting(current);
      break;

    case ADC_READING_PHASE:
      handleAdcReading(current);
      break;

    case CYCLE_COMPLETE:
      completeChannelProcessing(current);
      break;
  }
}

void startChannelProcessing(ChannelData& channel) {
  channel.state = DELAY_COUNTING;
  channel.processComplete = false;
  mysistem.timer1Expired=false;
  mysistem.timer2Expired = true;

  // Start LED timer
  NRF_TIMER1->CC[0] = mysistem.myLeds.leds[mysistem.currentChannel].kalansure * 1000;
  NRF_TIMER1->TASKS_START = 1;
  //start 
  NRF_TIMER2->CC[0] = mysistem.myAds.adc_delay[mysistem.currentChannel] * 1000;//delay controller
  NRF_TIMER2->TASKS_START = 1;

  digitalWrite(mysistem.currentChannel + 4, HIGH);
}

void handleLedOnState(ChannelData& channel) {
  if (mysistem.timer1Expired) {
    digitalWrite(mysistem.currentChannel + 4, LOW);
  }
}

void handleDelayCounting(ChannelData& channel) {
  handleLedOnState(channel);
  if (mysistem.timer2Expired) {
    channel.state = ADC_READING_PHASE;
    channel.adcAccumulator = 0;
    channel.adcReadCount = 0;

    mysistem.timer2Expired=false;
    NRF_TIMER2->CC[0] = mysistem.myAds.adc_readtime[mysistem.currentChannel] * 1000;
    NRF_TIMER2->TASKS_START = 1;
  }
}

void handleAdcReading(ChannelData& channel) {
  handleLedOnState(channel);
  if (!mysistem.timer2Expired) {
    channel.adcAccumulator += mysistem.myAds.ads.readADC_SingleEnded(mysistem.currentChannel);
    channel.adcReadCount++;
  } else {
    if (channel.adcReadCount > 0) {
      mysistem.myAds.adc[mysistem.currentChannel] = channel.adcAccumulator / channel.adcReadCount;
    } else {
      mysistem.myAds.adc[mysistem.currentChannel] = 0;
    }
    channel.state = CYCLE_COMPLETE;
  }
}

void completeChannelProcessing(ChannelData& channel) {
  handleLedOnState(channel);
  if (mysistem.timer1Expired) {
    String jsonPayload = makeJsonPayload(mysistem.myAds.adc);
    sendJsonPayload(jsonPayload);
    
    channel.state = CHANNEL_IDLE;
    channel.processComplete = true;

    advanceToNextChannel();
  }
}

void advanceToNextChannel() {
  mysistem.currentChannel = (mysistem.currentChannel + 1) % 4;
}

String makeJsonPayload(int values[4]) {
  String s = "[";
  for (int i = 0; i < 4; ++i) {
    s += "[";
    s += "\"";
    s += "mV";
    s += "\"";
    s += ",";
    s += String(millis());
    s += ",";
    s += String(((float)values[i] / 32768.0) * 2.048 * 1000.0);
    s += ",";
    s += String(values[i]);
    s += "]";
    if (i < 3) s += ",";
  }
  s += "]";
  s += "\n";
  return s;
}

void sendJsonPayload(const String& payload) {
  bleuart.write((uint8_t*)payload.c_str(), payload.length());
}

// BLE Callback Functions
void connect_callback(uint16_t conn_handle) {
  BLEConnection* connection = Bluefruit.Connection(conn_handle);
  char central_name[32] = { 0 };
  connection->getPeerName(central_name, sizeof(central_name));
  Serial.print("Connected to ");
  Serial.println(central_name);
  mysistem.myLeds.leds[4].counter = 0;  // Reset built-in LED counter
}

void disconnect_callback(uint16_t conn_handle, uint8_t reason) {
  (void)conn_handle;
  (void)reason;
  Serial.println();
  Serial.print("Disconnected, reason = 0x");
  Serial.println(reason, HEX);
}

void startAdv(void) {
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(bleuart);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
}

void uart_rx_callback(uint16_t conn_handle) {
  (void)conn_handle;
  static bool json_started = false;
  static int brace_count = 0;

  while (bleuart.available()) {
    char c = (char)bleuart.read();

    if (c == '{' && !json_started) {
      json_started = true;
      brace_count = 0;
      mysistem.rxBuffer = "";
    }

    if (json_started) {
      mysistem.rxBuffer += c;

      if (c == '{') brace_count++;
      if (c == '}') brace_count--;

      if (brace_count == 0 && mysistem.rxBuffer.length() > 2) {
        mysistem.jsonCallback = true;
        json_started = false;
        break;
      }
    }
  }
}

void handleBleMessages() {
  if (mysistem.jsonCallback) {
    mysistem.rxBuffer.trim();
    parseJsonBuffer(mysistem.rxBuffer);
    mysistem.rxBuffer = "";
    mysistem.jsonCallback = false;
  }
}

void parseJsonBuffer(const String& buffer) {
  if (buffer.length() == 0) return;

  String cleanBuffer = buffer;
  cleanBuffer.trim();
  Serial.print(cleanBuffer);
  StaticJsonDocument<2048> doc;
  DeserializationError err = deserializeJson(doc, cleanBuffer);

  if (err) {
    Serial.print("JSON parse error: ");
    Serial.println(err.f_str());
    return;
  }

  // Update system state
  if (doc.containsKey("state")) {
    mysistem.systemEnabled = doc["state"] | false;
  }

  // Update channel sequences
  if (doc.containsKey("sequences") && doc["sequences"].is<JsonArray>()) {
    JsonArray arr = doc["sequences"].as<JsonArray>();

    for (JsonObject obj : arr) {
      int pin = obj["led_pin"] | -1;
      int openMs = obj["time_open_ms"] | 0;
      int delayMs = obj["time_delay_ms"] | 0;
      int readMs = obj["time_read_ms"] | 0;
      bool enabled = obj["enabled"] | false;

      pin--;
      if (pin >= 0 && pin < 4) {
        mysistem.myLeds.leds[pin].kalansure = openMs;
        mysistem.myAds.adc_delay[pin] = delayMs;
        mysistem.myAds.adc_readtime[pin] = readMs;
        mysistem.myAds.read_state[pin] = enabled;

        if (enabled) {
          mysistem.channels[pin].state = CHANNEL_IDLE;
        }
      }
    }
  }
}

void handleChill(){
  //timerları durdur.
  
  if(digitalRead(mysistem.currentChannel))digitalWrite(mysistem.currentChannel+4,LOW);
  NRF_TIMER1->TASKS_STOP = 1;
  NRF_TIMER2->TASKS_STOP = 1;
  sd_app_evt_wait();
}

// Timer interrupt handler
extern "C" void TIMER1_IRQHandler(void) {
  if (NRF_TIMER1->EVENTS_COMPARE[0]) {
    NRF_TIMER1->TASKS_STOP = 1;
    NRF_TIMER1->EVENTS_COMPARE[0] = 0;
    mysistem.timer1Expired = true;
  }
}


extern "C" void TIMER2_IRQHandler(void) {
  if (NRF_TIMER2->EVENTS_COMPARE[0]) {
    NRF_TIMER2->TASKS_STOP = 1;
    NRF_TIMER2->EVENTS_COMPARE[0] = 0;
    mysistem.timer2Expired = true;
  }
}

void timer1_init() {
  NRF_TIMER1->TASKS_STOP = 1;
  NRF_TIMER1->MODE = TIMER_MODE_MODE_Timer;
  NRF_TIMER1->BITMODE = TIMER_BITMODE_BITMODE_32Bit << TIMER_BITMODE_BITMODE_Pos;
  NRF_TIMER1->PRESCALER = 4;

  NRF_TIMER1->INTENSET = TIMER_INTENSET_COMPARE0_Enabled << TIMER_INTENSET_COMPARE0_Pos;
  NRF_TIMER1->SHORTS = TIMER_SHORTS_COMPARE0_CLEAR_Enabled << TIMER_SHORTS_COMPARE0_CLEAR_Pos;

  NVIC_EnableIRQ(TIMER1_IRQn);
}

void timer2_init() {
  NRF_TIMER2->TASKS_STOP = 1;
  NRF_TIMER2->MODE = TIMER_MODE_MODE_Timer;
  NRF_TIMER2->BITMODE = TIMER_BITMODE_BITMODE_32Bit << TIMER_BITMODE_BITMODE_Pos;
  NRF_TIMER2->PRESCALER = 4;

  NRF_TIMER2->INTENSET = TIMER_INTENSET_COMPARE0_Enabled << TIMER_INTENSET_COMPARE0_Pos;
  NRF_TIMER2->SHORTS = TIMER_SHORTS_COMPARE0_CLEAR_Enabled << TIMER_SHORTS_COMPARE0_CLEAR_Pos;

  NVIC_EnableIRQ(TIMER2_IRQn);
}