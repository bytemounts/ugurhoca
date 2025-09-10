#include "ads.h"
#include "ledController.h"
#include "sistem.h"
#include <bluefruit.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <ArduinoJson.h>

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


int toplam[4];
unsigned long baslangiczamani;
unsigned long prev;
unsigned long json_delay = 20; //ms cinsinden belirli sürede bir json gönderme ayarı, şuanda kullanım dışı.
int itr=0;

bool dongu_led[4]={0,0,0,0};
bool dongu_delay[4]={0,0,0,0};
bool dongu_read_finish[4]={0,0,0,0};
bool callback=false;

String rxBuffer = "";
String gonderilecek_json="";
void setup() {
  Serial.begin(9600);
  while(!Serial); // bazı nRF kartlarda gerekli
  printResetReason();
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

  myleds.begin();
  mysistem.myAds.begin();
}

void loop() {
  if(!mysistem.myAds.is_adc_started) {
    mysistem.myAds.begin();
  }

  if (Bluefruit.connected()) {
    myleds.update();
    if(callback){
      parseJsonBuffer(rxBuffer);
      rxBuffer="";
      
      Serial.print("cp  7");
    }


    if(mysistem.state && mysistem.myAds.read_state[itr]){
      //itr ile döngüyü kontrol et 3 bool tipi ile kontrolü sağla 
      if(!dongu_led[itr] && !dongu_delay[itr] && !dongu_read_finish[itr]){
        //en başta buraya girer ve başlangıç ayarları yapılır.
        prev=millis();
        timer_start_handle(itr);
        Serial.print("cp1 ");
      }

      if(dongu_delay[itr] == true){
        //delay işlemi bittiyse içeri girer ve her bir loopta okuma yapar.
        
        
        if(millis()- baslangiczamani < mysistem.myAds.adc_readtime[itr]){//readtime kadar okur
          mysistem.myAds.adc[itr] = mysistem.myAds.ads.readADC_SingleEnded(itr);//adc okuma kısmı
          gonderilecek_json = makeJsonPayload(mysistem.myAds.adc);
          sendJsonPayload(gonderilecek_json);
          Serial.print(gonderilecek_json);
          Serial.print("cp3 ");
        }else dongu_read_finish[itr]=true;
      }
      else{//dongu delay süreci
        if(millis()-prev > toplam[itr]){
          //delay süresi bittiyse dongu_delay[itr] true yap. ve okuma işlemi başlayabilir.
          dongu_delay[itr]=true;
          baslangiczamani = millis();
        }
      }
      if(dongu_led[itr] ==true && dongu_delay[itr]==true && dongu_read_finish[itr]==true){
        timer_stop_handle(itr);//timer sıfırla, timer durdur
        dongu_led[itr]=false;
        dongu_delay[itr]=false;
        dongu_read_finish[itr]=false;
        if(itr == 3)itr=0;
        else itr++;
        Serial.print("cp4");//debug
      }
    }
    

    
    
  }else{
    if(mysistem.myAds.is_adc_started){
      //bluetooth bağlantısı gerçekleşmemiştir bunun anlaşılabilir olması için ve adc ile kart arassında I2C haberleşmesinin başladığını kabul ederek
      //adc led debugging metodu ile karışmaması için LED sürekli yanar eğer bluetooth bağlantısı yoksa.
      digitalWrite(LED_BUILTIN,HIGH);
    }
  }
  if(digitalRead(itr+4) == HIGH)dongu_led[itr]=true;


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
    static int brace_count = 0;
    static bool in_string = false;
    static bool escape = false;

    while (bleuart.available()) {
        char c = (char)bleuart.read();
        rxBuffer += c;

        
        if (escape) { escape = false; continue; }
        if (c == '\\') { escape = true; continue; }
        if (c == '"') { in_string = !in_string; }
        if (!in_string) {
            if (c == '{') brace_count++;
            if (c == '}') brace_count--;
        }
        if (brace_count == 0 && rxBuffer.length() > 0) {
            callback=true;
        }
    }
}

