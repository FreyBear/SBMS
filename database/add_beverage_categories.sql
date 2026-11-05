-- Migration: Add Beverage Categories and Subcategories
-- Supports hierarchical categorization (e.g. Øl -> Pils, Blonde, IPA, NEIPA; Cider -> Eplecider, Fruktcider; Vin -> Rødvin, Hvitvin)
-- and custom categories/subcategories across recipes, kits, brews, kegs, and bottle batches.

CREATE TABLE IF NOT EXISTS beverage_category (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    icon TEXT DEFAULT '🍺',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS beverage_subcategory (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES beverage_category(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (category_id, name)
);

-- Seed default main categories
INSERT INTO beverage_category (name, icon, sort_order) VALUES
    ('Øl', '🍺', 1),
    ('Cider', '🍏', 2),
    ('Vin', '🍷', 3),
    ('Mjød', '🍯', 4),
    ('Annet', '🥤', 5)
ON CONFLICT (name) DO NOTHING;

-- Seed default subcategories for Øl
INSERT INTO beverage_subcategory (category_id, name, sort_order)
SELECT c.id, s.name, s.sort_order
FROM beverage_category c
CROSS JOIN (VALUES
    ('Pils', 1),
    ('Blonde', 2),
    ('IPA', 3),
    ('NEIPA', 4),
    ('Pale Ale', 5),
    ('Stout / Porter', 6),
    ('Hveteøl', 7),
    ('Surøl', 8),
    ('Juleøl', 9),
    ('Ingefærøl', 10),
    ('Bock', 11),
    ('Annet øl', 12)
) AS s(name, sort_order)
WHERE c.name = 'Øl'
ON CONFLICT (category_id, name) DO NOTHING;

-- Seed default subcategories for Cider
INSERT INTO beverage_subcategory (category_id, name, sort_order)
SELECT c.id, s.name, s.sort_order
FROM beverage_category c
CROSS JOIN (VALUES
    ('Eplecider', 1),
    ('Eplecider med smak', 2),
    ('Fruktcider', 3),
    ('Pærecider', 4),
    ('Rosécider', 5),
    ('Annen cider', 6)
) AS s(name, sort_order)
WHERE c.name = 'Cider'
ON CONFLICT (category_id, name) DO NOTHING;

-- Seed default subcategories for Vin
INSERT INTO beverage_subcategory (category_id, name, sort_order)
SELECT c.id, s.name, s.sort_order
FROM beverage_category c
CROSS JOIN (VALUES
    ('Rødvin', 1),
    ('Hvitvin', 2),
    ('Rosévin', 3),
    ('Musserende', 4),
    ('Annen vin', 5)
) AS s(name, sort_order)
WHERE c.name = 'Vin'
ON CONFLICT (category_id, name) DO NOTHING;

-- Seed default subcategories for Mjød
INSERT INTO beverage_subcategory (category_id, name, sort_order)
SELECT c.id, s.name, s.sort_order
FROM beverage_category c
CROSS JOIN (VALUES
    ('Tradisjonell mjød', 1),
    ('Fruktmjød', 2)
) AS s(name, sort_order)
WHERE c.name = 'Mjød'
ON CONFLICT (category_id, name) DO NOTHING;

-- Add category_id and subcategory_id columns to core tables
ALTER TABLE recipe
    ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES beverage_category(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES beverage_subcategory(id) ON DELETE SET NULL;

ALTER TABLE kit
    ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES beverage_category(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES beverage_subcategory(id) ON DELETE SET NULL;

ALTER TABLE brew
    ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES beverage_category(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES beverage_subcategory(id) ON DELETE SET NULL;

ALTER TABLE keg
    ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES beverage_category(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES beverage_subcategory(id) ON DELETE SET NULL;

ALTER TABLE keg_history
    ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES beverage_category(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES beverage_subcategory(id) ON DELETE SET NULL;

ALTER TABLE bottle_batch
    ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES beverage_category(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES beverage_subcategory(id) ON DELETE SET NULL;

-- Create indexes for fast filtering and statistics aggregation
CREATE INDEX IF NOT EXISTS idx_subcategory_category_id ON beverage_subcategory(category_id);
CREATE INDEX IF NOT EXISTS idx_brew_category_id ON brew(category_id);
CREATE INDEX IF NOT EXISTS idx_keg_category_id ON keg(category_id);
CREATE INDEX IF NOT EXISTS idx_keg_subcategory_id ON keg(subcategory_id);
CREATE INDEX IF NOT EXISTS idx_bottle_batch_category_id ON bottle_batch(category_id);
CREATE INDEX IF NOT EXISTS idx_bottle_batch_subcategory_id ON bottle_batch(subcategory_id);

-- ============================================================================
-- DATA MIGRATION FOR EXISTING RECORDS
-- ============================================================================

-- 1. Migrate existing recipes (all current recipes are beer)
UPDATE recipe r
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl')
WHERE r.category_id IS NULL;

UPDATE recipe r
SET subcategory_id = (
    SELECT s.id FROM beverage_subcategory s
    JOIN beverage_category c ON s.category_id = c.id
    WHERE c.name = 'Øl' AND (
        (r.style ILIKE '%NEIPA%' AND s.name = 'NEIPA') OR
        (r.style ILIKE '%IPA%' AND r.style NOT ILIKE '%NEIPA%' AND s.name = 'IPA') OR
        (r.style ILIKE '%Pale Ale%' AND s.name = 'Pale Ale') OR
        ((r.style ILIKE '%Stout%' OR r.style ILIKE '%Porter%') AND s.name = 'Stout / Porter') OR
        (r.style ILIKE '%Pils%' AND s.name = 'Pils') OR
        (r.style ILIKE '%Blonde%' AND s.name = 'Blonde') OR
        (r.style ILIKE '%Bock%' AND s.name = 'Bock')
    )
    LIMIT 1
)
WHERE r.subcategory_id IS NULL;

-- 2. Migrate existing kits
UPDATE kit k
SET category_id = CASE
    WHEN k.kit_type = 'Fresh Wort' THEN (SELECT id FROM beverage_category WHERE name = 'Øl')
    WHEN k.kit_type = 'Cider' THEN (SELECT id FROM beverage_category WHERE name = 'Cider')
    WHEN k.kit_type IN ('Red Wine', 'White Wine', 'Rose Wine', 'Sparkling Wine') THEN (SELECT id FROM beverage_category WHERE name = 'Vin')
    WHEN k.kit_type = 'Mead' THEN (SELECT id FROM beverage_category WHERE name = 'Mjød')
    ELSE (SELECT id FROM beverage_category WHERE name = 'Annet')
END
WHERE k.category_id IS NULL;

UPDATE kit k
SET subcategory_id = (
    SELECT s.id FROM beverage_subcategory s
    WHERE s.category_id = k.category_id AND (
        (k.kit_type = 'Red Wine' AND s.name = 'Rødvin') OR
        (k.kit_type = 'White Wine' AND s.name = 'Hvitvin') OR
        (k.kit_type = 'Rose Wine' AND s.name = 'Rosévin') OR
        (k.kit_type = 'Sparkling Wine' AND s.name = 'Musserende') OR
        (k.kit_type = 'Fresh Wort' AND (k.style ILIKE '%Stout%' OR k.name ILIKE '%Black%' OR k.name ILIKE '%Dessert%') AND s.name = 'Stout / Porter') OR
        (k.kit_type = 'Cider' AND k.style ILIKE '%Eplecider med smak%' AND s.name = 'Eplecider med smak') OR
        (k.kit_type = 'Cider' AND k.style ILIKE 'Eplecider' AND s.name = 'Eplecider') OR
        (k.kit_type = 'Cider' AND k.style ILIKE '%Fruktcider%' AND s.name = 'Fruktcider') OR
        (k.kit_type = 'Cider' AND k.style ILIKE '%Pærecider%' AND s.name = 'Pærecider') OR
        (k.kit_type = 'Cider' AND k.name ILIKE '%Rosé%' AND s.name = 'Rosécider')
    )
    LIMIT 1
)
WHERE k.subcategory_id IS NULL;

-- 3. Migrate existing brews from linked recipe or kit
UPDATE brew b
SET category_id = r.category_id,
    subcategory_id = r.subcategory_id
FROM recipe r
WHERE b.recipe_id = r.id AND b.category_id IS NULL;

UPDATE brew b
SET category_id = k.category_id,
    subcategory_id = k.subcategory_id
FROM kit k
WHERE b.kit_id = k.id AND b.category_id IS NULL;

-- 4. Migrate existing bottle batches from linked brew
UPDATE bottle_batch bb
SET category_id = b.category_id,
    subcategory_id = b.subcategory_id
FROM brew b
WHERE bb.brew_id = b.id AND bb.category_id IS NULL;

-- 5. Migrate existing kegs from linked brew first
UPDATE keg kg
SET category_id = b.category_id,
    subcategory_id = b.subcategory_id
FROM brew b
WHERE kg.brew_id = b.id AND kg.category_id IS NULL;

-- 6. Migrate active kegs without brew_id based on contents
UPDATE keg
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'IPA')
WHERE category_id IS NULL AND (contents ILIKE '%Ink & Dagger%' OR contents ILIKE '%Ink and Dagger%' OR contents ILIKE '%IPA%');

UPDATE keg
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Pils')
WHERE category_id IS NULL AND (contents ILIKE '%Budish%' OR contents ILIKE '%Buddish%' OR contents ILIKE '%Pils%');

UPDATE keg
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Blonde')
WHERE category_id IS NULL AND contents ILIKE '%Blonde%';

UPDATE keg
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Ingefærøl')
WHERE category_id IS NULL AND contents ILIKE '%Ingefærøl%';

UPDATE keg
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Cider'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Cider' AND s.name = 'Pærecider')
WHERE category_id IS NULL AND contents ILIKE '%Perry%';

UPDATE keg
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Cider'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Cider' AND s.name = 'Fruktcider')
WHERE category_id IS NULL AND (contents ILIKE '%Jungle juice%' OR contents ILIKE '%Cider%');

-- 7. Backfill keg_history category_id and subcategory_id based on contents
UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Cider'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Cider' AND s.name = 'Pærecider')
WHERE category_id IS NULL AND (contents ILIKE '%Perry%' OR contents ILIKE '%pære%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Cider'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Cider' AND s.name = 'Rosécider')
WHERE category_id IS NULL AND contents ILIKE '%rosé%';

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Cider'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Cider' AND s.name = 'Eplecider')
WHERE category_id IS NULL AND (contents ILIKE '%Eplecider%' OR contents ILIKE '%Apple cider%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Cider'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Cider' AND s.name = 'Fruktcider')
WHERE category_id IS NULL AND (
    contents ILIKE '%cider%' OR contents ILIKE '%eple%' OR contents ILIKE '%jungle%'
    OR contents ILIKE '%mango%' OR contents ILIKE '%elderflower%' OR contents ILIKE '%hylleblomst%'
    OR contents ILIKE '%fersken%' OR contents ILIKE '%raspberry%' OR contents ILIKE '%pasjon%'
);

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Vin')
WHERE category_id IS NULL AND (contents ILIKE '%vin%' OR contents ILIKE '%wine%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'IPA')
WHERE category_id IS NULL AND (contents ILIKE '%IPA%' OR contents ILIKE '%Ink%' OR contents ILIKE '%I&D%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Pils')
WHERE category_id IS NULL AND (contents ILIKE '%Budish%' OR contents ILIKE '%Buddish%' OR contents ILIKE '%Buddis%' OR contents ILIKE '%Pils%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Blonde')
WHERE category_id IS NULL AND (contents ILIKE '%Blonde%' OR contents ILIKE '%Småtøs%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Stout / Porter')
WHERE category_id IS NULL AND (contents ILIKE '%Stout%' OR contents ILIKE '%Porter%' OR contents ILIKE '%Black Velvet%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Juleøl')
WHERE category_id IS NULL AND (contents ILIKE '%Jul%' OR contents ILIKE '%Bokk%');

UPDATE keg_history
SET category_id = (SELECT id FROM beverage_category WHERE name = 'Øl'),
    subcategory_id = (SELECT s.id FROM beverage_subcategory s JOIN beverage_category c ON s.category_id = c.id WHERE c.name = 'Øl' AND s.name = 'Ingefærøl')
WHERE category_id IS NULL AND contents ILIKE '%Ingefærøl%';

-- Fallback for remaining Full/Started keg_history rows: default to keg's category or Øl
UPDATE keg_history kh
SET category_id = COALESCE(k.category_id, (SELECT id FROM beverage_category WHERE name = 'Øl')),
    subcategory_id = COALESCE(kh.subcategory_id, k.subcategory_id)
FROM keg k
WHERE kh.keg_id = k.id
  AND kh.category_id IS NULL
  AND kh.status IN ('Full', 'Started');

-- 8. Bottle history table for tracking bottle inventory over time
CREATE TABLE IF NOT EXISTS bottle_history (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES bottle_batch(id) ON DELETE CASCADE,
    bottles_left INTEGER NOT NULL,
    bottle_size_liters NUMERIC(5,3) NOT NULL,
    recorded_date DATE NOT NULL DEFAULT CURRENT_DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bottle_history_batch_id ON bottle_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_bottle_history_date ON bottle_history(recorded_date);

-- Seed bottle_history from existing bottle_batch rows if empty
INSERT INTO bottle_history (batch_id, bottles_left, bottle_size_liters, recorded_date, notes)
SELECT bb.id, bb.initial_quantity, bb.bottle_size_liters, bb.bottling_date, 'Initial bottling'
FROM bottle_batch bb
WHERE NOT EXISTS (SELECT 1 FROM bottle_history bh WHERE bh.batch_id = bb.id);

INSERT INTO bottle_history (batch_id, bottles_left, bottle_size_liters, recorded_date, notes)
SELECT bb.id, bb.bottles_left, bb.bottle_size_liters, COALESCE(bb.updated_at::date, CURRENT_DATE), 'Current inventory'
FROM bottle_batch bb
WHERE bb.bottles_left != bb.initial_quantity
  AND NOT EXISTS (
      SELECT 1 FROM bottle_history bh
      WHERE bh.batch_id = bb.id AND bh.bottles_left = bb.bottles_left
  );


