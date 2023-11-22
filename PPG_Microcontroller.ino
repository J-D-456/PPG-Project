#include "BluetoothSerial.h"
#include "switch.h"

#define BAUD 115200
#define SENSOR_PIN 25
#define LED_PULSE 32
#define LED_RECORD 33
#define SWITCH_RECORD 34
#define SWITCH_EXIT 35

#define SAMPLE_PERIOD_US 20000


#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Please run `make menuconfig` to and enable it
#endif

#include "BluetoothSerial.h"
#include <Esp.h>

String btName = "ESP32testG01";
bool connected;

BluetoothSerial SerialBT;

// number of data points included in sample
const uint16_t samples_per_packet = 1000000/SAMPLE_PERIOD_US;

const uint16_t packet_string_size = 5*samples_per_packet + 100;
char packet_string[packet_string_size];

// signal values
uint16_t sensor_val = 0;
float heart_rate = 0;
bool button_status = false;

// timers for ms and 1s
unsigned long timer_ms = 0;
unsigned long timer_1s = 0;

// packet sequence number (0-99 loop)
uint8_t packet_seq_no = 0;

uint8_t sample_count = 0;

static unsigned long last_transition;

// Define switch data
#define DEBOUNCE_CNT 5
Switch switch_1(1, DEBOUNCE_CNT);
Switch switch_2(1, DEBOUNCE_CNT);

// Adaptive Threshold
int threshold = 3000;
int count_2_sec = 0;
int max_size = 250;
int record_list[250];
int current_size = 0;
int sum;
int average;


// Misc
bool latching_1 = false;
bool latching_2 = false;
bool control = true;
bool Pulse_Threshold = 0;
bool prev_state = 0;


void setup() {
  Serial.begin(BAUD);
  
  pinMode(LED_PULSE, OUTPUT);
  pinMode(LED_RECORD, OUTPUT);
  pinMode(SWITCH_RECORD, INPUT);
  pinMode(SWITCH_EXIT, INPUT);
  digitalWrite(LED_PULSE, 0);
  digitalWrite(LED_RECORD, 0);

  timer_ms = micros();
  timer_1s = timer_ms;


// BLUETOOTH
  SerialBT.register_callback(btCallback);

  SerialBT.begin(btName); //Bluetooth device name

  if (!SerialBT.begin(btName)){
    Serial.println("An error occurred initializing Bluetooth");
  }
  else{
    Serial.println("Bluetooth initialized");
    Serial.println(btName);
  }
}

