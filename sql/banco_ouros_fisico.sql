/* logico_ouros (2): */

CREATE TABLE tips (
    id SERIAL PRIMARY KEY,
    tip VARCHAR,
    id_farm SERIAL REFERENCES farms(id)
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    category VARCHAR,
    id_tip SERIAL REFERENCES tips(id)
);

CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    zip_code VARCHAR,
    state VARCHAR,
    city VARCHAR,
    number INT,
    country VARCHAR
);

CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    comment TEXT,
    pointing INTEGER,
    id_tip SERIAL REFERENCES tips(id)
);

CREATE TABLE farm_owners (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    password VARCHAR,
    email VARCHAR,
    zip_code VARCHAR,
    id_farm SERIAL REFERENCES farms(id),
    id_telephone VARCHAR REFERENCES telephone(id)
);

CREATE TABLE farms (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    area_property FLOAT,
    region VARCHAR,
    poultry_capacity  INTEGER,
    place VARCHAR,
    id_adress SERIAL REFERENCES addresses(id),
    id_enterprise SERIAL REFERENCES enterprises(id)
);

CREATE TABLE individual_goals (
    id SERIAL PRIMARY KEY,
    descripition VARCHAR,
    type VARCHAR,
    status VARCHAR,
    target_value FLOAT,
    title VARCHAR,
    id_farm SERIAL REFERENCES farms(id)
);

CREATE TABLE water_registries (
    id SERIAL PRIMARY KEY,
    registration_date DATE,
    strart_hydrometer FLOAT,
    end_hydrometer FLOAT,
    id_farm SERIAL REFERENCES farms(id) 
);

CREATE TABLE lots (
    id SERIAL PRIMARY KEY,
    received_chickens INT,
    delivered_chickens  INT,
    date_birth  DATE,
    delivery_date DATE,
    gain DOUBLE,
    id_enterprise SERIAL REFERENCES enterprises(id),
    id_energy_restries SERIAL REFERENCES energy_registries(id),
    id_water_restries SERIAL REFERENCES water_registries(id)
);

CREATE TABLE company_employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    zip_code VARCHAR UNIQUE,
    email VARCHAR,
    telephone VARCHAR,
    id_enterprise SERIAL REFERENCES enterprises(id)
);

CREATE TABLE enterprises (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    cnpj VARCHAR UNIQUE,
    id_telephone VARCHAR REFERENCES telephone(id),
    id_address SERIAL REFERENCES addresses(id)
);

CREATE TABLE adms (
    id SERIAL PRIMARY KEY,
    email VARCHAR,
    password VARCHAR
);

CREATE TABLE medication_plans (
    id SERIAL PRIMARY KEY UNIQUE,
    title VARCHAR,
    date_start_validity DATE,
    date_end_validity  DATE,
    description TEXT,
    id_enterprise INTEGER REFERENCES enterprises(id)
);

CREATE TABLE regions_medication_plans (
    id SERIAL PRIMARY KEY,
    region VARCHAR,
    id_plan INTEGER REFERENCES medication_plans(id)
);

CREATE TABLE vaccines (
    id SERIAL PRIMARY KEY, 
    aplication_days INTEGER,
    name VARCHAR,
    dose DOUBLE,
    aplication_route VARCHAR,
    id_plan INTEGER REFERENCES medication_plans(id)
);

CREATE TABLE diseases (
    id SERIAL PRIMARY KEY,
    disease VARCHAR,
    id_vacinne INTEGER REFERENCES vaccines(id)
);

CREATE TABLE state_goals (
    id SERIAL PRIMARY KEY,
    description VARCHAR,
    type VARCHAR,
    status VARCHAR,
    target_value FLOAT,
    title VARCHAR,
    date_ creation TIMESTAMP,
    date_end TIMESTAMP,
    id_farm SERIAL REFERENCES farms(id)
);

CREATE TABLE regions_goals (
    id SERIAL PRIMARY KEY,
    region VARCHAR,
    id_goal INTEGER REFERENCES state_goals(id)
);

CREATE TABLE status (
    id SERIAL PRIMARY KEY,
    status VARCHAR,
    id_estado INTEGER REFERENCES state_goals(id)
);

CREATE TABLE energy_registries (
    id SERIAL PRIMARY KEY,
    registration_date DATE,
    energy_consumption DOUBLE, 
    id_farm INTEGER REFERENCES farms(id)
);

