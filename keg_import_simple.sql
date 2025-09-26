-- SBMS Keg Import Script - Compatible Version
-- Import your Norwegian brewery data with history

-- First, insert all unique kegs
INSERT INTO keg (keg_number, volume_liters, status, amount_left_liters) 
SELECT DISTINCT keg_number, volume_liters, 'Available/Cleaned', 0
FROM (
    SELECT '1' as keg_number, 19 as volume_liters UNION ALL
    SELECT '2', 19 UNION ALL SELECT '3', 19 UNION ALL SELECT '4', 19 UNION ALL
    SELECT '5', 19 UNION ALL SELECT '6', 19 UNION ALL SELECT '7', 9 UNION ALL
    SELECT '8', 19 UNION ALL SELECT '9', 19 UNION ALL SELECT '10', 19 UNION ALL
    SELECT '11', 19 UNION ALL SELECT '12', 19 UNION ALL SELECT '13', 19 UNION ALL
    SELECT '14', 19 UNION ALL SELECT '15', 19 UNION ALL SELECT '16', 9 UNION ALL
    SELECT '17', 9 UNION ALL SELECT '18', 9 UNION ALL SELECT '19', 9 UNION ALL
    SELECT '20', 19 UNION ALL SELECT '21', 19 UNION ALL SELECT '22', 19 UNION ALL
    SELECT '23', 19
) as keg_list
ON CONFLICT (keg_number) DO NOTHING;

-- Insert all historical records
INSERT INTO keg_history (keg_id, contents, status, amount_left_liters, location, arrangement, notes, recorded_date)
SELECT 
    k.id,
    CASE WHEN h.contents = 'TOM' OR h.contents LIKE 'TOM %' THEN NULL ELSE h.contents END,
    CASE h.status
        WHEN 'Ledig/Vasket' THEN 'Available/Cleaned'
        WHEN 'Full' THEN 'Full'
        WHEN 'Påbegynt' THEN 'Started' 
        WHEN 'Tom - må vaskes' THEN 'Empty'
        ELSE 'Available/Cleaned'
    END,
    h.amount_left_liters,
    h.location,
    h.arrangement,
    h.notes,
    h.recorded_date::DATE
FROM keg k
JOIN (
    SELECT '13' as keg_number, 'jordbær og pærecider' as contents, NULL as arrangement, 'Ledig/Vasket' as status, NULL as amount_left_liters, NULL as location, NULL as notes, '2025-07-20' as recorded_date UNION ALL
    SELECT '11', 'I&D', NULL, 'Full', 19, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '2', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '10', 'Mango og bringebærcider', NULL, 'Påbegynt', 12.5, 'Bryggeriet', NULL, '2025-07-20' UNION ALL
    SELECT '1', 'Barth Haaze IPA', NULL, 'Påbegynt', 9, NULL, 'Lite poppulær', '2025-07-20' UNION ALL
    SELECT '8', 'Plutselig Jul Bokk', NULL, 'Påbegynt', 4.5, NULL, 'Lite poppulær', '2025-07-20' UNION ALL
    SELECT '4', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '6', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '14', 'Hylleblomst Cider', NULL, 'Påbegynt', 13.5, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '15', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '12', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '9', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '3', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '5', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '7', 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20' UNION ALL
    SELECT '3', 'I&D', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-07-29' UNION ALL
    SELECT '15', 'I&D', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-07-29' UNION ALL
    SELECT '9', 'Eple med Citrahumle', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-04' UNION ALL
    SELECT '12', 'Bringebær og mango', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-04' UNION ALL
    SELECT '2', 'Buddish 3.2', 'Carl Jørn (Benjamin)', 'Full', 19, 'Vinkjelleren', NULL, '2025-07-26' UNION ALL
    SELECT '4', 'Buddish 3.2', 'Carl Jørn (Benjamin)', 'Full', 19, 'Vinkjelleren', NULL, '2025-07-26' UNION ALL
    SELECT '16', 'TOM HOS FINN', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09' UNION ALL
    SELECT '17', 'TOM HOS FINN', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09' UNION ALL
    SELECT '2', 'Tilbakekommen etter fest', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09' UNION ALL
    SELECT '4', 'Tilbakekommen etter fest', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09' UNION ALL
    SELECT '5', 'Dessert in a Can STOUT', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-25' UNION ALL
    SELECT '6', 'Småtøs', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-22' UNION ALL
    SELECT '13', 'Småtøs', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-22' UNION ALL
    SELECT '7', 'Småtøs', NULL, 'Påbegynt', 5.5, 'Vinkjelleren', NULL, '2025-08-22' UNION ALL
    SELECT '16', 'Budish', NULL, 'Full', 9, NULL, NULL, '2025-09-17' UNION ALL
    SELECT '17', 'Budish', NULL, 'Full', 9, NULL, NULL, '2025-09-17' UNION ALL
    SELECT '18', 'Budish', NULL, 'Full', 9, NULL, 'HELT NYTT', '2025-09-17' UNION ALL
    SELECT '19', 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, 'HELT NYTT', '2025-09-17' UNION ALL
    SELECT '20', 'Budish', NULL, 'Full', 19, NULL, NULL, '2025-09-17' UNION ALL
    SELECT '21', 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-09-17' UNION ALL
    SELECT '22', 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-09-17' UNION ALL
    SELECT '23', 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-09-17' UNION ALL
    SELECT '14', 'Hylleblomst Cider', 'Akademisk avspark', 'Påbegynt', 5.5, 'Bryggeriet', NULL, '2025-09-21' UNION ALL
    SELECT '15', 'I&D', 'Akademisk avspark', 'Påbegynt', 5, 'Bryggeriet', NULL, '2025-09-21' UNION ALL
    SELECT '6', 'Småtøs', 'Akademisk avspark', 'Påbegynt', 13, 'Bryggeriet', NULL, '2025-09-21' UNION ALL
    SELECT '12', 'Bringebær og mango', 'Akademisk avspark', 'Påbegynt', 4, 'Bryggeriet', NULL, '2025-09-21'
) h ON k.keg_number = h.keg_number;

-- Update each keg with its latest status
WITH latest_status AS (
    SELECT DISTINCT ON (keg_id) 
        keg_id, contents, status, amount_left_liters, location, notes, recorded_date
    FROM keg_history 
    ORDER BY keg_id, recorded_date DESC, created_timestamp DESC
)
UPDATE keg SET
    contents = ls.contents,
    status = ls.status,
    amount_left_liters = COALESCE(ls.amount_left_liters, 0),
    location = ls.location,
    notes = ls.notes,
    last_measured = ls.recorded_date
FROM latest_status ls
WHERE keg.id = ls.keg_id;

-- Show import results
SELECT 'Import Results:' as info;

SELECT 
    'Kegs by Status' as category,
    status,
    COUNT(*) as count,
    SUM(amount_left_liters) as total_liters
FROM keg 
GROUP BY status 
ORDER BY status;

SELECT 
    'History Records' as category,
    '' as status,
    COUNT(*) as count,
    0 as total_liters
FROM keg_history;