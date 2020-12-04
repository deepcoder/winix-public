# winix
Winix python program to get current status of Winix air purifier units and publish to MQTT.

Requires Python version 3.7

check the top of the program module, winix-02.py for the line:
```
WORKING_DIRECTORY = "/home/user/winix/"
```

this is the directory where the program reads its configuration file 'winix-02.yaml' and also writes it log files 'winix-02.log', make sure your program has read and write rights to this directory.




Built on the strong work and shoulders of these fine github contributors:

```
@hfern
https://github.com/hfern/winix

@evandcoleman
https://github.com/evandcoleman/python-winix

@banzalik
https://github.com/banzalik/homebridge-winix-c545

@home-assistant

@homebridge
```

MQTT topic and server, syslog server, logging, and update period are configured in file : winix-02.yaml

Python 3 program downloads the data from Winix air purifiers listed in  winix-02.yaml

The program is run from the 'real' directory on host machine, I do NOT copy the python program into the docker container, this is why the --user command is necessary to make sure the 'user' user inside the docker container has rights to write to the log files in the real home directory for the app.

MQTT topic base in in config file. Each unit in config file publishes it information under base topic followed by it's MAC address, for example:

```
winix/11:22:33:44:55:66
```

each unit looks for control command under the sub topic /control, for example:

```
winix/11:22:33:44:55:66/control/"command"
```

for example to power the unit on, the MQTT topic for unit with MAC address 11:22:33:44:55:66 is:

```
winix/11:22:33:44:55:66/control/power
```

with a message of "ON"

all message are strings NOT numbers.

You can run it without Docker, as long as you have all the python 3 pip3 requirements.txt installed:

```
python3 winix02.py
```

or build a docker container with the pip3 requirements.

Docker information:
```
docker build -t winix02 .

# remove current docker container first

./docker-run.sh
```

```
MQTT commands:

# power on or off
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/power -m "OFF"
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/power -m "ON"

# auto or manual mode
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/mode -m "AUTO"
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/mode -m "MANUAL"

# plasmawave filter
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/plasmawave -m "ON"
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/plasmawave -m "OFF"

# sleep mode
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/sleep -m "ON"
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/sleep -m "OFF"

# fan speed adjust
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/fan_speed -m "100"
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/fan_speed -m "75"
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/fan_speed -m "50"
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/fan_speed -m "25"

# request a update of info for this unit from winix cloud
mosquitto_pub -h 192.168.xxx.yyy -t winix/aa:bb:cc:dd:ee:ff/control/update -m ""
```





Data retrieved from unit and published to MQTT:
```json
{
  "timestamp": "1604965716",
  "unit_update_ts": "1604964396",
  "update_age_text": "0:22:00",
  "unit_model": "C545",
  "home": "Home City",
  "room": "Room",
  "unit_power_ordinal": "1",
  "power_text": "ON",
  "unit_sleeping_text": "NO",
  "air_quality_ordinal": "1",
  "air_quality_text": "GOOD",
  "air_quality_value": "134",
  "unit_plasmawave_ordinal": "1",
  "unit_plasmawave_text": "ON",
  "unit_mode_ordinal": "2",
  "unit_mode_text": "MANUAL",
  "unit_fan_speed_ordinal": "1",
  "unit_fan_speed_text": "25",
  "unit_filter_hours": "4483",
  "unit_ambient_light": "82",
  "unit_rssi": "-56",
  "unit_body_json": {
    "deviceId": "xxxxxxx_yyyyyyyyy",
    "totalCnt": 1,
    "data": [
      {
        "apiNo": "A210",
        "apiGroup": "001",
        "deviceGroup": "Air01",
        "modelId": "C545",
        "attributes": {
          "A02": "1",
          "A03": "02",
          "A04": "01",
          "A05": "01",
          "A07": "1",
          "A21": "4483",
          "S07": "01",
          "S08": "134",
          "S14": "82"
        },
        "rssi": "-56",
        "creationTime": 1604964396861,
        "utcDatetime": "2020-11-09 23:26:36",
        "utcTimestamp": 1604964396
      }
    ]
  }
}
```
Basic decode of known attributes received for C545:

```
attributes:
A02 : Power
A03 : Operation mode
A04 : Fan speed/sleep
A05 : UNKNOWN
A07 : Plasmawave
A21 : Filter age in hours
S07 : Air quality ordinal
S08 : Air quality measure
S14 : Ambient light
```
