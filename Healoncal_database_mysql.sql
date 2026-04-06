-- =====================================================================
-- HEALONCAL DATABASE SCHEMA - MYSQL 8.0
-- Migrated from PostgreSQL (Supabase) - Medical-Grade Skin Analysis
-- =====================================================================
-- Requires MySQL 8.0.13+ (for DEFAULT (UUID()) and DEFAULT (expr) on datetime).
-- Run with InnoDB. Uses utf8mb4, UUIDs as CHAR(36), JSON columns, and
-- equivalent constraints/views as Healoncal_databse.sql.
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =====================================================================
-- DROP EXISTING OBJECTS (views first, then tables)
-- =====================================================================

DROP VIEW IF EXISTS comprehensive_treatment_view;
DROP VIEW IF EXISTS user_analysis_summary;
DROP VIEW IF EXISTS disease_analytics_view;

DROP TABLE IF EXISTS disease_heatmaps;
DROP TABLE IF EXISTS detected_skin_diseases;
DROP TABLE IF EXISTS treatment_recommendations;
DROP TABLE IF EXISTS healoncal_combined_results;
DROP TABLE IF EXISTS healoncal_analysis_results;
DROP TABLE IF EXISTS healoncal_captured_images;
DROP TABLE IF EXISTS healoncal_analysis_sessions;

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================================
-- CORE HEALONCAL ANALYSIS TABLES
-- =====================================================================

