-- Run this while connected to postgres as a superuser/admin user.
CREATE DATABASE font;

-- Connect to font DB before running statements below.

CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    nickname VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = CURRENT_TIMESTAMP;
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE base_fonts (
    base_font_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE handwritings (
    handwriting_id BIGSERIAL PRIMARY KEY,
    image_url VARCHAR(255) NOT NULL,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(50) NOT NULL,
    CONSTRAINT fk_handwriting_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE TABLE generation_jobs (
    job_id BIGSERIAL PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    progress INT DEFAULT 0,
    similarity_percent DECIMAL(5,2),
    fail_reason VARCHAR(255),
    requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    user_id VARCHAR(50) NOT NULL,
    base_font_id BIGINT NOT NULL,
    handwriting_id BIGINT NOT NULL,
    CONSTRAINT fk_job_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_job_basefont
        FOREIGN KEY (base_font_id) REFERENCES base_fonts(base_font_id),
    CONSTRAINT fk_job_handwriting
        FOREIGN KEY (handwriting_id) REFERENCES handwritings(handwriting_id)
);

CREATE TABLE generated_fonts (
    generated_font_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    file_url VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    job_id BIGINT NOT NULL UNIQUE,
    CONSTRAINT fk_font_job
        FOREIGN KEY (job_id) REFERENCES generation_jobs(job_id)
        ON DELETE CASCADE
);

CREATE TABLE download_records (
    download_id BIGSERIAL PRIMARY KEY,
    downloaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(50) NOT NULL,
    generated_font_id BIGINT NOT NULL,
    CONSTRAINT fk_download_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_download_font
        FOREIGN KEY (generated_font_id) REFERENCES generated_fonts(generated_font_id)
        ON DELETE CASCADE
);

CREATE TABLE ratings (
    rating_id BIGSERIAL PRIMARY KEY,
    score INT NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment VARCHAR(255),
    rated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(50) NOT NULL,
    generated_font_id BIGINT NOT NULL,
    CONSTRAINT fk_rating_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_rating_font
        FOREIGN KEY (generated_font_id) REFERENCES generated_fonts(generated_font_id)
        ON DELETE CASCADE,
    CONSTRAINT unique_user_font
        UNIQUE (user_id, generated_font_id)
);
