from unittest.mock import MagicMock, patch

from api.routing.osrm import select_osrm_route_payload

ROUTES = [
    {"distance": 100_000, "duration": 3600},
    {"distance": 120_000, "duration": 3000},
]

GEODESIC_KM = 90.0


def test_select_osrm_route_fastest() -> None:
    selected = select_osrm_route_payload(ROUTES, route_preference="fastest", geodesic_km=GEODESIC_KM)
    assert selected["duration"] == 3000


def test_select_fastest_route_prefers_similar_time_higher_avg_speed() -> None:
    from api.routing.osrm import select_fastest_route_payload

    routes = [
        {"distance": 556_500, "duration": 22_990},  # N-330 inland
        {"distance": 581_400, "duration": 23_170},  # A-7 + A-23 (~0.8% slower, faster avg)
    ]
    selected = select_fastest_route_payload(routes)
    assert selected["distance"] == 581_400


def test_select_fastest_route_keeps_clear_winner() -> None:
    from api.routing.osrm import select_fastest_route_payload

    routes = [
        {"distance": 100_000, "duration": 3600},
        {"distance": 120_000, "duration": 3000},
    ]
    selected = select_fastest_route_payload(routes)
    assert selected["duration"] == 3000


def test_select_osrm_route_shortest() -> None:
    selected = select_osrm_route_payload(ROUTES, route_preference="shortest", geodesic_km=GEODESIC_KM)
    assert selected["distance"] == 100_000


def test_summarize_osrm_alternatives() -> None:
    from api.routing.osrm import summarize_osrm_alternatives

    summary = summarize_osrm_alternatives(ROUTES, geodesic_km=GEODESIC_KM)
    assert summary.geodesic_distance_km == GEODESIC_KM
    assert summary.shortest_distance_km == 100.0
    assert summary.fastest_distance_km == 120.0
    assert summary.fastest_duration_minutes == 50.0
    assert summary.shortest_duration_minutes == 60.0
    assert summary.variants_approximate is True


def test_select_osrm_route_conventional_with_exclude() -> None:
    selected = select_osrm_route_payload(
        ROUTES,
        route_preference="conventional",
        exclude_applied=True,
        geodesic_km=GEODESIC_KM,
    )
    assert selected["distance"] == 100_000


def test_select_osrm_route_conventional_without_exclude() -> None:
    selected = select_osrm_route_payload(
        ROUTES,
        route_preference="conventional",
        exclude_applied=False,
        geodesic_km=GEODESIC_KM,
    )
    assert selected["distance"] == 120_000


def test_build_osrm_exclude_param() -> None:
    from api.config import settings
    from api.routing.osrm import build_osrm_exclude_param

    assert build_osrm_exclude_param("fastest", False) is None
    assert build_osrm_exclude_param("fastest", True) == "toll"

    original = settings.osrm_use_multi_profile
    settings.osrm_use_multi_profile = False
    try:
        assert build_osrm_exclude_param("conventional", False) == "motorway"
        assert build_osrm_exclude_param("conventional", True) == "motorway,toll"
    finally:
        settings.osrm_use_multi_profile = original

    settings.osrm_use_multi_profile = True
    assert build_osrm_exclude_param("conventional", False) is None
    settings.osrm_use_multi_profile = original


def test_geodesic_distance_km() -> None:
    from api.routing.osrm import geodesic_distance_km

    km = geodesic_distance_km(40.4168, -3.7038, 39.4699, -0.3763)
    assert 295 < km < 310


