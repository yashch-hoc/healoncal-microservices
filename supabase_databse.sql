-- =====================================================================
-- COMPLETE HEALONCAL DATABASE SCHEMA
-- Medical-Grade Skin Analysis System with AI Recommendations
-- =====================================================================
-- This file contains the complete database schema for the Healoncal 
-- medical-grade system including all tables, indexes, views, and constraints.
-- =====================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================================
-- DROP EXISTING TABLES (if they exist) - Clean slate approach
-- =====================================================================

-- Drop views first (they depend on tables)
DROP VIEW IF EXISTS public.comprehensive_treatment_view CASCADE;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS public.detected_skin_diseases CASCADE;
DROP TABLE IF EXISTS public.treatment_recommendations CASCADE;
DROP TABLE IF EXISTS public.healoncal_combined_results CASCADE;
DROP TABLE IF EXISTS public.healoncal_analysis_results CASCADE;
DROP TABLE IF EXISTS public.healoncal_captured_images CASCADE;
DROP TABLE IF EXISTS public.healoncal_analysis_sessions CASCADE;

-- =====================================================================
-- CORE HEALONCAL ANALYSIS TABLES
-- =====================================================================

-- 1. Analysis Sessions Table
-- Tracks each skin analysis session for a user
CREATE TABLE public.healoncal_analysis_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    session_id TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'ready', 'processing', 'completed', 'failed')),
    total_images INTEGER DEFAULT 0,
    processed_images INTEGER DEFAULT 0,
    analysis_type TEXT DEFAULT 'comprehensive' CHECK (analysis_type IN ('basic', 'comprehensive', 'medical')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    -- Session metadata
    device_info JSONB DEFAULT '{}',
    location_info JSONB DEFAULT '{}',
    session_notes TEXT,
    
    -- Quality control
    overall_quality_score FLOAT DEFAULT 0.0,
    session_validity TEXT DEFAULT 'valid' CHECK (session_validity IN ('valid', 'invalid', 'review_required'))
);

-- 2. Captured Images Table
-- Stores information about captured images for analysis
CREATE TABLE public.healoncal_captured_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.healoncal_analysis_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    angle TEXT NOT NULL CHECK (angle IN ('front', 'left', 'right', 'top', 'bottom')),
    image_url TEXT NOT NULL,
    file_path TEXT,
    
    -- Image quality metrics
    quality_score FLOAT DEFAULT 0.0,
    face_detected BOOLEAN DEFAULT FALSE,
    lighting_quality FLOAT DEFAULT 0.0,
    blur_score FLOAT DEFAULT 0.0,
    resolution_score FLOAT DEFAULT 0.0,
    
    -- Technical metadata
    file_size INTEGER,
    image_width INTEGER,
    image_height INTEGER,
    format TEXT DEFAULT 'JPEG',
    
    -- Timestamps
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    
    -- Storage information
    storage_bucket TEXT DEFAULT 'skin-scans',
    storage_path TEXT,
    cdn_url TEXT
);

-- 3. Healoncal Metrics Table - REMOVED (not used in code)

