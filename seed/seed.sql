-- Minimal seed data for dummy app
INSERT INTO platforms (platform_id, name) VALUES
    (1, 'amazon_us'),
    (2, 'cosme_jp')
ON CONFLICT (platform_id) DO NOTHING;

INSERT INTO categories (category_id, platform_id, name, source_url) VALUES
    (1, 1, 'skincare', 'https://www.amazon.com/s?k=skincare'),
    (2, 1, 'lipcare', 'https://www.amazon.com/s?k=lip+care'),
    (3, 2, 'skincare', 'https://www.cosme.net/'),
    (4, 2, 'makeup', 'https://www.cosme.net/')
ON CONFLICT (category_id) DO NOTHING;

-- Sample product and listings
INSERT INTO products (product_id, brand, name, canonical_name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Laneige', 'Laneige Water Bank', 'laneige_water_bank'),
    ('00000000-0000-0000-0000-000000000002', 'Laneige', 'Laneige Lip Sleeping Mask', 'laneige_lip_sleeping_mask')
ON CONFLICT (product_id) DO NOTHING;

INSERT INTO product_listings (listing_id, product_id, platform_id, product_url, external_id, title_raw) VALUES
    ('11111111-1111-1111-1111-111111111111', '00000000-0000-0000-0000-000000000001', 1, 'https://www.amazon.com/dp/B000000001', 'B000000001', 'Laneige Water Bank'),
    ('22222222-2222-2222-2222-222222222222', '00000000-0000-0000-0000-000000000002', 1, 'https://www.amazon.com/dp/B000000002', 'B000000002', 'Laneige Lip Sleeping Mask'),
    ('33333333-3333-3333-3333-333333333333', '00000000-0000-0000-0000-000000000001', 2, 'https://www.cosme.net/product/product_id', 'COSME001', 'Laneige Water Bank JP'),
    ('44444444-4444-4444-4444-444444444444', '00000000-0000-0000-0000-000000000002', 2, 'https://www.cosme.net/product/product_id2', 'COSME002', 'Laneige Lip Mask JP')
ON CONFLICT (listing_id) DO NOTHING;

-- Sample ranking snapshot for a single day
INSERT INTO ranking_daily (dt, platform_id, category_id, rank, listing_id, product_title_raw, product_url, captured_at) VALUES
    ('2024-09-01', 1, 1, 1, '11111111-1111-1111-1111-111111111111', 'Laneige Water Bank', 'https://www.amazon.com/dp/B000000001', NOW()),
    ('2024-09-01', 1, 1, 2, '22222222-2222-2222-2222-222222222222', 'Laneige Lip Sleeping Mask', 'https://www.amazon.com/dp/B000000002', NOW()),
    ('2024-09-01', 2, 3, 1, '33333333-3333-3333-3333-333333333333', 'Laneige Water Bank JP', 'https://www.cosme.net/product/product_id', NOW()),
    ('2024-09-01', 2, 4, 1, '44444444-4444-4444-4444-444444444444', 'Laneige Lip Mask JP', 'https://www.cosme.net/product/product_id2', NOW())
ON CONFLICT DO NOTHING;

-- Sample report metadata
INSERT INTO reports (report_id, period_start, period_end, platform_scope, category_scope, notion_url, summary, content_markdown, created_at)
VALUES (
    '55555555-5555-5555-5555-555555555555',
    '2024-08-25',
    '2024-08-31',
    'both',
    '{"categories":["skincare","lipcare"]}',
    'https://www.notion.so/example-report',
    'Weekly KPI snapshot for Laneige (dummy).',
    '# Dummy report\n\nThis is a placeholder report for the MVP skeleton.',
    NOW()
) ON CONFLICT (report_id) DO NOTHING;
