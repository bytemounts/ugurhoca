#include "ads.h"
#include "ledController.h"
#include "sistem.h"
#include <bluefruit.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <ArduinoJson.h>

#include <Arduino.h>
#include "nrfx_timer.h"
/*
#define LED_OFF_TIMER_INST  NRFX_TIMER_INSTANCE(0)
#define DELAY_TIMER_INST    NRFX_TIMER_INSTANCE(1)
#define READ_TIMER_INST     NRFX_TIMER_INSTANCE(2)

extern "C" void nrfx_timer_0_irq_handler(void) { nrfx_timer_irq_handler(&LED_OFF_TIMER_INST); }
extern "C" void nrfx_timer_1_irq_handler(void) { nrfx_timer_irq_handler(&DELAY_TIMER_INST); }
extern "C" void nrfx_timer_2_irq_handler(void) { nrfx_timer_irq_handler(&READ_TIMER_INST); }

void ledOffHandler(nrf_timer_event_t event_type, void* p_context) {
  if (event_type == NRF_TIMER_EVENT_COMPARE0) {
    int pin = (int)(intptr_t)p_context;
    digitalWrite(pin, LOW);
  }
}

void delayHandler(nrf_timer_event_t event_type, void* p_context) {
  if (event_type == NRF_TIMER_EVENT_COMPARE0) {
    int seq_id = (int)(intptr_t)p_context;

    // ADC okuma başlasın
    reading = true;
    adcSum = 0;
    adcCount = 0;

    // READ timer başlat
    nrfx_timer_clear(&READ_TIMER_INST);
    nrfx_timer_extended_compare(
      &READ_TIMER_INST,
      NRF_TIMER_CC_CHANNEL0,
      nrfx_timer_ms_to_ticks(&READ_TIMER_INST, sequences[seq_id].time_read_ms),
      NRF_TIMER_SHORT_COMPARE0_STOP_MASK,
      true
    );
    nrfx_timer_enable(&READ_TIMER_INST);
  }
}

void readHandler(nrf_timer_event_t event_type, void* p_context) {
  if (event_type == NRF_TIMER_EVENT_COMPARE0) {
    int seq_id = currentSeq;
    reading = false;

    float avg = (adcCount > 0) ? (float)adcSum / adcCount : 0;
    Serial.print("SEQ=");
    Serial.print(seq_id);
    Serial.print(" LED=");
    Serial.print(sequences[seq_id].led_pin);
    Serial.print(" AVG=");
    Serial.println(avg);

    // Sonraki sequence
    currentSeq++;
    if (currentSeq < seqCount && sequences[currentSeq].enabled) {
      startSequence(currentSeq);
    } else {
      Serial.println("Tüm sekanslar bitti.");
    }
  }
}

void startSequence(int id) {
  Sequence &seq = sequences[id];

  // LED aç
  digitalWrite(seq.led_pin, HIGH);

  // LED off timer ayarla
  nrfx_timer_clear(&LED_OFF_TIMER_INST);
  nrfx_timer_extended_compare(
    &LED_OFF_TIMER_INST,
    NRF_TIMER_CC_CHANNEL0,
    nrfx_timer_ms_to_ticks(&LED_OFF_TIMER_INST, seq.time_open_ms),
    NRF_TIMER_SHORT_COMPARE0_STOP_MASK,
    true
  );
  nrfx_timer_enable(&LED_OFF_TIMER_INST);

  // Delay timer ayarla
  nrfx_timer_clear(&DELAY_TIMER_INST);
  nrfx_timer_extended_compare(
    &DELAY_TIMER_INST,
    NRF_TIMER_CC_CHANNEL0,
    nrfx_timer_ms_to_ticks(&DELAY_TIMER_INST, seq.time_delay_ms),
    NRF_TIMER_SHORT_COMPARE0_STOP_MASK,
    true
  );
  nrfx_timer_enable(&DELAY_TIMER_INST);
}






*/
// BLE Service
BLEDfu  bledfu;  // OTA DFU service
BLEDis  bledis;  // device information
BLEUart bleuart; // uart over ble
BLEBas  blebas;  // battery

extern sistem mysistem;

ledController myleds;

struct data_box{
  bool state;
  uint32_t time_open;
  uint32_t time_delay;
  uint16_t time_read;
  int8_t pin;
}data_box[4];


unsigned long baslangiczamani;
unsigned long prev;
unsigned long json_delay = 20; //ms cinsinden belirli sürede bir json gönderme ayarı, şuanda kullanım dışı.
unsigned long adc_toplayici=0;
int adc_read_counter=0;
int itr=0;

bool dongu_led[4]={0,0,0,0};
bool dongu_delay[4]={0,0,0,0};
bool dongu_read_finish[4]={0,0,0,0};
bool callback=false;
bool starter_controller=false;