-- 4. Individual Analysis Results Table
-- Stores analysis results for each individual image
CREATE TABLE public.healoncal_analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.healoncal_analysis_sessions(id) ON DELETE CASCADE,
    image_id UUID REFERENCES public.healoncal_captured_images(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    angle TEXT NOT NULL,
    
    -- Core analysis metrics
    diagnostic_accuracy FLOAT DEFAULT 0.0,
    biomarkers_analyzed INTEGER DEFAULT 0,
    image_quality_score FLOAT DEFAULT 0.0,
    analysis_confidence FLOAT DEFAULT 0.0,
    
    -- Skin classifications
    skin_type_classification TEXT,
    skin_tone_classification TEXT,
    skin_age_estimate INTEGER,
    
    -- Detailed skin metrics (20+ biomarkers)
    wrinkles_score FLOAT DEFAULT 0.0,
    fine_lines_score FLOAT DEFAULT 0.0,
    dark_circles_score FLOAT DEFAULT 0.0,
    eye_bags_score FLOAT DEFAULT 0.0,
    crows_feet_score FLOAT DEFAULT 0.0,
    pores_score FLOAT DEFAULT 0.0,
    blackheads_score FLOAT DEFAULT 0.0,
    pigmentation_score FLOAT DEFAULT 0.0,
    dark_spots_score FLOAT DEFAULT 0.0,
    age_spots_score FLOAT DEFAULT 0.0,
    melasma_score FLOAT DEFAULT 0.0,
    acne_score FLOAT DEFAULT 0.0,
    rosacea_score FLOAT DEFAULT 0.0,
    redness_score FLOAT DEFAULT 0.0,
    inflammation_score FLOAT DEFAULT 0.0,
    hydration_score FLOAT DEFAULT 0.0,
    oiliness_score FLOAT DEFAULT 0.0,
    skin_texture_score FLOAT DEFAULT 0.0,
    elasticity_score FLOAT DEFAULT 0.0,
    firmness_score FLOAT DEFAULT 0.0,
    skin_firmness_score FLOAT DEFAULT 0.0,
    radiance_score FLOAT DEFAULT 0.0,
    uv_damage_score FLOAT DEFAULT 0.0,
    sensitivity_score FLOAT DEFAULT 0.0,
    
    -- Advanced analysis
    collagen_density FLOAT DEFAULT 0.0,
    sebum_production FLOAT DEFAULT 0.0,
    skin_barrier_function FLOAT DEFAULT 0.0,
    moisture_retention FLOAT DEFAULT 0.0,
    overall_skin_health_score FLOAT DEFAULT 0.0,
    
    -- Recommendations and treatments
    treatment_recommendations JSONB DEFAULT '[]',
    personalized_routine JSONB DEFAULT '[]',
    
    -- Technical metadata
    analysis_timestamp TIMESTAMPTZ DEFAULT NOW(),
    processing_time_ms INTEGER DEFAULT 0,
    model_version TEXT DEFAULT 'Healoncal_v2.0',
    algorithm_version TEXT DEFAULT '2.0',
    
    -- Analysis data (full result object)
    analysis_data JSONB DEFAULT '{}'
);

-- 4. Combined Analysis Results Table
-- Stores aggregated results from all images in a session
CREATE TABLE public.healoncal_combined_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.healoncal_analysis_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    
    -- Overall classifications
    final_skin_type_classification TEXT,
    final_skin_tone_classification TEXT,
    estimated_skin_age INTEGER,
    overall_diagnostic_accuracy FLOAT DEFAULT 0.0,
    
    -- Combined metrics (averaged from individual analyses)
    combined_wrinkles_score FLOAT DEFAULT 0.0,
    combined_fine_lines_score FLOAT DEFAULT 0.0,
    combined_dark_circles_score FLOAT DEFAULT 0.0,
    combined_eye_bags_score FLOAT DEFAULT 0.0,
    combined_crows_feet_score FLOAT DEFAULT 0.0,
    combined_pores_score FLOAT DEFAULT 0.0,
    combined_blackheads_score FLOAT DEFAULT 0.0,
    combined_pigmentation_score FLOAT DEFAULT 0.0,
    combined_dark_spots_score FLOAT DEFAULT 0.0,
    combined_age_spots_score FLOAT DEFAULT 0.0,
    combined_melasma_score FLOAT DEFAULT 0.0,
    combined_acne_score FLOAT DEFAULT 0.0,
    combined_rosacea_score FLOAT DEFAULT 0.0,
    combined_redness_score FLOAT DEFAULT 0.0,
    combined_inflammation_score FLOAT DEFAULT 0.0,
    combined_hydration_score FLOAT DEFAULT 0.0,
    combined_oiliness_score FLOAT DEFAULT 0.0,
    combined_skin_texture_score FLOAT DEFAULT 0.0,
    combined_elasticity_score FLOAT DEFAULT 0.0,
    combined_firmness_score FLOAT DEFAULT 0.0,
    combined_radiance_score FLOAT DEFAULT 0.0,
    combined_uv_damage_score FLOAT DEFAULT 0.0,
    combined_sensitivity_score FLOAT DEFAULT 0.0,
    
    -- Comprehensive recommendations
    consolidated_recommendations JSONB DEFAULT '[]',
    comprehensive_routine JSONB DEFAULT '{}',
    priority_concerns JSONB DEFAULT '[]',
    detected_diseases JSONB DEFAULT '[]',
    
    -- Analysis metadata
    images_analyzed INTEGER DEFAULT 0,
    analysis_completeness FLOAT DEFAULT 0.0,
    data_quality_score FLOAT DEFAULT 0.0,
    analysis_quality TEXT DEFAULT 'screening' CHECK (analysis_quality IN ('screening', 'diagnostic', 'clinical')),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Combined analysis data
    combined_analysis_data JSONB DEFAULT '{}'
);