void loop() {

  // this code block happens every SAMPLE_PERIOD_US
  if ((micros() - timer_ms) > SAMPLE_PERIOD_US) {

    // get sensor sample, add to packet string, increment sample_count
    sensor_val = analogRead(SENSOR_PIN);

    Serial.println(sensor_val); // To be plotted on the serial plotter

    sprintf(packet_string + sample_count*5, "%04d,", sensor_val);
    sample_count++;

    if (current_size < max_size){
      record_list[current_size] = sensor_val;
      current_size++;
      }
    else{
      for (int i = 1; i < max_size; i++){
        record_list[i - 1] = record_list[i];
        }
      record_list[max_size - 1] = sensor_val;
      }

  if (switch_1.update(digitalRead(SWITCH_RECORD))){
      //Serial.printf("New switch state: ->%x\n", switch_1.state());
      if (switch_1.state()){
        latching_1 = !latching_1;
        //Serial.printf("Latching signal state ->%x\n", latching_1);
        }
    }
    // Serial.printf("Latching signal state ->%x\n", latching_1);
    if (control == latching_1) {
      digitalWrite(LED_RECORD, 1);
    }
    else {
      digitalWrite(LED_RECORD, 0);
    }
    // reset timer_ms
    timer_ms = micros();
    if (switch_2.update(digitalRead(SWITCH_EXIT))){
      if (switch_2.state()){
        latching_2 = !latching_2;
          }
      }
  }

  if (sensor_val > threshold) {
    digitalWrite(LED_PULSE, 1);
    Pulse_Threshold = 1;
    if (prev_state != Pulse_Threshold) {
    unsigned long new_transition = millis();
    unsigned long pulse_period = new_transition - last_transition;
    last_transition = new_transition;
    heart_rate = 60000.0 / pulse_period;
    //Serial.printf("%.1f\n", heart_rate);
    if (heart_rate >999.9) {
      heart_rate = 999.9;
    }
   }
  }
 
  else {
    digitalWrite(LED_PULSE, 0);
    Pulse_Threshold = 0;
  }

  prev_state = Pulse_Threshold;

  // this code block happens if 'samples_per_packet' samples have been taken AND 1 second has elapsed.
  if ((sample_count >= samples_per_packet) && ((micros() - timer_1s) > 1000000)) {

    // add extra values and newline to packet_string
    sprintf(packet_string + sample_count*5, "%01d,%05.1f,%02d\n", latching_1, heart_rate, packet_seq_no);

    // print packet, increment packet sequence number
    SerialBT.printf(packet_string);
    packet_seq_no = (packet_seq_no + 1) % 100;

    // reset
    timer_1s = micros();
    sample_count = 0;
    count_2_sec++;
    if (count_2_sec > 2){
      count_2_sec = 1;
      for (int i = 0; i < max_size; i++){
        sum += record_list[i];
        }
      average = sum / max_size;
      threshold = average + 200;
      sum = 0;
      Serial.printf("\nThreshold is: %d\n", threshold);
      }
  }
}

int openEvt = 0;

void btCallback(esp_spp_cb_event_t event, esp_spp_cb_param_t *param)
//
// This function displays SPP events when they occur. This provides
// information on what is hapening on the bluetooth link.
//
//
{
  if (event == ESP_SPP_SRV_OPEN_EVT) {
    char buf[50];
    openEvt++;
    sprintf(buf, "Client Connected:%d", openEvt);
    Serial.println(buf);
    Serial.print("  Address = ");

    for (int i = 0; i < 6; i++)
    {
      sprintf(&(buf[i * 3]), "%02X:", param->srv_open.rem_bda[i]);
    }
    buf[17] = 0;
    Serial.println(buf);
  }

  if (event == ESP_SPP_INIT_EVT)
    Serial.println("ESP_SPP_INIT_EVT");
  else if (event == ESP_SPP_UNINIT_EVT)
    Serial.println("ESP_SPP_INIT_EVT");
  else if (event == ESP_SPP_DISCOVERY_COMP_EVT )
    Serial.println("ESP_SPP_DISCOVERY_COMP_EVT");
  else if (event == ESP_SPP_OPEN_EVT )
    Serial.println("ESP_SPP_OPEN_EVT");
  else if (event == ESP_SPP_CLOSE_EVT )
    Serial.println("ESP_SPP_CLOSE_EVT");
  else if (event == ESP_SPP_START_EVT )
    Serial.println("ESP_SPP_START_EVT");
  else if (event == ESP_SPP_CL_INIT_EVT )
    Serial.println("ESP_SPP_CL_INIT_EVT");
  else if (event == ESP_SPP_DATA_IND_EVT )
    Serial.println("ESP_SPP_DATA_IND_EVT");
  else if (event == ESP_SPP_CONG_EVT )
    Serial.println("ESP_SPP_CONG_EVT");
  else if (event == ESP_SPP_WRITE_EVT )
    Serial.println("ESP_SPP_WRITE_EVT");
  else if (event == ESP_SPP_SRV_OPEN_EVT )
    Serial.println("ESP_SPP_SRV_OPEN_EVT");
  else if (event == ESP_SPP_SRV_STOP_EVT )
    Serial.println("ESP_SPP_SRV_STOP_EVT");
  else
  {
    Serial.print("EV: ");
    Serial.println(event);
  };

}
