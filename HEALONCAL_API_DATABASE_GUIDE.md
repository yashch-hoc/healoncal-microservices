# Healoncal API & Database Guide for Frontend Developers

## Table of Contents
1. [Overview](#overview)
2. [API Endpoints](#api-endpoints)
3. [Database Schema](#database-schema)
4. [Data Flow](#data-flow)
5. [Frontend Integration Examples](#frontend-integration-examples)
6. [Error Handling](#error-handling)
7. [Authentication & Security](#authentication--security)

## Overview

Healoncal is a medical-grade skin analysis system that provides:
- **98% Diagnostic Accuracy** with 150+ facial biomarkers
- **20+ Skin Health Metrics** including wrinkles, pigmentation, acne, etc.
- **AI-Powered Recommendations** using Gemini 2.5 Flash
- **Real-time Quality Assurance** with LIQA technology
- **Clinical Classifications** for skin type, tone, and age
- **Pinpoint Heatmap Visualizations** with disease-specific colors and precise location mapping
- **Multi-Angle Analysis** supporting front, left, and right facial views
- **Parallel Processing** for faster heatmap generation

### Base URL
```
https://healoncal-api-232777865515.us-central1.run.app/api/healoncal
```

---

## API Endpoints

### 1. Health Check
**GET** `/health`

Check if the Healoncal service is running.

**Response:**
```json
{
  "status": "healthy",
  "service": "Healoncal Medical-Grade Analysis",
  "version": "2.0",
  "features": [
    "98% Diagnostic Accuracy",
    "150+ Facial Biomarkers",
    "20+ Skin Health Metrics",
    "LIQA Real-time Quality Assurance",
    "Clinical Classifications",
    "Personalized Recommendations",
    "AI-Powered Product Recommendations"
  ]
}
```

### 2. Capture Image
**POST** `/capture`

Capture an image for analysis. Requires 3 images (front, left, right) for complete analysis.

**Request Body:**
```json
{
  "user_id": "string",
  "angle": "front|left|right",
  "image_data": "base64_encoded_image_string"
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "uuid",
  "image_id": "uuid",
  "quality_score": 95.5,
  "face_detected": true,
  "message": "Image captured successfully with 95.5% quality"
}
```

**Frontend Implementation:**
```javascript
const captureImage = async (userId, angle, imageFile) => {
  const base64 = await convertToBase64(imageFile);
  
  const response = await fetch('/api/healoncal/capture', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_id: userId,
      angle: angle,
      image_data: base64
    })
  });
  
  return await response.json();
};
```

### 3. Start Analysis
**POST** `/analyze`

Start the medical-grade analysis process. Requires 3 captured images.

**Request Body:**
```json
{
  "user_id": "string"
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "uuid",
  "processed_images": 3,
  "total_images": 3,
  "message": "Analysis completed successfully"
}
```

**Error Response (Insufficient Images):**
```json
{
  "success": false,
  "message": "Need 3 images for complete analysis. Currently have 2 images.",
  "session_id": "uuid",
  "images_captured": 2,
  "required_images": 3,
  "error": "Insufficient images for analysis"
}
```

### 4. Get Analysis Results
**GET** `/results/{session_id}`

Retrieve comprehensive analysis results.

**Response:**
```json
{
  "success": true,
  "session_id": "uuid",
  "session_info": {
    "id": "uuid",
    "user_id": "string",
    "status": "completed",
    "created_at": "2024-01-01T00:00:00Z",
    "total_images": 3,
    "processed_images": 3
  },
  "healoncal_results": {
    "individual_analyses": [
      {
        "angle": "front",
        "healoncal_metrics": {
          "diagnostic_accuracy": 98.5,
          "biomarkers_analyzed": 150,
          "image_quality_score": 95.5,
          "analysis_confidence": 97.2
        },
        "skin_classification": {
          "skin_type": "Combination",
          "skin_tone": "Medium",
          "estimated_age": 28
        },
        "skin_health_metrics": {
          "wrinkles_score": 15.2,
          "fine_lines_score": 8.5,
          "dark_circles_score": 25.3,
          "pores_score": 45.8,
          "pigmentation_score": 12.1,
          "redness_score": 5.2,
          "acne_score": 2.1,
          "hydration_score": 78.5,
          "oiliness_score": 65.2,
          "skin_firmness_score": 82.1,
          "elasticity_score": 75.8,
          "overall_skin_health_score": 85.3
        },
        "recommendations": {
          "treatments": ["Retinol serum", "Vitamin C serum"],
          "routine": ["Morning: Cleanser, Vitamin C, Moisturizer, SPF"]
        },
        "analysis_metadata": {
          "processing_time_ms": 4500,
          "model_version": "Healoncal_v2.0",
          "analysis_timestamp": "2024-01-01T00:00:00Z"
        }
      }
    ],
    "combined_analysis": {
      "final_skin_type_classification": "Combination",
      "final_skin_tone_classification": "Medium",
      "estimated_skin_age": 28,
      "overall_diagnostic_accuracy": 98.5,
      "combined_wrinkles_score": 15.2,
      "combined_fine_lines_score": 8.5,
      "combined_dark_circles_score": 25.3,
      "combined_pores_score": 45.8,
      "combined_pigmentation_score": 12.1,
      "combined_redness_score": 5.2,
      "combined_acne_score": 2.1,
      "combined_hydration_score": 78.5,
      "combined_oiliness_score": 65.2,
      "combined_elasticity_score": 75.8,
      "combined_firmness_score": 82.1,
      "consolidated_recommendations": ["Retinol serum", "Vitamin C serum"],
      "comprehensive_routine": {
        "morning": ["Cleanser", "Vitamin C", "Moisturizer", "SPF"],
        "evening": ["Cleanser", "Retinol", "Moisturizer"]
      },
      "combined_analysis_data": {
        "total_biomarkers": 450,
        "average_confidence": 97.2,
        "quality_scores": [95.5, 94.2, 96.8],
        "analysis_timestamp": "2024-01-01T00:00:00Z",
        "processing_summary": {
          "images_processed": 3,
          "successful_analyses": 3,
          "average_processing_time": 4500
        }
      },
      "priority_concerns": [
        {
          "name": "Enlarged Pores",
          "score": 45.8,
          "severity": "moderate",
          "category": "structural"
        }
      ],
      "detected_diseases": [
        {
          "disease_name": "Enlarged Pores",
          "confidence_score": 0.85,
          "severity_level": "moderate",
          "requires_medical_attention": false
        }
      ]
    },
    "detected_diseases": [
      {
        "id": "uuid",
        "disease_name": "Enlarged Pores",
        "disease_category": "structural",
        "confidence_score": 0.85,
        "severity_level": "moderate",
        "requires_medical_attention": false,
        "recommended_specialist": "general_practitioner",
        "urgency_level": "routine"
      }
    ],
    "treatment_recommendations": [
      {
        "id": "uuid",
        "routine_type": "both",
        "products": [
          {
            "category": "serum",
            "product_name": "Retinol Serum",
            "brand": "Medical Grade",
            "key_ingredients": ["Retinol", "Hyaluronic Acid"],
            "target_concern": "anti-aging",
            "usage_instructions": "Apply at night",
            "priority": "high",
            "price_range": "mid-range",
            "medical_grade": true,
            "dermatologist_approved": true
          }
        ],
        "routine_steps": {
          "morning": ["Cleanser", "Vitamin C", "Moisturizer", "SPF"],
          "evening": ["Cleanser", "Retinol", "Moisturizer"]
        },
        "key_advice": [
          "Use SPF daily",
          "Apply retinol at night only",
          "Moisturize regularly"
        ],
        "expected_timeline": "4-6 weeks"
      }
    ],
    "analysis_summary": {
      "total_images": 3,
      "analysis_status": "completed",
      "processing_time": 13500
    }
  }
}
```

### 5. Get Latest Session
**GET** `/session/{user_id}/latest`

Get the latest analysis session for a user.

**Response:**
```json
{
  "success": true,
  "session": {
    "id": "uuid",
    "user_id": "string",
    "status": "completed",
    "total_images": 3,
    "processed_images": 3,
    "created_at": "2024-01-01T00:00:00Z",
    "completed_at": "2024-01-01T00:05:00Z"
  },
  "images_count": 3,
  "analysis_ready": true
}
```

### 6. Get Heatmap Visualizations
**GET** `/heatmaps/{session_id}`

Get ALL heat map visualizations for a session. Automatically fetches and returns all heatmaps for all images (front, left, right) organized by image angle with individual and combined heatmaps.

**Response:**
```json
{
  "success": true,
  "session_id": "uuid",
  "images": {
    "front": {
      "individual_heatmaps": [
        {
          "disease_name": "Early Skin Aging",
          "category": "structural",
          "confidence": 0.63,
          "severity": "moderate",
          "url": "https://storage.url/heatmap_Early_Skin_Aging_front_0.png",
          "index": 0,
          "colors": {
            "primary": "#FF6B6B",
            "secondary": "#FFB6C1",
            "alpha": 0.8
          },
          "type": "individual"
        }
      ],
      "combined_heatmap": {
        "disease_name": "Combined Analysis",
        "category": "combined",
        "confidence": 1.0,
        "severity": "combined",
        "url": "https://storage.url/combined_heatmap_front.png",
        "index": 0,
        "colors": {
          "primary": "#FF6B6B",
          "secondary": "#FFB6C1",
          "alpha": 0.8
        },
        "type": "combined"
      }
    },
    "left": {
      "individual_heatmaps": [...],
      "combined_heatmap": {...}
    },
    "right": {
      "individual_heatmaps": [...],
      "combined_heatmap": {...}
    }
  },
  "total_heatmaps": 63,
  "angles_available": ["front", "left", "right"]
}
```

**Frontend Implementation:**
```javascript
const getHeatmaps = async (sessionId) => {
  const response = await fetch(`/api/healoncal/heatmaps/${sessionId}`);
  const data = await response.json();
  
  if (data.success) {
    // Display heatmaps organized by angle
    Object.entries(data.images).forEach(([angle, imageData]) => {
      console.log(`${angle} view:`, imageData);
      
      // Display individual heatmaps
      imageData.individual_heatmaps.forEach(heatmap => {
        console.log(`Disease: ${heatmap.disease_name}, Confidence: ${heatmap.confidence}`);
      });
      
      // Display combined heatmap
      if (imageData.combined_heatmap) {
        console.log('Combined analysis:', imageData.combined_heatmap);
      }
    });
  }
  
  return data;
};
```

### 7. Get AI Recommendations
**POST** `/recommendations`

Get AI-powered product recommendations based on analysis results.

**Request Body:**
```json
{
  "session_id": "uuid",
  "user_preferences": {
    "budget_range": "mid-range",
    "skin_sensitivity": "normal",
    "preferred_brands": ["Medical Grade", "Dermatologist Approved"],
    "lifestyle": "busy_professional"
  }
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "uuid",
  "recommendations": {
    "routine_type": "both",
    "products": [
      {
        "category": "cleanser",
        "product_name": "Gentle Foaming Cleanser",
        "brand": "Medical Grade",
        "key_ingredients": ["Hyaluronic Acid", "Ceramides"],
        "target_concern": "hydration",
        "usage_instructions": "Use morning and evening",
        "priority": "high",
        "price_range": "mid-range",
        "why_recommended": "Based on your combination skin type and hydration needs",
        "medical_grade": true,
        "dermatologist_approved": true
      }
    ],
    "routine_steps": {
      "morning": [
        "Gentle Foaming Cleanser",
        "Vitamin C Serum",
        "Hyaluronic Acid Moisturizer",
        "Broad Spectrum SPF 30+"
      ],
      "evening": [
        "Gentle Foaming Cleanser",
        "Retinol Serum (2-3x/week)",
        "Hydrating Night Cream"
      ]
    },
    "medical_recommendations": {
      "dermatologist_consultation": "Schedule annual checkup",
      "prescription_treatments": ["Tretinoin for anti-aging"],
      "professional_treatments": ["Chemical peels for pore refinement"]
    },
    "beautician_recommendations": {
      "facials": ["HydraFacial", "LED Light Therapy"],
      "treatments": ["Microdermabrasion"],
      "frequency": "Monthly"
    },
    "home_care": {
      "daily_routine": ["Cleanse", "Treat", "Moisturize", "Protect"],
      "weekly_treatments": ["Exfoliating mask", "Hydrating sheet mask"],
      "lifestyle_changes": ["Increase water intake", "Use silk pillowcases"]
    },
    "key_advice": [
      "Always use SPF during the day",
      "Start retinol slowly (2-3x per week)",
      "Keep skin hydrated with hyaluronic acid"
    ],
    "ingredients_to_avoid": ["Alcohol", "Fragrance", "Sulfates"],
    "ingredients_to_seek": ["Hyaluronic Acid", "Retinol", "Vitamin C", "Ceramides"],
    "expected_timeline": "4-6 weeks for visible results",
    "follow_up_schedule": "Reassess in 6-8 weeks"
  },
  "analysis_summary": {
    "total_images_analyzed": 3,
    "overall_accuracy": 98.5,
    "analysis_date": "2024-01-01T00:00:00Z",
    "skin_type": "Combination",
    "skin_tone": "Medium"
  },
  "storage_status": "stored"
}
```

---

## Heatmap Features

### Pinpoint Heatmap Technology
The system generates precise heatmap visualizations that show:
- **Disease-Specific Colors**: Each disease has a unique color for easy identification
- **Pinpoint Accuracy**: Colored dots placed on actual infected areas, not rectangles
- **Multi-Angle Support**: Heatmaps generated for front, left, and right facial views
- **Parallel Processing**: Background generation for faster analysis completion

### Disease Color Coding
- **Early Skin Aging**: Pink dots
- **Skin Dehydration**: Sky Blue dots  
- **Rosacea**: Red dots
- **Dermatitis**: Orange dots
- **Solar Lentigines (Age Spots)**: Brown dots
- **Photoaging**: Purple dots
- **Acne**: Hot Pink dots
- **Melasma**: Dark Slate Gray dots
- **Eczema**: Tomato dots
- **Psoriasis**: Crimson dots

### Heatmap Types
1. **Individual Disease Heatmaps**: Separate visualization for each detected disease
2. **Combined Heatmaps**: Overlay of all diseases on a single image
3. **Angle-Specific Placement**: Anatomically appropriate locations for each facial view

---

## Database Schema

### Core Tables

#### 1. `healoncal_analysis_sessions`
Tracks each analysis session.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | TEXT | User identifier |
| `session_id` | TEXT | Unique session identifier |
| `status` | TEXT | pending/ready/processing/completed/failed |
| `total_images` | INTEGER | Total images in session |
| `processed_images` | INTEGER | Successfully processed images |
| `analysis_type` | TEXT | basic/comprehensive/medical |
| `created_at` | TIMESTAMPTZ | Session creation time |
| `completed_at` | TIMESTAMPTZ | Analysis completion time |
| `overall_quality_score` | FLOAT | Average quality score |

#### 2. `healoncal_captured_images`
Stores captured image information.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `session_id` | UUID | Foreign key to sessions |
| `user_id` | TEXT | User identifier |
| `angle` | TEXT | front/left/right |
| `image_url` | TEXT | Storage URL |
| `quality_score` | FLOAT | Image quality (0-100) |
| `face_detected` | BOOLEAN | Face detection result |
| `lighting_quality` | FLOAT | Lighting assessment |
| `blur_score` | FLOAT | Blur detection score |
| `resolution_score` | FLOAT | Resolution quality |
| `file_size` | INTEGER | Image file size |
| `image_width` | INTEGER | Image width |
| `image_height` | INTEGER | Image height |
| `captured_at` | TIMESTAMPTZ | Capture timestamp |

#### 3. `healoncal_analysis_results`
Individual image analysis results.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `session_id` | UUID | Foreign key to sessions |
| `image_id` | UUID | Foreign key to images |
| `user_id` | TEXT | User identifier |
| `angle` | TEXT | Image angle |
| `diagnostic_accuracy` | FLOAT | Analysis accuracy (0-100) |
| `biomarkers_analyzed` | INTEGER | Number of biomarkers |
| `image_quality_score` | FLOAT | Image quality (0-100) |
| `analysis_confidence` | FLOAT | Analysis confidence (0-100) |
| `skin_type_classification` | TEXT | Skin type result |
| `skin_tone_classification` | TEXT | Skin tone result |
| `skin_age_estimate` | INTEGER | Estimated age |
| `wrinkles_score` | FLOAT | Wrinkles severity (0-100) |
| `fine_lines_score` | FLOAT | Fine lines severity (0-100) |
| `dark_circles_score` | FLOAT | Dark circles severity (0-100) |
| `eye_bags_score` | FLOAT | Eye bags severity (0-100) |
| `pores_score` | FLOAT | Pores severity (0-100) |
| `pigmentation_score` | FLOAT | Pigmentation severity (0-100) |
| `acne_score` | FLOAT | Acne severity (0-100) |
| `hydration_score` | FLOAT | Hydration level (0-100) |
| `oiliness_score` | FLOAT | Oiliness level (0-100) |
| `elasticity_score` | FLOAT | Skin elasticity (0-100) |
| `firmness_score` | FLOAT | Skin firmness (0-100) |
| `treatment_recommendations` | JSONB | Treatment suggestions |
| `personalized_routine` | JSONB | Personalized routine |
| `processing_time_ms` | INTEGER | Processing time |
| `model_version` | TEXT | Analysis model version |

#### 4. `healoncal_combined_results`
Aggregated results from all images.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `session_id` | UUID | Foreign key to sessions |
| `user_id` | TEXT | User identifier |
| `final_skin_type_classification` | TEXT | Final skin type |
| `final_skin_tone_classification` | TEXT | Final skin tone |
| `estimated_skin_age` | INTEGER | Final age estimate |
| `overall_diagnostic_accuracy` | FLOAT | Overall accuracy |
| `combined_wrinkles_score` | FLOAT | Average wrinkles score |
| `combined_fine_lines_score` | FLOAT | Average fine lines score |
| `combined_dark_circles_score` | FLOAT | Average dark circles score |
| `combined_eye_bags_score` | FLOAT | Average eye bags score |
| `combined_pores_score` | FLOAT | Average pores score |
| `combined_pigmentation_score` | FLOAT | Average pigmentation score |
| `combined_acne_score` | FLOAT | Average acne score |
| `combined_hydration_score` | FLOAT | Average hydration score |
| `combined_oiliness_score` | FLOAT | Average oiliness score |
| `combined_elasticity_score` | FLOAT | Average elasticity score |
| `combined_firmness_score` | FLOAT | Average firmness score |
| `consolidated_recommendations` | JSONB | Combined recommendations |
| `comprehensive_routine` | JSONB | Complete routine |
| `combined_analysis_data` | JSONB | Analysis metadata |
| `priority_concerns` | JSONB | Top concerns |
| `detected_diseases` | JSONB | Detected conditions |
| `images_analyzed` | INTEGER | Number of images |
| `analysis_completeness` | FLOAT | Completeness percentage |
| `data_quality_score` | FLOAT | Data quality score |
| `analysis_quality` | TEXT | screening/diagnostic/clinical |

#### 5. `detected_skin_diseases`
Medical disease detection results.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `session_id` | UUID | Foreign key to sessions |
| `analysis_result_id` | UUID | Foreign key to results |
| `user_id` | TEXT | User identifier |
| `disease_name` | TEXT | Disease name |
| `disease_category` | TEXT | Disease category |
| `confidence_score` | FLOAT | Detection confidence (0-1) |
| `severity_level` | TEXT | very_mild/mild/moderate/severe/very_severe |
| `affected_area` | TEXT | Affected body area |
| `requires_medical_attention` | BOOLEAN | Medical attention needed |
| `recommended_specialist` | TEXT | Recommended specialist |
| `urgency_level` | TEXT | routine/moderate/urgent/emergency |
| `symptoms_noted` | JSONB | Observed symptoms |
| `risk_factors` | JSONB | Risk factors |
| `treatment_recommended` | JSONB | Treatment suggestions |
| `notes` | TEXT | Additional notes |
| `detected_at` | TIMESTAMPTZ | Detection timestamp |

#### 6. `disease_heatmaps`
Heatmap visualization data for detected skin diseases with confidence scores and severity levels.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `session_id` | UUID | Foreign key to sessions |
| `analysis_result_id` | UUID | Foreign key to results |
| `user_id` | TEXT | User identifier |
| `disease_name` | TEXT | Disease name |
| `category` | TEXT | Disease category |
| `confidence` | DECIMAL(3,2) | Confidence score (0.00-1.00) |
| `severity` | TEXT | very_mild/mild/moderate/severe/very_severe/combined |
| `heatmap_url` | TEXT | Heatmap image URL |
| `heatmap_index` | INTEGER | Heatmap index |
| `heatmap_type` | TEXT | individual/combined |
| `colors` | JSONB | Color scheme data |
| `total_diseases` | INTEGER | Total diseases detected |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Update timestamp |

#### 7. `treatment_recommendations`
AI-generated product recommendations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `session_id` | UUID | Foreign key to sessions |
| `user_id` | TEXT | User identifier |
| `recommendation_timestamp` | TIMESTAMPTZ | Generation time |
| `ai_model_version` | TEXT | AI model used |
| `ai_confidence` | FLOAT | AI confidence score |
| `personalization_level` | TEXT | basic/standard/advanced/premium |
| `routine_type` | TEXT | morning/evening/both/custom |
| `products` | JSONB | Recommended products |
| `routine_steps` | JSONB | Routine instructions |
| `key_advice` | JSONB | Key advice points |
| `ingredients_to_avoid` | JSONB | Ingredients to avoid |
| `expected_timeline` | TEXT | Expected results timeline |
| `primary_skin_concerns` | JSONB | Main concerns |
| `skin_type` | TEXT | User's skin type |
| `skin_tone` | TEXT | User's skin tone |
| `overall_accuracy` | FLOAT | Analysis accuracy |
| `user_preferences` | JSONB | User preferences |
| `budget_range` | TEXT | budget/mid-range/premium/luxury |
| `medical_flags` | JSONB | Medical considerations |
| `dermatologist_referral_needed` | BOOLEAN | Referral needed |
| `status` | TEXT | active/inactive/archived |

---

## Data Flow

### 1. Image Capture Flow
```
Frontend → POST /capture → Healoncal Service → Supabase Storage → Database
```

### 2. Analysis Flow
```
Frontend → POST /analyze → Healoncal Service → AI Analysis → Database Storage
```

### 3. Results Retrieval Flow
```
Frontend → GET /results/{session_id} → Healoncal Service → Database Query → Formatted Response
```

### 4. Heatmap Generation Flow
```
Frontend → POST /analyze → Healoncal Service → Heatmap Generation → Pinpoint Overlay → Storage → Database
```

### 5. Heatmap Retrieval Flow
```
Frontend → GET /heatmaps/{session_id} → Healoncal Service → Database Query → Organized Response
```

### 6. Recommendations Flow
```
Frontend → POST /recommendations → Gemini AI → Treatment Storage → Database
```

---

## Frontend Integration Examples

### Complete Analysis Workflow

```javascript
class HealoncalAnalysis {
  constructor(baseUrl = 'http://localhost:8080/api/healoncal') {
    this.baseUrl = baseUrl;
    this.sessionId = null;
  }

  // Step 1: Capture Images
  async captureImages(userId, images) {
    const results = [];
    
    for (const [angle, imageFile] of Object.entries(images)) {
      const base64 = await this.convertToBase64(imageFile);
      
      const response = await fetch(`${this.baseUrl}/capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          angle: angle,
          image_data: base64
        })
      });
      
      const result = await response.json();
      results.push(result);
      
      if (result.success) {
        this.sessionId = result.session_id;
      }
    }
    
    return results;
  }

  // Step 2: Start Analysis
  async startAnalysis(userId) {
    const response = await fetch(`${this.baseUrl}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    });
    
    return await response.json();
  }

  // Step 3: Get Results
  async getResults(sessionId) {
    const response = await fetch(`${this.baseUrl}/results/${sessionId}`);
    return await response.json();
  }

  // Step 4: Get Heatmaps
  async getHeatmaps(sessionId) {
    const response = await fetch(`${this.baseUrl}/heatmaps/${sessionId}`);
    return await response.json();
  }

  // Step 5: Get Recommendations
  async getRecommendations(sessionId, preferences = {}) {
    const response = await fetch(`${this.baseUrl}/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        user_preferences: preferences
      })
    });
    
    return await response.json();
  }

  // Utility: Convert File to Base64
  convertToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = error => reject(error);
    });
  }

  // Complete Workflow
  async runCompleteAnalysis(userId, images, preferences = {}) {
    try {
      // 1. Capture all images
      console.log('Capturing images...');
      const captureResults = await this.captureImages(userId, images);
      
      // 2. Start analysis
      console.log('Starting analysis...');
      const analysisResult = await this.startAnalysis(userId);
      
      if (!analysisResult.success) {
        throw new Error(analysisResult.message);
      }
      
      // 3. Get results
      console.log('Retrieving results...');
      const results = await this.getResults(this.sessionId);
      
      // 4. Get heatmaps
      console.log('Retrieving heatmaps...');
      const heatmaps = await this.getHeatmaps(this.sessionId);
      
      // 5. Get recommendations
      console.log('Generating recommendations...');
      const recommendations = await this.getRecommendations(this.sessionId, preferences);
      
      return {
        sessionId: this.sessionId,
        results: results,
        heatmaps: heatmaps,
        recommendations: recommendations
      };
      
    } catch (error) {
      console.error('Analysis failed:', error);
      throw error;
    }
  }
}