-- =====================================================================
-- AI RECOMMENDATIONS & TREATMENT TABLES
-- =====================================================================

-- 5. Treatment Recommendations Table
-- Stores AI-generated treatment recommendations using Gemini 2.5 Flash
CREATE TABLE public.treatment_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.healoncal_analysis_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    
    -- Recommendation metadata
    recommendation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    ai_model_version TEXT DEFAULT 'gemini-2.5-flash',
    ai_confidence FLOAT DEFAULT 0.0,
    personalization_level TEXT DEFAULT 'standard' CHECK (personalization_level IN ('basic', 'standard', 'advanced', 'premium')),
    
    -- Core recommendation data
    routine_type TEXT DEFAULT 'both' CHECK (routine_type IN ('morning', 'evening', 'both', 'custom')),
    products JSONB DEFAULT '[]', -- Array of recommended products
    routine_steps JSONB DEFAULT '{}', -- Morning and evening steps
    key_advice JSONB DEFAULT '[]', -- Key advice points
    ingredients_to_avoid JSONB DEFAULT '[]', -- Ingredients to avoid
    expected_timeline TEXT DEFAULT '4-6 weeks',
    
    -- Analysis-based data
    primary_skin_concerns JSONB DEFAULT '[]', -- Main concerns identified
    skin_type TEXT,
    skin_tone TEXT,
    overall_accuracy FLOAT DEFAULT 0.0,
    
    -- User preferences (if provided)
    user_preferences JSONB DEFAULT '{}',
    budget_range TEXT DEFAULT 'mid-range' CHECK (budget_range IN ('budget', 'mid-range', 'premium', 'luxury')),
    
    -- Medical considerations
    medical_flags JSONB DEFAULT '[]',
    dermatologist_referral_needed BOOLEAN DEFAULT FALSE,
    urgency_level TEXT DEFAULT 'routine' CHECK (urgency_level IN ('routine', 'moderate', 'urgent')),
    
    -- Status tracking
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'updated', 'superseded')),
    effectiveness_rating FLOAT DEFAULT 0.0,
    user_feedback JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '6 months')
);

-- 6. Detected Skin Diseases Table (Comprehensive version)
-- Tracks detected skin diseases and conditions from analysis
CREATE TABLE public.detected_skin_diseases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.healoncal_analysis_sessions(id) ON DELETE CASCADE,
    analysis_result_id UUID REFERENCES public.healoncal_analysis_results(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    
    -- Disease information
    disease_name TEXT NOT NULL,
    disease_category TEXT CHECK (disease_category IN ('inflammatory', 'infectious', 'pigmentary', 'structural', 'hormonal', 'genetic', 'environmental')),
    confidence_score FLOAT DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    severity_level TEXT CHECK (severity_level IN ('very_mild', 'mild', 'moderate', 'severe', 'very_severe')),
    affected_area TEXT DEFAULT 'face',
    
    -- Detection metadata
    detection_method TEXT DEFAULT 'healoncal_analysis',
    model_version TEXT DEFAULT 'Healoncal_v2.0',
    algorithm_confidence FLOAT DEFAULT 0.0,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Medical recommendations
    requires_medical_attention BOOLEAN DEFAULT FALSE,
    recommended_specialist TEXT CHECK (recommended_specialist IN ('dermatologist', 'general_practitioner', 'cosmetic_dermatologist', 'dermatopathologist')),
    urgency_level TEXT DEFAULT 'routine' CHECK (urgency_level IN ('routine', 'moderate', 'urgent', 'emergency')),
    follow_up_required BOOLEAN DEFAULT FALSE,
    
    -- Clinical information
    symptoms_noted JSONB DEFAULT '[]',
    risk_factors JSONB DEFAULT '[]',
    differential_diagnoses JSONB DEFAULT '[]',
    clinical_notes TEXT,
    
    -- Treatment tracking
    treatment_recommended JSONB DEFAULT '[]',
    contraindications JSONB DEFAULT '[]',
    monitoring_required BOOLEAN DEFAULT FALSE,
    
    -- Additional metadata
    notes TEXT,
    image_regions JSONB DEFAULT '[]', -- Specific regions where disease was detected
    biomarker_correlations JSONB DEFAULT '{}' -- Related biomarker scores
);

