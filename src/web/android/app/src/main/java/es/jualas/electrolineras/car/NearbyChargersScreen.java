package es.jualas.electrolineras.car;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationManager;
import android.os.Handler;
import android.os.Looper;
import android.text.SpannableString;
import android.text.Spanned;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.car.app.CarContext;
import androidx.car.app.Screen;
import androidx.car.app.model.Action;
import androidx.car.app.model.ActionStrip;
import androidx.car.app.model.CarLocation;
import androidx.car.app.model.Distance;
import androidx.car.app.model.DistanceSpan;
import androidx.car.app.model.ItemList;
import androidx.car.app.model.Metadata;
import androidx.car.app.model.Place;
import androidx.car.app.model.PlaceListMapTemplate;
import androidx.car.app.model.PlaceMarker;
import androidx.car.app.model.Row;
import androidx.car.app.model.Template;
import androidx.core.content.ContextCompat;
import androidx.lifecycle.DefaultLifecycleObserver;
import androidx.lifecycle.LifecycleOwner;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import es.jualas.electrolineras.car.CarModels.CarStationItem;
import es.jualas.electrolineras.car.CarModels.CarTelemetrySnapshot;

/**
 * Pantalla principal en Android Auto / AAOS: mapa nativo del coche + lista de hasta 6
 * electrolineras cercanas filtradas por potencia (heredada de la app móvil).
 */
public final class NearbyChargersScreen extends Screen {
    private static final int MAX_CAR_LIST_ITEMS = 6;
    private static final int SEARCH_RADIUS_M = 50_000;
    private static final double[] POWER_CYCLE_KW = {100.0, 50.0, 0.0};

    private final CarApiClient apiClient;
    private final CarTelemetryManager telemetryManager;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private double activeMinKw;
    private boolean loading = true;
    @Nullable private String errorMessage;
    @Nullable private Location lastLocation;
    @NonNull private List<CarStationItem> stations = new ArrayList<>();
    @NonNull private CarTelemetrySnapshot telemetry;

    public NearbyChargersScreen(
            @NonNull CarContext carContext,
            @NonNull CarPreferencesBridge prefs,
            @NonNull CarApiClient apiClient,
            @NonNull CarTelemetryManager telemetryManager) {
        super(carContext);
        this.apiClient = apiClient;
        this.telemetryManager = telemetryManager;
        this.activeMinKw = prefs.getMinKw();
        this.telemetry = telemetryManager.getSnapshot();

        this.telemetryManager.setListener(snapshot -> {
            this.telemetry = snapshot;
            mainHandler.post(this::invalidate);
        });

        getLifecycle().addObserver(new DefaultLifecycleObserver() {
            @Override
            public void onDestroy(@NonNull LifecycleOwner owner) {
                telemetryManager.setListener(null);
                executor.shutdownNow();
            }
        });

        loadNearbyStations();
    }

    @NonNull
    @Override
    public Template onGetTemplate() {
        PlaceListMapTemplate.Builder builder = new PlaceListMapTemplate.Builder()
                .setTitle(buildTitle())
                .setHeaderAction(Action.APP_ICON)
                .setActionStrip(buildActionStrip())
                .setCurrentLocationEnabled(hasLocationPermission());

        if (loading) {
            return builder.setLoading(true).build();
        }

        ItemList.Builder listBuilder = new ItemList.Builder();
        if (errorMessage != null) {
            listBuilder.setNoItemsMessage(errorMessage);
        } else if (stations.isEmpty()) {
            listBuilder.setNoItemsMessage(
                    String.format(
                            Locale.getDefault(),
                            "Sin cargadores ≥%.0f kW en 50 km. Pulsa el filtro para bajar potencia.",
                            activeMinKw));
        } else {
            for (CarStationItem station : stations) {
                listBuilder.addItem(buildStationRow(station));
            }
        }

        if (lastLocation != null) {
            builder.setAnchor(
                    new Place.Builder(
                                    CarLocation.create(
                                            lastLocation.getLatitude(),
                                            lastLocation.getLongitude()))
                            .build());
        }

        return builder.setItemList(listBuilder.build()).build();
    }

    @NonNull
    private String buildTitle() {
        String filterLabel = activeMinKw > 0
                ? String.format(Locale.getDefault(), "≥%.0f kW", activeMinKw)
                : "Todos";
        if (telemetry.batteryPercent != null) {
            return String.format(
                    Locale.getDefault(),
                    "Electrolineras · %.0f%% · %s",
                    telemetry.batteryPercent,
                    filterLabel);
        }
        return "Electrolineras · " + filterLabel;
    }

    @NonNull
    private ActionStrip buildActionStrip() {
        String nextFilterLabel = activeMinKw >= 100.0
                ? "≥50 kW"
                : (activeMinKw >= 50.0 ? "Todos" : "≥100 kW");
        return new ActionStrip.Builder()
                .addAction(
                        new Action.Builder()
                                .setTitle(nextFilterLabel)
                                .setOnClickListener(this::cyclePowerFilter)
                                .build())
                .addAction(
                        new Action.Builder()
                                .setTitle("Actualizar")
                                .setOnClickListener(this::loadNearbyStations)
                                .build())
                .build();
    }

