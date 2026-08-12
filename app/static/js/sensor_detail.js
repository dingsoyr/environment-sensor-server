const pageRoot = document.getElementById("sensor-detail-page");
const pageStatus = document.getElementById("sensor-page-status");
const pageContent = document.getElementById("sensor-page-content");
const sensorNameHeading = document.getElementById("sensor-name");
const sensorDeviceIdText = document.getElementById("sensor-device-id");
const sensorSyncBadge = document.getElementById("sensor-sync-badge");
const currentValues = document.getElementById("current-values");
const historyStatus = document.getElementById("history-status");
const historyEmpty = document.getElementById("history-empty");
const statusList = document.getElementById("sensor-status-list");
const configurationAlert = document.getElementById("configuration-alert");
const configurationForm = document.getElementById("configuration-form");
const deviceNameInput = document.getElementById("device-name-input");
const measurementIntervalInput = document.getElementById("measurement-interval-input");
const saveButton = document.getElementById("configuration-save-button");
const periodButtons = Array.from(document.querySelectorAll("[data-period]"));
const batteryStatus = window.BatteryStatus;

const STATUS_BADGES = {
    synced: { label: "Synkronisert", className: "text-bg-success" },
    waiting_for_sensor: { label: "Ventar på sensor", className: "text-bg-warning" },
    device_ahead: { label: "Sensor framfor server", className: "text-bg-secondary" },
};

const CHARTS = {
    temperature: {
        containerId: "temperature-chart",
        title: "Temperatur",
        valueKey: "temperature_c",
        unit: "°C",
    },
    humidity: {
        containerId: "humidity-chart",
        title: "Luftfukt",
        valueKey: "humidity_percent",
        unit: "%",
    },
    pressure: {
        containerId: "pressure-chart",
        title: "Lufttrykk",
        valueKey: "pressure_hpa",
        unit: "hPa",
    },
};

const deviceId = pageRoot ? pageRoot.dataset.deviceId || "" : "";

let sensorDetail = null;
let activePeriod = "24h";
let historyRequestId = 0;

function clearElement(element) {
    while (element.firstChild) {
        element.removeChild(element.firstChild);
    }
}

function createAlert(message, className, role = "alert") {
    const alert = document.createElement("div");
    alert.className = `alert ${className} mb-0`;
    alert.role = role;
    alert.textContent = message;
    return alert;
}

function setPageStatus(node) {
    clearElement(pageStatus);
    pageStatus.appendChild(node);
}

function setHistoryStatus(node) {
    clearElement(historyStatus);
    if (node) {
        historyStatus.appendChild(node);
    }
}

function setConfigurationAlert(node) {
    clearElement(configurationAlert);
    if (node) {
        configurationAlert.appendChild(node);
    }
}

function formatNumber(value, unit) {
    if (value === null || value === undefined) {
        return "Ingen målingar enno";
    }

    return `${value.toFixed(1)} ${unit}`;
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

    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(timestamp * 1000));
}

function hasBatteryPercent(sensor) {
    return sensor.battery_percent !== null && sensor.battery_percent !== undefined;
}

function hasBatteryVoltage(sensor) {
    return sensor.battery_voltage !== null && sensor.battery_voltage !== undefined;
}

function formatBatteryVoltage(voltage) {
    if (voltage === null || voltage === undefined) {
        return "";
    }

    return `${voltage.toFixed(2)} V`;
}

function createStatusBadge(state) {
    const config = STATUS_BADGES[state] ?? {
        label: "Ukjend status",
        className: "text-bg-secondary",
    };

    const badge = document.createElement("span");
    badge.className = `badge ${config.className} sensor-status-badge`;
    badge.textContent = config.label;
    return badge;
}

function createMeasurementTile(label, value) {
    const column = document.createElement("div");
    column.className = "col";

    const card = document.createElement("article");
    card.className = "card shadow-sm current-value-card";

    const body = document.createElement("div");
    body.className = "card-body";

    const labelElement = document.createElement("span");
    labelElement.className = "measurement-label";
    labelElement.textContent = label;

    const valueElement = document.createElement("span");
    valueElement.className = "measurement-value";
    valueElement.textContent = value;

    body.appendChild(labelElement);
    body.appendChild(valueElement);
    card.appendChild(body);
    column.appendChild(card);
    return column;
}

