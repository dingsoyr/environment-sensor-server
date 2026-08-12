const dashboardStatus = document.getElementById("dashboard-status");
const sensorGrid = document.getElementById("sensor-grid");
const batteryStatus = window.BatteryStatus;
const measurementColors = window.MeasurementColors;

const STATUS_BADGES = {
    synced: { label: "Synkronisert", className: "text-bg-success" },
    waiting_for_sensor: { label: "Ventar på sensor", className: "text-bg-warning" },
    device_ahead: { label: "Sensor framfor server", className: "text-bg-secondary" },
};

function formatNumber(value, unit) {
    if (value === null || value === undefined) {
        return { text: "Ukjend" };
    }

    return {
        number: value.toFixed(1),
        unit,
    };
}

function formatInteger(value, unit) {
    if (value === null || value === undefined) {
        return "Ukjend";
    }

    return `${Math.round(value)} ${unit}`;
}

function formatLastSeen(timestamp) {
    if (timestamp === null || timestamp === undefined) {
        return "Ikkje sett enno";
    }

    const date = new Date(timestamp * 1000);
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(date);
}

function hasBatteryPercent(sensor) {
    return sensor.battery_percent !== null && sensor.battery_percent !== undefined;
}

function formatBatteryVoltage(voltage) {
    if (voltage === null || voltage === undefined) {
        return "";
    }

    return `${voltage.toFixed(2)} V`;
}

function clearElement(element) {
    while (element.firstChild) {
        element.removeChild(element.firstChild);
    }
}

function setStatusMessage(node) {
    clearElement(dashboardStatus);
    dashboardStatus.appendChild(node);
}

function renderErrorState() {
    const alert = document.createElement("div");
    alert.className = "alert alert-danger";
    alert.role = "alert";
    alert.textContent = "Klarte ikkje å laste sensorane no.";
    setStatusMessage(alert);
}

function renderEmptyState() {
    const empty = document.createElement("div");
    empty.className = "alert alert-light border";
    empty.role = "status";
    empty.textContent = "Ingen sensorar er registrerte enno.";
    setStatusMessage(empty);
}

function createMeasurementTile(label, value, measurementType) {
    const column = document.createElement("div");
    column.className = "col d-flex";

    const tile = document.createElement("div");
    tile.className = "measurement-tile h-100";

    const labelElement = document.createElement("span");
    labelElement.className = "measurement-label";
    labelElement.textContent = label;

    const valueElement = document.createElement("span");
    valueElement.className = "measurement-value";

    if (value.text) {
        valueElement.textContent = value.text;
    } else {
        measurementColors.applyMeasurementValueColor(valueElement, measurementType);

        const numberElement = document.createElement("span");
        numberElement.className = "measurement-value-number";
        numberElement.textContent = value.number;

        const unitElement = document.createElement("span");
        unitElement.className = "measurement-value-unit";
        unitElement.textContent = value.unit;

        valueElement.appendChild(numberElement);
        valueElement.appendChild(unitElement);
    }

    tile.appendChild(labelElement);
    tile.appendChild(valueElement);
    column.appendChild(tile);
    return column;
}

function appendMetaRow(list, label, value) {
    const term = document.createElement("dt");
    term.textContent = label;

    const description = document.createElement("dd");
    if (typeof value === "string") {
        description.textContent = value;
    } else {
        description.className = "status-value";
        description.appendChild(value);
    }

    list.appendChild(term);
    list.appendChild(description);
}

function createBatteryStatusContent(sensor) {
    const status = batteryStatus.getStatus(sensor.battery_percent);
    const semanticClass = batteryStatus.getSemanticClass(sensor.battery_percent);
    const hasPercent = hasBatteryPercent(sensor);
    const wrapper = document.createElement("div");
    wrapper.className = "battery-status-block";
    wrapper.dataset.batteryStatus = status;

    const summary = document.createElement("div");
    summary.className = "battery-status-row";

    const icon = document.createElement("i");
    icon.className = `bi ${batteryStatus.getIconClass(sensor.battery_percent)} battery-status-icon text-${semanticClass}`;
    icon.setAttribute("aria-hidden", "true");

    const text = document.createElement("span");
    text.className = "battery-status-summary";

    const label = document.createElement("span");
    label.className = hasPercent ? `fw-medium text-${semanticClass}` : "fw-medium text-body-secondary";
    label.textContent = batteryStatus.getLabel(sensor.battery_percent);

    if (hasPercent) {
        const percent = document.createElement("span");
        percent.className = "fw-semibold";
        percent.textContent = `${sensor.battery_percent} %`;

        const separator = document.createElement("span");
        separator.className = "text-body-secondary";
        separator.setAttribute("aria-hidden", "true");
        separator.textContent = "·";

        text.appendChild(percent);
        text.appendChild(separator);
    }

    text.appendChild(label);

    summary.appendChild(icon);
    summary.appendChild(text);
    wrapper.appendChild(summary);

    const voltageText = formatBatteryVoltage(sensor.battery_voltage);
    if (voltageText) {
        const voltage = document.createElement("small");
        voltage.className = "battery-status-voltage text-body-secondary";
        voltage.textContent = voltageText;
        wrapper.appendChild(voltage);
    }

    return wrapper;
}

