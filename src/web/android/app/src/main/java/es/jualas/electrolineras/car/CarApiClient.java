package es.jualas.electrolineras.car;

import android.net.Uri;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import es.jualas.electrolineras.car.CarModels.CarReliabilityInfo;
import es.jualas.electrolineras.car.CarModels.CarStationItem;

/**
 * Cliente HTTP ligero contra la API REST de Electrolineras (`electro.jualas.es`).
 * Usa HttpURLConnection estándar sin dependencias externas adicionales.
 */
public final class CarApiClient {
    private static final String TAG = "ElectrolinerasCarApi";
    private static final int CONNECT_TIMEOUT_MS = 10_000;
    private static final int READ_TIMEOUT_MS = 12_000;

    private final CarPreferencesBridge prefs;

    public CarApiClient(@NonNull CarPreferencesBridge prefs) {
        this.prefs = prefs;
    }

    @NonNull
    public List<CarStationItem> fetchNearbyChargers(
            double lat,
            double lon,
            double minKw,
            int radiusMeters,
            int limit) throws IOException {
        Uri.Builder builder = Uri.parse(prefs.getApiBaseUrl() + "/api/v1/stations/nearby")
                .buildUpon()
                .appendQueryParameter("lat", String.format(Locale.US, "%.6f", lat))
                .appendQueryParameter("lon", String.format(Locale.US, "%.6f", lon))
                .appendQueryParameter("radius_m", String.valueOf(radiusMeters))
                .appendQueryParameter("min_kw", String.format(Locale.US, "%.1f", minKw))
                .appendQueryParameter("public_open_only", "true")
                .appendQueryParameter("limit", String.valueOf(limit));

        Double maxKw = prefs.getMaxKw();
        if (maxKw != null && maxKw >= minKw) {
            builder.appendQueryParameter("max_kw", String.format(Locale.US, "%.1f", maxKw));
        }

        String raw = getJson(builder.build().toString());
        return parseNearbyStations(raw);
    }

    @NonNull
    public CarReliabilityInfo fetchStationReliability(@NonNull String stationId) throws IOException {
        String encodedId = Uri.encode(stationId);
        String url = prefs.getApiBaseUrl()
                + "/api/v1/stations/"
                + encodedId
                + "/reliability?verify_google=true";
        String raw = getJson(url);
        return parseReliability(raw);
    }

    public boolean pushVehicleTelemetry(
            double lat,
            double lon,
            float batteryPercent,
            @Nullable Float estRangeKm,
            @Nullable String modelLabel) {
        String token = prefs.getPrivateToken();
        if (token == null || token.isEmpty()) {
            return false;
        }
        try {
            JSONObject body = new JSONObject();
            body.put("lat", lat);
            body.put("lon", lon);
            body.put("battery_level_pct", batteryPercent);
            if (estRangeKm != null && estRangeKm > 0f) {
                body.put("est_battery_range_km", estRangeKm);
            }
            if (modelLabel != null && !modelLabel.trim().isEmpty()) {
                body.put("car_model_label", modelLabel.trim());
                body.put("display_name", modelLabel.trim());
            }
            body.put("source", "android_car");

            String url = prefs.getApiBaseUrl() + "/api/v1/private/telemetry/ingest";
            postJson(url, body.toString(), token);
            return true;
        } catch (Exception exc) {
            Log.w(TAG, "No se pudo enviar telemetría del coche: " + exc.getMessage());
            return false;
        }
    }