function appendMetaRow(list, label, content) {
    const term = document.createElement("dt");
    term.textContent = label;

    const description = document.createElement("dd");
    if (typeof content === "string") {
        description.textContent = content;
    } else {
        description.className = "status-value";
        description.appendChild(content);
    }

    list.appendChild(term);
    list.appendChild(description);
}

function appendBatterySummaryPart(container, text, className = "") {
    const part = document.createElement("span");
    if (className) {
        part.className = className;
    }
    part.textContent = text;
    container.appendChild(part);
}

function appendBatterySeparator(container) {
    const separator = document.createElement("span");
    separator.className = "text-body-secondary";
    separator.setAttribute("aria-hidden", "true");
    separator.textContent = "·";
    container.appendChild(separator);
}

function createBatteryStatusContent(detail) {
    const status = batteryStatus.getStatus(detail.battery_percent);
    const semanticClass = batteryStatus.getSemanticClass(detail.battery_percent);
    const label = batteryStatus.getLabel(detail.battery_percent);
    const hasPercent = hasBatteryPercent(detail);
    const safePercent = batteryStatus.clampPercent(detail.battery_percent);

    const wrapper = document.createElement("div");
    wrapper.className = "battery-status-block";
    wrapper.dataset.batteryStatus = status;

    const summary = document.createElement("div");
    summary.className = "battery-status-row";

    const icon = document.createElement("i");
    icon.className = `bi ${batteryStatus.getIconClass(detail.battery_percent)} battery-status-icon text-${semanticClass}`;
    icon.setAttribute("aria-hidden", "true");

    const summaryText = document.createElement("span");
    summaryText.className = "battery-status-summary";

    if (hasPercent) {
        appendBatterySummaryPart(summaryText, `${detail.battery_percent} %`, "fw-semibold");
    }

    const voltageText = formatBatteryVoltage(detail.battery_voltage);
    if (voltageText) {
        if (hasPercent) {
            appendBatterySeparator(summaryText);
        }
        appendBatterySummaryPart(summaryText, voltageText, "text-body-secondary");
    }

    if (hasPercent || voltageText) {
        appendBatterySeparator(summaryText);
    }

    appendBatterySummaryPart(
        summaryText,
        label,
        hasPercent ? `fw-medium text-${semanticClass}` : "fw-medium text-body-secondary",
    );

    summary.appendChild(icon);
    summary.appendChild(summaryText);
    wrapper.appendChild(summary);

    if (hasPercent) {
        const progress = document.createElement("div");
        progress.className = "progress battery-progress";

        const progressBar = document.createElement("div");
        progressBar.className = `progress-bar bg-${semanticClass}`;
        progressBar.role = "progressbar";
        progressBar.style.width = `${safePercent}%`;
        progressBar.setAttribute("aria-valuenow", String(safePercent));
        progressBar.setAttribute("aria-valuemin", "0");
        progressBar.setAttribute("aria-valuemax", "100");
        progressBar.setAttribute("aria-label", `Batterinivå ${detail.battery_percent} %, ${label}`);
        progressBar.textContent = `${detail.battery_percent} %`;

        progress.appendChild(progressBar);
        wrapper.appendChild(progress);
    }

    return wrapper;
}

function renderCurrentValues(latestMeasurement) {
    clearElement(currentValues);

    const measurement = latestMeasurement || {};

    currentValues.appendChild(
        createMeasurementTile("Temperatur", formatNumber(measurement.temperature_c, "°C")),
    );
    currentValues.appendChild(
        createMeasurementTile("Luftfukt", formatNumber(measurement.humidity_percent, "%")),
    );
    currentValues.appendChild(
        createMeasurementTile("Lufttrykk", formatNumber(measurement.pressure_hpa, "hPa")),
    );
}

