-- Add calibration controls for Plaato MQTT weight processing
-- calibrated_kg = (raw_kg * calibration_factor) + calibration_offset_kg

ALTER TABLE mqtt_config
ADD COLUMN IF NOT EXISTS calibration_factor NUMERIC(10,6) NOT NULL DEFAULT 1.0;

ALTER TABLE mqtt_config
ADD COLUMN IF NOT EXISTS calibration_offset_kg NUMERIC(10,6) NOT NULL DEFAULT 0.0;

COMMENT ON COLUMN mqtt_config.calibration_factor IS 'Multiplier for incoming MQTT weight (1.0 means unchanged)';
COMMENT ON COLUMN mqtt_config.calibration_offset_kg IS 'Offset in kg added after factor to compensate sensor zero drift';
