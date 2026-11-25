WITH accounts AS (
  SELECT customer_id, MAX(customer_currency_code) AS currency_code
  FROM `$ads_customer`
  WHERE _DATA_DATE = _LATEST_DATE
  GROUP BY 1
),
totals AS (
  SELECT s._DATA_DATE AS report_date, CAST(s.customer_id AS STRING) AS customer_id,
    a.currency_code, COUNT(*) AS raw_rows, SUM(s.metrics_impressions) AS impressions,
    SUM(s.metrics_clicks) AS clicks, SUM(CAST(s.metrics_cost_micros AS NUMERIC)) / 1000000 AS cost,
    SUM(s.metrics_conversions) AS conversions
  FROM `$ads_stats` AS s
  LEFT JOIN accounts AS a USING (customer_id)
  WHERE s._DATA_DATE BETWEEN @start AND @end
  GROUP BY 1, 2, 3
),
daily AS (
  SELECT report_date, ARRAY_AGG(STRUCT(customer_id, currency_code, raw_rows, impressions, clicks,
    cost, conversions) ORDER BY customer_id) AS account_totals
  FROM totals
  GROUP BY 1
)
SELECT report_date, IF(account_totals IS NULL, 'no_rows_check_run', 'present') AS coverage,
  account_totals
FROM UNNEST(GENERATE_DATE_ARRAY(@start, @end)) AS report_date
LEFT JOIN daily USING (report_date)
ORDER BY report_date
