import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sourcesApi, type AMCSource } from '../api/sources'

export const useAmcSources = () =>
  useQuery({
    queryKey: ['amc-sources'],
    queryFn: sourcesApi.list,
    refetchInterval: (query) => {
      const data = query.state.data as AMCSource[] | undefined
      return data?.some(s => s.last_fetch_status === 'running') ? 4000 : false
    },
  })

export const useCreateAmcSource = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sourcesApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['amc-sources'] }),
    onError: () => alert('Failed to add source'),
  })
}

export const useDeleteAmcSource = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sourcesApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['amc-sources'] }),
  })
}

export const useFetchAmcSource = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sourcesApi.fetch,
    onSuccess: (_, id) => qc.setQueryData<AMCSource[]>(['amc-sources'], prev =>
      prev?.map(s => s.id === id ? { ...s, last_fetch_status: 'running' } : s)
    ),
  })
}

export const useFetchAllAmcSources = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sourcesApi.fetchAll,
    onSuccess: () => qc.setQueryData<AMCSource[]>(['amc-sources'], prev =>
      prev?.map(s => s.is_active ? { ...s, last_fetch_status: 'running' } : s)
    ),
  })
}
