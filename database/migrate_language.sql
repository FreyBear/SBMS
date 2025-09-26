-- Migration to add language support to existing database
-- Run this if you have existing data and don't want to recreate the database

-- Add language column to users table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'language'
    ) THEN
        ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en';
    END IF;
END $$;

-- Set default language for existing users
UPDATE users SET language = 'en' WHERE language IS NULL;