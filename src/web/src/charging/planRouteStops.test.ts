import { describe, expect, it } from 'vitest'

import type { ChargingPlanResponse } from '../api/types'
import {
  googleMapsRouteUrlFromPlan,
  haversineKm,
  routeChargingStops,
  routeExportSpecForNextStop,
  routeExportSpecFromChargingPlan,
} from './planRouteStops'

function stubPlan(overrides: Partial<ChargingPlanResponse> = {}): ChargingPlanResponse {
  return {
    mode: 'route',
    vehicle: {
      soc_percent: 70,
      usable_capacity_kwh: 60,
      consumption_wh_per_km: 160,
    },
    range_km: 250,
    charging_reach_km: 220,
    origin: { lat: 37.63, lon: -0.99 },
    destination: { lat: 37.79, lon: -3.61 },
    corridor_km: 10,
    route_distance_km: 350,
    route_duration_minutes: 250,
    soc_at_destination_pct: -40,
    reachable_without_stop: false,
    route_geometry: null,
    stops: [],
    origin_stops: [],
    planned_stops: [
      {
        order: 1,
        station: {
          id: 'sc-1',
          source: 'test',
          country: 'ES',
          site_name: 'SC Baza',
          operator: 'Tesla',
          location: { lat: 37.49, lon: -2.77 },
          connectors: [],
          max_power_kw: 250,
          access: 'public',
          raw_ref: '1',
        },
        deviation_km: 0.5,
        route_distance_km: 180,
        extra_minutes: 2,
        wrong_side: false,
        distance_from_origin_km: 180,
        soc_arrival_pct: 12,
        classification: 'safe',
        leg_distance_km: 180,
        soc_departure_pct: 70,
        charge_minutes: 20,
      },
      {
        order: 2,
        station: {
          id: 'sc-2',
          source: 'test',
          country: 'ES',
          site_name: 'SC Úbeda area',
          operator: 'Tesla',
          location: { lat: 37.75, lon: -3.4 },
          connectors: [],
          max_power_kw: 250,
          access: 'public',
          raw_ref: '2',
        },
        deviation_km: 0.2,
        route_distance_km: 300,
        extra_minutes: 1,
        wrong_side: false,
        distance_from_origin_km: 300,
        soc_arrival_pct: 15,
        classification: 'safe',
        leg_distance_km: 120,
        soc_departure_pct: 65,
        charge_minutes: 15,
      },
    ],
    strategies: [],
    warnings: [],
    candidates_in_bbox: 2,
    ...overrides,
  }
}

describe('export Google Maps con paradas de carga', () => {
  it('mete cada planned_stop como waypoint en la URL', () => {
    const plan = stubPlan()
    const spec = routeExportSpecFromChargingPlan(plan)
    expect(spec?.waypoints).toHaveLength(2)
    expect(spec?.title).toContain('2 paradas de carga')

    const url = googleMapsRouteUrlFromPlan(plan)
    expect(url).toContain('waypoints=')
    expect(url).toContain('37.490000')
    expect(url).toContain('-2.770000')
    expect(url).toContain('37.750000')
    expect(url).toContain('-3.400000')
    expect(url).toContain('destination=37.790000')
  })

  it('sin planned_stops no inventa waypoints si llega sin parar', () => {
    const plan = stubPlan({
      planned_stops: [],
      reachable_without_stop: true,
      soc_at_destination_pct: 40,
    })
    const spec = routeExportSpecFromChargingPlan(plan)
    expect(spec?.waypoints).toBeUndefined()
    const url = googleMapsRouteUrlFromPlan(plan)
    expect(url).not.toContain('waypoints=')
  })

  it('routeExportSpecForNextStop devuelve solo la parada indicada', () => {
    const plan = stubPlan()
    const spec = routeExportSpecForNextStop(plan, 1)
    expect(spec?.destination.lat).toBe(37.75)
    expect(spec?.title).toContain('Parada 2')
  })

  it('haversineKm calcula distancia razonable', () => {
    const km = haversineKm({ lat: 37.63, lon: -0.99 }, { lat: 37.79, lon: -3.61 })
    expect(km).toBeGreaterThan(200)
    expect(km).toBeLessThan(280)
  })

  it('no oculta planned_stops tempranas por exclusión UI (~2 h)', () => {
    // Hellín ~128 km + Atlante ~302 km: la UI no debe tirar Hellín y dejar solo Atlante
    // con leg 174 km dibujado desde el coche.
    const plan = stubPlan({
      vehicle: {
        soc_percent: 61,
        usable_capacity_kwh: 50,
        consumption_wh_per_km: 122,
      },
      range_km: 208,
      charging_reach_km: 229,
      route_distance_km: 503,
      route_duration_minutes: 374,
      planned_stops: [
        {
          ...stubPlan().planned_stops![0],
          order: 1,
          route_distance_km: 128,
          distance_from_origin_km: 128,
          leg_distance_km: 128,
          soc_arrival_pct: 30,
          soc_departure_pct: 55,
          station: {
            ...stubPlan().planned_stops![0].station,
            id: 'hellin',
            site_name: 'Hellín, Spain',
          },
        },
        {
          ...stubPlan().planned_stops![1],
          order: 2,
          route_distance_km: 302,
          distance_from_origin_km: 302,
          leg_distance_km: 174,
          soc_arrival_pct: 9,
          soc_departure_pct: 78,
          station: {
            ...stubPlan().planned_stops![1].station,
            id: 'atlante-fermin',
            site_name: 'Atlante - Restaurante San Fermin',
          },
        },
      ],
    })
    const stops = routeChargingStops(plan)
    expect(stops).toHaveLength(2)
    expect(stops[0].station.site_name).toContain('Hellín')
    expect(stops[1].station.site_name).toContain('Atlante')
  })
})
