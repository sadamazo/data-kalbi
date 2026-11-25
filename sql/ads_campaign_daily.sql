WITH campaign_names AS (
  SELECT customer_id, campaign_id,
    ARRAY_AGG(campaign_name IGNORE NULLS ORDER BY _DATA_DATE DESC, campaign_name LIMIT 1)[SAFE_OFFSET(0)] AS campaign_name
  FROM `$ads_campaign`
  WHERE _DATA_DATE = _LATEST_DATE
  GROUP BY 1, 2
),
accounts AS (
  SELECT customer_id, MAX(customer_currency_code) AS currency_code
  FROM `$ads_customer`
  WHERE _DATA_DATE = _LATEST_DATE
  GROUP BY 1
),
daily AS (
  SELECT CAST(segments_date AS DATE) AS report_date, customer_id, campaign_id,
    SUM(metrics_impressions) AS impressions,
    SUM(metrics_clicks) AS clicks,
    SUM(CAST(metrics_cost_micros AS NUMERIC)) / 1000000 AS cost,
    SUM(metrics_conversions) AS conversions,
    SUM(metrics_conversions_value) AS conversion_value
  FROM `$ads_stats`
  GROUP BY 1, 2, 3
)
SELECT d.report_date, CAST(d.customer_id AS STRING) AS customer_id,
  CAST(d.campaign_id AS STRING) AS campaign_id, c.campaign_name, a.currency_code,
  d.impressions, d.clicks, d.cost, d.conversions, d.conversion_value
FROM daily AS d
LEFT JOIN campaign_names AS c USING (customer_id, campaign_id)
LEFT JOIN accounts AS a USING (customer_id)
