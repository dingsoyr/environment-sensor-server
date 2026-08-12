from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def create_client(database_path: Path) -> TestClient:
    app = create_app(database_path)
    return TestClient(app)


def test_dashboard_home_page_returns_html_shell(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Miljøsensor" in response.text
    assert "Sensorar" in response.text
    assert "/static/css/dashboard.css" in response.text
    assert "/static/js/battery_status.js" in response.text
    assert "/static/js/measurement_colors.js" in response.text
    assert "/static/js/dashboard.js" in response.text
    assert "Oversikt over registrerte sensorar" in response.text


def test_dashboard_sensor_detail_page_returns_html_shell(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        response = client.get("/sensors/sensor-a")

    assert response.status_code == 200
    assert "Miljøsensor" in response.text
    assert "Sensorar" in response.text
    assert "Historikk" in response.text
    assert "Sensorstatus" in response.text
    assert "Konfigurasjon" in response.text
    assert "24 timar" in response.text
    assert "7 dagar" in response.text
    assert "30 dagar" in response.text
    assert "Periode" in response.text
    assert 'id="history-from-date"' in response.text
    assert 'id="history-to-date"' in response.text
    assert 'type="date"' in response.text
    assert "Frå" in response.text
    assert "Til" in response.text
    assert "Vis periode" in response.text
    assert 'id="history-custom-range"' in response.text
    assert "highcharts.js" in response.text
    assert "highcharts-more.js" in response.text
    assert "/static/js/battery_status.js" in response.text
    assert "/static/js/measurement_colors.js" in response.text
    assert "/static/js/sensor_detail.js" in response.text
    assert 'data-device-id="sensor-a"' in response.text


def test_dashboard_sensor_detail_page_escapes_device_id_in_html(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        response = client.get("/sensors/sensor-%3Cstrong%3E%22x%22%3Cstrong%3E")

    assert response.status_code == 200
    assert 'data-device-id="sensor-&lt;strong&gt;&#34;x&#34;&lt;strong&gt;"' in response.text
    assert 'data-device-id="sensor-<strong>"x"<strong>"' not in response.text


def test_dashboard_frontend_assets_include_shared_battery_hooks(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        helper_response = client.get("/static/js/battery_status.js")
        measurement_colors_response = client.get("/static/js/measurement_colors.js")
        dashboard_script_response = client.get("/static/js/dashboard.js")
        detail_script_response = client.get("/static/js/sensor_detail.js")
        css_response = client.get("/static/css/dashboard.css")

    assert helper_response.status_code == 200
    assert "okMinimumPercent: 50" in helper_response.text
    assert "lowMinimumPercent: 20" in helper_response.text
    assert 'label: "Batteristatus ukjend"' in helper_response.text
    assert "bi-battery-full" in helper_response.text
    assert "bi-battery-half" in helper_response.text
    assert 'iconClass: "bi-battery"' in helper_response.text

    assert measurement_colors_response.status_code == 200
    assert 'temperature: "#c4575a"' in measurement_colors_response.text
    assert 'humidity: "#4d8a57"' in measurement_colors_response.text
    assert 'pressure: "#7b62b3"' in measurement_colors_response.text
    assert "window.MeasurementColors" in measurement_colors_response.text
    assert "function applyMeasurementValueColor(element, measurementType)" in measurement_colors_response.text

    assert dashboard_script_response.status_code == 200
    assert "BatteryStatus" in dashboard_script_response.text
    assert "const measurementColors = window.MeasurementColors;" in dashboard_script_response.text
    assert "dataset.batteryStatus" in dashboard_script_response.text
    assert "batteryStatus.getLabel(sensor.battery_percent)" in dashboard_script_response.text
    assert 'appendMetaRow(metaList, "Batteri", createBatteryStatusContent(sensor));' in dashboard_script_response.text
    assert 'measurementSummary.className = "measurement-summary row row-cols-3 g-0 g-sm-2";' in dashboard_script_response.text
    assert 'unitElement.className = "measurement-value-unit";' in dashboard_script_response.text
    assert "measurementColors.applyMeasurementValueColor(valueElement, measurementType);" in dashboard_script_response.text
    assert '"temperature"' in dashboard_script_response.text
    assert '"humidity"' in dashboard_script_response.text
    assert '"pressure"' in dashboard_script_response.text
    assert "hasBatteryPercent(sensor) || hasBatteryVoltage(sensor)" not in dashboard_script_response.text

    assert detail_script_response.status_code == 200
    assert "BatteryStatus" in detail_script_response.text
    assert "const measurementColors = window.MeasurementColors;" in detail_script_response.text
    assert "battery-progress" in detail_script_response.text
    assert "progress-bar" in detail_script_response.text
    assert "aria-valuenow" in detail_script_response.text
    assert "if (hasPercent) {" in detail_script_response.text
    assert "batteryStatus.getLabel(detail.battery_percent)" in detail_script_response.text
    assert 'document.getElementById("history-custom-form")' in detail_script_response.text
    assert 'document.getElementById("history-from-date")' in detail_script_response.text
    assert 'document.getElementById("history-to-date")' in detail_script_response.text
    assert 'data-history-mode' in detail_script_response.text
    assert 'mode: "custom"' in detail_script_response.text
    assert 'type: "arearange"' in detail_script_response.text
    assert 'payload.resolution === "day"' in detail_script_response.text
    assert 'Frå-datoen kan ikkje vere etter Til-datoen.' in detail_script_response.text
    assert 'measurementColors.getMeasurementColor("temperature")' in detail_script_response.text
    assert 'measurementColors.getMeasurementColor("humidity")' in detail_script_response.text
    assert 'measurementColors.getMeasurementColor("pressure")' in detail_script_response.text
    assert 'measurementColors.applyMeasurementValueColor(valueElement, measurementType);' in detail_script_response.text
    assert "Highcharts.setOptions({" in detail_script_response.text
    assert "useUTC: false" in detail_script_response.text
    assert 'Highcharts.dateFormat("%e. %b %Y, %H:%M", this.x)' in detail_script_response.text
    assert 'color: CHARTS.temperature.color' in detail_script_response.text
    assert 'color: CHARTS.humidity.color' in detail_script_response.text
    assert 'color: CHARTS.pressure.color' in detail_script_response.text
    assert 'color: createChartRangeColor(chartConfig.color)' in detail_script_response.text
    assert 'color: chartConfig.color' in detail_script_response.text

    assert css_response.status_code == 200
    assert ".measurement-value-unit" in css_response.text
    assert ".measurement-summary > .col + .col .measurement-tile" in css_response.text
    assert "@media (min-width: 768px) and (max-width: 1199.98px)" in css_response.text
    assert "font-size: 1rem;" in css_response.text
    assert "white-space: nowrap;" in css_response.text
    assert ".battery-status-row" in css_response.text
    assert ".battery-progress" in css_response.text
    assert ".history-period-group" in css_response.text
    assert ".history-range-panel" in css_response.text