    @NonNull
    static List<CarStationItem> parseNearbyStations(@NonNull String rawJson) throws IOException {
        try {
            JSONObject root = new JSONObject(rawJson);
            JSONArray results = root.optJSONArray("results");
            List<CarStationItem> items = new ArrayList<>();
            if (results == null) {
                return items;
            }
            for (int i = 0; i < results.length(); i++) {
                JSONObject entry = results.optJSONObject(i);
                if (entry == null) {
                    continue;
                }
                JSONObject station = entry.optJSONObject("station");
                if (station == null) {
                    continue;
                }
                JSONObject location = station.optJSONObject("location");
                if (location == null) {
                    continue;
                }
                String id = station.optString("id", "");
                if (id.isEmpty()) {
                    continue;
                }
                String siteName = optNullableString(station, "site_name");
                String operator = optNullableString(station, "operator");
                String address = optNullableString(location, "address");
                String displayName = siteName != null ? siteName : (operator != null ? operator : id);
                double lat = location.optDouble("lat", 0.0);
                double lon = location.optDouble("lon", 0.0);
                double maxKw = station.optDouble("max_power_kw", 0.0);
                double distanceKm = entry.optDouble("distance_km", 0.0);
                String dynamicStatus = optNullableString(station, "dynamic_status");
                Double price = station.isNull("dynamic_price_eur_kwh")
                        ? null
                        : station.optDouble("dynamic_price_eur_kwh");

                items.add(new CarStationItem(
                        id,
                        displayName,
                        operator,
                        address,
                        lat,
                        lon,
                        maxKw,
                        distanceKm,
                        dynamicStatus,
                        price));
            }
            return items;
        } catch (Exception exc) {
            throw new IOException("Error parseando estaciones cercanas", exc);
        }
    }

    @NonNull
    static CarReliabilityInfo parseReliability(@NonNull String rawJson) throws IOException {
        try {
            JSONObject obj = new JSONObject(rawJson);
            return new CarReliabilityInfo(
                    obj.optString("level", "medium"),
                    obj.optString("summary", "Estado no disponible"),
                    obj.optBoolean("isolated_area", false),
                    obj.optDouble("isolation_radius_km", 50.0),
                    obj.isNull("backup_station_km") ? null : obj.optDouble("backup_station_km"),
                    optNullableString(obj, "backup_station_label"),
                    obj.optBoolean("google_matched", false),
                    obj.isNull("google_available_count") ? null : obj.optInt("google_available_count"),
                    obj.isNull("google_total_connectors") ? null : obj.optInt("google_total_connectors"),
                    obj.isNull("google_out_of_service_count") ? null : obj.optInt("google_out_of_service_count"));
        } catch (Exception exc) {
            throw new IOException("Error parseando fiabilidad de estación", exc);
        }
    }

    @Nullable
    private static String optNullableString(@NonNull JSONObject obj, @NonNull String key) {
        if (obj.isNull(key)) {
            return null;
        }
        String value = obj.optString(key, "").trim();
        return value.isEmpty() ? null : value;
    }

    @NonNull
    private String getJson(@NonNull String urlString) throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(urlString).openConnection();
        try {
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(CONNECT_TIMEOUT_MS);
            conn.setReadTimeout(READ_TIMEOUT_MS);
            conn.setRequestProperty("Accept", "application/json");
            String token = prefs.getPrivateToken();
            if (token != null) {
                conn.setRequestProperty("X-Private-Token", token);
            }
            int code = conn.getResponseCode();
            InputStream stream = code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream();
            String body = readStream(stream);
            if (code < 200 || code >= 300) {
                throw new IOException("HTTP " + code + ": " + body);
            }
            return body;
        } finally {
            conn.disconnect();
        }
    }

    private void postJson(@NonNull String urlString, @NonNull String jsonBody, @NonNull String token)
            throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(urlString).openConnection();
        try {
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setConnectTimeout(CONNECT_TIMEOUT_MS);
            conn.setReadTimeout(READ_TIMEOUT_MS);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("X-Private-Token", token);
            byte[] payload = jsonBody.getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(payload);
            }
            int code = conn.getResponseCode();
            if (code < 200 || code >= 300) {
                String body = readStream(conn.getErrorStream());
                throw new IOException("HTTP " + code + ": " + body);
            }
        } finally {
            conn.disconnect();
        }
    }

    @NonNull
    private static String readStream(@Nullable InputStream stream) throws IOException {
        if (stream == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }
}
