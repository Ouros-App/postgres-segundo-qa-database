CREATE TABLE tips (
    id SERIAL PRIMARY KEY,
    tip TEXT NOT NULL,
    id_farm SERIAL REFERENCES farms(id) NOT NULL
);


CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL CHECK(length(category) > 0),
    id_tip SERIAL REFERENCES tips(id) NOT NULL
);


CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    zip_code VARCHAR(32) NOT NULL CHECK(length(zip_code) > 0),
    state VARCHAR(2) NOT NULL CHECK(length(state) = 2),
    city VARCHAR(32) NOT NULL CHECK(length(city) > 0),
    number VARCHAR(32) NOT NULL CHECK(length(number) > 0),
    country VARCHAR(2) NOT NULL CHECK(length(country) = 2)
);


CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    comment TEXT NOT NULL,
    pointing INTEGER NOT NULL,
    id_tip SERIAL REFERENCES tips(id) NOT NULL
);


CREATE TABLE farm_owners (
    id SERIAL PRIMARY KEY,
    name VARCHAR(32) NOT NULL CHECK(length(name) > 0),
    password VARCHAR(32) NOT NULL CHECK(length(password) > 0),
    email VARCHAR(32) NOT NULL CHECK(length(email) > 0),
    zip_code(32) VARCHAR NOT NULL CHECK(length(zip_code) > 0),
    id_farm SERIAL REFERENCES farms(id) NOT NULL,
    id_telephone VARCHAR REFERENCES telephone(id) NOT NULL
);


CREATE TABLE farms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL CHECK(length(name)> 0),
    area_property FLOAT NOT NULL,
    region VARCHAR(20) NOT NULL CHECK(length(region)> 0),
    poultry_capacity INTEGER NOT NULL,
    place VARCHAR(40) NOT NULL CHECK(length(place)> 0),
    id_adress SERIAL REFERENCES addresses(id) NOT NULL,
    id_enterprise SERIAL REFERENCES enterprises(id) NOT NULL
);


CREATE TABLE individual_goals (
    id SERIAL PRIMARY KEY,
    descripition VARCHAR,
    type VARCHAR(30) NOT NULL CHECK(length(type)> 0),
    status VARCHAR(30) NOT NULL CHECK(length(status)> 0),
    target_value FLOAT NOT NULL,
    title VARCHAR(40) NOT NULL CHECK(length(title)> 0),
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
    name VARCHAR(32) NOT NULL CHECK(length(name) > 0),
    zip_code VARCHAR NOT NULL,
    email VARCHAR(32) NOT NULL CHECK(length(email) > 0),
    telephone VARCHAR NOT NULL,
    id_enterprise SERIAL REFERENCES enterprises(id) NOT NULL
);


CREATE TABLE enterprises (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR(32) NOT NULL CHECK(length(email) > 0),
    cnpj VARCHAR UNIQUE NOT NULL,
    id_address SERIAL REFERENCES addresses(id) NOT NULL
);


CREATE TABLE adms (
    id SERIAL PRIMARY KEY,
    email VARCHAR(32) NOT NULL CHECK(length(email) > 0),
    password VARCHAR(32) NOT NULL CHECK(length(password) > 0),
);


CREATE TABLE medication_plans (
    id SERIAL PRIMARY KEY UNIQUE,
    title VARCHAR(40) NOT NULL CHECK(length(title)> 0),
    date_start_validity DATE NOT NULL,
    date_end_validity DATE NOT NULL,
    description TEXT,
    id_enterprise INTEGER REFERENCES enterprises(id) NOT NULL
);


CREATE TABLE regions_medication_plans (
    id SERIAL PRIMARY KEY,
    region VARCHAR(20) NOT NULL CHECK(length(region)> 0),
    id_plan INTEGER REFERENCES medication_plans(id) NOT NULL
);


CREATE TABLE vaccines (
    id SERIAL PRIMARY KEY,
    aplication_days INTEGER NOT NULL,
    name VARCHAR(20) NOT NULL CHECK(length(name)> 0),
    dose DOUBLE NOT NULL,
    aplication_route VARCHAR(50) NOT NULL CHECK(length(aplication_route)> 0),
    id_plan INTEGER REFERENCES medication_plans(id) NOT NULL
);


CREATE TABLE diseases (
    id SERIAL PRIMARY KEY,
    disease VARCHAR(100) NOT NULL CHECK(length(disease)> 0),
    id_vacinne INTEGER REFERENCES vaccines(id) NOT NULL
);


CREATE TABLE state_goals (
    id SERIAL PRIMARY KEY,
    description TEXT,
    type VARCHAR(30) NOT NULL CHECK(length(type)> 0),
    status VARCHAR(30) NOT NULL CHECK(length(status)> 0),
    target_value FLOAT NOT NULL,
    title VARCHAR(40) NOT NULL CHECK(length(title)> 0),
    date_creation TIMESTAMP NOT NULL,
    date_end TIMESTAMP NOT NULL,
    id_farm SERIAL REFERENCES farms(id) NOT NULL
);


CREATE TABLE regions_goals (
    id SERIAL PRIMARY KEY,
    region VARCHAR(20) NOT NULL CHECK(length(region)> 0),
    id_goal INTEGER REFERENCES state_goals(id) NOT NULL
);


CREATE TABLE status (
    id SERIAL PRIMARY KEY,
    status VARCHAR(30) NOT NULL CHECK(length(status)> 0),
    id_estado INTEGER REFERENCES state_goals(id) NOT NULL
);


CREATE TABLE energy_registries (
    id SERIAL PRIMARY KEY,
    registration_date DATE NOT NULL,
    energy_consumption DOUBLE NOT NULL,
    id_farm INTEGER REFERENCES farms(id) NOT NULL
);