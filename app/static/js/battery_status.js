(function () {
    const STATUS_CONFIG = {
        ok: {
            label: "Batteri OK",
            semanticClass: "success",
            iconClass: "bi-battery-full",
        },
        low: {
            label: "Lågt batteri",
            semanticClass: "warning",
            iconClass: "bi-battery-half",
        },
        critical: {
            label: "Kritisk batterinivå",
            semanticClass: "danger",
            iconClass: "bi-battery",
        },
        unknown: {
            label: "Batteristatus ukjend",
            semanticClass: "secondary",
            iconClass: "bi-battery",
        },
    };

    function getStatus(percent) {
        if (percent === null || percent === undefined) {
            return "unknown";
        }

        if (percent >= 50) {
            return "ok";
        }

        if (percent >= 20) {
            return "low";
        }

        return "critical";
    }

    function clampPercent(percent) {
        if (percent === null || percent === undefined || Number.isNaN(percent)) {
            return 0;
        }

        return Math.max(0, Math.min(100, percent));
    }

    function getConfig(percent) {
        return STATUS_CONFIG[getStatus(percent)];
    }

    window.BatteryStatus = {
        thresholds: {
            okMinimumPercent: 50,
            lowMinimumPercent: 20,
        },
        getStatus,
        clampPercent,
        getSemanticClass(percent) {
            return getConfig(percent).semanticClass;
        },
        getLabel(percent) {
            return getConfig(percent).label;
        },
        getIconClass(percent) {
            return getConfig(percent).iconClass;
        },
    };
})();