// ---- JSON parse fonksiyonu ----
void parseJsonBuffer(const String &buffer) {
  callback=false;
  StaticJsonDocument<2048> doc;
  DeserializationError err = deserializeJson(doc, buffer);
  Serial.print(buffer);
  if (err) {
    Serial.print("JSON parse error: ");
    Serial.println(err.f_str());
    return;
  }

  // Sequences array varsa işle
  if (doc["sequences"].is<JsonArray>()) {
    JsonArray arr = doc["sequences"].as<JsonArray>();
    for (JsonObject obj : arr) {
      int pin      = obj["led_pin"] | -1;
      int openMs   = obj["time_open_ms"] | 0;
      int delayMs  = obj["time_delay_ms"] | 0;
      int readMs   = obj["time_read_ms"] | 0;
      bool enabled = obj["enabled"] | false;

      Serial.print("Pin: "); Serial.print(pin);
      Serial.print(" open: "); Serial.print(openMs);
      Serial.print(" delay: "); Serial.print(delayMs);
      Serial.print(" read: "); Serial.print(readMs);
      Serial.print(" enabled: "); Serial.println(enabled);
      if (enabled && pin >= 0 && pin < 4) {
        mysistem.state=true;
        myleds.leds[pin].kalansure       = openMs * 1000;
        mysistem.myAds.adc_delay[pin]    = delayMs;
        mysistem.myAds.read_state[pin] = true;
        handle(pin, openMs * 1000,delayMs*1000);
        digitalWrite(myleds.pinNos[pin], HIGH);
        timer_interrupt_set(pin);
      } 
      else if (pin >= 0 && pin < 4) {
        mysistem.myAds.read_state[pin] = false;
        timer_stop_handle(pin);
      }


    }
  }
}

void timer_start_handle(int id){
  switch(id){
    case 0:
    NRF_TIMER1->TASKS_START = 1;
    break;
    case 1:
    NRF_TIMER2->TASKS_START = 1;
    break;
    case 2:
    NRF_TIMER3->TASKS_START = 1;
    break;
    case 3:
    NRF_TIMER4->TASKS_START = 1;
    break;
    default:
    break;
  }
}

void timer_stop_handle(int id){
  switch(id){
    case 0:
    NRF_TIMER1->TASKS_CLEAR=1;
    NRF_TIMER1->TASKS_STOP = 1;
    break;
    case 1:
    NRF_TIMER2->TASKS_CLEAR=1;
    NRF_TIMER2->TASKS_STOP = 1;
    break;
    case 2:
    NRF_TIMER1->TASKS_CLEAR=1;
    NRF_TIMER3->TASKS_STOP = 1;
    break;
    case 3:
    NRF_TIMER1->TASKS_CLEAR=1;
    NRF_TIMER4->TASKS_STOP = 1;
    break;
    default:
    break;
  }
}

void timer_interrupt_set(int id){
  switch(id){
    case 0:
    NRF_TIMER1->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
    break;
    case 1:
    NRF_TIMER2->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
    break;
    case 2:
    NRF_TIMER3->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
    break;
    case 3:
    NRF_TIMER4->INTENSET = TIMER_INTENSET_COMPARE0_Msk;
    break;
    default:
    break;
  }
}


void handle(int8_t led_id,uint32_t time_open_v,uint32_t delay_ms){
  switch(led_id){
    case 0:
    NRF_TIMER1->TASKS_STOP = 1;
    NRF_TIMER1->TASKS_CLEAR = 1;
    NRF_TIMER1->CC[0]=time_open_v;
    NRF_TIMER1->CC[1]=delay_ms;
    break;

    case 1:
    NRF_TIMER2->TASKS_STOP = 1;
    NRF_TIMER2->TASKS_CLEAR = 1;
    NRF_TIMER2->CC[0]=time_open_v;
    NRF_TIMER2->CC[1]=delay_ms;
    break;

    case 2:
    NRF_TIMER3->TASKS_STOP = 1;
    NRF_TIMER3->TASKS_CLEAR = 1;
    NRF_TIMER3->CC[0]=time_open_v;
    NRF_TIMER3->CC[1]=delay_ms;
    break;

    case 3:
    NRF_TIMER4->TASKS_STOP = 1;
    NRF_TIMER4->TASKS_CLEAR = 1;
    NRF_TIMER4->CC[0]=time_open_v;
    NRF_TIMER4->CC[1]=delay_ms;
    break;

    default:
    break;
  }
}


void printResetReason() {
  uint32_t reas = NRF_POWER->RESETREAS;
  Serial.print("RESETREAS = 0x"); Serial.println(reas, HEX);
  // clear
  NRF_POWER->RESETREAS = reas;
}



/*
gelen veri yapısı
state
timeopen led'in yanma süresi ms
timedelay led yanmaya başladıktan timedelay ms sonra adc verisini okumaya başla
time read   
pin (0,1,2,3), -1 için hepsi olsun
*/
