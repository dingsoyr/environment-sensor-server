const MEASUREMENT_COLORS = {
    temperature: "#c4575a",
    humidity: "#4d8a57",
    pressure: "#7b62b3",
    battery: "#b8860b",
};

function getMeasurementColor(measurementType) {
    return MEASUREMENT_COLORS[measurementType] ?? null;
}

function applyMeasurementValueColor(element, measurementType) {
    const color = getMeasurementColor(measurementType);
    if (!color) {
        return;
    }

    element.style.color = color;
}

window.MeasurementColors = {
    getMeasurementColor,
    applyMeasurementValueColor,
};