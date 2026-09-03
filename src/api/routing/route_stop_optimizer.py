"""
Optimizador global de paradas (#6087): minimiza tiempo total (conducción + recarga DC).

Algoritmo: programación dinámica sobre candidatos del corredor (solo hacia delante),
con poda por bins espaciales para mantener n acotado.
"""

from __future__ import annotations

from dataclasses import dataclass

from api.routing.charging_plan import (
    CHARGING_MIN_ARRIVAL_SOC_PCT,
    FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT,
    MAX_DRIVING_LEG_MINUTES,
    MAX_PLANNED_ROUTE_STOPS,
    MIN_FORWARD_PROGRESS_KM,
    MIN_ORIGIN_SKIP_ABSOLUTE_KM,
    PREFERRED_ON_ROUTE_TIME_BONUS_MIN,
    TARGET_DRIVING_LEG_MINUTES,
    PlannedRouteStop,
    VehicleEnergyProfile,
    _is_final_driving_hop,
    _is_meaningful_charging_stop,
    _is_worth_charging_stop,
    _optimal_departure_soc_for_stop,
    _profile_at_soc,
    _stop_from_corridor_match,
    clamp_display_soc_pct,
    driving_minutes_for_distance,
    estimate_charge_minutes,
    estimate_charging_reach_km,
    estimate_range_km,
    first_stop_comfort_matches,
    leg_distance_for_driving_minutes,
    min_leg_progress_fraction,
    origin_exclusion_radius_km,
    relaxed_origin_exclusion_km,
    resolve_avg_speed_kmh,
    soc_at_distance_km,
)
from api.routing.charging_preferences import ChargingPreferences, preferred_on_route_time_bonus_min
from api.routing.corridor import CorridorMatch

_CANDIDATE_BIN_KM = 35.0
_MAX_CANDIDATES_PER_BIN = 6
_MAX_CANDIDATES = 120
_INF = 1e18


@dataclass(frozen=True)
class _RouteCandidate:
    match: CorridorMatch
    route_km: float
    deviation_km: float
    extra_minutes: float
    wrong_side: bool


@dataclass
class _NodeState:
    time_min: float
    dep_soc: float
    prev: int


def _route_km(match: CorridorMatch) -> float:
    return match.route_position_m / 1000.0


