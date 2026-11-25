WITH events AS (
  SELECT PARSE_DATE('%Y%m%d', event_date) AS report_date, event_name, user_pseudo_id, stream_id,
    session_traffic_source_last_click.cross_channel_campaign.source AS session_source,
    session_traffic_source_last_click.cross_channel_campaign.medium AS session_medium,
    (SELECT MAX(IF(key = 'ga_session_id', value.int_value, NULL)) FROM UNNEST(event_params)) AS session_id,
    (SELECT MAX(IF(key = 'engagement_time_msec', value.int_value, NULL)) FROM UNNEST(event_params)) AS engagement_ms
  FROM `$ga4.events_20*`
  WHERE REGEXP_CONTAINS(_TABLE_SUFFIX, r'^\d{6}$$')
)
SELECT report_date, session_source, session_medium,
  COUNT(*) AS events,
  COUNT(DISTINCT user_pseudo_id) AS observed_users,
  COUNT(DISTINCT IF(event_name = 'session_start' AND user_pseudo_id IS NOT NULL AND session_id IS NOT NULL,
    TO_JSON_STRING(STRUCT(stream_id, user_pseudo_id, session_id)), NULL)) AS observed_sessions_started,
  SUM(COALESCE(engagement_ms, 0)) / 1000 AS engagement_seconds,
  $key_events AS configured_key_event_occurrences
FROM events
GROUP BY 1, 2, 3
