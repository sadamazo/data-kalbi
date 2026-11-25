SELECT data_date AS report_date, site_url, search_type,
  SUM(clicks) AS clicks, SUM(impressions) AS impressions,
  SUM(sum_top_position) AS position_sum_zero_based,
  SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(sum_top_position), SUM(impressions)) + 1 AS avg_position
FROM `$search.searchdata_site_impression`
GROUP BY 1, 2, 3
