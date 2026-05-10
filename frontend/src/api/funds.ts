import { api } from './client'

export interface Fund {
  id: string
  name: string
  amc_name: string
  category: string | null
  aum_crores: number | null
  expense_ratio: number | null
  nav: number | null
}

export interface FundInfo {
  id: string
  name: string
  amc_name: string
  isin: string | null
  nav: number | null
  nav_date: string | null
  aum_crores: number | null
  expense_ratio: number | null
  fund_manager: string | null
  inception_date: string | null
  benchmark_index: string | null
  exit_load: string | null
}

export interface FundSearchResult {
  id: string
  scheme_code?: number
  name: string
  amc_name: string
  has_local_data?: boolean
}

export interface Metric {
  key: string
  display_name: string
  value: number | null
  unit: string
  extraction_date: string
}

export interface CreditRow { rating: string; percentage: number }
export interface MaturityRow { bucket: string; percentage: number }

export interface Holding {
  instrument_name: string | null
  issuer: string | null
  rating: string | null
  percentage: number | null
  type: string | null
}

export interface SectorRow { sector: string; percentage: number }

export const fundsApi = {
  list: (): Promise<Fund[]> =>
    api.get('/api/funds?limit=200').then(r => r.data),

  get: (fundId: string): Promise<FundInfo> =>
    api.get(`/api/funds/${fundId}`).then(r => r.data),

  search: (q: string): Promise<FundSearchResult[]> =>
    api.get(`/api/funds/search?q=${encodeURIComponent(q)}`).then(r => r.data),

  metrics: (fundId: string): Promise<Metric[]> =>
    api.get(`/api/funds/${fundId}/metrics`).then(r => r.data),

  credit: (fundId: string): Promise<CreditRow[]> =>
    api.get(`/api/funds/${fundId}/credit`).then(r => r.data),

  maturity: (fundId: string): Promise<MaturityRow[]> =>
    api.get(`/api/funds/${fundId}/maturity`).then(r => r.data),

  holdings: (fundId: string): Promise<Holding[]> =>
    api.get(`/api/funds/${fundId}/holdings`).then(r => r.data),

  sectors: (fundId: string): Promise<SectorRow[]> =>
    api.get(`/api/funds/${fundId}/sectors`).then(r => r.data),

  holdingsHistory: (fundId: string): Promise<Record<string, Holding[]>> =>
    api.get(`/api/funds/${fundId}/holdings/history`).then(r => r.data),
}
