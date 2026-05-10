import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentsApi, type Doc } from '../api/documents'

export const useDocuments = () =>
  useQuery({
    queryKey: ['documents'],
    queryFn: documentsApi.list,
    refetchInterval: (query) => {
      const data = query.state.data as Doc[] | undefined
      return data?.some(d => d.status === 'pending' || d.status === 'processing') ? 3000 : false
    },
  })

export const useUploadDocument = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: documentsApi.upload,
    onSuccess: (res) => {
      if (res.duplicate) alert(`This file was already uploaded as "${res.filename}".`)
      qc.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (e: unknown) => alert(e instanceof Error ? e.message : 'Upload failed'),
  })
}

export const useReprocessDocument = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: documentsApi.reprocess,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })
}

export const useDeleteDocument = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: documentsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })
}
