import { apiClient } from './client'
import type {
  AuditLogEntry,
  BehavioralContext,
  BlockchainStatus,
  CopilotAskResponse,
  CopilotStatus,
  FraudPredictionOut,
  IngestionStatus,
  InvestigationView,
  ModelComparisonMetrics,
  PqcReadinessStatus,
  QuantumSafeExportBundle,
  Role,
  SecurityCenterOverview,
  ChainVerificationResult,
  SourceBreakdown,
  TokenPair,
  TransactionCreate,
  TransactionListResponse,
  TransactionOut,
  UserOut,
  WalletNeighborhood,
  WalletNode,
} from './types'

// --- Auth ---
export const authApi = {
  register: (data: { email: string; full_name: string; password: string }) =>
    apiClient.post<UserOut>('/auth/register', data).then((r) => r.data),

  login: (data: { email: string; password: string }) =>
    apiClient.post<TokenPair>('/auth/login', data).then((r) => r.data),

  me: () => apiClient.get<UserOut>('/auth/me').then((r) => r.data),
}

// --- Transactions ---
export const transactionsApi = {
  list: (params: { page?: number; page_size?: number; customer_id?: string; merchant_id?: string } = {}) =>
    apiClient.get<TransactionListResponse>('/transactions', { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<TransactionOut>(`/transactions/${id}`).then((r) => r.data),

  create: (data: TransactionCreate) => apiClient.post<TransactionOut>('/transactions', data).then((r) => r.data),
}

// --- Fraud ---
export const fraudApi = {
  status: () => apiClient.get<{ ready: boolean }>('/fraud/status').then((r) => r.data),

  score: (transactionId: string) =>
    apiClient.post<FraudPredictionOut>(`/fraud/transactions/${transactionId}/score`).then((r) => r.data),

  predictions: (transactionId: string) =>
    apiClient.get<FraudPredictionOut[]>(`/fraud/transactions/${transactionId}/predictions`).then((r) => r.data),

  modelMetrics: () => apiClient.get<ModelComparisonMetrics>('/fraud/models/metrics').then((r) => r.data),
}

// --- Behavioral ---
export const behavioralApi = {
  customerContext: (customerId: string, transactionId: string) =>
    apiClient
      .get<BehavioralContext>(`/behavioral/customers/${customerId}/context`, { params: { transaction_id: transactionId } })
      .then((r) => r.data),

  merchantContext: (merchantId: string, transactionId: string) =>
    apiClient
      .get<BehavioralContext>(`/behavioral/merchants/${merchantId}/context`, { params: { transaction_id: transactionId } })
      .then((r) => r.data),
}

// --- Blockchain ---
export const blockchainApi = {
  status: () => apiClient.get<BlockchainStatus>('/blockchain/status').then((r) => r.data),

  flaggedWallets: (limit = 20) =>
    apiClient.get<WalletNode[]>('/blockchain/wallets/flagged', { params: { limit } }).then((r) => r.data),

  getWallet: (address: string) => apiClient.get<WalletNode>(`/blockchain/wallets/${address}`).then((r) => r.data),

  neighborhood: (address: string, depth = 1) =>
    apiClient
      .get<WalletNeighborhood>(`/blockchain/wallets/${address}/neighborhood`, { params: { depth } })
      .then((r) => r.data),
}

// --- Security ---
export const securityApi = {
  verifyIntegrity: () => apiClient.get<ChainVerificationResult>('/security/integrity/verify').then((r) => r.data),

  pqcStatus: () => apiClient.get<PqcReadinessStatus>('/security/pqc/status').then((r) => r.data),

  auditLog: (params: { limit?: number; action?: string; resource_type?: string; resource_id?: string } = {}) =>
    apiClient.get<AuditLogEntry[]>('/security/audit-log', { params }).then((r) => r.data),

  centerOverview: () => apiClient.get<SecurityCenterOverview>('/security/center/overview').then((r) => r.data),

  exportAuditLog: (limit = 100) =>
    apiClient.post<QuantumSafeExportBundle>('/security/pqc/export-audit-log', null, { params: { limit } }).then((r) => r.data),

  importAuditExport: (bundle: QuantumSafeExportBundle) =>
    apiClient.post('/security/pqc/import-audit-export', bundle).then((r) => r.data),
}

// --- Data status ---
export const dataApi = {
  ingestionStatus: () => apiClient.get<IngestionStatus>('/data/ingestion-status').then((r) => r.data),

  sourceBreakdown: () => apiClient.get<SourceBreakdown>('/data/transactions/source-breakdown').then((r) => r.data),
}

// --- Investigation ---
export const investigationApi = {
  get: (transactionId: string) =>
    apiClient.get<InvestigationView>(`/investigation/transactions/${transactionId}`).then((r) => r.data),
}

// --- Copilot ---
export const copilotApi = {
  status: () => apiClient.get<CopilotStatus>('/copilot/status').then((r) => r.data),

  ask: (question: string, transactionId?: string) =>
    apiClient
      .post<CopilotAskResponse>('/copilot/ask', { question, transaction_id: transactionId ?? null })
      .then((r) => r.data),
}

export type { Role }
