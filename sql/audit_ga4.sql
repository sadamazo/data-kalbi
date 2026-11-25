WITH totals AS (
  SELECT PARSE_DATE('%Y%m%d', CONCAT('20', _TABLE_SUFFIX)) AS report_date,
    COUNT(*) AS events, COUNTIF(event_name = 'session_start') AS session_start_events,
    COUNT(DISTINCT user_pseudo_id) AS observed_users
  FROM `$ga4.events_20*`
  WHERE _TABLE_SUFFIX BETWEEN '$start_suffix' AND '$end_suffix'
    AND REGEXP_CONTAINS(_TABLE_SUFFIX, r'^\d{6}$$')
  GROUP BY 1
)
SELECT report_date, IF(events IS NULL, 'no_events_check_export', 'present') AS coverage,
  events, session_start_events, observed_users
FROM UNNEST(GENERATE_DATE_ARRAY(@start, @end)) AS report_date
LEFT JOIN totals USING (report_date)
ORDER BY report_date