function renderStatusSection(detail) {
    clearElement(statusList);

    appendMetaRow(statusList, "Sist sett", formatLastSeen(detail.last_seen_at));
    appendMetaRow(statusList, "Signal", formatInteger(detail.rssi_dbm, "dBm"));
    appendMetaRow(statusList, "Firmware", detail.firmware_version || "Ukjend");
    appendMetaRow(statusList, "Device ID", detail.device_id);

    if (hasBatteryPercent(detail) || hasBatteryVoltage(detail)) {
        appendMetaRow(statusList, "Batteri", createBatteryStatusContent(detail));
    } else {
        const batteryContent = createBatteryStatusContent(detail);
        appendMetaRow(statusList, "Batteri", batteryContent);
    }

    appendMetaRow(statusList, "Server config-versjon", String(detail.configuration.config_version));
    appendMetaRow(
        statusList,
        "Sensor rapportert config-versjon",
        String(detail.configuration.reported_config_version),
    );
    appendMetaRow(statusList, "Synkroniseringsstatus", createStatusBadge(detail.configuration.config_sync_state));
}

function renderSensorDetail(detail) {
    sensorDetail = detail;

    sensorNameHeading.textContent = detail.device_name || detail.device_id;
    sensorDeviceIdText.textContent = detail.device_id;

    clearElement(sensorSyncBadge);
    sensorSyncBadge.appendChild(createStatusBadge(detail.configuration.config_sync_state));

    renderCurrentValues(detail.latest_measurement);
    renderStatusSection(detail);

    deviceNameInput.value = detail.device_name || "";
    measurementIntervalInput.value = String(detail.configuration.measurement_interval_seconds);
}

function setPeriodButtonsDisabled(disabled) {
    periodButtons.forEach((button) => {
        button.disabled = disabled;
    });
}

