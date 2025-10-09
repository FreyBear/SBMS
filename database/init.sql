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
    language TEXT DEFAULT 'en',
    bank_account VARCHAR(11) -- Norwegian bank account number for expense reimbursement
);

-- Insert default roles with expense management permissions
INSERT INTO user_role (name, description, permissions) VALUES 
('admin', 'Full system access', '{"kegs": "full", "brews": "full", "recipes": "full", "users": "full", "system": "full", "expenses": "full"}'),
('brewer', 'Brew management and keg updates', '{"kegs": "edit", "brews": "full", "recipes": "full", "users": "view", "system": "none", "expenses": "edit"}'),
('economy', 'Financial management and expense approval', '{"kegs": "view", "brews": "view", "recipes": "view", "users": "view", "system": "none", "expenses": "full"}'),
('operator', 'Keg operations only', '{"kegs": "edit", "brews": "view", "recipes": "view", "users": "none", "system": "none", "expenses": "view"}'),
('viewer', 'Read-only access', '{"kegs": "view", "brews": "view", "recipes": "view", "users": "none", "system": "none", "expenses": "view"}');

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

-- Table for expense management
CREATE TABLE expenses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    amount NUMERIC(10,2) NOT NULL,
    description TEXT NOT NULL,
    purchase_date DATE NOT NULL,
    submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'Pending' CHECK (status IN ('Pending', 'Paid', 'Rejected')),
    paid_by INTEGER REFERENCES users(id),
    paid_date TIMESTAMP,
    notes TEXT,
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rejection_reason TEXT,
    rejected_by INTEGER REFERENCES users(id),
    rejected_date TIMESTAMP
);

-- Table for expense receipt images
CREATE TABLE expense_images (
    id SERIAL PRIMARY KEY,
    expense_id INTEGER REFERENCES expenses(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    content_type TEXT,
    uploaded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL
);

-- Create indexes for better performance
CREATE INDEX idx_keg_number ON keg(keg_number);
CREATE INDEX idx_keg_status ON keg(status);
CREATE INDEX idx_keg_location ON keg(location);
CREATE INDEX idx_brew_date ON brew(date_brewed);
CREATE INDEX idx_keg_history_keg_id ON keg_history(keg_id);
CREATE INDEX idx_keg_history_date ON keg_history(recorded_date);
CREATE INDEX idx_expenses_user_id ON expenses(user_id);
CREATE INDEX idx_expenses_status ON expenses(status);
CREATE INDEX idx_expenses_submitted_date ON expenses(submitted_date);
CREATE INDEX idx_expense_images_expense_id ON expense_images(expense_id);