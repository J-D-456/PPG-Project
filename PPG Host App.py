import PySimpleGUI as sg
import serial
import time
import sys
import os.path
from datetime import datetime
import numpy as np
import PIL.Image
import base64
import io
import csv

# Resize Image function
def convert_to_bytes(file_or_bytes, resize=None):
    if isinstance(file_or_bytes, str):
        img = PIL.Image.open(file_or_bytes)
    else:
        try:
            img = PIL.Image.open(io.BytesIO(base64.b64decode(file_or_bytes)))
        except Exception as e:
            dataBytesIO = io.BytesIO(file_or_bytes)
            img = PIL.Image.open(dataBytesIO)

    cur_width, cur_height = img.size
    if resize:
        new_width, new_height = resize
        scale = min(new_height/cur_height, new_width/cur_width)
        img = img.resize((int(cur_width*scale), int(cur_height*scale)), PIL.Image.ADAPTIVE)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    del img
    return bio.getvalue()

# Microcontroller Exit
def close_window_on_button_state():
    serialString = serialPort.readline()
    data = serialString.decode("ASCII").strip()  # Removing leading/trailing whitespaces
    data_list = data.split(',') # Split the data by comma
    Exit_state = int(data_list[53])
    return Exit_state
    
previous_psn = 128

# Fonts
def update_font(font, size, font_color):
    window["HEART_RATE"].update(font=(font, size), text_color=font_color)
# Define available font styles, font sizes, and font colors
available_font_styles = ['Arial', 'Times New Roman', 'Courier New', 'Verdana']
available_font_sizes = ['8', '10', '12', '14', '16', '18', '20', '24', '26', '28', '30']
available_font_colors = ['Black', 'Red', 'Green', 'Blue', 'Yellow']

# GUI code
sg.theme('LightGray1')

delay = x = lastx = lasty = 0
x_BPM = lastx_BPM = lasty_BPM = 0

left_layout = [
    [sg.Image(filename="Raw y axis.png", size=(22, 200), key="Raw_y_axis"),
     sg.Graph(canvas_size=(400,200), graph_bottom_left=(0,0), graph_top_right=(400,200), background_color="lightblue", key="Raw_graph")],
    [sg.Image(filename="BPM y axis.png", size=(22, 100), key="BPM_y_axis"),
     sg.Graph(canvas_size=(400, 100), graph_bottom_left=(0,0), graph_top_right=(400, 100), background_color="lightcoral", key="BPM_graph")],
    [sg.Text("High Threshold:", size=(12, 1)),
     sg.Slider(range=(0, 200), default_value=130, orientation="h", key='HIGH_THRESHOLD')],
    [sg.Text("Low Threshold:", size=(12, 1)),
     sg.Slider(range=(0, 200), default_value=60, orientation='h', key='LOW_THRESHOLD')],
]

right_layout = [
    [sg.Image(filename="Heart.png", size=(150, 150), key="Image")],
    [sg.Text("Heart Rate:", size=(12, 1)), 
     sg.Text('', size=(3, 1), key='HEART_RATE')],
    [sg.Text("High Threshold", size=(12, 1)), 
     sg.Graph((30, 30), (30, 30), (0, 0), background_color='white', key='HIGH_CIRCLE')],
    [sg.Text("Low Threshold", size=(12, 1)), 
     sg.Graph((30, 30), (30, 30), (0, 0), background_color='white', key='LOW_CIRCLE')],
    [sg.Text("Packet Alarm", size=(12, 1)), 
     sg.Graph((30, 30), (30, 30), (0, 0), background_color='white', key='PACKET_ALARM')],
    [sg.Text("Recording", size=(12, 1)),
     sg.Graph((30, 30), (30, 30), (0, 0), background_color='white', key='Record_status')],
    [sg.Text("Packet Received in Sequence", size=(12, 1)),
     sg.Graph((30, 30), (30, 30), (0, 0), background_color='white', key='PSN_Order')],
]

bottom_layout = [
    [sg.Text("System Log", size=(12, 1))],
    [sg.Multiline(size=(70, 6), font=("Arial", 10), key="Log_window")],
    [sg.Button('Exit')]
]

layout = [
    [sg.TabGroup([
        [sg.Tab('Monitor', [
            [sg.Column(left_layout), sg.Column(right_layout)],
            [sg.Column(bottom_layout)]
        ]),
        sg.Tab('Settings', [
            [sg.Text('Font Style:'), sg.Combo(available_font_styles, key='_FONT_', default_value='Arial')],
            [sg.Text('Font Size:'), sg.Combo(available_font_sizes, key='_SIZE_', default_value='12')],
            [sg.Text('Font Color:'), sg.Combo(available_font_colors, key='_FONT_COLOR_', default_value='Black')],
            [sg.Button('Apply', key='_APPLY_')]
        ])
        ]
    ])
    ]
]