def _reduce_corridor_candidates(
    matches: list[CorridorMatch],
    *,
    origin_route_km: float,
    destination_km: float,
    origin_exclusion_km: float,
) -> list[_RouteCandidate]:
    """Mantiene los mejores cargadores por bin espacial (~35 km)."""
    bins: dict[int, list[CorridorMatch]] = {}
    for match in matches:
        km = _route_km(match)
        if km <= origin_route_km + MIN_FORWARD_PROGRESS_KM:
            continue
        if km >= destination_km - 5.0:
            continue
        if origin_exclusion_km > 0 and (km - origin_route_km) < origin_exclusion_km - 1e-6:
            continue
        bin_id = int(km // _CANDIDATE_BIN_KM)
        bins.setdefault(bin_id, []).append(match)

    selected: list[_RouteCandidate] = []
    seen_ids: set[str] = set()
    for bin_matches in bins.values():
        ranked = sorted(
            bin_matches,
            key=lambda m: (m.deviation_m, -m.station.max_power_kw),
        )
        for match in ranked[:_MAX_CANDIDATES_PER_BIN]:
            if match.station.id in seen_ids:
                continue
            seen_ids.add(match.station.id)
            selected.append(
                _RouteCandidate(
                    match=match,
                    route_km=_route_km(match),
                    deviation_km=match.deviation_m / 1000.0,
                    extra_minutes=match.extra_minutes,
                    wrong_side=match.wrong_side,
                )
            )
            if len(selected) >= _MAX_CANDIDATES:
                break
        if len(selected) >= _MAX_CANDIDATES:
            break

    selected.sort(key=lambda c: c.route_km)
    return selected


def _min_leg_km_for_stop(
    *,
    target_leg_km: float,
    max_leg_km: float,
    profile: VehicleEnergyProfile,
    from_soc: float,
    route_preference: str | None = None,
) -> float:
    progress = min_leg_progress_fraction(route_preference)
    min_leg_km = target_leg_km * progress
    if from_soc >= 70.0:
        min_leg_km = max(min_leg_km, target_leg_km * max(0.8, progress - 0.05))
    min_leg_km = min(min_leg_km, max_leg_km)
    charging_reach_km = estimate_charging_reach_km(_profile_at_soc(profile, from_soc))
    return min(min_leg_km, charging_reach_km * 0.95)


def _worth_stop_transition(
    *,
    profile: VehicleEnergyProfile,
    from_soc: float,
    arrival_soc: float,
    departure_soc: float,
    charge_min: float,
    leg_km: float,
    cand_route_km: float,
    trip_start_route_km: float,
    origin_exclusion_km: float,
    is_first_hop: bool,
    target_leg_km: float,
    max_leg_km: float,
    avg_speed_kmh: float,
    route_preference: str | None = None,
) -> bool:
    min_leg_km = _min_leg_km_for_stop(
        target_leg_km=target_leg_km,
        max_leg_km=max_leg_km,
        profile=profile,
        from_soc=from_soc,
        route_preference=route_preference,
    )
    return _is_worth_charging_stop(
        arrival_soc_pct=arrival_soc,
        departure_soc_pct=departure_soc,
        charge_minutes=charge_min,
        leg_distance_km=leg_km,
        min_leg_km=min_leg_km,
        stop_route_km=cand_route_km,
        trip_start_route_km=trip_start_route_km,
        origin_exclusion_km=origin_exclusion_km if is_first_hop else 0.0,
        trip_start_soc_pct=profile.soc_percent,
        avg_speed_kmh=avg_speed_kmh,
    )


def _drive_and_arrival(
    profile: VehicleEnergyProfile,
    *,
    from_km: float,
    from_soc: float,
    to_km: float,
    avg_speed_kmh: float,
    extra_minutes: float,
) -> tuple[float, float, float] | None:
    leg_km = to_km - from_km
    if leg_km <= 0:
        return None
    segment = _profile_at_soc(profile, from_soc)
    charging_reach = estimate_charging_reach_km(segment)
    if leg_km > charging_reach + 1e-6:
        return None
    max_leg_km = leg_distance_for_driving_minutes(avg_speed_kmh, MAX_DRIVING_LEG_MINUTES)
    if leg_km > max_leg_km + 1e-6:
        return None
    arrival = soc_at_distance_km(segment, leg_km)
    if arrival < CHARGING_MIN_ARRIVAL_SOC_PCT - 1e-6:
        return None
    drive_min = driving_minutes_for_distance(leg_km, avg_speed_kmh) + extra_minutes
    return leg_km, arrival, drive_min


def _charge_at_stop(
    *,
    profile: VehicleEnergyProfile,
    arrival_soc: float,
    candidate_km: float,
    destination_km: float,
    avg_speed_kmh: float,
    destination_target_soc: float,
    station_max_kw: float,
) -> tuple[float, float]:
    remaining = max(0.0, destination_km - candidate_km)
    is_final = _is_final_driving_hop(remaining, profile, avg_speed_kmh)
    departure = _optimal_departure_soc_for_stop(
        arrival_soc_pct=arrival_soc,
        remaining_km=remaining,
        profile=profile,
        destination_target_soc_pct=destination_target_soc,
        is_final_hop=is_final,
        avg_speed_kmh=avg_speed_kmh,
    )
    charge_min = estimate_charge_minutes(
        arrival_soc,
        departure,
        usable_capacity_kwh=profile.usable_capacity_kwh,
        max_power_kw=station_max_kw,
        vehicle_preset_id=profile.vehicle_preset_id,
        vehicle_max_charge_kw=profile.max_charge_power_kw,
    )
    return departure, charge_min


def _finish_from(
    profile: VehicleEnergyProfile,
    *,
    from_km: float,
    from_soc: float,
    destination_km: float,
    avg_speed_kmh: float,
    min_destination_soc: float,
) -> tuple[float, float] | None:
    remaining = destination_km - from_km
    if remaining <= 0:
        return 0.0, from_soc
    segment = _profile_at_soc(profile, from_soc)
    projected = soc_at_distance_km(segment, remaining)
    if projected + 1e-6 < min_destination_soc:
        return None
    drive_min = driving_minutes_for_distance(remaining, avg_speed_kmh)
    return drive_min, projected


def optimize_planned_route_stops(
    matches: list[CorridorMatch],
    *,
    origin_position_km: float,
    destination_distance_km: float,
    profile: VehicleEnergyProfile,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    destination_target_soc_pct: float | None = None,
    max_stops: int = MAX_PLANNED_ROUTE_STOPS,
    preferences: ChargingPreferences | None = None,
    route_distance_km: float | None = None,
    route_duration_minutes: float | None = None,
    trip_start_route_km: float | None = None,
    route_preference: str | None = None,
) -> tuple[list[PlannedRouteStop], list[str], float | None] | None:
    """
    Devuelve el plan de mínimo tiempo total o None si no hay solución factible.
    """
    resolved_destination_soc = (
        destination_target_soc_pct
        if destination_target_soc_pct is not None
        else profile.min_destination_soc_pct
    )
    trip_start = origin_position_km if trip_start_route_km is None else trip_start_route_km
    avg_speed_kmh = resolve_avg_speed_kmh(route_distance_km, route_duration_minutes)
    target_leg_km = leg_distance_for_driving_minutes(avg_speed_kmh, TARGET_DRIVING_LEG_MINUTES)
    max_leg_km = leg_distance_for_driving_minutes(avg_speed_kmh, MAX_DRIVING_LEG_MINUTES)
    origin_exclusion_km = origin_exclusion_radius_km(
        target_leg_km,
        profile.soc_percent,
        charging_reach_km=estimate_charging_reach_km(profile),
        max_leg_km=max_leg_km,
    )

    distance_to_dest = max(0.0, destination_distance_km - origin_position_km)
    if distance_to_dest <= estimate_range_km(profile) + 1e-6:
        projected = soc_at_distance_km(profile, distance_to_dest)
        return [], [], round(clamp_display_soc_pct(projected), 1)

    early_first_stop_warning = False
    charging_reach_km = estimate_charging_reach_km(profile)

    def _reachable_first_arrivals(cands: list[_RouteCandidate]) -> list[float]:
        reach_end = origin_position_km + charging_reach_km
        arrivals: list[float] = []
        for cand in cands:
            if not (origin_position_km < cand.route_km <= reach_end + 1e-6):
                continue
            leg = _drive_and_arrival(
                profile,
                from_km=origin_position_km,
                from_soc=profile.soc_percent,
                to_km=cand.route_km,
                avg_speed_kmh=avg_speed_kmh,
                extra_minutes=cand.extra_minutes,
            )
            if leg is not None:
                arrivals.append(leg[1])
        return arrivals

    def _needs_earlier_first_stop(cands: list[_RouteCandidate]) -> bool:
        arrivals = _reachable_first_arrivals(cands)
        if not arrivals:
            return True
        return min(arrivals) < FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT - 1e-6

    candidates = _reduce_corridor_candidates(
        matches,
        origin_route_km=origin_position_km,
        destination_km=destination_distance_km,
        origin_exclusion_km=origin_exclusion_km,
    )
    if _needs_earlier_first_stop(candidates):
        relaxed = relaxed_origin_exclusion_km(origin_exclusion_km)
        if relaxed < origin_exclusion_km - 1e-6:
            relaxed_cands = _reduce_corridor_candidates(
                matches,
                origin_route_km=origin_position_km,
                destination_km=destination_distance_km,
                origin_exclusion_km=relaxed,
            )
            comfort_matches = first_stop_comfort_matches(
                [c.match for c in relaxed_cands],
                current_route_km=origin_position_km,
                profile=profile,
            )
            comfort_ids = {m.station.id for m in comfort_matches}
            comfort_cands = [c for c in relaxed_cands if c.match.station.id in comfort_ids]
            # Si hay 1.ª parada cómoda (≥20 %), ampliar ventana; el semillado 1.ª hop
            # solo usa comfort_first_ids (Hellín, no Albacete al 6 %).
            if comfort_cands:
                candidates = relaxed_cands
                origin_exclusion_km = relaxed
                early_first_stop_warning = True
            else:
                old_arrivals = _reachable_first_arrivals(candidates)
                new_arrivals = _reachable_first_arrivals(relaxed_cands)
                if new_arrivals and (
                    not old_arrivals or min(new_arrivals) > min(old_arrivals) + 1e-6
                ):
                    candidates = relaxed_cands
                    origin_exclusion_km = relaxed
                    early_first_stop_warning = True
    if not candidates:
        return None

    n = len(candidates)
    best: list[_NodeState | None] = [None] * n
    comfort_first_ids = {
        m.station.id
        for m in first_stop_comfort_matches(
            [c.match for c in candidates],
            current_route_km=origin_position_km,
            profile=profile,
        )
    }

    def _transition_cost(
        *,
        drive_min: float,
        charge_min: float,
        cand: _RouteCandidate,
    ) -> float:
        bonus = preferred_on_route_time_bonus_min(
            cand.match.station.operator,
            preferences,
            cand.deviation_km,
            bonus_min=PREFERRED_ON_ROUTE_TIME_BONUS_MIN,
        )
        return drive_min + charge_min - bonus

    # Salida → primera parada
    for j, cand in enumerate(candidates):
        if comfort_first_ids and cand.match.station.id not in comfort_first_ids:
            # Hay alternativas cómodas: no sembrar 1.ª parada crítica (p. ej. Albacete al 6 %).
            continue
        leg = _drive_and_arrival(
            profile,
            from_km=origin_position_km,
            from_soc=profile.soc_percent,
            to_km=cand.route_km,
            avg_speed_kmh=avg_speed_kmh,
            extra_minutes=cand.extra_minutes,
        )
        if leg is None:
            continue
        leg_km, arrival, drive_min = leg
        dep_soc, charge_min = _charge_at_stop(
            profile=profile,
            arrival_soc=arrival,
            candidate_km=cand.route_km,
            destination_km=destination_distance_km,
            avg_speed_kmh=avg_speed_kmh,
            destination_target_soc=resolved_destination_soc,
            station_max_kw=cand.match.station.max_power_kw,
        )
        if not _worth_stop_transition(
            profile=profile,
            from_soc=profile.soc_percent,
            arrival_soc=arrival,
            departure_soc=dep_soc,
            charge_min=charge_min,
            leg_km=leg_km,
            cand_route_km=cand.route_km,
            trip_start_route_km=trip_start,
            origin_exclusion_km=origin_exclusion_km,
            is_first_hop=True,
            target_leg_km=target_leg_km,
            max_leg_km=max_leg_km,
            avg_speed_kmh=avg_speed_kmh,
            route_preference=route_preference,
        ):
            # Con exclusión relajada (#6151) aceptar 1.ª parada alcanzable aunque sea < ~2 h.
            if not (
                early_first_stop_warning
                and leg_km + 1e-6 >= max(MIN_ORIGIN_SKIP_ABSOLUTE_KM, origin_exclusion_km)
            ):
                continue
        best[j] = _NodeState(
            time_min=_transition_cost(drive_min=drive_min, charge_min=charge_min, cand=cand),
            dep_soc=dep_soc,
            prev=-1,
        )

    # Parada → parada (solo hacia delante)
    for _hop in range(max_stops - 1):
        updated = False
        for i in range(n):
            state_i = best[i]
            if state_i is None:
                continue
            for j in range(i + 1, n):
                cand_j = candidates[j]
                leg = _drive_and_arrival(
                    profile,
                    from_km=candidates[i].route_km,
                    from_soc=state_i.dep_soc,
                    to_km=cand_j.route_km,
                    avg_speed_kmh=avg_speed_kmh,
                    extra_minutes=cand_j.extra_minutes,
                )
                if leg is None:
                    continue
                leg_km, arrival, drive_min = leg
                dep_soc, charge_min = _charge_at_stop(
                    profile=profile,
                    arrival_soc=arrival,
                    candidate_km=cand_j.route_km,
                    destination_km=destination_distance_km,
                    avg_speed_kmh=avg_speed_kmh,
                    destination_target_soc=resolved_destination_soc,
                    station_max_kw=cand_j.match.station.max_power_kw,
                )
                if not _worth_stop_transition(
                    profile=profile,
                    from_soc=state_i.dep_soc,
                    arrival_soc=arrival,
                    departure_soc=dep_soc,
                    charge_min=charge_min,
                    leg_km=leg_km,
                    cand_route_km=cand_j.route_km,
                    trip_start_route_km=trip_start,
                    origin_exclusion_km=origin_exclusion_km,
                    is_first_hop=False,
                    target_leg_km=target_leg_km,
                    max_leg_km=max_leg_km,
                    avg_speed_kmh=avg_speed_kmh,
                    route_preference=route_preference,
                ):
                    continue
                new_time = state_i.time_min + _transition_cost(
                    drive_min=drive_min,
                    charge_min=charge_min,
                    cand=cand_j,
                )
                if best[j] is None or new_time < best[j].time_min - 1e-6:
                    best[j] = _NodeState(time_min=new_time, dep_soc=dep_soc, prev=i)
                    updated = True
        if not updated:
            break

    # Mejor llegada al destino (directo o tras paradas)
    best_total = _INF
    best_end_prev = -3
    best_projected = None

    direct = _finish_from(
        profile,
        from_km=origin_position_km,
        from_soc=profile.soc_percent,
        destination_km=destination_distance_km,
        avg_speed_kmh=avg_speed_kmh,
        min_destination_soc=resolved_destination_soc,
    )
    if direct is not None:
        drive_min, projected = direct
        if drive_min < best_total:
            best_total = drive_min
            best_end_prev = -2
            best_projected = projected

    for i in range(n):
        state_i = best[i]
        if state_i is None:
            continue
        finish = _finish_from(
            profile,
            from_km=candidates[i].route_km,
            from_soc=state_i.dep_soc,
            destination_km=destination_distance_km,
            avg_speed_kmh=avg_speed_kmh,
            min_destination_soc=resolved_destination_soc,
        )
        if finish is None:
            continue
        drive_min, projected = finish
        total = state_i.time_min + drive_min
        if total < best_total:
            best_total = total
            best_end_prev = i
            best_projected = projected

    if best_end_prev == -2:
        projected = round(clamp_display_soc_pct(best_projected or 0.0), 1)
        return [], [], projected

    if best_end_prev < 0 or best_projected is None:
        return None

    # Reconstruir cadena de paradas
    chain: list[int] = []
    idx = best_end_prev
    while idx >= 0:
        chain.append(idx)
        state = best[idx]
        if state is None:
            return None
        idx = state.prev
    chain.reverse()

    if len(chain) > max_stops:
        return None

    warnings: list[str] = []
    if early_first_stop_warning:
        warnings.append(
            "Primera parada anticipada: el tramo ~2 h dejaría poca batería al llegar; "
            "se sugiere cargar antes."
        )
    planned: list[PlannedRouteStop] = []
    previous_km = origin_position_km
    from_soc = profile.soc_percent

    for order, cand_idx in enumerate(chain, start=1):
        cand = candidates[cand_idx]
        leg = _drive_and_arrival(
            profile,
            from_km=previous_km,
            from_soc=from_soc,
            to_km=cand.route_km,
            avg_speed_kmh=avg_speed_kmh,
            extra_minutes=cand.extra_minutes,
        )
        if leg is None:
            return None
        leg_km, arrival, drive_min = leg
        dep_soc, charge_min = _charge_at_stop(
            profile=profile,
            arrival_soc=arrival,
            candidate_km=cand.route_km,
            destination_km=destination_distance_km,
            avg_speed_kmh=avg_speed_kmh,
            destination_target_soc=resolved_destination_soc,
            station_max_kw=cand.match.station.max_power_kw,
        )
        arrival_round = round(clamp_display_soc_pct(arrival), 1)
        charging_reach = estimate_charging_reach_km(_profile_at_soc(profile, from_soc))
        scored = _stop_from_corridor_match(
            cand.match,
            origin_position_km=previous_km,
            profile=_profile_at_soc(profile, from_soc),
            charging_reach_km=charging_reach,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
        )
        if not _is_meaningful_charging_stop(
            arrival_soc_pct=arrival_round,
            departure_soc_pct=dep_soc,
            charge_minutes=charge_min,
            leg_distance_km=leg_km,
            min_leg_km=_min_leg_km_for_stop(
                target_leg_km=target_leg_km,
                max_leg_km=max_leg_km,
                profile=profile,
                from_soc=from_soc,
            ),
            stop_route_km=cand.route_km,
            trip_start_route_km=trip_start,
            origin_exclusion_km=origin_exclusion_km if order == 1 else 0.0,
        ):
            warnings.append(
                f"Parada {order} en km {cand.route_km:.0f} aporta poca energía; "
                "incluida por optimización global de tiempo."
            )
        leg_driving = driving_minutes_for_distance(leg_km, avg_speed_kmh)
        if leg_driving > MAX_DRIVING_LEG_MINUTES + 5:
            warnings.append(
                f"Tramo {order}: ~{leg_driving:.0f} min conducción "
                f"(recomendado ≤{TARGET_DRIVING_LEG_MINUTES:.0f} min)."
            )
        planned.append(
            PlannedRouteStop(
                order=order,
                station=cand.match.station,
                deviation_km=round(cand.deviation_km, 2),
                route_distance_km=round(cand.route_km, 2),
                extra_minutes=round(cand.extra_minutes, 1),
                wrong_side=cand.wrong_side,
                distance_from_origin_km=round(cand.route_km - trip_start, 2),
                leg_distance_km=round(leg_km, 2),
                leg_driving_minutes=round(leg_driving, 1),
                soc_arrival_pct=arrival_round,
                soc_departure_pct=round(dep_soc, 1),
                charge_minutes=charge_min,
                classification=scored.classification,
            )
        )
        previous_km = cand.route_km
        from_soc = dep_soc

    projected = round(clamp_display_soc_pct(best_projected), 1)
    if best_projected < resolved_destination_soc:
        warnings.append(
            f"Con {len(planned)} parada(s) llegarías con ~{projected:.0f} % "
            f"(objetivo {resolved_destination_soc:.0f} %)."
        )
    warnings.append(
        f"Plan optimizado: {len(planned)} parada(s), "
        f"~{best_total:.0f} min conducción+recarga hasta destino."
    )
    return planned, warnings, projected