function createStatusBadge(state) {
    const config = STATUS_BADGES[state] ?? {
        label: "Ukjend status",
        className: "text-bg-secondary",
    };

    const badge = document.createElement("span");
    badge.className = `badge ${config.className}`;
    badge.textContent = config.label;
    return badge;
}

function createSensorCard(sensor) {
    const column = document.createElement("div");
    column.className = "col";

    const card = document.createElement("article");
    card.className = "card shadow-sm sensor-card";

    const body = document.createElement("div");
    body.className = "card-body";

    const header = document.createElement("div");

    const title = document.createElement("h2");
    title.className = "h4 card-title mb-1";
    title.textContent = sensor.device_name || sensor.device_id;

    const deviceId = document.createElement("p");
    deviceId.className = "text-body-secondary mb-2";
    deviceId.textContent = sensor.device_id;

    header.appendChild(title);
    header.appendChild(deviceId);
    header.appendChild(createStatusBadge(sensor.config_sync_state));

    body.appendChild(header);

    if (sensor.latest_measurement === null) {
        const noMeasurement = document.createElement("div");
        noMeasurement.className = "alert alert-light border mb-0";
        noMeasurement.role = "status";
        noMeasurement.textContent = "Ingen målingar enno";
        body.appendChild(noMeasurement);
    } else {
        const measurementSummary = document.createElement("div");
        measurementSummary.className = "measurement-summary row row-cols-3 g-0 g-sm-2";
        measurementSummary.appendChild(
            createMeasurementTile(
                "Temperatur",
                formatNumber(sensor.latest_measurement.temperature_c, "°C"),
                "temperature",
            ),
        );
        measurementSummary.appendChild(
            createMeasurementTile(
                "Luftfukt",
                formatNumber(sensor.latest_measurement.humidity_percent, "%"),
                "humidity",
            ),
        );
        measurementSummary.appendChild(
            createMeasurementTile(
                "Lufttrykk",
                formatNumber(sensor.latest_measurement.pressure_hpa, "hPa"),
                "pressure",
            ),
        );
        body.appendChild(measurementSummary);
    }

    const metaList = document.createElement("dl");
    metaList.className = "sensor-meta";
    appendMetaRow(metaList, "Sist sett", formatLastSeen(sensor.last_seen_at));
    appendMetaRow(metaList, "Signal", formatInteger(sensor.rssi_dbm, "dBm"));
    appendMetaRow(metaList, "Firmware", sensor.firmware_version || "Ukjend");
    appendMetaRow(metaList, "Batteri", createBatteryStatusContent(sensor));

    body.appendChild(metaList);

    const footer = document.createElement("div");
    footer.className = "card-footer border-0 pt-0";

    const link = document.createElement("a");
    link.className = "btn btn-outline-primary w-100";
    link.href = `/sensors/${encodeURIComponent(sensor.device_id)}`;
    link.textContent = "Sjå sensor";

    footer.appendChild(link);
    card.appendChild(body);
    card.appendChild(footer);
    column.appendChild(card);
    return column;
}

function renderSensors(sensors) {
    clearElement(sensorGrid);
    clearElement(dashboardStatus);

    sensors.forEach((sensor) => {
        sensorGrid.appendChild(createSensorCard(sensor));
    });
}

async function fetchSensors() {
    const response = await fetch("/api/dashboard/sensors", {
        headers: {
            Accept: "application/json",
        },
    });

    if (!response.ok) {
        throw new Error("Request failed");
    }

    return response.json();
}

async function initializeDashboard() {
    try {
        const payload = await fetchSensors();
        const sensors = Array.isArray(payload.sensors) ? payload.sensors : [];

        if (sensors.length === 0) {
            clearElement(sensorGrid);
            renderEmptyState();
            return;
        }

        renderSensors(sensors);
    } catch (error) {
        clearElement(sensorGrid);
        renderErrorState();
    }
}

initializeDashboard();