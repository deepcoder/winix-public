-- retrieve by room and show age of last up in decimal minutes
SELECT
    to_char(last_updated, 'YYYYMMDD HH24:MI:SS') AS "last update",
    attributes::json ->> 'room' AS room,
    round(extract(epoch FROM (attributes::json ->> 'update_age_text')::interval)::numeric / 60, 1) AS "age min",
    attributes::json ->> 'power_text' AS power,
    attributes::json ->> 'unit_sleeping_text' AS sleep,
    attributes::json ->> 'unit_plasmawave_text' AS pwave,
    attributes::json ->> 'unit_mode_text' AS mode,
    attributes::json ->> 'air_quality_text' AS aqt,
    (attributes::json ->> 'air_quality_value')::numeric AS aqv,
    (attributes::json ->> 'unit_fan_speed_text')::numeric AS fan,
    (attributes::json ->> 'unit_ambient_light')::numeric AS light,
    (attributes::json ->> 'unit_filter_hours')::numeric AS "filter hr",
    (attributes::json ->> 'unit_rssi')::numeric AS rssi
FROM
    states_archive_01
WHERE
    last_updated > now() - interval '0.5 day'
    AND entity_id LIKE 'sensor.air_quality%'
ORDER BY
    room,
    last_updated DESC;