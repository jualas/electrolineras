package es.jualas.electrolineras.car;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

/** Modelos de datos ligeros para las pantallas de Android Auto / AAOS. */
public final class CarModels {
    private CarModels() {}

    public static final class CarStationItem {
        @NonNull public final String id;
        @NonNull public final String name;
        @Nullable public final String operator;
        @Nullable public final String address;
        public final double lat;
        public final double lon;
        public final double maxPowerKw;
        public final double distanceKm;
        @Nullable public final String dynamicStatus;
        @Nullable public final Double priceEurKwh;

        public CarStationItem(
                @NonNull String id,
                @NonNull String name,
                @Nullable String operator,
                @Nullable String address,
                double lat,
                double lon,
                double maxPowerKw,
                double distanceKm,
                @Nullable String dynamicStatus,
                @Nullable Double priceEurKwh) {
            this.id = id;
            this.name = name;
            this.operator = operator;
            this.address = address;
            this.lat = lat;
            this.lon = lon;
            this.maxPowerKw = maxPowerKw;
            this.distanceKm = distanceKm;
            this.dynamicStatus = dynamicStatus;
            this.priceEurKwh = priceEurKwh;
        }
    }

    public static final class CarReliabilityInfo {
        @NonNull public final String level;
        @NonNull public final String summary;
        public final boolean isolatedArea;
        public final double isolationRadiusKm;
        @Nullable public final Double backupStationKm;
        @Nullable public final String backupStationLabel;
        public final boolean googleMatched;
        @Nullable public final Integer googleAvailableCount;
        @Nullable public final Integer googleTotalConnectors;
        @Nullable public final Integer googleOutOfServiceCount;

        public CarReliabilityInfo(
                @NonNull String level,
                @NonNull String summary,
                boolean isolatedArea,
                double isolationRadiusKm,
                @Nullable Double backupStationKm,
                @Nullable String backupStationLabel,
                boolean googleMatched,
                @Nullable Integer googleAvailableCount,
                @Nullable Integer googleTotalConnectors,
                @Nullable Integer googleOutOfServiceCount) {
            this.level = level;
            this.summary = summary;
            this.isolatedArea = isolatedArea;
            this.isolationRadiusKm = isolationRadiusKm;
            this.backupStationKm = backupStationKm;
            this.backupStationLabel = backupStationLabel;
            this.googleMatched = googleMatched;
            this.googleAvailableCount = googleAvailableCount;
            this.googleTotalConnectors = googleTotalConnectors;
            this.googleOutOfServiceCount = googleOutOfServiceCount;
        }
    }

    public static final class CarTelemetrySnapshot {
        @Nullable public final Float batteryPercent;
        @Nullable public final Float rangeRemainingKm;
        @Nullable public final String modelLabel;

        public CarTelemetrySnapshot(
                @Nullable Float batteryPercent,
                @Nullable Float rangeRemainingKm,
                @Nullable String modelLabel) {
            this.batteryPercent = batteryPercent;
            this.rangeRemainingKm = rangeRemainingKm;
            this.modelLabel = modelLabel;
        }
    }
}