-- 7. Disease Heatmaps Table (NEW - Missing table causing errors)
-- Stores heatmap visualization data for detected skin diseases
-- SAFE TO RUN: DROP IF EXISTS prevents "relation already exists" errors
DROP TABLE IF EXISTS public.disease_heatmaps CASCADE;
CREATE TABLE public.disease_heatmaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.healoncal_analysis_sessions(id) ON DELETE CASCADE,
    analysis_result_id UUID REFERENCES public.healoncal_analysis_results(id) ON DELETE SET NULL,
    user_id TEXT NOT NULL,
    
    -- Heatmap information
    disease_name TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0.00 AND confidence <= 1.00),
             severity TEXT NOT NULL CHECK (severity IN ('very_mild', 'mild', 'moderate', 'severe', 'very_severe', 'combined')),
    
    -- Visualization data
    heatmap_url TEXT NOT NULL,
    heatmap_index INTEGER,
    heatmap_type TEXT DEFAULT 'individual' CHECK (heatmap_type IN ('individual', 'combined')),
    colors JSONB DEFAULT '{}',
    total_diseases INTEGER,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- =====================================================================

-- Analysis Sessions Indexes
CREATE INDEX idx_healoncal_sessions_user_id ON public.healoncal_analysis_sessions(user_id);
CREATE INDEX idx_healoncal_sessions_status ON public.healoncal_analysis_sessions(status);
CREATE INDEX idx_healoncal_sessions_created_at ON public.healoncal_analysis_sessions(created_at);
CREATE INDEX idx_healoncal_sessions_session_id ON public.healoncal_analysis_sessions(session_id);

-- Captured Images Indexes
CREATE INDEX idx_healoncal_images_session_id ON public.healoncal_captured_images(session_id);
CREATE INDEX idx_healoncal_images_user_id ON public.healoncal_captured_images(user_id);
CREATE INDEX idx_healoncal_images_angle ON public.healoncal_captured_images(angle);
CREATE INDEX idx_healoncal_images_quality_score ON public.healoncal_captured_images(quality_score);

-- Healoncal Metrics Indexes - REMOVED (table not used)

-- Analysis Results Indexes
CREATE INDEX idx_healoncal_results_session_id ON public.healoncal_analysis_results(session_id);
CREATE INDEX idx_healoncal_results_user_id ON public.healoncal_analysis_results(user_id);
CREATE INDEX idx_healoncal_results_image_id ON public.healoncal_analysis_results(image_id);
CREATE INDEX idx_healoncal_results_accuracy ON public.healoncal_analysis_results(diagnostic_accuracy);

-- Combined Results Indexes
CREATE INDEX idx_healoncal_combined_session_id ON public.healoncal_combined_results(session_id);
CREATE INDEX idx_healoncal_combined_user_id ON public.healoncal_combined_results(user_id);
CREATE INDEX idx_healoncal_combined_accuracy ON public.healoncal_combined_results(overall_diagnostic_accuracy);

-- Treatment Recommendations Indexes
CREATE INDEX idx_treatment_recommendations_session_id ON public.treatment_recommendations(session_id);
CREATE INDEX idx_treatment_recommendations_user_id ON public.treatment_recommendations(user_id);
CREATE INDEX idx_treatment_recommendations_timestamp ON public.treatment_recommendations(recommendation_timestamp);
CREATE INDEX idx_treatment_recommendations_status ON public.treatment_recommendations(status);
CREATE INDEX idx_treatment_recommendations_ai_model ON public.treatment_recommendations(ai_model_version);

-- Disease Detection Indexes (Comprehensive only)
CREATE INDEX idx_detected_skin_diseases_session_id ON public.detected_skin_diseases(session_id);
CREATE INDEX idx_detected_skin_diseases_user_id ON public.detected_skin_diseases(user_id);
CREATE INDEX idx_detected_skin_diseases_name ON public.detected_skin_diseases(disease_name);
CREATE INDEX idx_detected_skin_diseases_confidence ON public.detected_skin_diseases(confidence_score);
CREATE INDEX idx_detected_skin_diseases_category ON public.detected_skin_diseases(disease_category);
CREATE INDEX idx_detected_skin_diseases_severity ON public.detected_skin_diseases(severity_level);
CREATE INDEX idx_detected_skin_diseases_medical_attention ON public.detected_skin_diseases(requires_medical_attention);

