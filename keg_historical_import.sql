-- SBMS Keg Import Script for Norwegian Brewery Data
-- This script imports your keg data with proper history tracking

-- Status mapping from Norwegian to English
-- 'Ledig/Vasket' -> 'Available/Cleaned'
-- 'Full' -> 'Full' 
-- 'Påbegynt' -> 'Started'
-- 'Tom - må vaskes' -> 'Empty'

-- First, let's create a function to get or create keg IDs
CREATE OR REPLACE FUNCTION get_or_create_keg(keg_num TEXT, vol_liters NUMERIC) 
RETURNS INTEGER AS $$
DECLARE
    keg_id INTEGER;
BEGIN
    -- Try to find existing keg
    SELECT id INTO keg_id FROM keg WHERE keg_number = keg_num;
    
    -- If not found, create it
    IF keg_id IS NULL THEN
        INSERT INTO keg (keg_number, volume_liters, status, amount_left_liters)
        VALUES (keg_num, vol_liters, 'Available/Cleaned', 0)
        RETURNING id INTO keg_id;
    END IF;
    
    RETURN keg_id;
END;
$$ LANGUAGE plpgsql;

-- Function to translate Norwegian status to English
CREATE OR REPLACE FUNCTION translate_status(norwegian_status TEXT)
RETURNS TEXT AS $$
BEGIN
    CASE norwegian_status
        WHEN 'Ledig/Vasket' THEN RETURN 'Available/Cleaned';
        WHEN 'Full' THEN RETURN 'Full';
        WHEN 'Påbegynt' THEN RETURN 'Started';
        WHEN 'Tom - må vaskes' THEN RETURN 'Empty';
        ELSE RETURN 'Available/Cleaned'; -- Default fallback
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- Now import all your historical data
DO $$
DECLARE
    keg_data RECORD;
    keg_id INTEGER;
    english_status TEXT;
    final_contents TEXT;
    final_status TEXT;
    final_amount NUMERIC;
    final_location TEXT;
    final_notes TEXT;
    final_date DATE;
