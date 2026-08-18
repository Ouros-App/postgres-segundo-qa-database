CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    zip_code VARCHAR,
    state VARCHAR,
    city VARCHAR,
    number INTEGER,
    country VARCHAR
);

CREATE TABLE IF NOT EXISTS enterprises (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    cnpj VARCHAR UNIQUE,
    document_number VARCHAR UNIQUE,
    telephone VARCHAR,
    id_address INTEGER REFERENCES addresses (id)
);

CREATE TABLE IF NOT EXISTS farms (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    area_property DOUBLE PRECISION,
    region VARCHAR,
    poultry_capacity INTEGER,
    place VARCHAR,
    id_adress INTEGER REFERENCES addresses (id),
    id_enterprise INTEGER REFERENCES enterprises (id)
);

CREATE TABLE IF NOT EXISTS tips (
    id SERIAL PRIMARY KEY,
    tip VARCHAR,
    id_farm INTEGER REFERENCES farms (id)
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    category VARCHAR,
    id_tip INTEGER REFERENCES tips (id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    comment TEXT,
    pointing INTEGER,
    id_tip INTEGER REFERENCES tips (id)
);

CREATE TABLE IF NOT EXISTS farm_owners (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    password VARCHAR,
    email VARCHAR,
    document_number VARCHAR UNIQUE,
    telephone VARCHAR,
    zip_code VARCHAR,
    id_farm INTEGER REFERENCES farms (id)
);

CREATE TABLE IF NOT EXISTS individual_goals (
    id SERIAL PRIMARY KEY,
    descripition VARCHAR,
    type VARCHAR,
    status VARCHAR,
    target_value DOUBLE PRECISION,
    title VARCHAR,
    id_farm INTEGER REFERENCES farms (id)
);

CREATE TABLE IF NOT EXISTS water_registries (
    id SERIAL PRIMARY KEY,
    registration_date DATE,
    strart_hydrometer DOUBLE PRECISION,
    end_hydrometer DOUBLE PRECISION,
    id_farm INTEGER REFERENCES farms (id)
);

CREATE TABLE IF NOT EXISTS energy_registries (
    id SERIAL PRIMARY KEY,
    registration_date DATE,
    energy_consumption DOUBLE PRECISION,
    id_farm INTEGER REFERENCES farms (id)
);

CREATE TABLE IF NOT EXISTS lots (
    id SERIAL PRIMARY KEY,
    received_chickens INTEGER,
    delivered_chickens INTEGER,
    date_birth DATE,
    delivery_date DATE,
    gain DOUBLE PRECISION,
    id_enterprise INTEGER REFERENCES enterprises (id),
    id_farm INTEGER REFERENCES farms (id),
    id_energy_restries INTEGER REFERENCES energy_registries (id),
    id_water_restries INTEGER REFERENCES water_registries (id)
);

CREATE TABLE IF NOT EXISTS company_employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    zip_code VARCHAR UNIQUE,
    document_number VARCHAR UNIQUE,
    email VARCHAR,
    telephone VARCHAR,
    password VARCHAR,
    id_enterprise INTEGER REFERENCES enterprises (id)
);

CREATE TABLE IF NOT EXISTS adms (
    id SERIAL PRIMARY KEY,
    email VARCHAR,
    password VARCHAR
);

CREATE TABLE IF NOT EXISTS medication_plans (
    id SERIAL PRIMARY KEY,
    title VARCHAR,
    date_start_validity DATE,
    date_end_validity DATE,
    description TEXT,
    id_enterprise INTEGER REFERENCES enterprises (id)
);

CREATE TABLE IF NOT EXISTS regions_medication_plans (
    id SERIAL PRIMARY KEY,
    region VARCHAR,
    id_plan INTEGER REFERENCES medication_plans (id)
);

CREATE TABLE IF NOT EXISTS vaccines (
    id SERIAL PRIMARY KEY,
    aplication_days INTEGER,
    name VARCHAR,
    dose DOUBLE PRECISION,
    aplication_route VARCHAR,
    id_plan INTEGER REFERENCES medication_plans (id)
);

CREATE TABLE IF NOT EXISTS diseases (
    id SERIAL PRIMARY KEY,
    disease VARCHAR,
    id_vacinne INTEGER REFERENCES vaccines (id)
);

CREATE TABLE IF NOT EXISTS state_goals (
    id SERIAL PRIMARY KEY,
    description VARCHAR,
    type VARCHAR,
    status VARCHAR,
    target_value DOUBLE PRECISION,
    title VARCHAR,
    date_creation TIMESTAMP,
    date_end TIMESTAMP,
    id_farm INTEGER REFERENCES farms (id)
);

CREATE TABLE IF NOT EXISTS regions_goals (
    id SERIAL PRIMARY KEY,
    region VARCHAR,
    id_goal INTEGER REFERENCES state_goals (id)
);

CREATE TABLE IF NOT EXISTS status (
    id SERIAL PRIMARY KEY,
    status VARCHAR,
    id_estado INTEGER REFERENCES state_goals (id)
);

/* Tabelas associativas adicionadas a partir da versão lógica mais nova. */

CREATE TABLE IF NOT EXISTS farm_goals (
    id SERIAL PRIMARY KEY,
    id_farm INTEGER NOT NULL REFERENCES farms (id),
    id_goal INTEGER NOT NULL REFERENCES state_goals (id),
    UNIQUE (id_farm, id_goal)
);

CREATE TABLE IF NOT EXISTS tip_categories (
    id SERIAL PRIMARY KEY,
    id_tip INTEGER NOT NULL REFERENCES tips (id),
    id_categories INTEGER NOT NULL REFERENCES categories (id),
    UNIQUE (id_tip, id_categories)
);

CREATE TABLE IF NOT EXISTS state_goal_regions (
    id SERIAL PRIMARY KEY,
    id_goal INTEGER NOT NULL REFERENCES state_goals (id),
    id_region INTEGER NOT NULL REFERENCES regions_goals (id),
    UNIQUE (id_goal, id_region)
);

CREATE TABLE IF NOT EXISTS medication_regions_plan (
    id SERIAL PRIMARY KEY,
    id_medication INTEGER NOT NULL REFERENCES medication_plans (id),
    id_region INTEGER NOT NULL REFERENCES regions_medication_plans (id),
    UNIQUE (id_medication, id_region)
);

CREATE TABLE IF NOT EXISTS medication_plans_vaccines (
    id SERIAL PRIMARY KEY,
    id_medication INTEGER NOT NULL REFERENCES medication_plans (id),
    id_vaccine INTEGER NOT NULL REFERENCES vaccines (id),
    UNIQUE (id_medication, id_vaccine)
);

CREATE TABLE IF NOT EXISTS farms_tips (
    id SERIAL PRIMARY KEY,
    id_farm INTEGER NOT NULL REFERENCES farms (id),
    id_tips INTEGER NOT NULL REFERENCES tips (id),
    UNIQUE (id_farm, id_tips)
);
