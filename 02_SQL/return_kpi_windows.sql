-- =============================================================================
-- eBay Return Analysis - KPI comparison windows
-- Feeds the three KPI cards (this month / last month / same month last year).
-- Same Returns metric and same eBay scope as ebay_return_analysis.sql; the only
-- difference is that a window is NOT restricted to the rows that returned in the
-- reporting period, so each window gives that month's true return count.
-- Grain is the four fields the report filters on, so the cards can respond to the
-- Account, Market Place, SKU and Listing ID controls.
-- Keep the six date literals below in step with ebay_return_analysis.sql.
-- =============================================================================
WITH params AS (
    SELECT DATE '2026-08-01' AS p_start,  DATE '2026-09-01' AS p_end,
           DATE '2026-07-01' AS lm_start, DATE '2026-08-01' AS lm_end,
           DATE '2025-08-01' AS ly_start, DATE '2025-09-01' AS ly_end
),

windows AS (
    SELECT 'period'     AS window_key, p_start  AS w_start, p_end  AS w_end FROM params
    UNION ALL
    SELECT 'last_month' AS window_key, lm_start AS w_start, lm_end AS w_end FROM params
    UNION ALL
    SELECT 'last_year'  AS window_key, ly_start AS w_start, ly_end AS w_end FROM params
)

SELECT w.window_key,
       r.item_id::text                                AS listing_id,
       COALESCE(NULLIF(oi.real_sku, ''), oi.item_sku) AS sku,
       ss.map_name                                    AS account,
       r.market_place_code                            AS market_place,
       COUNT(DISTINCT r.return_id)                    AS returns
FROM windows w
JOIN customer_service.ebay_returns r
  ON r.res_his_order = 0
 AND r.request_date >= w.w_start
 AND r.request_date <  w.w_end
JOIN order_management.order_item_info oi
  ON oi.item_transaction_id = r.transaction_id
LEFT JOIN order_management.sub_source ss
  ON ss.id = r.sub_source
GROUP BY w.window_key, r.item_id, COALESCE(NULLIF(oi.real_sku, ''), oi.item_sku),
         ss.map_name, r.market_place_code
ORDER BY w.window_key, listing_id, sku;
