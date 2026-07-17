"""ML subsystem — feature engineering, model definitions, and training scripts.

Structure:
  features/   — datasource abstraction + windowing + pipeline stages
  training/   — class weights, replay buffer, baseline training, evaluation
  models/     — BaseLocalModel ABC (model classes in services/federated_learning/)
  artifacts/  — generated outputs (gitignored except .gitkeep files)
"""
