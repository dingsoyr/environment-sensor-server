const pageRoot = document.getElementById("sensor-detail-page");
const pageStatus = document.getElementById("sensor-page-status");
const pageContent = document.getElementById("sensor-page-content");
const sensorNameHeading = document.getElementById("sensor-name");
const sensorDeviceIdText = document.getElementById("sensor-device-id");
const sensorSyncBadge = document.getElementById("sensor-sync-badge");
const currentValues = document.getElementById("current-values");
const historyStatus = document.getElementById("history-status");
const historyEmpty = document.getElementById("history-empty");
const historyCustomRange = document.getElementById("history-custom-range");
const historyCustomForm = document.getElementById("history-custom-form");
const historyFromInput = document.getElementById("history-from-date");
const historyToInput = document.getElementById("history-to-date");
const historyCustomSubmit = document.getElementById("history-custom-submit");
const statusList = document.getElementById("sensor-status-list");
const configurationAlert = document.getElementById("configuration-alert");
const configurationForm = document.getElementById("configuration-form");
const deviceNameInput = document.getElementById("device-name-input");
const measurementIntervalInput = document.getElementById("measurement-interval-input");
const saveButton = document.getElementById("configuration-save-button");
const periodButtons = Array.from(document.querySelectorAll("[data-period]"));
const historyModeButtons = Array.from(document.querySelectorAll("[data-history-mode]"));
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
        rawValueKey: "temperature_c",
        averageValueKey: "temperature_avg_c",
        minimumValueKey: "temperature_min_c",
        maximumValueKey: "temperature_max_c",
        unit: "°C",
    },
    humidity: {
        containerId: "humidity-chart",
        title: "Luftfukt",
        rawValueKey: "humidity_percent",
        averageValueKey: "humidity_avg_percent",
        minimumValueKey: "humidity_min_percent",
        maximumValueKey: "humidity_max_percent",
        unit: "%",
    },
    pressure: {
        containerId: "pressure-chart",
        title: "Lufttrykk",
        rawValueKey: "pressure_hpa",
        averageValueKey: "pressure_avg_hpa",
        minimumValueKey: "pressure_min_hpa",
        maximumValueKey: "pressure_max_hpa",
        unit: "hPa",
    },
};

const deviceId = pageRoot ? pageRoot.dataset.deviceId || "" : "";

let sensorDetail = null;
let activeHistoryMode = "period";
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

function setHistoryControlsDisabled(disabled) {
    historyModeButtons.forEach((button) => {
        button.disabled = disabled;
    });

    if (historyFromInput) {
        historyFromInput.disabled = disabled;
    }

    if (historyToInput) {
        historyToInput.disabled = disabled;
    }

    if (historyCustomSubmit) {
        historyCustomSubmit.disabled = disabled;
    }
}

function updateHistoryModeButtons() {
    historyModeButtons.forEach((button) => {
        const isPeriodButton = button.dataset.historyMode === "period";
        const isActive = isPeriodButton
            ? activeHistoryMode === "period" && button.dataset.period === activePeriod
            : activeHistoryMode === "custom";
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");

        if (!isPeriodButton) {
            button.setAttribute("aria-expanded", activeHistoryMode === "custom" ? "true" : "false");
        }
    });
}

function setActiveFixedPeriod(period) {
    activeHistoryMode = "period";
    activePeriod = period;
    if (historyCustomRange) {
        historyCustomRange.hidden = true;
    }
    updateHistoryModeButtons();
}

function setCustomHistoryModeActive() {
    activeHistoryMode = "custom";
    if (historyCustomRange) {
        historyCustomRange.hidden = false;
    }
    updateHistoryModeButtons();
}

function formatDateInputValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function ensureCustomDateDefaults() {
    if (!historyFromInput || !historyToInput) {
        return;
    }

    if (historyFromInput.value && historyToInput.value) {
        return;
    }

    const today = new Date();
    const fromDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    fromDate.setFullYear(fromDate.getFullYear() - 1);

    historyFromInput.value = formatDateInputValue(fromDate);
    historyToInput.value = formatDateInputValue(today);
}

