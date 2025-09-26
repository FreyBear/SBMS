-- SBMS Database Schema
-- Small Brewery Management System

-- Table for user roles
CREATE TABLE user_role (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    permissions TEXT -- JSON string of permissions
);

-- Table for users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role_id INTEGER REFERENCES user_role(id),
    is_active BOOLEAN DEFAULT true,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    language TEXT DEFAULT 'en'
);

-- Insert default roles
INSERT INTO user_role (name, description, permissions) VALUES 
('admin', 'Full system access', '{"kegs": "full", "brews": "full", "recipes": "full", "users": "full", "system": "full"}'),
('brewer', 'Brew management and keg updates', '{"kegs": "edit", "brews": "full", "recipes": "full", "users": "view", "system": "none"}'),
('viewer', 'Read-only access', '{"kegs": "view", "brews": "view", "recipes": "view", "users": "none", "system": "none"}'),
('operator', 'Keg operations only', '{"kegs": "edit", "brews": "view", "recipes": "view", "users": "none", "system": "none"}');

-- Table for recipes
CREATE TABLE recipe (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    style TEXT,
    notes TEXT,
    created_date DATE DEFAULT CURRENT_DATE
);

-- Table for brew batches
CREATE TABLE brew (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    date_brewed DATE NOT NULL,
    recipe_id INTEGER REFERENCES recipe(id),
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for kegs
CREATE TABLE keg (
    id SERIAL PRIMARY KEY,
    keg_number TEXT NOT NULL UNIQUE,
    volume_liters NUMERIC NOT NULL,
    condition TEXT DEFAULT 'God', -- 'God', 'Defekt'
    location TEXT,
    status TEXT DEFAULT 'Available/Cleaned', -- 'Full', 'Started', 'Available/Cleaned', 'Empty'
    amount_left_liters NUMERIC DEFAULT 0,
    last_cleaned DATE,
    notes TEXT,
    brew_id INTEGER REFERENCES brew(id),
    contents TEXT,
    date_filled DATE,
    last_measured DATE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert some sample data based on the CSV template
INSERT INTO recipe (name, style, notes) VALUES 
('IPA Recipe', 'IPA', 'Standard IPA recipe'),
('Cider Recipe', 'Cider', 'Fruit cider base'),
('Christmas Bock', 'Bock', 'Seasonal winter beer');

INSERT INTO brew (name, date_brewed, recipe_id, notes) VALUES
('Batch 001 IPA', '2025-07-01', 1, 'First IPA batch'),
('Batch 002 Strawberry Pear Cider', '2025-07-05', 2, 'Summer fruit cider'),
('Batch 003 Christmas Bock', '2025-07-10', 3, 'Winter seasonal');

-- Create default admin user (password: admin123)
-- IMPORTANT: Change this password immediately after first login!
INSERT INTO users (username, email, password_hash, full_name, role_id, is_active) VALUES 
('admin', 'admin@brewery.local', '$2b$12$LFXhcrs.SosoJD5MxToRKeCFq3L9INtfYL5qNO.x.Y7qxEuk9Jj6q', 'System Administrator', 1, true);

-- Table for keg history tracking
CREATE TABLE keg_history (
    id SERIAL PRIMARY KEY,
    keg_id INTEGER REFERENCES keg(id),
    contents TEXT,
    status TEXT,
    amount_left_liters NUMERIC,
    location TEXT,
    arrangement TEXT, -- Event/occasion name
    notes TEXT,
    recorded_date DATE NOT NULL,
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_keg_number ON keg(keg_number);
CREATE INDEX idx_keg_status ON keg(status);
CREATE INDEX idx_keg_location ON keg(location);
CREATE INDEX idx_brew_date ON brew(date_brewed);
CREATE INDEX idx_keg_history_keg_id ON keg_history(keg_id);
CREATE INDEX idx_keg_history_date ON keg_history(recorded_date);