// Usage Example
const analysis = new HealoncalAnalysis();

// Prepare images (front, left, right)
const images = {
  front: frontImageFile,
  left: leftImageFile,
  right: rightImageFile
};

const preferences = {
  budget_range: 'mid-range',
  skin_sensitivity: 'normal',
  lifestyle: 'busy_professional'
};

// Run complete analysis
analysis.runCompleteAnalysis('user123', images, preferences)
  .then(result => {
    console.log('Analysis Results:', result.results);
    console.log('Heatmaps:', result.heatmaps);
    console.log('Recommendations:', result.recommendations);
  })
  .catch(error => {
    console.error('Analysis failed:', error);
  });
```

### React Component Example

```jsx
import React, { useState } from 'react';

const HealoncalAnalysis = () => {
  const [step, setStep] = useState('capture');
  const [images, setImages] = useState({});
  const [results, setResults] = useState(null);
  const [heatmaps, setHeatmaps] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleImageCapture = async (angle, file) => {
    setLoading(true);
    
    try {
      const base64 = await convertToBase64(file);
      
      const response = await fetch('/api/healoncal/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'user123',
          angle: angle,
          image_data: base64
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        setImages(prev => ({ ...prev, [angle]: result }));
        
        // Check if all images captured
        if (Object.keys({ ...images, [angle] }).length === 3) {
          setStep('analyze');
        }
      }
    } catch (error) {
      console.error('Capture failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalysis = async () => {
    setLoading(true);
    
    try {
      const response = await fetch('/api/healoncal/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'user123' })
      });
      
      const result = await response.json();
      
      if (result.success) {
        setStep('results');
        await getResults(result.session_id);
        await getHeatmaps(result.session_id);
      }
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const getResults = async (sessionId) => {
    try {
      const response = await fetch(`/api/healoncal/results/${sessionId}`);
      const result = await response.json();
      setResults(result);
    } catch (error) {
      console.error('Failed to get results:', error);
    }
  };

  const getHeatmaps = async (sessionId) => {
    try {
      const response = await fetch(`/api/healoncal/heatmaps/${sessionId}`);
      const result = await response.json();
      setHeatmaps(result);
    } catch (error) {
      console.error('Failed to get heatmaps:', error);
    }
  };

  const getRecommendations = async (sessionId) => {
    try {
      const response = await fetch('/api/healoncal/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          user_preferences: {
            budget_range: 'mid-range',
            skin_sensitivity: 'normal'
          }
        })
      });
      
      const result = await response.json();
      setRecommendations(result);
    } catch (error) {
      console.error('Failed to get recommendations:', error);
    }
  };

  return (
    <div className="healoncal-analysis">
      {step === 'capture' && (
        <div>
          <h2>Capture Images</h2>
          <div className="image-capture">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => handleImageCapture('front', e.target.files[0])}
            />
            <input
              type="file"
              accept="image/*"
              onChange={(e) => handleImageCapture('left', e.target.files[0])}
            />
            <input
              type="file"
              accept="image/*"
              onChange={(e) => handleImageCapture('right', e.target.files[0])}
            />
          </div>
        </div>
      )}
      
      {step === 'analyze' && (
        <div>
          <h2>Analyzing Images</h2>
          <button onClick={handleAnalysis} disabled={loading}>
            {loading ? 'Analyzing...' : 'Start Analysis'}
          </button>
        </div>
      )}
      
      {step === 'results' && results && (
        <div>
          <h2>Analysis Results</h2>
          <div className="results">
            <h3>Skin Classification</h3>
            <p>Type: {results.healoncal_results.combined_analysis.final_skin_type_classification}</p>
            <p>Tone: {results.healoncal_results.combined_analysis.final_skin_tone_classification}</p>
            <p>Age: {results.healoncal_results.combined_analysis.estimated_skin_age}</p>
            
            <h3>Skin Health Metrics</h3>
            <div className="metrics">
              <p>Wrinkles: {results.healoncal_results.combined_analysis.combined_wrinkles_score}</p>
              <p>Pores: {results.healoncal_results.combined_analysis.combined_pores_score}</p>
              <p>Hydration: {results.healoncal_results.combined_analysis.combined_hydration_score}</p>
            </div>
            
            <button onClick={() => getRecommendations(results.session_id)}>
              Get AI Recommendations
            </button>
          </div>
        </div>
      )}
      
      {heatmaps && (
        <div>
          <h2>Heatmap Visualizations</h2>
          <div className="heatmaps">
            {Object.entries(heatmaps.images).map(([angle, imageData]) => (
              <div key={angle} className="angle-section">
                <h3>{angle.toUpperCase()} View</h3>
                
                {/* Individual Disease Heatmaps */}
                <div className="individual-heatmaps">
                  <h4>Individual Disease Analysis</h4>
                  {imageData.individual_heatmaps.map((heatmap, index) => (
                    <div key={index} className="heatmap-item">
                      <h5>{heatmap.disease_name}</h5>
                      <p>Confidence: {(heatmap.confidence * 100).toFixed(1)}%</p>
                      <p>Severity: {heatmap.severity}</p>
                      <img src={heatmap.url} alt={heatmap.disease_name} />
                    </div>
                  ))}
                </div>
                
                {/* Combined Heatmap */}
                {imageData.combined_heatmap && (
                  <div className="combined-heatmap">
                    <h4>Combined Analysis</h4>
                    <img src={imageData.combined_heatmap.url} alt="Combined Heatmap" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {recommendations && (
        <div>
          <h2>AI Recommendations</h2>
          <div className="recommendations">
            <h3>Products</h3>
            {recommendations.recommendations.products.map((product, index) => (
              <div key={index} className="product">
                <h4>{product.product_name}</h4>
                <p>Brand: {product.brand}</p>
                <p>Category: {product.category}</p>
                <p>Why: {product.why_recommended}</p>
              </div>
            ))}
            
            <h3>Routine</h3>
            <div className="routine">
              <h4>Morning</h4>
              <ul>
                {recommendations.recommendations.routine_steps.morning.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ul>
              
              <h4>Evening</h4>
              <ul>
                {recommendations.recommendations.routine_steps.evening.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HealoncalAnalysis;
```

---

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "Invalid image data: Invalid base64 encoding"
}
```

#### 404 Not Found
```json
{
  "detail": "Analysis results not found"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Failed to generate recommendations: Gemini API call failed"
}
```

### Error Handling Best Practices

```javascript
const handleApiCall = async (url, options) => {
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    
    // Handle specific error types
    if (error.message.includes('Invalid image data')) {
      showError('Please select a valid image file');
    } else if (error.message.includes('Insufficient images')) {
      showError('Please capture all 3 images (front, left, right)');
    } else if (error.message.includes('Analysis results not found')) {
      showError('Analysis not found. Please try again.');
    } else {
      showError('An unexpected error occurred. Please try again.');
    }
    
    throw error;
  }
};
```

---

## Authentication & Security

### Current Implementation
- No authentication required for basic usage
- Session-based tracking using `user_id`
- UUID-based session management

### Recommended Security Enhancements
1. **API Key Authentication**: Add API key validation
2. **Rate Limiting**: Implement request rate limiting
3. **Input Validation**: Validate all input parameters
4. **CORS Configuration**: Configure proper CORS settings
5. **Data Encryption**: Encrypt sensitive data in transit

### Example with API Key
```javascript
const apiKey = 'your-api-key-here';

const makeAuthenticatedRequest = async (url, options = {}) => {
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
    ...options.headers
  };
  
  return fetch(url, {
    ...options,
    headers
  });
};
```

---

## Performance Considerations

### Image Optimization
- **Recommended Size**: 720x1280 pixels or higher
- **Format**: JPEG or PNG
- **File Size**: Under 5MB per image
- **Quality**: High quality for better analysis

### API Rate Limits
- **Capture**: 10 requests per minute per user
- **Analysis**: 5 requests per minute per user
- **Results**: 20 requests per minute per user
- **Recommendations**: 3 requests per minute per user

### Caching Strategy
```javascript
// Cache results for 1 hour
const cacheResults = (sessionId, results) => {
  localStorage.setItem(`healoncal_results_${sessionId}`, JSON.stringify({
    data: results,
    timestamp: Date.now()
  }));
};

const getCachedResults = (sessionId) => {
  const cached = localStorage.getItem(`healoncal_results_${sessionId}`);
  if (cached) {
    const { data, timestamp } = JSON.parse(cached);
    if (Date.now() - timestamp < 3600000) { // 1 hour
      return data;
    }
  }
  return null;
};
```

---

## Testing

### Unit Tests
```javascript
describe('HealoncalAnalysis', () => {
  test('should capture image successfully', async () => {
    const mockResponse = {
      success: true,
      session_id: 'test-session-id',
      quality_score: 95.5
    };
    
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });
    
    const result = await analysis.captureImage('user123', 'front', mockFile);
    expect(result.success).toBe(true);
  });
});
```

### Integration Tests
```javascript
describe('Healoncal API Integration', () => {
  test('complete analysis workflow', async () => {
    // Test complete workflow from capture to recommendations
    const result = await analysis.runCompleteAnalysis('user123', mockImages);
    expect(result.sessionId).toBeDefined();
    expect(result.results).toBeDefined();
    expect(result.recommendations).toBeDefined();
  });
});
```

---

## Support & Troubleshooting

### Common Issues

1. **Image Quality Issues**
   - Ensure good lighting
   - Avoid blurry images
   - Use high-resolution images

2. **Analysis Failures**
   - Check if all 3 images are captured
   - Verify image quality scores
   - Ensure face is detected in images

3. **Recommendation Issues**
   - Check if analysis is completed
   - Verify session ID is valid
   - Ensure Gemini API is configured

### Debug Information
Enable debug logging by adding query parameter: `?debug=true`

### Support Contact
- **Technical Issues**: Check server logs for detailed error messages
- **API Issues**: Verify endpoint URLs and request formats
- **Database Issues**: Check database connection and table structure

---

This guide provides comprehensive information for frontend developers to integrate with the Healoncal API and understand the database structure. For additional support or questions, refer to the server logs and error messages for detailed troubleshooting information.
