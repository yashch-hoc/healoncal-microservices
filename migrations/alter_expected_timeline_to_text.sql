-- Fix: Data too long for column 'expected_timeline' (was VARCHAR(100))
-- Run once against stage/prod MySQL before relying on long timelines.

ALTER TABLE treatment_recommendations
  MODIFY COLUMN expected_timeline TEXT DEFAULT ('4-6 weeks');