BEGIN
    -- Your keg data with history
    FOR keg_data IN 
        VALUES 
        ('13', 19, 'jordbær og pærecider', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('11', 19, 'I&D', NULL, 'Full', 19, NULL, NULL, '2025-07-20'),
        ('2', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('10', 19, 'Mango og bringebærcider', NULL, 'Påbegynt', 12.5, 'Bryggeriet', NULL, '2025-07-20'),
        ('1', 19, 'Barth Haaze IPA', NULL, 'Påbegynt', 9, NULL, 'Lite poppulær', '2025-07-20'),
        ('8', 19, 'Plutselig Jul Bokk', NULL, 'Påbegynt', 4.5, NULL, 'Lite poppulær', '2025-07-20'),
        ('4', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('6', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('14', 19, 'Hylleblomst Cider', NULL, 'Påbegynt', 13.5, NULL, NULL, '2025-07-20'),
        ('15', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('12', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('9', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('3', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('5', 19, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('7', 9, 'TOM', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-07-20'),
        ('3', 19, 'I&D', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-07-29'),
        ('15', 19, 'I&D', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-07-29'),
        ('9', 19, 'Eple med Citrahumle', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-04'),
        ('12', 19, 'Bringebær og mango', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-04'),
        ('2', 19, 'Buddish 3.2', 'Carl Jørn (Benjamin)', 'Full', 19, 'Vinkjelleren', NULL, '2025-07-26'),
        ('4', 19, 'Buddish 3.2', 'Carl Jørn (Benjamin)', 'Full', 19, 'Vinkjelleren', NULL, '2025-07-26'),
        ('16', 9, 'TOM HOS FINN', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09'),
        ('17', 9, 'TOM HOS FINN', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09'),
        ('2', 19, 'Tilbakekommen etter fest', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09'),
        ('4', 19, 'Tilbakekommen etter fest', NULL, 'Tom - må vaskes', 0, NULL, NULL, '2025-09-09'),
        ('5', 19, 'Dessert in a Can STOUT', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-25'),
        ('6', 19, 'Småtøs', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-22'),
        ('13', 19, 'Småtøs', NULL, 'Full', 19, 'Vinkjelleren', NULL, '2025-08-22'),
        ('7', 9, 'Småtøs', NULL, 'Påbegynt', 5.5, 'Vinkjelleren', NULL, '2025-08-22'),
        ('16', 9, 'Budish', NULL, 'Full', 9, NULL, NULL, '2025-09-17'),
        ('17', 9, 'Budish', NULL, 'Full', 9, NULL, NULL, '2025-09-17'),
        ('18', 9, 'Budish', NULL, 'Full', 9, NULL, 'HELT NYTT', '2025-09-17'),
        ('19', 9, 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, 'HELT NYTT', '2025-09-17'),
        ('20', 19, 'Budish', NULL, 'Full', 19, NULL, NULL, '2025-09-17'),
        ('21', 19, 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-09-17'),
        ('22', 19, 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-09-17'),
        ('23', 19, 'Vasket av Benjamin', NULL, 'Ledig/Vasket', NULL, NULL, NULL, '2025-09-17'),
        ('14', 19, 'Hylleblomst Cider', 'Akademisk avspark', 'Påbegynt', 5.5, 'Bryggeriet', NULL, '2025-09-21'),
        ('15', 19, 'I&D', 'Akademisk avspark', 'Påbegynt', 5, 'Bryggeriet', NULL, '2025-09-21'),
        ('6', 19, 'Småtøs', 'Akademisk avspark', 'Påbegynt', 13, 'Bryggeriet', NULL, '2025-09-21'),
        ('12', 19, 'Bringebær og mango', 'Akademisk avspark', 'Påbegynt', 4, 'Bryggeriet', NULL, '2025-09-21')
    AS t(keg_number, volume_liters, contents, arrangement, status, amount_left_liters, location, notes, recorded_date)
    LOOP
        -- Get or create the keg
        SELECT get_or_create_keg(keg_data.keg_number, keg_data.volume_liters) INTO keg_id;
        
        -- Translate status
        SELECT translate_status(keg_data.status) INTO english_status;
        
        -- Clean up contents (replace TOM with NULL)
        final_contents := CASE 
            WHEN keg_data.contents = 'TOM' OR keg_data.contents LIKE 'TOM %' THEN NULL
            ELSE keg_data.contents
        END;
        
        -- Insert into history table
        INSERT INTO keg_history (
            keg_id, contents, status, amount_left_liters, 
            location, arrangement, notes, recorded_date
        ) VALUES (
            keg_id, final_contents, english_status, keg_data.amount_left_liters,
            keg_data.location, keg_data.arrangement, keg_data.notes, keg_data.recorded_date::DATE
        );
        
        -- Store the latest values for this keg
        final_contents := final_contents;
        final_status := english_status;
        final_amount := COALESCE(keg_data.amount_left_liters, 0);
        final_location := keg_data.location;
        final_notes := keg_data.notes;
        final_date := keg_data.recorded_date::DATE;
    END LOOP;
    
    -- Now update each keg with its most recent status
    FOR keg_data IN 
        SELECT DISTINCT 
            k.id, k.keg_number,
            (SELECT contents FROM keg_history WHERE keg_id = k.id ORDER BY recorded_date DESC LIMIT 1) as latest_contents,
            (SELECT status FROM keg_history WHERE keg_id = k.id ORDER BY recorded_date DESC LIMIT 1) as latest_status,
            (SELECT amount_left_liters FROM keg_history WHERE keg_id = k.id ORDER BY recorded_date DESC LIMIT 1) as latest_amount,
            (SELECT location FROM keg_history WHERE keg_id = k.id ORDER BY recorded_date DESC LIMIT 1) as latest_location,
            (SELECT notes FROM keg_history WHERE keg_id = k.id ORDER BY recorded_date DESC LIMIT 1) as latest_notes,
            (SELECT recorded_date FROM keg_history WHERE keg_id = k.id ORDER BY recorded_date DESC LIMIT 1) as latest_date
        FROM keg k
    LOOP
        UPDATE keg SET
            contents = keg_data.latest_contents,
            status = keg_data.latest_status,
            amount_left_liters = COALESCE(keg_data.latest_amount, 0),
            location = keg_data.latest_location,
            notes = keg_data.latest_notes,
            last_measured = keg_data.latest_date
        WHERE id = keg_data.id;
    END LOOP;
    
    RAISE NOTICE 'Keg import completed successfully!';
END $$;

-- Clean up helper functions
DROP FUNCTION get_or_create_keg(TEXT, NUMERIC);
DROP FUNCTION translate_status(TEXT);

-- Show summary of imported data
SELECT 'Imported Kegs Summary:' as summary;
SELECT 
    status,
    COUNT(*) as count,
    SUM(amount_left_liters) as total_liters
FROM keg 
GROUP BY status 
ORDER BY status;

SELECT 'Total History Records:' as summary;
SELECT COUNT(*) as history_records FROM keg_history;