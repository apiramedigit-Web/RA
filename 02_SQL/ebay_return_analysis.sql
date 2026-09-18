-- =============================================================================
-- eBay Return Analysis - dataset query
-- Requirement : System Task - Return Analysis - kobiga.pdf
-- Prior spec  : REQ-14-D01 (2026-07-20, abiraj) - column/source rules reused
-- Database    : ledsone (PostgreSQL) - READ ONLY
-- Grain       : one row per (Listing ID, SKU) with >= 1 return in the period
-- Parameters  : the six date literals in the `params` CTE - nothing else
-- =============================================================================
WITH params AS (
    SELECT DATE '2026-08-01' AS p_start,  DATE '2026-09-01' AS p_end,    -- reporting period
           DATE '2026-07-01' AS lm_start, DATE '2026-08-01' AS lm_end,   -- last month
           DATE '2025-08-01' AS ly_start, DATE '2025-09-01' AS ly_end    -- same month, last year
),

-- A. Return universe. res_his_order = 0 is the current row of a return (one per
--    return, reason populated); every other row is resolution history.
--    transaction_id -> order_item_info.item_transaction_id is 1:1 (verified).
returns_base AS (
    SELECT r.return_id,
           r.item_id::text                                AS listing_id,
           COALESCE(NULLIF(oi.real_sku, ''), oi.item_sku) AS sku,
           oi.item_title,
           ss.map_name                                    AS account,
           r.market_place_code                            AS market_place,
           r.reason,
           COALESCE(r.seller_refund_amount, 0)            AS refund,
           r.current_state,
           r.transaction_id,
           r.request_date
    FROM customer_service.ebay_returns r
    JOIN order_management.order_item_info oi
      ON oi.item_transaction_id = r.transaction_id
    LEFT JOIN order_management.sub_source ss
      ON ss.id = r.sub_source
    CROSS JOIN params p
    WHERE r.res_his_order = 0
      AND (   (r.request_date >= p.p_start  AND r.request_date < p.p_end)
           OR (r.request_date >= p.lm_start AND r.request_date < p.lm_end)
           OR (r.request_date >= p.ly_start AND r.request_date < p.ly_end))
),

-- B. Row driver: listing + SKU that had at least one return in the period.
period_returns AS (
    SELECT rb.listing_id,
           rb.sku,
           COUNT(DISTINCT rb.return_id)                                            AS returns,
           SUM(rb.refund)                                                          AS refund_amt,
           COUNT(DISTINCT rb.return_id) FILTER (WHERE rb.current_state <> 'CLOSED') AS open_cases,
           MODE() WITHIN GROUP (ORDER BY rb.reason)                                AS main_return_reason,
           MODE() WITHIN GROUP (ORDER BY rb.item_title)                            AS product_title,
           MODE() WITHIN GROUP (ORDER BY rb.account)                               AS account,
           MODE() WITHIN GROUP (ORDER BY rb.market_place)                          AS market_place
    FROM returns_base rb
    CROSS JOIN params p
    WHERE rb.request_date >= p.p_start AND rb.request_date < p.p_end
    GROUP BY rb.listing_id, rb.sku
),

-- Last Month Refund comes from the same July return population and grain as
-- Last Month Returns. returns_base holds one row per return (res_his_order = 0,
-- 1:1 order-line join), so SUM counts each return's refund exactly once.
last_month_returns AS (
    SELECT rb.listing_id, rb.sku, COUNT(DISTINCT rb.return_id) AS returns,
           SUM(rb.refund)                                       AS refund_amt
    FROM returns_base rb CROSS JOIN params p
    WHERE rb.request_date >= p.lm_start AND rb.request_date < p.lm_end
    GROUP BY rb.listing_id, rb.sku
),

last_year_returns AS (
    SELECT rb.listing_id, rb.sku, COUNT(DISTINCT rb.return_id) AS returns
    FROM returns_base rb CROSS JOIN params p
    WHERE rb.request_date >= p.ly_start AND rb.request_date < p.ly_end
    GROUP BY rb.listing_id, rb.sku
),

