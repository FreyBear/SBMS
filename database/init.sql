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

-- Table for kits (fresh wort, cider, wine kits, etc.)
CREATE TABLE kit (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    kit_type TEXT NOT NULL CHECK (kit_type = ANY (ARRAY['Fresh Wort'::text, 'Cider'::text, 'Red Wine'::text, 'White Wine'::text, 'Rose Wine'::text, 'Sparkling Wine'::text, 'Mead'::text])),
    manufacturer TEXT,
    style TEXT,
    estimated_abv NUMERIC(4,2),
    volume_liters NUMERIC(6,2),
    cost NUMERIC(10,2),
    supplier TEXT,
    additional_ingredients_needed TEXT,
    description TEXT,
    label_image_filename TEXT,
    instruction_pdf_filename TEXT,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add comments for kit table
COMMENT ON TABLE kit IS 'Stores information about brewing kits (fresh wort, cider, wine kits, etc.)';
COMMENT ON COLUMN kit.kit_type IS 'Type of kit: Fresh Wort, Cider, Red Wine, White Wine, Rose Wine, Sparkling Wine, Mead';
COMMENT ON COLUMN kit.label_image_filename IS 'Filename of uploaded label/package image (stored in uploads/kits/)';
COMMENT ON COLUMN kit.instruction_pdf_filename IS 'Filename of uploaded instruction PDF (stored in uploads/kits/)';

-- Table for brew batches
CREATE TABLE brew (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    date_brewed DATE NOT NULL,
    recipe_id INTEGER REFERENCES recipe(id),
    kit_id INTEGER REFERENCES kit(id),
    style TEXT,
    estimated_abv NUMERIC(4,1),
    expected_og NUMERIC(6,4),
    expected_fg NUMERIC(6,4),
    batch_size_liters NUMERIC(6,2),
    actual_og NUMERIC(6,4),
    actual_fg NUMERIC(6,4),
    actual_abv NUMERIC(4,1),
    gluten_free BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT brew_source_check CHECK (
        (recipe_id IS NOT NULL AND kit_id IS NULL) OR 
        (recipe_id IS NULL AND kit_id IS NOT NULL)
    )
);

-- Table for brew tasks (fermentation schedule tracking)
CREATE TABLE brew_task (
    id SERIAL PRIMARY KEY,
    brew_id INTEGER NOT NULL REFERENCES brew(id) ON DELETE CASCADE,
    scheduled_date DATE NOT NULL,
    completed_date DATE,
    action TEXT NOT NULL,
    notes TEXT,
    is_completed BOOLEAN DEFAULT false,
    google_calendar_event_id TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Function to update brew_task updated_date
CREATE OR REPLACE FUNCTION update_brew_task_updated_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for brew_task updated_date
CREATE TRIGGER trigger_update_brew_task_updated_date
    BEFORE UPDATE ON brew_task
    FOR EACH ROW
    EXECUTE FUNCTION update_brew_task_updated_date();

-- Table for recipe malts
CREATE TABLE recipe_malts (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    malt_name VARCHAR(255) NOT NULL,
    amount_kg NUMERIC(6,3) NOT NULL,
    malt_type VARCHAR(100),
    lovibond NUMERIC(4,1),
    percentage NUMERIC(5,2),
    notes TEXT,
    sort_order INTEGER DEFAULT 0
);

-- Table for recipe hops
CREATE TABLE recipe_hops (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    hop_name VARCHAR(255) NOT NULL,
    amount_grams NUMERIC(7,2) NOT NULL,
    alpha_acid NUMERIC(4,2),
    time_minutes INTEGER NOT NULL,
    hop_type VARCHAR(50),
    hop_form VARCHAR(50),
    notes TEXT,
    sort_order INTEGER DEFAULT 0
);

-- Table for recipe yeast
CREATE TABLE recipe_yeast (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    yeast_name VARCHAR(255) NOT NULL,
    yeast_type VARCHAR(100),
    manufacturer VARCHAR(100),
    product_code VARCHAR(50),
    amount VARCHAR(100),
    attenuation NUMERIC(4,1),
    temperature_range VARCHAR(50),
    notes TEXT,
    sort_order INTEGER DEFAULT 0
);

-- Table for recipe adjuncts
CREATE TABLE recipe_adjuncts (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    ingredient_name VARCHAR(255) NOT NULL,
    amount VARCHAR(100),
    ingredient_type VARCHAR(100),
    time_added VARCHAR(100),
    notes TEXT,
    sort_order INTEGER DEFAULT 0
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
    abv NUMERIC(4,2) CHECK (abv >= 0 AND abv <= 20),
    gluten_free BOOLEAN,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert some sample data based on the CSV template
INSERT INTO recipe (name, style, notes) VALUES 
('IPA Recipe', 'IPA', 'Standard IPA recipe'),
('Cider Recipe', 'Cider', 'Fruit cider base'),
('Christmas Bock', 'Bock', 'Seasonal winter beer');

-- Insert sample kits
INSERT INTO kit (name, kit_type, manufacturer, style, estimated_abv, volume_liters, cost, supplier, description) VALUES 
('Bringebær og Lime Cider', 'Cider', 'Unknown', 'Fruit Cider', 4.50, 23.00, 350.00, 'Local Supplier', 'Refreshing raspberry and lime cider kit'),
('Jordbær og pære Cider', 'Cider', 'Premium Kits', 'Fruit Cider', 5.00, 23.00, 375.00, 'Brew Store', 'Settet inneholder flytende konsentrat fra pærer og jordbær, og Premium Cider gjær.');

INSERT INTO brew (name, date_brewed, recipe_id, notes) VALUES
('Batch 001 IPA', '2025-07-01', 1, 'First IPA batch'),
('Batch 003 Christmas Bock', '2025-07-10', 3, 'Winter seasonal');

-- Example of kit-based brew (using kit instead of recipe)
-- INSERT INTO brew (name, date_brewed, kit_id, notes) VALUES
-- ('Batch 004 Strawberry Pear Cider', '2025-08-01', 2, 'Made from kit #2');

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
CREATE INDEX idx_kit_name ON kit(name);
CREATE INDEX idx_kit_type ON kit(kit_type);
CREATE INDEX idx_keg_number ON keg(keg_number);
CREATE INDEX idx_keg_status ON keg(status);
CREATE INDEX idx_keg_location ON keg(location);
CREATE INDEX idx_brew_date ON brew(date_brewed);
CREATE INDEX idx_brew_kit_id ON brew(kit_id);
CREATE INDEX idx_brew_task_brew_id ON brew_task(brew_id);
CREATE INDEX idx_brew_task_scheduled_date ON brew_task(scheduled_date);
CREATE INDEX idx_brew_task_is_completed ON brew_task(is_completed);
CREATE INDEX idx_recipe_malts_recipe ON recipe_malts(recipe_id);
CREATE INDEX idx_recipe_hops_recipe ON recipe_hops(recipe_id);
CREATE INDEX idx_recipe_yeast_recipe ON recipe_yeast(recipe_id);
CREATE INDEX idx_recipe_adjuncts_recipe ON recipe_adjuncts(recipe_id);
CREATE INDEX idx_keg_history_keg_id ON keg_history(keg_id);
CREATE INDEX idx_keg_history_date ON keg_history(recorded_date);
CREATE INDEX idx_expenses_user_id ON expenses(user_id);
CREATE INDEX idx_expenses_status ON expenses(status);
CREATE INDEX idx_expenses_submitted_date ON expenses(submitted_date);
CREATE INDEX idx_expense_images_expense_id ON expense_images(expense_id);