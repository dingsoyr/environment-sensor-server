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
    assert "/static/js/dashboard.js" in response.text
    assert "Oversikt over registrerte sensorar" in response.text


def test_dashboard_sensor_placeholder_page_returns_html(tmp_path: Path) -> None:
    database_path = tmp_path / "environment.db"

    with create_client(database_path) as client:
        response = client.get("/sensors/sensor-a")

    assert response.status_code == 200
    assert "Detaljsida for sensor-a kjem i neste milepåle." in response.text