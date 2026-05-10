import { api } from './client'

export interface Profile { id: string; name: string; is_system: boolean }

export interface MetricBreakdown {
  raw_value: number | null
  normalized_score: number
  weight: number
  weighted_contribution: number
  unit: string
  higher_is_better: boolean
}

export interface CompareRow {
  fund_id: string
  fund_name: string
  total_score: number
  breakdown: Record<string, MetricBreakdown>
}

export interface RankedFund {
  rank: number
  fund_id: string
  fund_name: string
  total_score: number
  score_breakdown: Record<string, Omit<MetricBreakdown, 'higher_is_better'>>
}

export const rankingApi = {
  profiles: (): Promise<Profile[]> =>
    api.get('/api/ranking/profiles').then(r => r.data),

  scores: (profileId: string): Promise<RankedFund[]> =>
    api.get(`/api/ranking/scores?profile_id=${profileId}`).then(r => r.data),

  compare: (fundIds: string[], profileId: string): Promise<CompareRow[]> =>
    api.get(`/api/ranking/compare?fund_ids=${fundIds.join(',')}&profile_id=${profileId}`).then(r => r.data),
}