-- C. eBay ordered units per listing + SKU for each of the three windows.
--    item_quantity is text-typed in source, so it is cast defensively.
order_units AS (
    SELECT oi.item_id                                     AS listing_id,
           COALESCE(NULLIF(oi.real_sku, ''), oi.item_sku)  AS sku,
           SUM(CASE WHEN o.order_date >= p.p_start  AND o.order_date < p.p_end
                    THEN COALESCE(NULLIF(oi.item_quantity, '')::numeric, 0) ELSE 0 END) AS units_period,
           SUM(CASE WHEN o.order_date >= p.lm_start AND o.order_date < p.lm_end
                    THEN COALESCE(NULLIF(oi.item_quantity, '')::numeric, 0) ELSE 0 END) AS units_lm,
           SUM(CASE WHEN o.order_date >= p.ly_start AND o.order_date < p.ly_end
                    THEN COALESCE(NULLIF(oi.item_quantity, '')::numeric, 0) ELSE 0 END) AS units_ly
    FROM order_management.orders o
    JOIN order_management.sub_source ss ON ss.id = o.sub_source_id
    JOIN order_management.source     s  ON s.id  = ss.source_id AND s.source_name = 'EBAY'
    JOIN order_management.order_item_info oi ON oi.order_id = o.id
    CROSS JOIN params p
    WHERE (o.order_date >= p.ly_start AND o.order_date < p.ly_end)
       OR (o.order_date >= p.lm_start AND o.order_date < p.p_end)
    GROUP BY oi.item_id, COALESCE(NULLIF(oi.real_sku, ''), oi.item_sku)
),

-- D. Period units for the whole listing (all its SKUs) - the basis used to split
--    listing-level ad figures down to the listing + SKU rows without double count.
listing_units AS (
    SELECT listing_id, SUM(units_period) AS units_period
    FROM order_units
    GROUP BY listing_id
),

-- E. Ad spend / ad sales per listing for the period. performance_data carries both
--    campaign types; the *_listing_currency columns are the only pair populated for
--    Promoted Listings Standard (COST_PER_SALE), so both metrics are taken from them.
ads AS (
    SELECT pd.ebay_listing_id::text                          AS listing_id,
           SUM(COALESCE(pd.ad_fees_listing_currency, 0))     AS ad_spend,
           SUM(COALESCE(pd.sale_amount_listing_currency, 0)) AS ad_sales
    FROM ebay_campaigns.performance_data pd
    CROSS JOIN params p
    WHERE pd.date >= p.p_start AND pd.date < p.p_end
    GROUP BY pd.ebay_listing_id::text
),

-- F. Return cost: eBay refund-side selling fees on the returned order lines.
--    In ebay_order_expenses the FINAL_VALUE_FEE rows carry the ORDER LINE id in
--    item_id (14 digits), which is the return's transaction_id.
returned_lines AS (
    SELECT DISTINCT rb.listing_id, rb.sku, rb.transaction_id
    FROM returns_base rb CROSS JOIN params p
    WHERE rb.request_date >= p.p_start AND rb.request_date < p.p_end
),

return_cost AS (
    SELECT rl.listing_id, rl.sku, SUM(COALESCE(e.fee, 0)) AS return_cost
    FROM returned_lines rl
    JOIN accounting.ebay_order_expenses e
      ON e.item_id::text = rl.transaction_id
    WHERE e.transaction_type = 'REFUND'
      AND e.fee_type IN ('FINAL_VALUE_FEE', 'FINAL_VALUE_FEE_FIXED_PER_ORDER')
    GROUP BY rl.listing_id, rl.sku
),

-- G. Negative feedback in the period, resolved to listing + SKU via the order line.
neg_feedback AS (
    SELECT oi.item_id                                    AS listing_id,
           COALESCE(NULLIF(oi.real_sku, ''), oi.item_sku) AS sku,
           COUNT(*)                                      AS negative_feedback
    FROM customer_service.ebay_orders_customer_feedbacks f
    JOIN order_management.order_item_info oi
      ON oi.item_transaction_id = f.transaction_id
    CROSS JOIN params p
    WHERE f.type = 'Negative'
      AND f.date >= p.p_start AND f.date < p.p_end
    GROUP BY oi.item_id, COALESCE(NULLIF(oi.real_sku, ''), oi.item_sku)
),

-- H. Live stock per SKU, summed over every warehouse location.
stock AS (
    SELECT pr.sku, SUM(COALESCE(st.stock, 0)) AS stock
    FROM inventory.products pr
    JOIN inventory.local_inventory_current_stock_location_wise st
      ON st.inventory_id = pr.id
    GROUP BY pr.sku
),