window = sg.Window('Heart Monitor', layout, finalize=True)

directory = os.path.dirname(os.path.abspath(__file__))
logo_filename = "Heart.png"
logo_filepath = os.path.join(directory, logo_filename)
size_on_gui = 150, 150
window["Image"].update(data=convert_to_bytes(logo_filepath, size_on_gui))

logo_filename = "Raw y axis.png"
logo_filepath = os.path.join(directory, logo_filename)
size_on_gui = 22, 200
window["Raw_y_axis"].update(data=convert_to_bytes(logo_filepath, size_on_gui))

logo_filename = "BPM y axis.png"
logo_filepath = os.path.join(directory, logo_filename)
size_on_gui = 22, 100
window["BPM_y_axis"].update(data=convert_to_bytes(logo_filepath, size_on_gui))

# Recording data lists
record_list = []
time_from_record_start = []
date = []
clock_time = []
previous_button_state = 0
raw_data = []

# High to Low Pulse state anti-spam
current_high_low_pulse = "middle"
previous_high_low_pulse = current_high_low_pulse

# Other global variables
raw_count = 0
packet_alarm_state = 0
previous_packet_alarm_state = packet_alarm_state


# Bluetooth 
serialString = ""  # Used to hold data coming over UART
portName = "COM3"          # PC format

# define the serial port.
# specify parameters as needed
serialPort = serial.Serial()
serialPort.port=portName
serialPort.baudrate=115200
serialPort.bytesize=8
serialPort.timeout=2
serialPort.stopbits=serial.STOPBITS_ONE

if __name__ == "__main__":
    # Opening the port
    try:
        serialPort.open()
    except:
        print("Port open failed: " + portName)
        for e in sys.exc_info():
            print("  ",e)

packet_received_time = time.time() # Packet receive time

