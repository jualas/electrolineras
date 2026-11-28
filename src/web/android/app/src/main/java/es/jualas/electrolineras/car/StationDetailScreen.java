package es.jualas.electrolineras.car;

import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.car.app.CarContext;
import androidx.car.app.CarToast;
import androidx.car.app.Screen;
import androidx.car.app.model.Action;
import androidx.car.app.model.CarColor;
import androidx.car.app.model.Pane;
import androidx.car.app.model.PaneTemplate;
import androidx.car.app.model.Row;
import androidx.car.app.model.Template;
import androidx.lifecycle.DefaultLifecycleObserver;
import androidx.lifecycle.LifecycleOwner;

import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import es.jualas.electrolineras.car.CarModels.CarReliabilityInfo;
import es.jualas.electrolineras.car.CarModels.CarStationItem;

/**
 * Pantalla de detalle de un cargador en Android Auto / AAOS:
 * muestra verificación mixta en vivo (REVE + Google Places), alerta de zona aislada
 * (plan B en 50 km) y botón primario «Navegar» hacia el navegador del coche.
 */
public final class StationDetailScreen extends Screen {
    private final CarApiClient apiClient;
    private final CarStationItem station;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private boolean loading = true;
    @Nullable private CarReliabilityInfo reliability;
    @Nullable private String loadError;

    public StationDetailScreen(
            @NonNull CarContext carContext,
            @NonNull CarApiClient apiClient,
            @NonNull CarStationItem station) {
        super(carContext);
        this.apiClient = apiClient;
        this.station = station;

        getLifecycle().addObserver(new DefaultLifecycleObserver() {
            @Override
            public void onDestroy(@NonNull LifecycleOwner owner) {
                executor.shutdownNow();
            }
        });

        loadReliability();
    }

    @NonNull
    @Override
    public Template onGetTemplate() {
        Pane.Builder paneBuilder = new Pane.Builder();
        if (loading) {
            paneBuilder.setLoading(true);
        } else {
            String subtitle = String.format(
                    Locale.getDefault(),
                    "%.0f kW · %.1f km%s",
                    station.maxPowerKw,
                    station.distanceKm,
                    station.operator != null ? " · " + station.operator : "");
            Row.Builder infoRow = new Row.Builder().setTitle(subtitle);
            if (station.address != null) {
                infoRow.addText(station.address);
            }
            paneBuilder.addRow(infoRow.build());

            if (reliability != null) {
                Row.Builder relRow = new Row.Builder()
                        .setTitle(reliabilityHeading(reliability.level))
                        .addText(reliability.summary);
                String googleLine = buildGoogleLine(reliability);
                if (googleLine != null) {
                    relRow.addText(googleLine);
                }
                paneBuilder.addRow(relRow.build());

                if (reliability.isolatedArea) {
                    paneBuilder.addRow(
                            new Row.Builder()
                                    .setTitle("Zona aislada (sin plan B)")
                                    .addText(
                                            String.format(
                                                    Locale.getDefault(),
                                                    "Sin otro cargador rápido en %.0f km",
                                                    reliability.isolationRadiusKm))
                                    .build());
                } else if (reliability.backupStationKm != null) {
                    paneBuilder.addRow(
                            new Row.Builder()
                                    .setTitle("Plan B cercano")
                                    .addText(
                                            String.format(
                                                    Locale.getDefault(),
                                                    "%s a %.1f km",
                                                    reliability.backupStationLabel != null
                                                            ? reliability.backupStationLabel
                                                            : "Alternativa",
                                                    reliability.backupStationKm))
                                    .build());
                }
            } else if (loadError != null) {
                paneBuilder.addRow(
                        new Row.Builder()
                                .setTitle("Verificación en vivo no disponible")
                                .addText(loadError)
                                .build());
            }

            paneBuilder.addAction(
                    new Action.Builder()
                            .setTitle("Navegar")
                            .setFlags(Action.FLAG_PRIMARY)
                            .setBackgroundColor(CarColor.BLUE)
                            .setOnClickListener(this::launchNavigation)
                            .build());
            paneBuilder.addAction(
                    new Action.Builder()
                            .setTitle("Re-verificar")
                            .setOnClickListener(this::loadReliability)
                            .build());
        }

        return new PaneTemplate.Builder(paneBuilder.build())
                .setTitle(station.name)
                .setHeaderAction(Action.BACK)
                .build();
    }

    private void loadReliability() {
        loading = true;
        loadError = null;
        invalidate();

        executor.execute(() -> {
            try {
                CarReliabilityInfo fetched = apiClient.fetchStationReliability(station.id);
                mainHandler.post(() -> {
                    reliability = fetched;
                    loading = false;
                    loadError = null;
                    invalidate();
                });
            } catch (Exception exc) {
                mainHandler.post(() -> {
                    loading = false;
                    loadError = "Sin respuesta del servidor; comprueba antes de apurar batería.";
                    invalidate();
                });
            }
        });
    }

    private void launchNavigation() {
        String uri = String.format(
                Locale.US,
                "geo:%.6f,%.6f?q=%.6f,%.6f(%s)",
                station.lat,
                station.lon,
                station.lat,
                station.lon,
                Uri.encode(station.name));
        Intent navIntent = new Intent(CarContext.ACTION_NAVIGATE, Uri.parse(uri));
        try {
            getCarContext().startCarApp(navIntent);
        } catch (Exception exc) {
            CarToast.makeText(
                            getCarContext(),
                            "No se pudo abrir la navegación del coche",
                            CarToast.LENGTH_SHORT)
                    .show();
        }
    }

    @NonNull
    private static String reliabilityHeading(@NonNull String level) {
        if ("high".equals(level)) {
            return "Alta fiabilidad";
        }
        if ("low".equals(level)) {
            return "No fiable · Evitar";
        }
        return "Precaución";
    }

    @Nullable
    private static String buildGoogleLine(@NonNull CarReliabilityInfo info) {
        if (!info.googleMatched) {
            return null;
        }
        StringBuilder sb = new StringBuilder("Google: ");
        if (info.googleAvailableCount != null) {
            sb.append(info.googleAvailableCount)
                    .append("/")
                    .append(info.googleTotalConnectors != null ? info.googleTotalConnectors : "?")
                    .append(" libres");
        } else if (info.googleTotalConnectors != null) {
            sb.append(info.googleTotalConnectors).append(" conectores");
        } else {
            sb.append("operativa");
        }
        if (info.googleOutOfServiceCount != null && info.googleOutOfServiceCount > 0) {
            sb.append(" · ").append(info.googleOutOfServiceCount).append(" averiado(s)");
        }
        return sb.toString();
    }
}
