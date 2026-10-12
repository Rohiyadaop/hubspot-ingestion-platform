WITH deal_summary AS (
    SELECT
        d.id AS deal_id,
        d.dealname,
        d.amount,
        d.company_id,
        c.name AS company_name,
        p.label AS pipeline_stage
    FROM deals d
    LEFT JOIN companies c ON c.id = d.company_id
    LEFT JOIN pipelines p ON p.id = d.pipeline_id
)
SELECT
    deal_id,
    dealname,
    amount,
    company_name,
    pipeline_stage,
    CASE
        WHEN amount >= 700000 THEN 'High Value'
        WHEN amount >= 500000 THEN 'Medium Value'
        ELSE 'Low Value'
    END AS deal_tier
FROM deal_summary
ORDER BY amount DESC;