def test_conventional_route_falls_back_when_exclude_unsupported() -> None:
    from api.config import settings
    from api.routing.osrm import _request_osrm_routes, fetch_osrm_route_with_alternatives

    blocked = MagicMock()
    blocked.status_code = 400
    blocked.json.return_value = {
        "code": "InvalidValue",
        "message": "Exclude flag combination is not supported.",
    }
    ok_payload = MagicMock()
    ok_payload.status_code = 200
    ok_payload.json.return_value = {
        "code": "Ok",
        "routes": [
            {
                "distance": 100_000,
                "duration": 3600,
                "geometry": {"coordinates": [[0.0, 40.0], [0.5, 40.0]]},
            },
            {
                "distance": 130_000,
                "duration": 4200,
                "geometry": {"coordinates": [[0.0, 40.0], [1.0, 40.0]]},
            },
        ],
    }
    highway_payload = MagicMock()
    highway_payload.status_code = 200
    highway_payload.json.return_value = {
        "code": "Ok",
        "routes": [
            {
                "distance": 100_000,
                "duration": 3000,
                "geometry": {"coordinates": [[0.0, 40.0], [0.5, 40.0]]},
            },
            {
                "distance": 120_000,
                "duration": 3600,
                "geometry": {"coordinates": [[0.0, 40.0], [1.0, 40.0]]},
            },
        ],
    }

    client = MagicMock()
    client.get.side_effect = [blocked, ok_payload]

    original = settings.osrm_use_multi_profile
    settings.osrm_use_multi_profile = False
    try:
        with patch("api.routing.osrm.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = client
            routes, warnings, exclude_applied = _request_osrm_routes(
                40.0,
                0.0,
                40.0,
                1.0,
                base_url="https://router.project-osrm.org",
                timeout_s=5.0,
                profile="driving",
                route_preference="conventional",
                avoid_highways=False,
            )

        assert len(routes) == 2
        assert exclude_applied is False
        assert warnings
        assert "aproximadas" in warnings[0]

        with patch("api.routing.osrm._request_osrm_routes") as mock_request:
            mock_request.side_effect = [
                (
                    highway_payload.json.return_value["routes"],
                    [],
                    False,
                ),
                (routes, warnings, exclude_applied),
            ]
            _route, summary, route_warnings, variant_routes = fetch_osrm_route_with_alternatives(
                40.0,
                0.0,
                40.0,
                1.0,
                route_preference="conventional",
            )
    finally:
        settings.osrm_use_multi_profile = original

    assert _route.route_preference == "conventional"
    assert _route.distance_m == 130_000
    assert route_warnings
    assert summary.conventional_distance_km == 130.0
    assert summary.fastest_distance_km == 100.0
    assert "conventional" in variant_routes
    assert "fastest" in variant_routes
    assert variant_routes["fastest"].distance_m == 100_000
    assert mock_request.call_count == 2


def test_fallback_variants_use_separate_osrm_requests() -> None:
    from api.config import settings
    from api.routing.osrm import _fetch_fallback_variants

    highway_routes = [
        {"distance": 500_000, "duration": 18_000, "geometry": {"coordinates": [[0, 40], [1, 41]]}},
        {"distance": 520_000, "duration": 17_500, "geometry": {"coordinates": [[0, 40], [1.2, 41]]}},
    ]
    conventional_routes = [
        {"distance": 680_000, "duration": 28_000, "geometry": {"coordinates": [[0, 40], [0.8, 40.5]]}},
    ]

    original = settings.osrm_use_multi_profile
    settings.osrm_use_multi_profile = False
    try:
        with patch("api.routing.osrm._request_osrm_routes") as mock_request:
            mock_request.side_effect = [
                (highway_routes, [], False),
                (conventional_routes, [], True),
            ]
            variants, warnings, exclude_applied = _fetch_fallback_variants(
                40.0,
                0.0,
                43.0,
                1.5,
                base_url="https://router.project-osrm.org",
                timeout_s=5.0,
                profile="driving",
                avoid_highways=False,
                geodesic_km=400.0,
            )
    finally:
        settings.osrm_use_multi_profile = original

    assert mock_request.call_count == 2
    assert mock_request.call_args_list[0].kwargs["route_preference"] == "fastest"
    assert mock_request.call_args_list[1].kwargs["route_preference"] == "conventional"
    assert variants["fastest"].route["distance"] == 520_000
    assert variants["conventional"].route["distance"] == 680_000
    assert variants["conventional"].approximate is False
    assert exclude_applied is True
    assert not warnings