function parseLocalDateInput(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) {
        return null;
    }

    const year = Number.parseInt(match[1], 10);
    const monthIndex = Number.parseInt(match[2], 10) - 1;
    const day = Number.parseInt(match[3], 10);
    const date = new Date(year, monthIndex, day);

    if (
        date.getFullYear() !== year
        || date.getMonth() !== monthIndex
        || date.getDate() !== day
    ) {
        return null;
    }

    return date;
}

function createCustomHistoryRequest() {
    const fromValue = historyFromInput ? historyFromInput.value : "";
    const toValue = historyToInput ? historyToInput.value : "";

    if (!fromValue || !toValue) {
        return { error: "Vel både Frå og Til før du viser perioden." };
    }

    const fromDate = parseLocalDateInput(fromValue);
    const toDate = parseLocalDateInput(toValue);

    if (!fromDate || !toDate) {
        return { error: "Vel gyldige datoar for Frå og Til." };
    }

    if (fromDate.getTime() > toDate.getTime()) {
        return { error: "Frå-datoen kan ikkje vere etter Til-datoen." };
    }

    const toExclusiveDate = new Date(toDate.getFullYear(), toDate.getMonth(), toDate.getDate() + 1);

    return {
        request: {
            mode: "custom",
            from: Math.floor(fromDate.getTime() / 1000),
            to: Math.floor(toExclusiveDate.getTime() / 1000),
        },
    };
}

function createRawSeries(points, valueKey) {
    return points.map((point) => [
        point.measured_at * 1000,
        point[valueKey],
    ]);
}

function createAggregateAverageSeries(points, valueKey) {
    return points.map((point) => [
        point.period_start * 1000,
        point[valueKey],
    ]);
}

function createAggregateRangeSeries(points, minimumKey, maximumKey) {
    return points.map((point) => [
        point.period_start * 1000,
        point[minimumKey],
        point[maximumKey],
    ]);
}

function buildTooltipOptions(title, unit, resolution) {
    if (resolution === "day") {
        return {
            shared: true,
            formatter() {
                const averagePoint = this.points.find(
                    (point) => point.series.userOptions.custom?.kind === "average",
                );
                const rangePoint = this.points.find(
                    (point) => point.series.userOptions.custom?.kind === "range",
                );

                const parts = [
                    `<span>${Highcharts.dateFormat("%e. %b %Y", this.x)}</span>`,
                ];

                if (averagePoint) {
                    parts.push(
                        `<br><span>${title}, gjennomsnitt: <b>${Highcharts.numberFormat(averagePoint.y, 1)} ${unit}</b></span>`,
                    );
                }

                if (rangePoint) {
                    parts.push(
                        `<br><span>${title}, minimum: <b>${Highcharts.numberFormat(rangePoint.point.low, 1)} ${unit}</b></span>`,
                    );
                    parts.push(
                        `<br><span>${title}, maksimum: <b>${Highcharts.numberFormat(rangePoint.point.high, 1)} ${unit}</b></span>`,
                    );
                }

                return parts.join("");
            },
        };
    }

    return {
        xDateFormat: "%e. %b %Y, %H:%M",
        pointFormatter() {
            return `<span>${title}: <b>${Highcharts.numberFormat(this.y, 1)} ${unit}</b></span>`;
        },
    };
}

