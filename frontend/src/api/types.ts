// Types here are grounded in the actual QuantumFinGuard backend responses,
// verified through live testing during backend development (Phases 3-11),
// not guessed from convention. Where the backend's status/reason pattern
// means a field may be absent, that's reflected as optional/union types
// rather than assumed-present.

export type Role = 'analyst' | 'senior_analyst' | 'compliance_officer' | 'admin'

export interface UserOut {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

// --- Transactions ---
export interface TransactionOut {
  id: string
  external_ref: string | null
  customer_id: string
  merchant_id: string
  merchant_category: string | null
  amount: number
  currency: string
  timestamp: string
  device_type: string | null
  card_type: string | null
  country: string | null
  record_hash: string | null
  created_at: string
}

export interface TransactionListResponse {
  items: TransactionOut[]
  total: number
  page: number
  page_size: number
}

export interface TransactionCreate {
  external_ref?: string
  customer_id: string
  merchant_id: string
  merchant_category?: string
  amount: number
  currency?: string
  timestamp: string
  device_type?: string
  card_type?: string
  country?: string
  source_dataset?: string
}

// --- Fraud / SHAP ---
export interface ShapFeatureContribution {
  feature: string
  value: string
  contribution: number
  direction: 'increases_risk' | 'decreases_risk'
}

export interface FraudPredictionOut {
  transaction_id: string
  model_version: string
  risk_score: number
  fraud_probability: number
  predicted_class: 'legitimate' | 'suspicious'
  risk_category: 'low' | 'medium' | 'high'
  shap_explanation: ShapFeatureContribution[] | null
  scored_at: string
}

export interface ModelMetricsEntry {
  precision: number
  recall: number
  f1: number
  roc_auc: number
  pr_auc: number
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number }
  positive_rate_in_test: number
  test_size: number
}

export interface ModelComparisonMetrics {
  model_version: string
  selected_model: string
  is_synthetic_data: boolean
  selection_metric: string
  selection_set: string
  test_metrics: ModelMetricsEntry
  validation_comparison: Record<string, { val_metrics: ModelMetricsEntry }>
  skipped_models: Record<string, string>
  training_rows: number
  fraud_rate_full_dataset: number
  trained_at: string
}

// --- Behavioral ---
export interface BehavioralSignal {
  name: string
  observed_value: number
  baseline_mean: number
  baseline_stddev: number
  deviation_sigma: number
  is_unusual: boolean
}

export interface BehavioralContext {
  entity_type: 'customer' | 'merchant'
  entity_id: string
  history_window_days: number
  history_sample_size: number
  signals: BehavioralSignal[]
}

// --- Blockchain ---
export interface WalletNode {
  address: string
  first_seen: string | null
  last_seen: string | null
  total_transactions: number
  total_value_eth: number
  is_flagged: boolean
}

export interface TransactionEdge {
  from_address: string
  to_address: string
  value_eth: number
  timestamp: string
  tx_hash: string
}

export interface WalletNeighborhood {
  center: WalletNode
  nodes: WalletNode[]
  edges: TransactionEdge[]
  depth: number
}

export interface BlockchainStatus {
  ready: boolean
  backend: string
}

// --- Security ---
export interface ChainVerificationResult {
  valid: boolean
  total_records: number
  first_broken_record_id: string | null
  checked_at_count: number
}

export interface PqcReadinessStatus {
  kem_algorithm: string
  kem_standard: string
  signature_algorithm: string
  signature_standard: string
  kem_self_test_passed: boolean
  signature_self_test_passed: boolean
  checked_at: string
  scope_note: string
}

export interface AuditLogEntry {
  id: string
  actor_user_id: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  metadata_json: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

export interface SecurityCenterOverview {
  generated_at: string
  application_security: {
    authentication: string
    password_hashing: string
    authorization_model: string
    roles: string[]
    rate_limit_per_minute: number
    security_headers_enforced: string[]
    structured_logging: boolean
  }
  blockchain_integrity: {
    mechanism: string
    scope_note: string
    total_transactions: number
    sealed_transactions: number
    last_verification: {
      checked_at: string | null
      result: ChainVerificationResult | null
      status: 'available' | 'not_yet_run'
    }
    note_if_never_run: string | null
  }
  quantum_safe_security: {
    kem_algorithm: string
    kem_standard: string
    signature_algorithm: string
    signature_standard: string
    kem_self_test_passed: boolean
    signature_self_test_passed: boolean
    scope_note: string
  }
  audit_trail: {
    total_events: number
    events_by_action: Record<string, number>
  }
}

export interface QuantumSafeExportBundle {
  algorithm: { kem: string; signature: string; symmetric: string }
  kem_ciphertext: string
  nonce: string
  encrypted_payload: string
  signature: string
  signer_public_key: string
  created_at: string
}

// --- Data status ---
export interface IngestionStatus {
  ieee_cis: { real_data_available: boolean }
  ibm_credit: { real_data_available: boolean }
  ethereum: { real_data_available: boolean }
  synthetic_fallback_enabled: boolean
}

export interface SourceBreakdownEntry {
  count: number
  is_synthetic: boolean
}
export type SourceBreakdown = Record<string, SourceBreakdownEntry>

// --- Investigation view (assembled evidence) ---

export interface RiskAssessmentEvidence {
  status: 'available' | 'not_available'
  reason?: string
  source?: 'cached_prediction' | 'computed_now'
  risk_score?: number
  fraud_probability?: number
  predicted_class?: string
  risk_category?: string
  model_version?: string
  scored_at?: string
}

export interface ExplanationEvidence {
  status: 'available' | 'not_available'
  reason?: string
  top_features?: ShapFeatureContribution[]
}

export interface BehavioralEvidence {
  status: 'available' | 'not_available'
  reason?: string
  context?: BehavioralContext
}

export interface BlockchainEvidence {
  status: 'not_applicable' | 'available'
  reason?: string
}

export interface SecurityEvidence {
  status: 'available' | 'not_available'
  sealed: boolean
  chain_sequence: number | null
  record_hash: string | null
  previous_record_hash: string | null
  hash_recomputation_matches: boolean
  note: string
}

export interface InvestigationView {
  transaction: TransactionOut
  risk_assessment: RiskAssessmentEvidence
  explanation: ExplanationEvidence
  behavioral_context: BehavioralEvidence
  blockchain_context: BlockchainEvidence
  security_context: SecurityEvidence
  investigation_summary: string
}

// --- Copilot ---
export interface CopilotSource {
  id: string
  type: 'evidence' | 'knowledge_base'
  detail: string
}

export interface CopilotAskResponse {
  mode: 'llm_generated' | 'evidence_digest'
  answer: string
  sources: CopilotSource[]
  llm_provider: string
  warning: string | null
}

export interface CopilotStatus {
  llm_provider: string
  llm_configured: boolean
  retrieval_ready: boolean
  knowledge_base_chunks: number
  note: string | null
}

// --- Generic API error shape ---
export interface ApiErrorBody {
  detail?: string
  errors?: unknown
  path?: string
}
