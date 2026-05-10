import { useQuery } from '@tanstack/react-query'
import { fundsApi, type FundSearchResult, type Holding, type SectorRow } from '../api/funds'

export const useFunds = () =>
  useQuery({ queryKey: ['funds'], queryFn: fundsApi.list })

export const useFund = (fundId: string | undefined) =>
  useQuery({
    queryKey: ['fund', fundId],
    queryFn: () => fundsApi.get(fundId!),
    enabled: !!fundId,
  })

export const useFundMetrics = (fundId: string | undefined) =>
  useQuery({
    queryKey: ['fund-metrics', fundId],
    queryFn: () => fundsApi.metrics(fundId!),
    enabled: !!fundId,
  })

export const useFundCredit = (fundId: string | undefined) =>
  useQuery({
    queryKey: ['fund-credit', fundId],
    queryFn: () => fundsApi.credit(fundId!),
    enabled: !!fundId,
  })

export const useFundMaturity = (fundId: string | undefined) =>
  useQuery({
    queryKey: ['fund-maturity', fundId],
    queryFn: () => fundsApi.maturity(fundId!),
    enabled: !!fundId,
  })

export const useFundHoldings = (fundId: string | undefined) =>
  useQuery({
    queryKey: ['fund-holdings', fundId],
    queryFn: () => fundsApi.holdings(fundId!),
    enabled: !!fundId,
  })

export const useFundSectors = (fundId: string | undefined) =>
  useQuery<SectorRow[]>({
    queryKey: ['fund-sectors', fundId],
    queryFn: () => fundsApi.sectors(fundId!).catch(() => []),
    enabled: !!fundId,
  })

export const useFundHoldingsHistory = (fundId: string | undefined) =>
  useQuery<Record<string, Holding[]>>({
    queryKey: ['fund-holdings-history', fundId],
    queryFn: () => fundsApi.holdingsHistory(fundId!).catch(() => ({} as Record<string, Holding[]>)),
    enabled: !!fundId,
  })

export const useFundSearch = (query: string, exclude: FundSearchResult[] = []) =>
  useQuery({
    queryKey: ['fund-search', query],
    queryFn: () => fundsApi.search(query).then(results =>
      results.filter(f => !exclude.find(e => e.id === f.id))
    ),
    enabled: query.length >= 2,
  })
