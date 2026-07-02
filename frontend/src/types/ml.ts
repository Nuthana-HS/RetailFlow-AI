/**
 * RetailFlow AI — ML Model Types
 * Mirrors backend app/api/v1/ml/router.py schemas
 */

export interface ModelInfo {
  store_id: string;
  model_loaded: boolean;
  model_metadata: ModelMetadata | null;
}

export interface ModelMetadata {
  model_id: string;
  store_id: string;
  store_name: string;
  trained_at: string;
  n_samples: number;
  n_train: number;
  n_val: number;
  mae: number;       // seconds
  rmse: number;      // seconds
  r2: number;
  feature_importances: Record<string, number>;
}

export interface TrainResponse {
  model_id: string;
  store_id: string;
  trained_at: string;
  n_samples: number;
  n_train: number;
  n_val: number;
  mae_seconds: number;
  rmse_seconds: number;
  r2: number;
  feature_importances: Record<string, number>;
  message: string;
}

export interface PredictResponse {
  predicted_wait_seconds: number;
  predicted_wait_formatted: string;
  queue_length: number;
  from_cache: boolean;
  model_loaded: boolean;
  store_id: string;
}