function renderChart(containerId, title, unit, series, resolution) {
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
        tooltip: buildTooltipOptions(title, unit, resolution),
        series,
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

function renderRawHistory(points) {
    renderChart(
        CHARTS.temperature.containerId,
        CHARTS.temperature.title,
        CHARTS.temperature.unit,
        [
            {
                type: "line",
                data: createRawSeries(points, CHARTS.temperature.rawValueKey),
            },
        ],
        "raw",
    );
    renderChart(
        CHARTS.humidity.containerId,
        CHARTS.humidity.title,
        CHARTS.humidity.unit,
        [
            {
                type: "line",
                data: createRawSeries(points, CHARTS.humidity.rawValueKey),
            },
        ],
        "raw",
    );
    renderChart(
        CHARTS.pressure.containerId,
        CHARTS.pressure.title,
        CHARTS.pressure.unit,
        [
            {
                type: "line",
                data: createRawSeries(points, CHARTS.pressure.rawValueKey),
            },
        ],
        "raw",
    );

    historyEmpty.hidden = points.length !== 0;
}

function createAggregateSeries(chartConfig, points) {
    return [
        {
            type: "arearange",
            name: `${chartConfig.title} spenn`,
            data: createAggregateRangeSeries(
                points,
                chartConfig.minimumValueKey,
                chartConfig.maximumValueKey,
            ),
            fillOpacity: 0.12,
            lineWidth: 0,
            marker: {
                enabled: false,
            },
            zIndex: 0,
            custom: {
                kind: "range",
            },
        },
        {
            type: "line",
            name: `${chartConfig.title} gjennomsnitt`,
            data: createAggregateAverageSeries(points, chartConfig.averageValueKey),
            lineWidth: 2,
            marker: {
                enabled: false,
            },
            zIndex: 1,
            custom: {
                kind: "average",
            },
        },
    ];
}

function renderAggregatedHistory(points) {
    renderChart(
        CHARTS.temperature.containerId,
        CHARTS.temperature.title,
        CHARTS.temperature.unit,
        createAggregateSeries(CHARTS.temperature, points),
        "day",
    );
    renderChart(
        CHARTS.humidity.containerId,
        CHARTS.humidity.title,
        CHARTS.humidity.unit,
        createAggregateSeries(CHARTS.humidity, points),
        "day",
    );
    renderChart(
        CHARTS.pressure.containerId,
        CHARTS.pressure.title,
        CHARTS.pressure.unit,
        createAggregateSeries(CHARTS.pressure, points),
        "day",
    );

    historyEmpty.hidden = points.length !== 0;
}

function renderHistoryPayload(payload) {
    const points = Array.isArray(payload.points) ? payload.points : [];

    if (payload.resolution === "day") {
        renderAggregatedHistory(points);
        return;
    }

    renderRawHistory(points);
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

function buildHistoryUrl(request) {
    const encodedDeviceId = encodeURIComponent(deviceId);

    if (request.mode === "custom") {
        const params = new URLSearchParams({
            from: String(request.from),
            to: String(request.to),
        });
        return `/api/dashboard/sensors/${encodedDeviceId}/history?${params.toString()}`;
    }

    return `/api/dashboard/sensors/${encodedDeviceId}/history?period=${encodeURIComponent(request.period)}`;
}

async function loadHistory(request) {
    const requestId = historyRequestId + 1;
    historyRequestId = requestId;

    setHistoryControlsDisabled(true);
    setHistoryStatus(createAlert("Lastar historikk...", "alert-light border", "status"));
    historyEmpty.hidden = true;

    try {
        const payload = await fetchJson(buildHistoryUrl(request), {
            headers: { Accept: "application/json" },
        });

        if (requestId !== historyRequestId) {
            return;
        }

        renderHistoryPayload(payload);
        setHistoryStatus(null);
    } catch (error) {
        if (requestId !== historyRequestId) {
            return;
        }

        setHistoryStatus(createAlert("Klarte ikkje å laste historikken no.", "alert-danger"));
    } finally {
        if (requestId === historyRequestId) {
            setHistoryControlsDisabled(false);
        }
    }
}

async function applyFixedPeriod(period) {
    setActiveFixedPeriod(period);
    await loadHistory({ mode: "period", period });
}

async function submitCustomHistoryRange(event) {
    event.preventDefault();

    const customRequestResult = createCustomHistoryRequest();
    if (customRequestResult.error) {
        setHistoryStatus(createAlert(customRequestResult.error, "alert-warning py-2"));
        return;
    }

    setCustomHistoryModeActive();
    await loadHistory(customRequestResult.request);
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
        await applyFixedPeriod(activePeriod);
    } catch (error) {
        if (error.status === 404) {
            renderNotFoundState();
            return;
        }

        renderPageErrorState();
    }
}

historyModeButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const nextMode = button.dataset.historyMode;

        if (nextMode === "custom") {
            ensureCustomDateDefaults();
            setCustomHistoryModeActive();
            setHistoryStatus(null);
            return;
        }

        const nextPeriod = button.dataset.period;
        if (!nextPeriod || (activeHistoryMode === "period" && nextPeriod === activePeriod)) {
            return;
        }

        void applyFixedPeriod(nextPeriod);
    });
});

historyCustomForm.addEventListener("submit", (event) => {
    void submitCustomHistoryRange(event);
});

configurationForm.addEventListener("submit", (event) => {
    void submitConfiguration(event);
});

void initializeSensorDetailPage();