-- Disease Heatmaps Indexes (NEW - For missing table)
DROP INDEX IF EXISTS idx_disease_heatmaps_session_id;
DROP INDEX IF EXISTS idx_disease_heatmaps_user_id;
DROP INDEX IF EXISTS idx_disease_heatmaps_disease_name;
DROP INDEX IF EXISTS idx_disease_heatmaps_category;
DROP INDEX IF EXISTS idx_disease_heatmaps_confidence;
DROP INDEX IF EXISTS idx_disease_heatmaps_severity;
DROP INDEX IF EXISTS idx_disease_heatmaps_created_at;
DROP INDEX IF EXISTS idx_disease_heatmaps_heatmap_type;

CREATE INDEX idx_disease_heatmaps_session_id ON public.disease_heatmaps(session_id);
CREATE INDEX idx_disease_heatmaps_user_id ON public.disease_heatmaps(user_id);
CREATE INDEX idx_disease_heatmaps_disease_name ON public.disease_heatmaps(disease_name);
CREATE INDEX idx_disease_heatmaps_category ON public.disease_heatmaps(category);
CREATE INDEX idx_disease_heatmaps_confidence ON public.disease_heatmaps(confidence);
CREATE INDEX idx_disease_heatmaps_severity ON public.disease_heatmaps(severity);
CREATE INDEX idx_disease_heatmaps_created_at ON public.disease_heatmaps(created_at);
CREATE INDEX idx_disease_heatmaps_heatmap_type ON public.disease_heatmaps(heatmap_type);

-- =====================================================================
-- COMPREHENSIVE VIEWS FOR EASY DATA ACCESS
-- =====================================================================

