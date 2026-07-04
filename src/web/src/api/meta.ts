import { fetchApi } from './client'

export type OperatorCount = {
  operator: string
  count: number
}

export type MetaOperatorsResponse = {
  operators: OperatorCount[]
  country: string | null
  limit: number
}

export async function fetchTopOperators(
  country = 'ES',
  limit = 12,
): Promise<MetaOperatorsResponse> {
  const params = new URLSearchParams({
    country,
    limit: String(limit),
  })
  return fetchApi<MetaOperatorsResponse>(`/api/v1/meta/operators?${params.toString()}`)
}