while True:
    event, values = window.read(timeout=10)
    if event in (sg.WIN_CLOSED, 'Exit'):
        break

    # Events occur when the if serial port is open
    if serialPort.isOpen():
        # Wait until there is data waiting in the serial buffer
        if serialPort.in_waiting > 0:

            # Read data out of the buffer until a carraige return / new line is found
            serialString = serialPort.readline()
            data = serialString.decode("ASCII").strip()  # Removing leading/trailing whitespaces
            data_list = data.split(',') # Split the data by commas

            if len(data_list) == 53: # Extract the data (Can add more code for errors if data package isn't 53 elements)
                raw_data = list(map(int, data_list[:50]))
                button_state = int(data_list[50])
                heart_rate = float(data_list[51])
                PSN = int(data_list[52])

                window['HEART_RATE'].update(heart_rate)  # Update the heart rate display

                high_threshold = values['HIGH_THRESHOLD']
                low_threshold = values['LOW_THRESHOLD']
                high_circle = window['HIGH_CIRCLE']
                low_circle = window['LOW_CIRCLE']
                record_circle = window['Record_status']

                if PSN == previous_psn + 1 or PSN == previous_psn - 99 or previous_psn == 128: # 128 So it doesnt alarm at the beginning
                    # Draw a yellow circle
                    window['PSN_Order'].DrawCircle((15, 15), 10, fill_color='white')
                else:
                    # Draw a white circle
                    window['PSN_Order'].DrawCircle((15, 15), 10, fill_color='yellow')
                    current_time = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
                    window['Log_window'].print(f'{current_time}: Out of Order Sequence of Packets detected: {heart_rate}')
                
                # Update the previous PSN for the next iteration
                previous_psn = PSN

                # Warnings
                if heart_rate > high_threshold: # High heart rate
                    high_circle.DrawCircle((15, 15), 10, fill_color='red')
                    current_high_low_pulse = "high"
                    if previous_high_low_pulse != "high" and low_threshold < high_threshold:
                        current_time = datetime.now().strftime("%H:%M:%S %d-%m-%y")
                        window['Log_window'].print(f'{current_time} - High heart rate detected: {heart_rate}')
                        previous_high_low_pulse = "high"
                else:
                    high_circle.DrawCircle((15, 15), 10, fill_color='white')

                if heart_rate < low_threshold: # Low heart rate
                    low_circle.DrawCircle((15, 15), 10, fill_color='red')
                    current_high_low_pulse = "low"
                    if previous_high_low_pulse != "low" and low_threshold < high_threshold:
                        current_time = datetime.now().strftime("%H:%M:%S %d-%m-%y")
                        window['Log_window'].print(f'{current_time} - Low heart rate detected: {heart_rate}')
                        previous_high_low_pulse = "low"
                else:
                    low_circle.DrawCircle((15, 15), 10, fill_color='white')

                if heart_rate > low_threshold and heart_rate < high_threshold and low_threshold < high_threshold:
                    previous_high_low_pulse = "middle"

                # Record data with button
                if button_state == 1:
                    for i in raw_data:
                        record_list.append(i)

                        current_clock_time = datetime.now().strftime("%H:%M:%S")
                        clock_time.append(current_clock_time)

                        current_date = datetime.now().strftime("%d/%m/%y")
                        date.append(current_date)

                    record_circle.DrawCircle((15, 15), 10, fill_color='green')
                    if previous_button_state == 0:
                        current_time = datetime.now().strftime("%H:%M:%S %d-%m-%y")
                        window['Log_window'].print(f"{current_time} - Data is now being recorded")
                    previous_button_state = button_state

                elif button_state == 0:
                    if previous_button_state == 1: # Checking if button go from recording to finish recording
                        current_time = datetime.now().strftime("%H:%M:%S %d-%m-%y")
                        window['Log_window'].print(f"{current_time} - Data has stopped being recorded and has been saved")

                        # Giving raw data values a time value
                        k = 1
                        for i in record_list:
                            time_from_record_start.append(k*0.02)
                            k = k + 1

                        combined_data = np.column_stack((date, clock_time, time_from_record_start, record_list))

                        # Saving data to a CSV file
                        csv_filename = "Heart Pulse Data.csv"

                        # Save the combined data to a CSV file
                        with open(csv_filename, mode='w', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow(['Date', 'Time','Timer (s)', 'Raw Data'])  # Writing the header
                            writer.writerows(combined_data)  # Writing the data

                    record_circle.DrawCircle((15, 15), 10, fill_color='white')
                    previous_button_state=button_state
                    record_list = []
                    time_from_record_start = []
                    date = []
                    clock_time = []

                if len(raw_data) == 50:
                    y_BPM = heart_rate / 2
                    if x_BPM < 400:               # if still drawing initial width of graph
                        window['BPM_graph'].DrawLine((lastx_BPM, lasty_BPM), (x_BPM, y_BPM), width=1)
                    else:                               # finished drawing full graph width so move each time to make room
                        window['BPM_graph'].Move(-15, 0)
                        window['BPM_graph'].DrawLine((lastx_BPM, lasty_BPM), (x_BPM, y_BPM), width=1)
                        x -= 15
                    lastx_BPM, lasty_BPM = x_BPM, y_BPM
                    x_BPM += 15


                # Reset the packet received time
                packet_received_time = time.time()

        # Check for packet arrival alarm
        if time.time() - packet_received_time > 5:
            packet_alarm = window['PACKET_ALARM']
            packet_alarm.DrawCircle((15, 15), 10, fill_color='red')
            packet_alarm_state = 1
            if packet_alarm_state == 1:
                if previous_packet_alarm_state == 0:
                    window['Log_window'].print(f"{current_time} - Packet not received for 5 seconds")
            previous_packet_alarm_state = packet_alarm_state
        else:
            packet_alarm = window['PACKET_ALARM']
            packet_alarm.DrawCircle((15, 15), 10, fill_color='white')
            previous_packet_alarm_state = packet_alarm_state

        if event == '_APPLY_':
            font = values['_FONT_']
            size = int(values['_SIZE_'])
            font_color = values['_FONT_COLOR_']
            update_font(font, size, font_color)

    if len(raw_data) == 50:
        y = raw_data[raw_count] / 20      # get random point for graph
        window['Raw_plotted_number'].update(raw_data[raw_count])  # Update the heart rate display
        window["Raw_plotted_index"].update(raw_count)
        if x < 400:               # if still drawing initial width of graph
            window['Raw_graph'].DrawLine((lastx, lasty), (x, y), width=1)

        else:                     # finished drawing full graph width so move each time to make room
            window['Raw_graph'].Move(-5, 0)
            window['Raw_graph'].DrawLine((lastx, lasty), (x, y), width=1)
            x -= 5
        lastx, lasty = x, y
        x += 5
        raw_count = raw_count + 1
        if raw_count > 49:
            raw_count = 0
    else:
        window['Log_window'].print("Bluetooth connection has been lost")
        window['Log_window'].print("Trying to reconnect")

window.close()