-- I. Assemble the report rows and work out each row's share of its listing's ads.
assembled AS (
    SELECT pr.listing_id,
           pr.sku,
           pr.product_title,
           pr.account,
           pr.market_place,
           COALESCE(ou.units_period, 0) AS total_orders,
           COALESCE(ou.units_lm, 0)     AS lm_orders,
           COALESCE(ou.units_ly, 0)     AS ly_orders,
           pr.returns,
           COALESCE(lm.returns, 0)      AS lm_returns,
           COALESCE(ly.returns, 0)      AS ly_returns,
           pr.refund_amt,
           COALESCE(lm.refund_amt, 0)   AS lm_refund_amt,
           COALESCE(rc.return_cost, 0)  AS return_cost,
           pr.main_return_reason,
           COALESCE(nf.negative_feedback, 0) AS negative_feedback,
           pr.open_cases,
           st.stock,
           COALESCE(ad.ad_spend, 0)     AS listing_ad_spend,
           COALESCE(ad.ad_sales, 0)     AS listing_ad_sales,
           CASE
               WHEN COALESCE(lu.units_period, 0) > 0
                    THEN COALESCE(ou.units_period, 0) / lu.units_period
               ELSE 1.0 / COUNT(*) OVER (PARTITION BY pr.listing_id)
           END AS ad_share
    FROM period_returns pr
    LEFT JOIN order_units        ou ON ou.listing_id = pr.listing_id AND ou.sku = pr.sku
    LEFT JOIN listing_units      lu ON lu.listing_id = pr.listing_id
    LEFT JOIN last_month_returns lm ON lm.listing_id = pr.listing_id AND lm.sku = pr.sku
    LEFT JOIN last_year_returns  ly ON ly.listing_id = pr.listing_id AND ly.sku = pr.sku
    LEFT JOIN return_cost        rc ON rc.listing_id = pr.listing_id AND rc.sku = pr.sku
    LEFT JOIN neg_feedback       nf ON nf.listing_id = pr.listing_id AND nf.sku = pr.sku
    LEFT JOIN stock              st ON st.sku = pr.sku
    LEFT JOIN ads                ad ON ad.listing_id = pr.listing_id
)

SELECT a.listing_id                                        AS "Listing ID",
       a.sku                                               AS "SKU",
       a.product_title                                     AS "Product Title",
       a.account                                           AS "Account",
       a.market_place                                      AS "Market Place",
       a.total_orders::bigint                              AS "Total Orders",
       a.returns                                           AS "Returns",
       CASE WHEN a.total_orders > 0
            THEN ROUND(a.returns / a.total_orders * 100, 2) END          AS "Return Rate",
       a.lm_returns                                        AS "Last Month Returns",
       CASE WHEN a.lm_orders > 0
            THEN ROUND(a.lm_returns / a.lm_orders * 100, 2) END          AS "Last Month Returns %",
       a.ly_returns                                        AS "Last Year Returns",
       CASE WHEN a.ly_orders > 0
            THEN ROUND(a.ly_returns / a.ly_orders * 100, 2) END          AS "Last Year Returns %",
       ROUND(a.refund_amt::numeric, 2)                     AS "Refund",
       ROUND(a.lm_refund_amt::numeric, 2)                  AS "Last Month Refund",
       ROUND(a.return_cost::numeric, 2)                    AS "Return Cost",
       a.main_return_reason                                AS "Main Return Reason",
       RANK() OVER (ORDER BY a.returns DESC, a.refund_amt DESC)         AS "Return Rank",
       a.negative_feedback                                 AS "Negative Feedback",
       a.open_cases                                        AS "Open Cases",
       a.stock                                             AS "Stock",
       a.ad_spend                                          AS "Ad Spend",
       a.ad_sales                                          AS "Ad Sales",
       -- derived from the displayed (rounded) figures so the table is self-consistent
       CASE WHEN a.ad_sales > 0 THEN ROUND(a.ad_spend / a.ad_sales * 100, 2) END AS "ACOS",
       CASE WHEN a.ad_spend > 0 THEN ROUND(a.ad_sales / a.ad_spend, 2)       END AS "ROAS"
FROM (
    SELECT a.*,
           ROUND((a.listing_ad_spend * a.ad_share)::numeric, 2) AS ad_spend,
           ROUND((a.listing_ad_sales * a.ad_share)::numeric, 2) AS ad_sales
    FROM assembled a
) a
ORDER BY a.returns DESC, a.refund_amt DESC, a.sku;