    @NonNull
    private Row buildStationRow(@NonNull CarStationItem station) {
        String title = String.format(
                Locale.getDefault(), "%s · %.0f kW", station.name, station.maxPowerKw);

        StringBuilder meta = new StringBuilder("  ");
        if (station.operator != null) {
            meta.append(station.operator);
        }
        String statusText = formatDynamicStatus(station.dynamicStatus);
        if (statusText != null) {
            if (meta.length() > 2) {
                meta.append(" · ");
            }
            meta.append(statusText);
        }
        if (station.priceEurKwh != null) {
            if (meta.length() > 2) {
                meta.append(" · ");
            }
            meta.append(String.format(Locale.getDefault(), "%.2f €/kWh", station.priceEurKwh));
        }

        SpannableString line = new SpannableString(meta.toString());
        line.setSpan(
                DistanceSpan.create(
                        Distance.create(
                                Math.max(0.1, station.distanceKm),
                                Distance.UNIT_KILOMETERS)),
                0,
                1,
                Spanned.SPAN_INCLUSIVE_INCLUSIVE);

        Place place = new Place.Builder(CarLocation.create(station.lat, station.lon))
                .setMarker(new PlaceMarker.Builder().build())
                .build();

        return new Row.Builder()
                .setTitle(title)
                .addText(line)
                .setBrowsable(true)
                .setMetadata(new Metadata.Builder().setPlace(place).build())
                .setOnClickListener(() ->
                        getScreenManager().push(
                                new StationDetailScreen(getCarContext(), apiClient, station)))
                .build();
    }

    private void cyclePowerFilter() {
        double next = POWER_CYCLE_KW[0];
        for (int i = 0; i < POWER_CYCLE_KW.length; i++) {
            if (Math.abs(activeMinKw - POWER_CYCLE_KW[i]) < 1.0) {
                next = POWER_CYCLE_KW[(i + 1) % POWER_CYCLE_KW.length];
                break;
            }
        }
        activeMinKw = next;
        loadNearbyStations();
    }

    private void loadNearbyStations() {
        loading = true;
        errorMessage = null;
        invalidate();

        if (!hasLocationPermission()) {
            loading = false;
            errorMessage = "Abre la app en el móvil y concede permiso de ubicación (GPS).";
            invalidate();
            return;
        }

        Location loc = resolveBestLastKnownLocation();
        if (loc == null) {
            loading = false;
            errorMessage = "Esperando señal GPS del teléfono. Pulsa Actualizar en unos segundos.";
            invalidate();
            return;
        }

        lastLocation = loc;
        telemetryManager.updateLastLocation(loc.getLatitude(), loc.getLongitude());

        final double lat = loc.getLatitude();
        final double lon = loc.getLongitude();
        final double minKw = activeMinKw;

        executor.execute(() -> {
            try {
                List<CarStationItem> fetched = apiClient.fetchNearbyChargers(
                        lat, lon, minKw, SEARCH_RADIUS_M, MAX_CAR_LIST_ITEMS);
                mainHandler.post(() -> {
                    stations = fetched;
                    loading = false;
                    errorMessage = null;
                    invalidate();
                });
            } catch (Exception exc) {
                mainHandler.post(() -> {
                    stations = new ArrayList<>();
                    loading = false;
                    errorMessage = "Sin conexión con Electrolineras. Reintenta con Actualizar.";
                    invalidate();
                });
            }
        });
    }

    private boolean hasLocationPermission() {
        return ContextCompat.checkSelfPermission(
                        getCarContext(), Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(
                        getCarContext(), Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    @Nullable
    private Location resolveBestLastKnownLocation() {
        LocationManager lm =
                (LocationManager) getCarContext().getSystemService(Context.LOCATION_SERVICE);
        if (lm == null) {
            return null;
        }
        Location best = null;
        try {
            for (String provider : lm.getProviders(true)) {
                Location candidate = lm.getLastKnownLocation(provider);
                if (candidate == null) {
                    continue;
                }
                if (best == null || candidate.getTime() > best.getTime()) {
                    best = candidate;
                }
            }
        } catch (SecurityException ignored) {
            return null;
        }
        return best;
    }

    @Nullable
    private static String formatDynamicStatus(@Nullable String status) {
        if (status == null) {
            return null;
        }
        switch (status.toUpperCase(Locale.US)) {
            case "AVAILABLE":
                return "Disponible";
            case "CHARGING":
                return "Ocupado";
            case "RESERVED":
                return "Reservado";
            case "OUTOFORDER":
            case "INOPERATIVE":
                return "Averiado";
            default:
                return null;
        }
    }
}
