import { useQuery, useMutation } from '@tanstack/react-query'
import { rankingApi } from '../api/ranking'

export const useRankingProfiles = () =>
  useQuery({ queryKey: ['ranking-profiles'], queryFn: rankingApi.profiles })

export const useRankingScores = (profileId: string) =>
  useQuery({
    queryKey: ['ranking-scores', profileId],
    queryFn: () => rankingApi.scores(profileId),
    enabled: !!profileId,
  })

export const useCompareFunds = () =>
  useMutation({
    mutationFn: ({ fundIds, profileId }: { fundIds: string[]; profileId: string }) =>
      rankingApi.compare(fundIds, profileId),
  })