function setActivePeriod(period) {
    activePeriod = period;

    periodButtons.forEach((button) => {
        const isActive = button.dataset.period === period;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
}

function renderChart(containerId, title, unit, points) {
    Highcharts.chart(containerId, {
        chart: {
            height: 280,
        },
        title: {
            text: null,
        },
        credits: {
            enabled: false,
        },
        legend: {
            enabled: false,
        },
        xAxis: {
            type: "datetime",
        },
        yAxis: {
            title: {
                text: unit,
            },
        },
        tooltip: {
            xDateFormat: "%e. %b %Y, %H:%M",
            pointFormatter() {
                return `<span>${title}: <b>${Highcharts.numberFormat(this.y, 1)} ${unit}</b></span>`;
            },
        },
        series: [
            {
                type: "line",
                data: points,
            },
        ],
        responsive: {
            rules: [
                {
                    condition: {
                        maxWidth: 575,
                    },
                    chartOptions: {
                        chart: {
                            height: 240,
                        },
                    },
                },
            ],
        },
    });
}

function renderHistory(points) {
    const seriesPoints = Object.values(CHARTS).reduce((accumulator, chartConfig) => {
        accumulator[chartConfig.valueKey] = points.map((point) => [
            point.measured_at * 1000,
            point[chartConfig.valueKey],
        ]);
        return accumulator;
    }, {});

    renderChart(
        CHARTS.temperature.containerId,
        CHARTS.temperature.title,
        CHARTS.temperature.unit,
        seriesPoints.temperature_c,
    );
    renderChart(
        CHARTS.humidity.containerId,
        CHARTS.humidity.title,
        CHARTS.humidity.unit,
        seriesPoints.humidity_percent,
    );
    renderChart(
        CHARTS.pressure.containerId,
        CHARTS.pressure.title,
        CHARTS.pressure.unit,
        seriesPoints.pressure_hpa,
    );

    historyEmpty.hidden = points.length !== 0;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);

    if (!response.ok) {
        const error = new Error("Request failed");
        error.status = response.status;

        try {
            error.payload = await response.json();
        } catch {
            error.payload = null;
        }

        throw error;
    }

    return response.json();
}

async function loadSensorDetail() {
    const encodedDeviceId = encodeURIComponent(deviceId);
    const detail = await fetchJson(`/api/dashboard/sensors/${encodedDeviceId}`, {
        headers: { Accept: "application/json" },
    });

    renderSensorDetail(detail);
    clearElement(pageStatus);
    pageContent.hidden = false;
}

async function loadHistory(period) {
    const requestId = historyRequestId + 1;
    historyRequestId = requestId;

    setActivePeriod(period);
    setPeriodButtonsDisabled(true);
    setHistoryStatus(createAlert("Lastar historikk...", "alert-light border", "status"));
    historyEmpty.hidden = true;

    try {
        const encodedDeviceId = encodeURIComponent(deviceId);
        const payload = await fetchJson(
            `/api/dashboard/sensors/${encodedDeviceId}/history?period=${encodeURIComponent(period)}`,
            {
                headers: { Accept: "application/json" },
            },
        );

        if (requestId !== historyRequestId) {
            return;
        }

        renderHistory(Array.isArray(payload.points) ? payload.points : []);
        setHistoryStatus(null);
    } catch (error) {
        if (requestId !== historyRequestId) {
            return;
        }

        setHistoryStatus(createAlert("Klarte ikkje å laste historikken no.", "alert-danger"));
    } finally {
        if (requestId === historyRequestId) {
            setPeriodButtonsDisabled(false);
        }
    }
}

function getConfigurationPayload() {
    return {
        device_name: deviceNameInput.value,
        measurement_interval_seconds: Number.parseInt(measurementIntervalInput.value, 10),
    };
}

function getConfigurationSuccessMessage(configuration) {
    if (configuration.config_sync_state === "waiting_for_sensor") {
        return "Konfigurasjonen er lagra på serveren og blir sendt til sensoren neste gong han kontaktar serveren.";
    }

    return "Konfigurasjonen er oppdatert.";
}

function applyConfigurationResponse(configuration) {
    if (!sensorDetail) {
        return;
    }

    sensorDetail.device_name = configuration.device_name;
    sensorDetail.configuration.measurement_interval_seconds = configuration.measurement_interval_seconds;
    sensorDetail.configuration.config_version = configuration.config_version;
    sensorDetail.configuration.reported_config_version = configuration.reported_config_version;
    sensorDetail.configuration.config_sync_state = configuration.config_sync_state;

    renderSensorDetail(sensorDetail);
}

async function submitConfiguration(event) {
    event.preventDefault();

    setConfigurationAlert(null);
    saveButton.disabled = true;

    try {
        const encodedDeviceId = encodeURIComponent(deviceId);
        const payload = getConfigurationPayload();
        const response = await fetchJson(`/api/dashboard/sensors/${encodedDeviceId}/configuration`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(payload),
        });

        applyConfigurationResponse(response);
        setConfigurationAlert(createAlert(getConfigurationSuccessMessage(response), "alert-success"));
    } catch (error) {
        const message = error.status === 404
            ? "Fann ikkje sensoren."
            : "Klarte ikkje å lagre konfigurasjonen. Kontroller felta og prøv igjen.";
        setConfigurationAlert(createAlert(message, "alert-danger"));
    } finally {
        saveButton.disabled = false;
    }
}

function renderNotFoundState() {
    pageContent.hidden = true;
    setPageStatus(createAlert("Fann ikkje sensoren du bad om.", "alert-warning"));
}

function renderPageErrorState() {
    pageContent.hidden = true;
    setPageStatus(createAlert("Klarte ikkje å laste sensoren no.", "alert-danger"));
}

async function initializeSensorDetailPage() {
    if (!pageRoot || !deviceId) {
        return;
    }

    try {
        await loadSensorDetail();
        await loadHistory(activePeriod);
    } catch (error) {
        if (error.status === 404) {
            renderNotFoundState();
            return;
        }

        renderPageErrorState();
    }
}

periodButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const nextPeriod = button.dataset.period;
        if (!nextPeriod || nextPeriod === activePeriod) {
            return;
        }

        void loadHistory(nextPeriod);
    });
});

configurationForm.addEventListener("submit", (event) => {
    void submitConfiguration(event);
});

void initializeSensorDetailPage();