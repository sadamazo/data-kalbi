SELECT data_date AS report_date, site_url, search_type,
  NULLIF(query, '') AS search_query, url AS page_url, is_anonymized_query,
  SUM(clicks) AS clicks, SUM(impressions) AS impressions,
  SUM(sum_position) AS position_sum_zero_based,
  SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(sum_position), SUM(impressions)) + 1 AS avg_position
FROM `$search.searchdata_url_impression`
GROUP BY 1, 2, 3, 4, 5, 6
