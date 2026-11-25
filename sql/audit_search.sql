WITH exports AS (
  SELECT data_date AS report_date,
    COUNTIF(namespace = 'searchdata_site_impression') > 0 AS site_exported,
    COUNTIF(namespace = 'searchdata_url_impression') > 0 AS url_exported
  FROM `$search.ExportLog`
  WHERE data_date BETWEEN @start AND @end
  GROUP BY 1
),
site AS (
  SELECT data_date AS report_date, COUNT(*) AS site_rows,
    SUM(IF(LOWER(search_type) = 'web', clicks, 0)) AS site_web_clicks,
    SUM(IF(LOWER(search_type) = 'web', impressions, 0)) AS site_web_impressions
  FROM `$search.searchdata_site_impression`
  WHERE data_date BETWEEN @start AND @end
  GROUP BY 1
),
page AS (
  SELECT data_date AS report_date, COUNT(*) AS page_rows
  FROM `$search.searchdata_url_impression`
  WHERE data_date BETWEEN @start AND @end
  GROUP BY 1
)
SELECT report_date,
  IF(site_exported AND url_exported AND site_rows > 0 AND page_rows > 0, 'present',
    IF(site_exported AND url_exported, 'logged_check_empty_data', 'no_export_log')) AS coverage,
  site_exported, url_exported, site_rows, page_rows, site_web_clicks, site_web_impressions
FROM UNNEST(GENERATE_DATE_ARRAY(@start, @end)) AS report_date
LEFT JOIN exports USING (report_date)
LEFT JOIN site USING (report_date)
LEFT JOIN page USING (report_date)
ORDER BY report_date