String rxBuffer = "";           // Gelen parçaları biriktirir
String gonderilecek_json="";
void ble_check(){
      //myleds.update(itr);
    digitalWrite(22,LOW);
    
    if(callback){
      rxBuffer.trim();
      Serial.print(rxBuffer);
      parseJsonBuffer(rxBuffer);
      rxBuffer="";
      callback=false;
    }

}
void setup() {
  Serial.begin(9600);
  while(!Serial); // bazı nRF kartlarda gerekli
  Serial.println("Program basladi");

  Serial.println("Bluefruit52 BLEUART JSON sender");//checkpoint 1
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
  Serial.println("Bluefruit52 BLEUART JSON sender");//checkpoint 2
  bleuart.setRxCallback(uart_rx_callback);//her veri gelişinde bu fonksiyon çalışır
  blebas.begin();
  blebas.write(100);
  startAdv();
  timer1_init();
  myleds.begin();
  mysistem.myAds.begin();
}

void loop() {
  if(!mysistem.myAds.is_adc_started) {
    mysistem.myAds.begin();
  }

  if (Bluefruit.connected()) {
    ble_check();

    // Ana değişiklik: mysistem.state kontrolü ve read_state[itr] kontrolü
    if(mysistem.state) {
      
      // Eğer bu kanal aktif değilse bir sonraki kanala geç
      if(!mysistem.myAds.read_state[itr]) {
        // Bu kanalı atla ve bir sonrakine geç
        if(itr == 3) itr = 0;
        else itr++;
        return; // Bu döngüyü bitir, bir sonraki loop() çağrısında devam et
      }
      
      // Bu noktada hem mysistem.state true hem de read_state[itr] true
      if(!dongu_led[itr] && !dongu_delay[itr] && !dongu_read_finish[itr] && !starter_controller){
        //en başta buraya girer ve başlangıç ayarları yapılır.
        starter_controller = true;

        NRF_TIMER1->CC[0] = (uint32_t)myleds.leds[itr].kalansure * 1000;// ms -> µs çevir
        NRF_TIMER1->TASKS_START = 1;
        digitalWrite(itr+4,HIGH);

        prev = millis();
        adc_read_counter = 0;
        adc_toplayici = 0;
        Serial.print("Starting channel: ");
        Serial.println(itr);
      }
      
      if(!dongu_delay[itr]){
        if(millis()-prev > mysistem.myAds.adc_delay[itr]){
          //delay süresi bittiyse dongu_delay[itr] true yap. ve okuma işlemi başlayabilir.
          dongu_delay[itr] = true;
          baslangiczamani = millis();
          Serial.print("Delay finished for channel: ");
          Serial.println(itr);
        }
      }
      else{
        if(!dongu_read_finish[itr]){
          if(millis()- baslangiczamani < mysistem.myAds.adc_readtime[itr]){//readtime kadar okur
            adc_toplayici += mysistem.myAds.ads.readADC_SingleEnded(itr);//adc okuma kısmı
            adc_read_counter++;
          }else {
            if (adc_read_counter > 0) {
              mysistem.myAds.adc[itr] = adc_toplayici / adc_read_counter;
            } else {
              mysistem.myAds.adc[itr] = 0;
              Serial.print("Warning: adc_read_counter == 0 for channel ");
              Serial.println(itr);
            }
            dongu_read_finish[itr] = true;
            gonderilecek_json = makeJsonPayload(mysistem.myAds.adc);
            sendJsonPayload(gonderilecek_json);
            Serial.print("ADC reading finished for channel: ");
            Serial.print(itr);
            Serial.print(" - ");
            Serial.println(gonderilecek_json);
          }
        }
      }

      // Kanal işlemi tamamlandıysa bir sonraki kanala geç
      if(dongu_led[itr] && dongu_delay[itr] && dongu_read_finish[itr]){
        dongu_led[itr] = false;
        dongu_delay[itr] = false;
        dongu_read_finish[itr] = false;
        starter_controller = false;
        
        Serial.print("Channel ");
        Serial.print(itr);
        Serial.println(" completed, moving to next");
        
        if(itr == 3) itr = 0;
        else itr++;
      }
    }
  }
  else{
    //ble bağlantısı yoksa
    if(mysistem.myAds.is_adc_started){
      digitalWrite(LED_BUILTIN,HIGH);
    }
  }
}

String makeJsonPayload(int values[4]) { // Fixed parameter types
  String s = "[";
  for (int i = 0; i < 4; ++i) {
    s += "[";                   // başlangıç indeks
    s += "\"";
    s += "mV";                  // birim string
    s += "\"";
    s += ",";
    s += String(millis()); // timestamp
    s += ",";
    s += String(((float)values[i] / 32768.0) * 2.048 * 1000.0);       // mV
    s += ",";
    s += String(values[i]);    // değer
    s += "]";
    if (i < 3) s += ",";       // indeks ayırıcı
  }
  s += "]";
  s += "\n"; // newline ile bitiriyoruz, Python tarafı buna göre parse edecek
  return s;
}


void sendJsonPayload(const String &payload) { // Fixed parameter type
  // bleuart.write bekler; String.c_str() ile char* veriyoruz
  bleuart.write((uint8_t*)payload.c_str(), payload.length());
  // debug
  //Serial.print("Sent JSON: ");
  //Serial.print(payload);
}

