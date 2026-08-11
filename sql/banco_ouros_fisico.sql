CREATE TABLE tips (
    id SERIAL PRIMARY KEY,
    tip VARCHAR NOT NULL,
    id_farm SERIAL REFERENCES farms(id) NOT NULL
);


CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    category VARCHAR NOT NULL,
    id_tip SERIAL REFERENCES tips(id) NOT NULL
);


CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    zip_code VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    city VARCHAR NOT NULL,
    number INT NOT NULL,
    country VARCHAR NOT NULL
);


CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    comment TEXT NOT NULL,
    pointing INTEGER NOT NULL,
    id_tip SERIAL REFERENCES tips(id) NOT NULL
);


CREATE TABLE farm_owners (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    password VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    zip_code VARCHAR NOT NULL,
    id_farm SERIAL REFERENCES farms(id) NOT NULL,
    id_telephone VARCHAR REFERENCES telephone(id) NOT NULL
);


CREATE TABLE farms (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    area_property FLOAT NOT NULL,
    region VARCHAR NOT NULL,
    poultry_capacity INTEGER NOT NULL,
    place VARCHAR NOT NULL,
    id_adress SERIAL REFERENCES addresses(id) NOT NULL,
    id_enterprise SERIAL REFERENCES enterprises(id) NOT NULL
);


CREATE TABLE individual_goals (
    id SERIAL PRIMARY KEY,
    descripition VARCHAR,
    type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    target_value FLOAT NOT NULL,
    title VARCHAR NOT NULL,
    id_farm SERIAL REFERENCES farms(id) NOT NULL
);


CREATE TABLE water_registries (
    id SERIAL PRIMARY KEY,
    registration_date DATE NOT NULL,
    strart_hydrometer FLOAT NOT NULL,
    end_hydrometer FLOAT NOT NULL,
    id_farm SERIAL REFERENCES farms(id) NOT NULL
);


CREATE TABLE lots (
    id SERIAL PRIMARY KEY,
    received_chickens INT NOT NULL,
    delivered_chickens INT NOT NULL,
    date_birth DATE NOT NULL,
    delivery_date DATE NOT NULL,
    gain DOUBLE NOT NULL,
    id_enterprise SERIAL REFERENCES enterprises(id) NOT NULL,
    id_energy_restries SERIAL REFERENCES energy_registries(id) NOT NULL,
    id_water_restries SERIAL REFERENCES water_registries(id) NOT NULL
);


CREATE TABLE company_employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    zip_code VARCHAR UNIQUE NOT NULL,
    email VARCHAR NOT NULL,
    telephone VARCHAR NOT NULL,
    id_enterprise SERIAL REFERENCES enterprises(id) NOT NULL
);


CREATE TABLE enterprises (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    cnpj VARCHAR UNIQUE NOT NULL,
    id_telephone VARCHAR REFERENCES telephone(id) NOT NULL,
    id_address SERIAL REFERENCES addresses(id) NOT NULL
);


CREATE TABLE adms (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL,
    password VARCHAR NOT NULL
);


CREATE TABLE medication_plans (
    id SERIAL PRIMARY KEY UNIQUE,
    title VARCHAR NOT NULL,
    date_start_validity DATE NOT NULL,
    date_end_validity DATE NOT NULL,
    description TEXT,
    id_enterprise INTEGER REFERENCES enterprises(id) NOT NULL
);


CREATE TABLE regions_medication_plans (
    id SERIAL PRIMARY KEY,
    region VARCHAR NOT NULL,
    id_plan INTEGER REFERENCES medication_plans(id) NOT NULL
);


CREATE TABLE vaccines (
    id SERIAL PRIMARY KEY,
    aplication_days INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    dose DOUBLE NOT NULL,
    aplication_route VARCHAR NOT NULL,
    id_plan INTEGER REFERENCES medication_plans(id) NOT NULL
);


CREATE TABLE diseases (
    id SERIAL PRIMARY KEY,
    disease VARCHAR NOT NULL,
    id_vacinne INTEGER REFERENCES vaccines(id) NOT NULL
);


CREATE TABLE state_goals (
    id SERIAL PRIMARY KEY,
    description VARCHAR,
    type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    target_value FLOAT NOT NULL,
    title VARCHAR NOT NULL,
    date_creation TIMESTAMP NOT NULL,
    date_end TIMESTAMP NOT NULL,
    id_farm SERIAL REFERENCES farms(id) NOT NULL
);


CREATE TABLE regions_goals (
    id SERIAL PRIMARY KEY,
    region VARCHAR NOT NULL,
    id_goal INTEGER REFERENCES state_goals(id) NOT NULL
);


CREATE TABLE status (
    id SERIAL PRIMARY KEY,
    status VARCHAR NOT NULL,
    id_estado INTEGER REFERENCES state_goals(id) NOT NULL
);


CREATE TABLE energy_registries (
    id SERIAL PRIMARY KEY,
    registration_date DATE NOT NULL,
    energy_consumption DOUBLE NOT NULL,
    id_farm INTEGER REFERENCES farms(id) NOT NULL
);