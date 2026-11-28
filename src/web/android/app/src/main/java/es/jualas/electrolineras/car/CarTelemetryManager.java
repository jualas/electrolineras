package es.jualas.electrolineras.car;

import android.os.SystemClock;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.car.app.CarContext;
import androidx.car.app.hardware.CarHardwareManager;
import androidx.car.app.hardware.common.CarValue;
import androidx.car.app.hardware.common.OnCarDataAvailableListener;
import androidx.car.app.hardware.info.CarInfo;
import androidx.car.app.hardware.info.EnergyLevel;
import androidx.car.app.hardware.info.Model;
import androidx.core.content.ContextCompat;

import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import es.jualas.electrolineras.car.CarModels.CarTelemetrySnapshot;

/**
 * Escucha la telemetría de energía del coche vía Android for Cars (`CarHardwareManager`).
 * Compatible tanto con Android Auto (proyección) como con Android Automotive OS (AAOS).
 * Si el vehículo no expone `EnergyLevel`, falla de forma silenciosa sin afectar a la app.
 */
public final class CarTelemetryManager {
    private static final String TAG = "ElectrolinerasCarTel";
    private static final long MIN_PUSH_INTERVAL_MS = 60_000L;

    public interface Listener {
        void onTelemetryUpdated(@NonNull CarTelemetrySnapshot snapshot);
    }

    private final CarContext carContext;
    private final CarApiClient apiClient;
    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();

    @Nullable private CarInfo carInfo;
    @Nullable private Listener listener;
    @Nullable private Float lastBatteryPct;
    @Nullable private Float lastRangeKm;
    @Nullable private String modelLabel;
    @Nullable private Double lastLat;
    @Nullable private Double lastLon;

    private long lastPushElapsedMs = 0L;
    @Nullable private Float lastPushedSoc;

    private final OnCarDataAvailableListener<EnergyLevel> energyListener = this::handleEnergyLevel;

    public CarTelemetryManager(@NonNull CarContext carContext, @NonNull CarApiClient apiClient) {
        this.carContext = carContext;
        this.apiClient = apiClient;
    }

    public void setListener(@Nullable Listener listener) {
        this.listener = listener;
    }

    public void updateLastLocation(double lat, double lon) {
        this.lastLat = lat;
        this.lastLon = lon;
        maybePushTelemetry();
    }

    @NonNull
    public CarTelemetrySnapshot getSnapshot() {
        return new CarTelemetrySnapshot(lastBatteryPct, lastRangeKm, modelLabel);
    }

    public void start() {
        try {
            CarHardwareManager hardwareManager =
                    carContext.getCarService(CarHardwareManager.class);
            carInfo = hardwareManager.getCarInfo();
            Executor mainExecutor = ContextCompat.getMainExecutor(carContext);
            carInfo.fetchModel(mainExecutor, this::handleModel);
            carInfo.addEnergyLevelListener(mainExecutor, energyListener);
        } catch (SecurityException sec) {
            Log.i(TAG, "Sin permiso de hardware de vehículo todavía: " + sec.getMessage());
        } catch (Throwable exc) {
            Log.i(TAG, "CarHardwareManager no disponible en este host: " + exc.getMessage());
        }
    }

    public void stop() {
        if (carInfo != null) {
            try {
                carInfo.removeEnergyLevelListener(energyListener);
            } catch (Throwable ignored) {
                // Algunos hosts cierran antes de removeListener
            }
            carInfo = null;
        }
        networkExecutor.shutdownNow();
    }

    private void handleModel(@NonNull Model model) {
        String manufacturer =
                model.getManufacturer().getStatus() == CarValue.STATUS_SUCCESS
                        ? model.getManufacturer().getValue()
                        : null;
        String name =
                model.getName().getStatus() == CarValue.STATUS_SUCCESS
                        ? model.getName().getValue()
                        : null;
        String combined = ((manufacturer != null ? manufacturer : "") + " " + (name != null ? name : "")).trim();
        if (!combined.isEmpty()) {
            this.modelLabel = combined;
            notifyListener();
        }
    }

    private void handleEnergyLevel(@NonNull EnergyLevel energy) {
        boolean changed = false;
        CarValue<Float> battery = energy.getBatteryPercent();
        if (battery.getStatus() == CarValue.STATUS_SUCCESS && battery.getValue() != null) {
            float pct = battery.getValue();
            if (pct >= 0f && pct <= 100f) {
                lastBatteryPct = pct;
                changed = true;
            }
        }
        CarValue<Float> rangeMeters = energy.getRangeRemainingMeters();
        if (rangeMeters.getStatus() == CarValue.STATUS_SUCCESS && rangeMeters.getValue() != null) {
            float meters = rangeMeters.getValue();
            if (meters > 0f) {
                lastRangeKm = meters / 1000.0f;
                changed = true;
            }
        }
        if (changed) {
            notifyListener();
            maybePushTelemetry();
        }
    }

    private void notifyListener() {
        Listener current = this.listener;
        if (current != null) {
            current.onTelemetryUpdated(getSnapshot());
        }
    }

    private void maybePushTelemetry() {
        Float soc = this.lastBatteryPct;
        Double lat = this.lastLat;
        Double lon = this.lastLon;
        if (soc == null || lat == null || lon == null) {
            return;
        }
        long now = SystemClock.elapsedRealtime();
        boolean socShifted = lastPushedSoc == null || Math.abs(soc - lastPushedSoc) >= 1.0f;
        boolean intervalElapsed = (now - lastPushElapsedMs) >= MIN_PUSH_INTERVAL_MS;
        if (!socShifted && !intervalElapsed) {
            return;
        }
        lastPushElapsedMs = now;
        lastPushedSoc = soc;

        Float rangeKm = this.lastRangeKm;
        String label = this.modelLabel;
        networkExecutor.execute(
                () -> apiClient.pushVehicleTelemetry(lat, lon, soc, rangeKm, label));
    }
}
