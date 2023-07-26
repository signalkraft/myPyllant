LOGIN_URL = "https://identity.vaillant-group.com/auth/realms/{brand}-{country}-b2c/login-actions/authenticate"
AUTHENTICATE_URL = "https://identity.vaillant-group.com/auth/realms/{brand}-{country}-b2c/protocol/openid-connect/auth"
TOKEN_URL = "https://identity.vaillant-group.com/auth/realms/{brand}-{country}-b2c/protocol/openid-connect/token"
CLIENT_ID = "myvaillant"
API_URL_BASE = (
    "https://api.vaillant-group.com/service-connected-control/end-user-app-api/v1"
)
BRANDS = {
    "vaillant": "Vaillant",
    "sdbg": "Saunier Duval",
}
DEFAULT_BRAND = "vaillant"
COUNTRIES = {
    "vaillant": {
        "austria": "Austria",
        "belgium": "Belgium",
        "bulgaria": "Bulgaria",
        "croatia": "Croatia",
        "czechrepublic": "Czechia",
        "denmark": "Denmark",
        "estonia": "Estonia",
        "finland": "Finland",
        "france": "France",
        "germany": "Germany",
        "greece": "Greece",
        "hungary": "Hungary",
        "italy": "Italy",
        "latvia": "Latvia",
        "lithuania": "Lithuania",
        "netherlands": "Netherlands",
        "norway": "Norway",
        "poland": "Poland",
        "portugal": "Portugal",
        "romania": "Romania",
        "serbia": "Serbia",
        "slovakia": "Slovakia",
        "slovenia": "Slovenia",
        "spain": "Spain",
        "sweden": "Sweden",
        "switzerland": "Switzerland",
        "unitedkingdom": "United Kingdom",
    },
    "sdbg": {
        "austria": "Austria",
        "czechrepublic": "Czechia",
        "finland": "Finland",
        "france": "France",
        "greece": "Greece",
        "hungary": "Hungary",
        "italy": "Italy",
        "lithuania": "Lithuania",
        "poland": "Poland",
        "portugal": "Portugal",
        "romania": "Romania",
        "slovakia": "Slovakia",
        "spain": "Spain",
    },
}
MANUAL_SETPOINT_TYPES = {
    "HEATING": "Heating",
    "COOLING": "Cooling",
}
DEFAULT_MANUAL_SETPOINT_TYPE = "HEATING"
DEFAULT_QUICK_VETO_DURATION = 3
DEFAULT_CONTROL_IDENTIFIER = "tli"
