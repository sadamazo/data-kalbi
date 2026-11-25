SELECT PARSE_DATE('%Y%m%d', event_date) AS report_date, event_name,
  COUNT(*) AS event_count
FROM `$ga4.events_20*`
WHERE REGEXP_CONTAINS(_TABLE_SUFFIX, r'^\d{6}$$')
GROUP BY 1, 2
