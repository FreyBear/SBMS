-- SQL import file for keg data from Fatstyring.csv
-- Assumes the PostgreSQL schema described in README.md
-- Adjust table/column names if needed

INSERT INTO keg (
    keg_number, volume_liters, contents, arrangement, status, amount_left_liters, location, notes, last_measured
) VALUES
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
    ('12', 19, 'Bringebær og mango', 'Akademisk avspark', 'Påbegynt', 4, 'Bryggeriet', NULL, '2025-09-21');

-- Add more rows as needed from Fatstyring.csv