-- 1. Comprehensive Treatment View
-- Combines recommendations with detected diseases for complete treatment overview
CREATE OR REPLACE VIEW public.comprehensive_treatment_view AS
SELECT 
    tr.id as recommendation_id,
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
    tr.status as recommendation_status,
    
    -- Aggregate disease information (from detected_skin_diseases only)
    COALESCE(
        json_agg(
            json_build_object(
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
        ) FILTER (WHERE dsd.id IS NOT NULL),
        '[]'::json
    ) as detected_diseases,
    
    -- Session information
    has.status as analysis_status,
    has.created_at as analysis_date,
    has.total_images,
    has.overall_quality_score as session_quality,
    
    -- Combined analysis summary
    hcr.final_skin_type_classification,
    hcr.final_skin_tone_classification,
    hcr.estimated_skin_age,
    hcr.overall_diagnostic_accuracy as combined_accuracy,
    hcr.priority_concerns
    
FROM public.treatment_recommendations tr
LEFT JOIN public.detected_skin_diseases dsd ON tr.session_id = dsd.session_id
LEFT JOIN public.healoncal_analysis_sessions has ON tr.session_id = has.id
LEFT JOIN public.healoncal_combined_results hcr ON tr.session_id = hcr.session_id
GROUP BY tr.id, has.status, has.created_at, has.total_images, has.overall_quality_score,
         hcr.final_skin_type_classification, hcr.final_skin_tone_classification, 
         hcr.estimated_skin_age, hcr.overall_diagnostic_accuracy, hcr.priority_concerns;

-- 2. User Analysis Summary View
-- Provides a summary of all analyses for each user
CREATE OR REPLACE VIEW public.user_analysis_summary AS
SELECT 
    has.user_id,
    COUNT(DISTINCT has.session_id) as total_sessions,
    COUNT(DISTINCT CASE WHEN has.status = 'completed' THEN has.session_id END) as completed_sessions,
    AVG(has.overall_quality_score) as avg_session_quality,
    MAX(has.created_at) as last_analysis_date,
    MIN(has.created_at) as first_analysis_date,
    
    -- Disease statistics (from detected_skin_diseases only)
    COUNT(DISTINCT dsd.disease_name) as unique_diseases_detected,
    COUNT(CASE WHEN dsd.requires_medical_attention = true THEN 1 END) as medical_attention_cases,
    
    -- Recommendation statistics
    COUNT(DISTINCT tr.id) as total_recommendations,
    COUNT(CASE WHEN tr.dermatologist_referral_needed = true THEN 1 END) as dermatologist_referrals
    
FROM public.healoncal_analysis_sessions has
LEFT JOIN public.detected_skin_diseases dsd ON has.id = dsd.session_id
LEFT JOIN public.treatment_recommendations tr ON has.id = tr.session_id
GROUP BY has.user_id;

-- 3. Disease Analytics View
-- Provides insights into disease detection patterns
CREATE OR REPLACE VIEW public.disease_analytics_view AS
SELECT 
    disease_name,
    disease_category,
    COUNT(*) as detection_count,
    AVG(confidence_score) as avg_confidence,
    COUNT(CASE WHEN requires_medical_attention = true THEN 1 END) as medical_attention_count,
    COUNT(CASE WHEN severity_level IN ('severe', 'very_severe') THEN 1 END) as severe_cases,
    
    -- Temporal patterns
    DATE_TRUNC('month', detected_at) as detection_month,
    COUNT(*) OVER (PARTITION BY DATE_TRUNC('month', detected_at)) as monthly_detections
    
FROM public.detected_skin_diseases
GROUP BY disease_name, disease_category, DATE_TRUNC('month', detected_at)
ORDER BY detection_count DESC;

-- =====================================================================
-- TABLE COMMENTS AND DOCUMENTATION
-- =====================================================================

-- Analysis Sessions
COMMENT ON TABLE public.healoncal_analysis_sessions IS 'Core table tracking each skin analysis session with comprehensive metadata and quality control';

-- Captured Images
COMMENT ON TABLE public.healoncal_captured_images IS 'Stores captured image information with detailed quality metrics and technical metadata';

-- Healoncal Metrics - REMOVED (not used in code)

-- Analysis Results
COMMENT ON TABLE public.healoncal_analysis_results IS 'Individual image analysis results with 20+ biomarkers and comprehensive skin health metrics';

-- Combined Results
COMMENT ON TABLE public.healoncal_combined_results IS 'Aggregated analysis results from all images in a session providing comprehensive skin assessment';

-- Treatment Recommendations
COMMENT ON TABLE public.treatment_recommendations IS 'AI-generated treatment recommendations using Gemini 2.5 Flash with personalized product suggestions';

-- Disease Detection (Comprehensive only)
COMMENT ON TABLE public.detected_skin_diseases IS 'Medical-grade skin disease detection results with clinical recommendations and severity assessment';

-- Disease Heatmaps (NEW - Missing table)
COMMENT ON TABLE public.disease_heatmaps IS 'Heatmap visualization data for detected skin diseases with confidence scores and severity levels';

-- Views
COMMENT ON VIEW public.comprehensive_treatment_view IS 'Complete treatment overview combining recommendations, diseases, and analysis results';
COMMENT ON VIEW public.user_analysis_summary IS 'User-level analytics showing analysis history and patterns';
COMMENT ON VIEW public.disease_analytics_view IS 'Disease detection analytics for medical insights and trend analysis';

-- =====================================================================
-- SECURITY AND ACCESS CONTROL
-- =====================================================================

-- Row Level Security (RLS) policies can be added here based on requirements
-- Example: Users can only access their own data
-- ALTER TABLE public.healoncal_analysis_sessions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY user_own_sessions ON public.healoncal_analysis_sessions FOR ALL USING (user_id = current_user);

-- =====================================================================
-- SCHEMA VERSION AND METADATA - REMOVED (not needed for production)
-- ===================================================================== 

-- =====================================================================
-- COMPLETION MESSAGE
-- =====================================================================

-- This completes the optimized Healoncal database schema
-- Features included:
-- ✅ Essential table structure with DROP IF EXISTS
-- ✅ Medical-grade skin analysis tracking
-- ✅ Gemini 2.5 Flash AI recommendations
-- ✅ Comprehensive disease detection (single table)
-- ✅ Disease heatmaps visualization table (FIXED - was missing)
-- ✅ SAFE TO RUN: Added DROP IF EXISTS to prevent "relation already exists" errors
-- ✅ Optimized indexing for performance
-- ✅ Clean views for easy data access
-- ✅ Proper constraints and data validation
-- ✅ Full documentation and comments
-- ✅ Code compatibility with existing application
-- ✅ Removed unused/duplicate tables
-- ✅ Streamlined database structure
-- ✅ FIXED: Added missing disease_heatmaps table causing API errors