-- 1. Analysis Sessions
CREATE TABLE healoncal_analysis_sessions (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    total_images INT DEFAULT 0,
    processed_images INT DEFAULT 0,
    analysis_type VARCHAR(50) DEFAULT 'comprehensive',
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) NULL,
    device_info JSON DEFAULT ('{}'),
    location_info JSON DEFAULT ('{}'),
    session_notes TEXT,
    overall_quality_score DOUBLE DEFAULT 0.0,
    session_validity VARCHAR(50) DEFAULT 'valid',
    UNIQUE KEY uk_sessions_session_id (session_id),
    CONSTRAINT chk_sessions_status CHECK (status IN ('pending', 'ready', 'processing', 'completed', 'failed')),
    CONSTRAINT chk_sessions_analysis_type CHECK (analysis_type IN ('basic', 'comprehensive', 'medical')),
    CONSTRAINT chk_sessions_validity CHECK (session_validity IN ('valid', 'invalid', 'review_required'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Core table tracking each skin analysis session with comprehensive metadata and quality control';

-- 2. Captured Images
CREATE TABLE healoncal_captured_images (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    angle VARCHAR(50) NOT NULL,
    image_url TEXT NOT NULL,
    file_path TEXT,
    quality_score DOUBLE DEFAULT 0.0,
    face_detected TINYINT(1) DEFAULT 0,
    lighting_quality DOUBLE DEFAULT 0.0,
    blur_score DOUBLE DEFAULT 0.0,
    resolution_score DOUBLE DEFAULT 0.0,
    file_size INT NULL,
    image_width INT NULL,
    image_height INT NULL,
    format VARCHAR(50) DEFAULT 'JPEG',
    captured_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    processed_at DATETIME(6) NULL,
    storage_bucket VARCHAR(255) DEFAULT 'skin-scans',
    storage_path TEXT,
    cdn_url TEXT,
    CONSTRAINT fk_images_session FOREIGN KEY (session_id) REFERENCES healoncal_analysis_sessions(id) ON DELETE CASCADE,
    CONSTRAINT chk_images_angle CHECK (angle IN ('front', 'left', 'right', 'top', 'bottom'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Stores captured image information; image files are stored in AWS S3 (storage_bucket, storage_path = S3 key, cdn_url = optional CloudFront/S3 URL)';

-- 3. Individual Analysis Results
CREATE TABLE healoncal_analysis_results (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    image_id CHAR(36) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    angle VARCHAR(50) NOT NULL,
    diagnostic_accuracy DOUBLE DEFAULT 0.0,
    biomarkers_analyzed INT DEFAULT 0,
    image_quality_score DOUBLE DEFAULT 0.0,
    analysis_confidence DOUBLE DEFAULT 0.0,
    skin_type_classification TEXT,
    skin_tone_classification TEXT,
    skin_age_estimate INT NULL,
    wrinkles_score DOUBLE DEFAULT 0.0,
    fine_lines_score DOUBLE DEFAULT 0.0,
    dark_circles_score DOUBLE DEFAULT 0.0,
    eye_bags_score DOUBLE DEFAULT 0.0,
    crows_feet_score DOUBLE DEFAULT 0.0,
    pores_score DOUBLE DEFAULT 0.0,
    blackheads_score DOUBLE DEFAULT 0.0,
    pigmentation_score DOUBLE DEFAULT 0.0,
    dark_spots_score DOUBLE DEFAULT 0.0,
    age_spots_score DOUBLE DEFAULT 0.0,
    melasma_score DOUBLE DEFAULT 0.0,
    acne_score DOUBLE DEFAULT 0.0,
    rosacea_score DOUBLE DEFAULT 0.0,
    redness_score DOUBLE DEFAULT 0.0,
    inflammation_score DOUBLE DEFAULT 0.0,
    hydration_score DOUBLE DEFAULT 0.0,
    oiliness_score DOUBLE DEFAULT 0.0,
    skin_texture_score DOUBLE DEFAULT 0.0,
    elasticity_score DOUBLE DEFAULT 0.0,
    firmness_score DOUBLE DEFAULT 0.0,
    skin_firmness_score DOUBLE DEFAULT 0.0,
    radiance_score DOUBLE DEFAULT 0.0,
    uv_damage_score DOUBLE DEFAULT 0.0,
    sensitivity_score DOUBLE DEFAULT 0.0,
    collagen_density DOUBLE DEFAULT 0.0,
    sebum_production DOUBLE DEFAULT 0.0,
    skin_barrier_function DOUBLE DEFAULT 0.0,
    moisture_retention DOUBLE DEFAULT 0.0,
    overall_skin_health_score DOUBLE DEFAULT 0.0,
    treatment_recommendations JSON DEFAULT ('[]'),
    personalized_routine JSON DEFAULT ('[]'),
    analysis_timestamp DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    processing_time_ms INT DEFAULT 0,
    model_version VARCHAR(100) DEFAULT 'Healoncal_v2.0',
    algorithm_version VARCHAR(50) DEFAULT '2.0',
    analysis_data JSON DEFAULT ('{}'),
    CONSTRAINT fk_results_session FOREIGN KEY (session_id) REFERENCES healoncal_analysis_sessions(id) ON DELETE CASCADE,
    CONSTRAINT fk_results_image FOREIGN KEY (image_id) REFERENCES healoncal_captured_images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Individual image analysis results with 20+ biomarkers and comprehensive skin health metrics';

-- 4. Combined Analysis Results
CREATE TABLE healoncal_combined_results (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    final_skin_type_classification TEXT,
    final_skin_tone_classification TEXT,
    estimated_skin_age INT NULL,
    overall_diagnostic_accuracy DOUBLE DEFAULT 0.0,
    combined_wrinkles_score DOUBLE DEFAULT 0.0,
    combined_fine_lines_score DOUBLE DEFAULT 0.0,
    combined_dark_circles_score DOUBLE DEFAULT 0.0,
    combined_eye_bags_score DOUBLE DEFAULT 0.0,
    combined_crows_feet_score DOUBLE DEFAULT 0.0,
    combined_pores_score DOUBLE DEFAULT 0.0,
    combined_blackheads_score DOUBLE DEFAULT 0.0,
    combined_pigmentation_score DOUBLE DEFAULT 0.0,
    combined_dark_spots_score DOUBLE DEFAULT 0.0,
    combined_age_spots_score DOUBLE DEFAULT 0.0,
    combined_melasma_score DOUBLE DEFAULT 0.0,
    combined_acne_score DOUBLE DEFAULT 0.0,
    combined_rosacea_score DOUBLE DEFAULT 0.0,
    combined_redness_score DOUBLE DEFAULT 0.0,
    combined_inflammation_score DOUBLE DEFAULT 0.0,
    combined_hydration_score DOUBLE DEFAULT 0.0,
    combined_oiliness_score DOUBLE DEFAULT 0.0,
    combined_skin_texture_score DOUBLE DEFAULT 0.0,
    combined_elasticity_score DOUBLE DEFAULT 0.0,
    combined_firmness_score DOUBLE DEFAULT 0.0,
    combined_radiance_score DOUBLE DEFAULT 0.0,
    combined_uv_damage_score DOUBLE DEFAULT 0.0,
    combined_sensitivity_score DOUBLE DEFAULT 0.0,
    consolidated_recommendations JSON DEFAULT ('[]'),
    comprehensive_routine JSON DEFAULT ('{}'),
    priority_concerns JSON DEFAULT ('[]'),
    detected_diseases JSON DEFAULT ('[]'),
    images_analyzed INT DEFAULT 0,
    analysis_completeness DOUBLE DEFAULT 0.0,
    data_quality_score DOUBLE DEFAULT 0.0,
    analysis_quality VARCHAR(50) DEFAULT 'screening',
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    combined_analysis_data JSON DEFAULT ('{}'),
    CONSTRAINT fk_combined_session FOREIGN KEY (session_id) REFERENCES healoncal_analysis_sessions(id) ON DELETE CASCADE,
    CONSTRAINT chk_combined_quality CHECK (analysis_quality IN ('screening', 'diagnostic', 'clinical'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Aggregated analysis results from all images in a session providing comprehensive skin assessment';

-- 5. Treatment Recommendations
CREATE TABLE treatment_recommendations (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    recommendation_timestamp DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    ai_model_version VARCHAR(100) DEFAULT 'gemini-2.5-flash',
    ai_confidence DOUBLE DEFAULT 0.0,
    personalization_level VARCHAR(50) DEFAULT 'standard',
    routine_type VARCHAR(50) DEFAULT 'both',
    products JSON DEFAULT ('[]'),
    routine_steps JSON DEFAULT ('{}'),
    key_advice JSON DEFAULT ('[]'),
    ingredients_to_avoid JSON DEFAULT ('[]'),
    expected_timeline TEXT DEFAULT ('4-6 weeks'),
    primary_skin_concerns JSON DEFAULT ('[]'),
    skin_type VARCHAR(255) NULL,
    skin_tone VARCHAR(255) NULL,
    overall_accuracy DOUBLE DEFAULT 0.0,
    user_preferences JSON DEFAULT ('{}'),
    budget_range VARCHAR(50) DEFAULT 'mid-range',
    medical_flags JSON DEFAULT ('[]'),
    dermatologist_referral_needed TINYINT(1) DEFAULT 0,
    urgency_level VARCHAR(50) DEFAULT 'routine',
    status VARCHAR(50) DEFAULT 'active',
    effectiveness_rating DOUBLE DEFAULT 0.0,
    user_feedback JSON DEFAULT ('{}'),
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    expires_at DATETIME(6) DEFAULT (CURRENT_TIMESTAMP(6) + INTERVAL 6 MONTH),
    CONSTRAINT fk_treatment_session FOREIGN KEY (session_id) REFERENCES healoncal_analysis_sessions(id) ON DELETE CASCADE,
    CONSTRAINT chk_treatment_personalization CHECK (personalization_level IN ('basic', 'standard', 'advanced', 'premium')),
    CONSTRAINT chk_treatment_routine_type CHECK (routine_type IN ('morning', 'evening', 'both', 'custom')),
    CONSTRAINT chk_treatment_budget CHECK (budget_range IN ('budget', 'mid-range', 'premium', 'luxury')),
    CONSTRAINT chk_treatment_urgency CHECK (urgency_level IN ('routine', 'moderate', 'urgent')),
    CONSTRAINT chk_treatment_status CHECK (status IN ('active', 'archived', 'updated', 'superseded'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'AI-generated treatment recommendations using Gemini 2.5 Flash with personalized product suggestions';

-- 6. Detected Skin Diseases
CREATE TABLE detected_skin_diseases (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    analysis_result_id CHAR(36) NULL,
    user_id VARCHAR(255) NOT NULL,
    disease_name VARCHAR(255) NOT NULL,
    disease_category VARCHAR(100) NULL,
    confidence_score DOUBLE DEFAULT 0.0,
    severity_level VARCHAR(50) NULL,
    affected_area VARCHAR(100) DEFAULT 'face',
    detection_method VARCHAR(100) DEFAULT 'healoncal_analysis',
    model_version VARCHAR(100) DEFAULT 'Healoncal_v2.0',
    algorithm_confidence DOUBLE DEFAULT 0.0,
    detected_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    requires_medical_attention TINYINT(1) DEFAULT 0,
    recommended_specialist VARCHAR(100) NULL,
    urgency_level VARCHAR(50) DEFAULT 'routine',
    follow_up_required TINYINT(1) DEFAULT 0,
    symptoms_noted JSON DEFAULT ('[]'),
    risk_factors JSON DEFAULT ('[]'),
    differential_diagnoses JSON DEFAULT ('[]'),
    clinical_notes TEXT,
    treatment_recommended JSON DEFAULT ('[]'),
    contraindications JSON DEFAULT ('[]'),
    monitoring_required TINYINT(1) DEFAULT 0,
    notes TEXT,
    image_regions JSON DEFAULT ('[]'),
    biomarker_correlations JSON DEFAULT ('{}'),
    CONSTRAINT fk_diseases_session FOREIGN KEY (session_id) REFERENCES healoncal_analysis_sessions(id) ON DELETE CASCADE,
    CONSTRAINT fk_diseases_result FOREIGN KEY (analysis_result_id) REFERENCES healoncal_analysis_results(id) ON DELETE SET NULL,
    CONSTRAINT chk_diseases_category CHECK (disease_category IS NULL OR disease_category IN ('inflammatory', 'infectious', 'pigmentary', 'structural', 'hormonal', 'genetic', 'environmental')),
    CONSTRAINT chk_diseases_confidence CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    CONSTRAINT chk_diseases_severity CHECK (severity_level IS NULL OR severity_level IN ('very_mild', 'mild', 'moderate', 'severe', 'very_severe')),
    CONSTRAINT chk_diseases_specialist CHECK (recommended_specialist IS NULL OR recommended_specialist IN ('dermatologist', 'general_practitioner', 'cosmetic_dermatologist', 'dermatopathologist')),
    CONSTRAINT chk_diseases_urgency CHECK (urgency_level IN ('routine', 'moderate', 'urgent', 'emergency'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Medical-grade skin disease detection results with clinical recommendations and severity assessment';

-- 7. Disease Heatmaps
CREATE TABLE disease_heatmaps (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    analysis_result_id CHAR(36) NULL,
    user_id VARCHAR(255) NOT NULL,
    disease_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    heatmap_url TEXT NOT NULL,
    heatmap_index INT NULL,
    heatmap_type VARCHAR(50) DEFAULT 'individual',
    colors JSON DEFAULT ('{}'),
    total_diseases INT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_heatmaps_session FOREIGN KEY (session_id) REFERENCES healoncal_analysis_sessions(id) ON DELETE CASCADE,
    CONSTRAINT fk_heatmaps_result FOREIGN KEY (analysis_result_id) REFERENCES healoncal_analysis_results(id) ON DELETE SET NULL,
    CONSTRAINT chk_heatmaps_confidence CHECK (confidence >= 0.00 AND confidence <= 1.00),
    CONSTRAINT chk_heatmaps_severity CHECK (severity IN ('very_mild', 'mild', 'moderate', 'severe', 'very_severe', 'combined')),
    CONSTRAINT chk_heatmaps_type CHECK (heatmap_type IN ('individual', 'combined'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Heatmap visualization data for detected skin diseases with confidence scores and severity levels';

-- =====================================================================
-- INDEXES
-- =====================================================================

CREATE INDEX idx_healoncal_sessions_user_id ON healoncal_analysis_sessions(user_id);
CREATE INDEX idx_healoncal_sessions_status ON healoncal_analysis_sessions(status);
CREATE INDEX idx_healoncal_sessions_created_at ON healoncal_analysis_sessions(created_at);
CREATE INDEX idx_healoncal_sessions_session_id ON healoncal_analysis_sessions(session_id);

CREATE INDEX idx_healoncal_images_session_id ON healoncal_captured_images(session_id);
CREATE INDEX idx_healoncal_images_user_id ON healoncal_captured_images(user_id);
CREATE INDEX idx_healoncal_images_angle ON healoncal_captured_images(angle);
CREATE INDEX idx_healoncal_images_quality_score ON healoncal_captured_images(quality_score);

CREATE INDEX idx_healoncal_results_session_id ON healoncal_analysis_results(session_id);
CREATE INDEX idx_healoncal_results_user_id ON healoncal_analysis_results(user_id);
CREATE INDEX idx_healoncal_results_image_id ON healoncal_analysis_results(image_id);
CREATE INDEX idx_healoncal_results_accuracy ON healoncal_analysis_results(diagnostic_accuracy);

CREATE INDEX idx_healoncal_combined_session_id ON healoncal_combined_results(session_id);
CREATE INDEX idx_healoncal_combined_user_id ON healoncal_combined_results(user_id);
CREATE INDEX idx_healoncal_combined_accuracy ON healoncal_combined_results(overall_diagnostic_accuracy);

CREATE INDEX idx_treatment_recommendations_session_id ON treatment_recommendations(session_id);
CREATE INDEX idx_treatment_recommendations_user_id ON treatment_recommendations(user_id);
CREATE INDEX idx_treatment_recommendations_timestamp ON treatment_recommendations(recommendation_timestamp);
CREATE INDEX idx_treatment_recommendations_status ON treatment_recommendations(status);
CREATE INDEX idx_treatment_recommendations_ai_model ON treatment_recommendations(ai_model_version);

CREATE INDEX idx_detected_skin_diseases_session_id ON detected_skin_diseases(session_id);
CREATE INDEX idx_detected_skin_diseases_user_id ON detected_skin_diseases(user_id);
CREATE INDEX idx_detected_skin_diseases_name ON detected_skin_diseases(disease_name);
CREATE INDEX idx_detected_skin_diseases_confidence ON detected_skin_diseases(confidence_score);
CREATE INDEX idx_detected_skin_diseases_category ON detected_skin_diseases(disease_category);
CREATE INDEX idx_detected_skin_diseases_severity ON detected_skin_diseases(severity_level);
CREATE INDEX idx_detected_skin_diseases_medical_attention ON detected_skin_diseases(requires_medical_attention);

CREATE INDEX idx_disease_heatmaps_session_id ON disease_heatmaps(session_id);
CREATE INDEX idx_disease_heatmaps_user_id ON disease_heatmaps(user_id);
CREATE INDEX idx_disease_heatmaps_disease_name ON disease_heatmaps(disease_name);
CREATE INDEX idx_disease_heatmaps_category ON disease_heatmaps(category);
CREATE INDEX idx_disease_heatmaps_confidence ON disease_heatmaps(confidence);
CREATE INDEX idx_disease_heatmaps_severity ON disease_heatmaps(severity);
CREATE INDEX idx_disease_heatmaps_created_at ON disease_heatmaps(created_at);
CREATE INDEX idx_disease_heatmaps_heatmap_type ON disease_heatmaps(heatmap_type);

-- =====================================================================
-- VIEWS
-- =====================================================================

CREATE OR REPLACE VIEW comprehensive_treatment_view AS
SELECT
    tr.id AS recommendation_id,
    tr.session_id,
    tr.user_id,
    tr.recommendation_timestamp,
    tr.ai_model_version,
    tr.ai_confidence,
    tr.personalization_level,
    tr.routine_type,
    tr.products,
    tr.key_advice,
    tr.expected_timeline,
    tr.primary_skin_concerns,
    tr.skin_type,
    tr.skin_tone,
    tr.overall_accuracy,
    tr.user_preferences,
    tr.budget_range,
    tr.medical_flags,
    tr.dermatologist_referral_needed,
    tr.status AS recommendation_status,
    COALESCE(
        JSON_ARRAYAGG(
            CASE WHEN dsd.id IS NOT NULL THEN
                JSON_OBJECT(
                    'disease_name', dsd.disease_name,
                    'category', dsd.disease_category,
                    'confidence', dsd.confidence_score,
                    'severity', dsd.severity_level,
                    'requires_medical_attention', dsd.requires_medical_attention,
                    'urgency_level', dsd.urgency_level,
                    'affected_area', dsd.affected_area,
                    'symptoms', dsd.symptoms_noted,
                    'dermatologist_recommendation', dsd.treatment_recommended
                )
            END
        ),
        JSON_ARRAY()
    ) AS detected_diseases,
    has.status AS analysis_status,
    has.created_at AS analysis_date,
    has.total_images,
    has.overall_quality_score AS session_quality,
    hcr.final_skin_type_classification,
    hcr.final_skin_tone_classification,
    hcr.estimated_skin_age,
    hcr.overall_diagnostic_accuracy AS combined_accuracy,
    hcr.priority_concerns
FROM treatment_recommendations tr
LEFT JOIN detected_skin_diseases dsd ON tr.session_id = dsd.session_id
LEFT JOIN healoncal_analysis_sessions has ON tr.session_id = has.id
LEFT JOIN healoncal_combined_results hcr ON tr.session_id = hcr.session_id
GROUP BY
    tr.id, tr.session_id, tr.user_id, tr.recommendation_timestamp, tr.ai_model_version,
    tr.ai_confidence, tr.personalization_level, tr.routine_type, tr.products, tr.key_advice,
    tr.expected_timeline, tr.primary_skin_concerns, tr.skin_type, tr.skin_tone, tr.overall_accuracy,
    tr.user_preferences, tr.budget_range, tr.medical_flags, tr.dermatologist_referral_needed, tr.status,
    has.status, has.created_at, has.total_images, has.overall_quality_score,
    hcr.final_skin_type_classification, hcr.final_skin_tone_classification, hcr.estimated_skin_age,
    hcr.overall_diagnostic_accuracy, hcr.priority_concerns;

CREATE OR REPLACE VIEW user_analysis_summary AS
SELECT
    has.user_id,
    COUNT(DISTINCT has.session_id) AS total_sessions,
    COUNT(DISTINCT CASE WHEN has.status = 'completed' THEN has.session_id END) AS completed_sessions,
    AVG(has.overall_quality_score) AS avg_session_quality,
    MAX(has.created_at) AS last_analysis_date,
    MIN(has.created_at) AS first_analysis_date,
    COUNT(DISTINCT dsd.disease_name) AS unique_diseases_detected,
    COUNT(CASE WHEN dsd.requires_medical_attention = 1 THEN 1 END) AS medical_attention_cases,
    COUNT(DISTINCT tr.id) AS total_recommendations,
    COUNT(CASE WHEN tr.dermatologist_referral_needed = 1 THEN 1 END) AS dermatologist_referrals
FROM healoncal_analysis_sessions has
LEFT JOIN detected_skin_diseases dsd ON has.id = dsd.session_id
LEFT JOIN treatment_recommendations tr ON has.id = tr.session_id
GROUP BY has.user_id;

CREATE OR REPLACE VIEW disease_analytics_view AS
SELECT
    disease_name,
    disease_category,
    COUNT(*) AS detection_count,
    AVG(confidence_score) AS avg_confidence,
    COUNT(CASE WHEN requires_medical_attention = 1 THEN 1 END) AS medical_attention_count,
    COUNT(CASE WHEN severity_level IN ('severe', 'very_severe') THEN 1 END) AS severe_cases,
    DATE_FORMAT(detected_at, '%Y-%m-01 00:00:00') AS detection_month,
    COUNT(*) OVER (PARTITION BY DATE_FORMAT(detected_at, '%Y-%m-01')) AS monthly_detections
FROM detected_skin_diseases
GROUP BY disease_name, disease_category, DATE_FORMAT(detected_at, '%Y-%m-01')
ORDER BY detection_count DESC;

-- =====================================================================
-- END OF MYSQL SCHEMA
-- =====================================================================
