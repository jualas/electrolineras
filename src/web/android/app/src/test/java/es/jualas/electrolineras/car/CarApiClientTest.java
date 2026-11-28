package es.jualas.electrolineras.car;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.List;

import es.jualas.electrolineras.car.CarModels.CarReliabilityInfo;
import es.jualas.electrolineras.car.CarModels.CarStationItem;

public class CarApiClientTest {
    @Test
    public void parsesNearbyStationsJson() throws Exception {
        String sample = "{"
                + "\"results\": [{"
                + "  \"distance_km\": 3.4,"
                + "  \"station\": {"
                + "    \"id\": \"es-ionity-1\","
                + "    \"site_name\": \"Ionity Guadix\","
                + "    \"operator\": \"IONITY\","
                + "    \"max_power_kw\": 350.0,"
                + "    \"dynamic_status\": \"AVAILABLE\","
                + "    \"dynamic_price_eur_kwh\": 0.59,"
                + "    \"location\": {\"lat\": 37.30, \"lon\": -3.13, \"address\": \"A-92 km 292\"}"
                + "  }"
                + "}]}";

        List<CarStationItem> items = CarApiClient.parseNearbyStations(sample);
        assertEquals(1, items.size());
        CarStationItem first = items.get(0);
        assertEquals("es-ionity-1", first.id);
        assertEquals("Ionity Guadix", first.name);
        assertEquals(350.0, first.maxPowerKw, 0.01);
        assertEquals(3.4, first.distanceKm, 0.01);
        assertEquals("AVAILABLE", first.dynamicStatus);
    }

    @Test
    public void parsesReliabilityJson() throws Exception {
        String sample = "{"
                + "\"level\": \"medium\","
                + "\"summary\": \"Precaución (zona aislada)\","
                + "\"isolated_area\": true,"
                + "\"isolation_radius_km\": 50.0,"
                + "\"backup_station_km\": null,"
                + "\"backup_station_label\": null,"
                + "\"google_matched\": true,"
                + "\"google_available_count\": 2,"
                + "\"google_total_connectors\": 4,"
                + "\"google_out_of_service_count\": 1"
                + "}";

        CarReliabilityInfo info = CarApiClient.parseReliability(sample);
        assertEquals("medium", info.level);
        assertTrue(info.isolatedArea);
        assertTrue(info.googleMatched);
        assertEquals(Integer.valueOf(2), info.googleAvailableCount);
        assertEquals(Integer.valueOf(1), info.googleOutOfServiceCount);
    }
}
