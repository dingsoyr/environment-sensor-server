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
    assert "Environment Sensor" in response.text
    assert "Sensorar" in response.text
    assert "/static/css/dashboard.css" in response.text
    assert "/static/js/battery_status.js" in response.text
    assert "/static/js/dashboard.js" in response.text
    assert "Oversikt over registrerte sensorar" in response.text


def test_dashboard_sensor_detail_page_returns_html_shell(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        response = client.get("/sensors/sensor-a")

    assert response.status_code == 200
    assert "Environment Sensor" in response.text
    assert "Sensorar" in response.text
    assert "Historikk" in response.text
    assert "Sensorstatus" in response.text
    assert "Konfigurasjon" in response.text
    assert "highcharts.js" in response.text
    assert "/static/js/battery_status.js" in response.text
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
        dashboard_script_response = client.get("/static/js/dashboard.js")
        detail_script_response = client.get("/static/js/sensor_detail.js")
        css_response = client.get("/static/css/dashboard.css")

    assert helper_response.status_code == 200
    assert "okMinimumPercent: 50" in helper_response.text
    assert "lowMinimumPercent: 20" in helper_response.text
    assert "bi-battery-full" in helper_response.text
    assert "bi-battery-half" in helper_response.text
    assert 'iconClass: "bi-battery"' in helper_response.text

    assert dashboard_script_response.status_code == 200
    assert "BatteryStatus" in dashboard_script_response.text
    assert "dataset.batteryStatus" in dashboard_script_response.text

    assert detail_script_response.status_code == 200
    assert "BatteryStatus" in detail_script_response.text
    assert "battery-progress" in detail_script_response.text
    assert "progress-bar" in detail_script_response.text
    assert "aria-valuenow" in detail_script_response.text

    assert css_response.status_code == 200
    assert ".battery-status-row" in css_response.text
    assert ".battery-progress" in css_response.text