// callback invoked when central connects
void connect_callback(uint16_t conn_handle)
{
  BLEConnection* connection = Bluefruit.Connection(conn_handle);
  char central_name[32] = { 0 };
  connection->getPeerName(central_name, sizeof(central_name));
  Serial.print("Connected to ");
  Serial.println(central_name);
  myleds.toggleFlag[4]=true;//mikroişlemci bluetooth bağlantısını gerçekleştirdiyse led kapalı kalır.
}

void disconnect_callback(uint16_t conn_handle, uint8_t reason)
{
  (void) conn_handle;
  (void) reason;
  Serial.println();
  Serial.print("Disconnected, reason = 0x"); Serial.println(reason, HEX);
}

void startAdv(void)
{
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
    (void) conn_handle;
    static bool json_started = false;
    static int brace_count = 0;
    static int brace_state = 0;
    while (bleuart.available()) {
        char c = (char)bleuart.read();
        Serial.print(c); // USB Serial’e aktar
        // Détecter le début d'un JSON
        if (c == '{' && !json_started) {
            json_started = true;
            brace_count = 0;
            brace_state=1;
            rxBuffer = ""; // Vider le buffer pour un nouveau message
        }
        
        if (json_started) {
            rxBuffer += c;
            if (c == '{') brace_count++;
            if (c == '}') brace_count--;
            
            // JSON complet détecté
            if (brace_count == 0 && rxBuffer.length() > 2) {
                callback = true;
                json_started = false;
                break;
            }
        }
    }
}

void parseJsonBuffer(const String &buffer) {
  if (buffer.length() == 0) return; // boş string geldiyse çık

  // CORRECTION : Nettoyer le buffer des caractères de contrôle et newlines
  String cleanBuffer = buffer;
  cleanBuffer.trim(); // Enlever les espaces et newlines au début/fin
  
  // Optionnel : debug pour voir ce qu'on reçoit
  Serial.print("Received buffer length: ");
  Serial.println(cleanBuffer.length());
  Serial.print("Buffer content: ");
  Serial.println(cleanBuffer);

  StaticJsonDocument<2048> doc;
  DeserializationError err = deserializeJson(doc, cleanBuffer); // Utiliser cleanBuffer

  if (err) {
    Serial.print("JSON parse error: ");
    Serial.println(err.f_str());
    return;
  }


 if (doc.containsKey("state")) {
    mysistem.state = doc["state"] | false;
  }

  // sequences kısmını al
  if (doc.containsKey("sequences") && doc["sequences"].is<JsonArray>()) {
    JsonArray arr = doc["sequences"].as<JsonArray>();

    for (JsonObject obj : arr) {
      int pin      = obj["led_pin"]      | -1;
      int openMs   = obj["time_open_ms"] | 0;
      int delayMs  = obj["time_delay_ms"]| 0;
      int readMs   = obj["time_read_ms"] | 0;
      bool enabled = obj["enabled"]      | false;
      /*
      Serial.print("Pin: "); Serial.print(pin);
      Serial.print(" open: "); Serial.print(openMs);
      Serial.print(" delay: "); Serial.print(delayMs);
      Serial.print(" read: "); Serial.print(readMs);
      Serial.print(" enabled: "); Serial.println(enabled);
      */
      pin--;
      if (enabled && pin >= 0 && pin < 4) {
        mysistem.state = true;
        myleds.leds[pin].kalansure       = openMs;
        mysistem.myAds.adc_delay[pin]    = delayMs;
        mysistem.myAds.adc_readtime[pin] = readMs;
        mysistem.myAds.read_state[pin]   = true;
      } 
      else if (pin >= 0 && pin < 4) {
        mysistem.myAds.read_state[pin] = false;
        //mysistem.myAds.adc[pin]=0;
      }
    }
  } else {
    Serial.println("JSON içinde sequences bulunamadı!");
  }
}

extern "C" void TIMER1_IRQHandler(void) {
  if (NRF_TIMER1->EVENTS_COMPARE[0]) {
    NRF_TIMER1->TASKS_STOP = 1; 
    NRF_TIMER1->EVENTS_COMPARE[0] = 0;   // Bayrak temizle
    digitalWrite(itr+4,LOW);
    dongu_led[itr]=true;
  }
}

void timer1_init() {
  NRF_TIMER1->TASKS_STOP = 1; 
  NRF_TIMER1->MODE = TIMER_MODE_MODE_Timer;
  NRF_TIMER1->BITMODE = TIMER_BITMODE_BITMODE_32Bit << TIMER_BITMODE_BITMODE_Pos;
  NRF_TIMER1->PRESCALER = 4;               // 1 MHz (1 µs per tick)

  NRF_TIMER1->INTENSET = TIMER_INTENSET_COMPARE0_Enabled << TIMER_INTENSET_COMPARE0_Pos;
  NRF_TIMER1->SHORTS = TIMER_SHORTS_COMPARE0_CLEAR_Enabled << TIMER_SHORTS_COMPARE0_CLEAR_Pos;

  NVIC_EnableIRQ(TIMER1_IRQn);

}

/*
gelen veri yapısı
state
timeopen led'in yanma süresi ms
timedelay led yanmaya başladıktan timedelay ms sonra adc verisini okumaya başla
time read   
pin (0,1,2,3)
*/
