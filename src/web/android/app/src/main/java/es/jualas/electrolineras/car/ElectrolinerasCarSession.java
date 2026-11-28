package es.jualas.electrolineras.car;

import android.content.Intent;

import androidx.annotation.NonNull;
import androidx.car.app.Screen;
import androidx.car.app.Session;
import androidx.lifecycle.DefaultLifecycleObserver;
import androidx.lifecycle.LifecycleOwner;

/**
 * Sesión de Android Auto / AAOS. Gestiona el ciclo de vida del lector de telemetría
 * (`CarTelemetryManager`) y arranca la pantalla de cargadores cercanos.
 */
public final class ElectrolinerasCarSession extends Session {
    private CarPreferencesBridge prefs;
    private CarApiClient apiClient;
    private CarTelemetryManager telemetryManager;

    @NonNull
    @Override
    public Screen onCreateScreen(@NonNull Intent intent) {
        prefs = new CarPreferencesBridge(getCarContext());
        apiClient = new CarApiClient(prefs);
        telemetryManager = new CarTelemetryManager(getCarContext(), apiClient);

        getLifecycle().addObserver(new DefaultLifecycleObserver() {
            @Override
            public void onStart(@NonNull LifecycleOwner owner) {
                telemetryManager.start();
            }

            @Override
            public void onDestroy(@NonNull LifecycleOwner owner) {
                telemetryManager.stop();
            }
        });

        return new NearbyChargersScreen(getCarContext(), prefs, apiClient, telemetryManager);
    }
}
