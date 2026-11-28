package es.jualas.electrolineras.car;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

/**
 * Lee las preferencias compartidas por la app móvil Capacitor (`@capacitor/preferences`
 * guarda en SharedPreferences bajo el nombre "CapacitorStorage").
 */
public final class CarPreferencesBridge {
    private static final String PREFS_NAME = "CapacitorStorage";
    private static final String KEY_API_BASE_URL = "car_api_base_url";
    private static final String KEY_PRIVATE_TOKEN = "car_private_token";
    private static final String KEY_MIN_KW = "car_filter_min_kw";
    private static final String KEY_MAX_KW = "car_filter_max_kw";

    public static final String DEFAULT_API_BASE_URL = "https://electro.jualas.es";
    public static final double DEFAULT_MIN_KW = 100.0;

    private final SharedPreferences prefs;

    public CarPreferencesBridge(@NonNull Context context) {
        this.prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    @NonNull
    public String getApiBaseUrl() {
        String raw = prefs.getString(KEY_API_BASE_URL, null);
        if (raw == null || raw.trim().isEmpty()) {
            return DEFAULT_API_BASE_URL;
        }
        String trimmed = raw.trim();
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed.isEmpty() ? DEFAULT_API_BASE_URL : trimmed;
    }

    @Nullable
    public String getPrivateToken() {
        String raw = prefs.getString(KEY_PRIVATE_TOKEN, null);
        if (raw == null || raw.trim().isEmpty()) {
            return null;
        }
        return raw.trim();
    }

    public double getMinKw() {
        String raw = prefs.getString(KEY_MIN_KW, null);
        if (raw == null || raw.trim().isEmpty()) {
            return DEFAULT_MIN_KW;
        }
        try {
            double parsed = Double.parseDouble(raw.trim());
            return parsed >= 0 ? parsed : DEFAULT_MIN_KW;
        } catch (NumberFormatException ignored) {
            return DEFAULT_MIN_KW;
        }
    }

    @Nullable
    public Double getMaxKw() {
        String raw = prefs.getString(KEY_MAX_KW, null);
        if (raw == null || raw.trim().isEmpty()) {
            return null;
        }
        try {
            double parsed = Double.parseDouble(raw.trim());
            return parsed > 0 ? parsed : null;
        } catch (NumberFormatException ignored) {
            return null;
        }
    }
}
