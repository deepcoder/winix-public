# winix-public
Python 3 program that download Winix C545 status from cloud and publishes to MQTT

Winix air purifiers listed in winix-01.yaml

Other attributes are still hard code in app:
```
MQTT server and topic
Directories
Query period
RSYSLOG server
```

The program is run from the 'real' directory on host machine, I do NOT copy the python program into the docker container, this is why the --user command is necessary to make sure the 'user' user inside the docker container has rights to write to the log files in the real home directory for the app.

Docker information:
```
docker build -t winix01 .

docker-run.sh
```
Data retrieved from unit and published to MQTT in JSON:
```
{
  "timestamp": "1604965716",
  "unit_update_ts": "1604964396",
  "update_age_text": "0:22:00",
  "unit_model": "C545",
  "home": "North Beach",
  "room": "Small Bedroom",
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
    "deviceId": "abcdefg_zzzzzz",
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
