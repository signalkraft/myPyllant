AUTH_BASE_URL = "https://identity.vaillant-group.com/auth/realms"
LOGIN_URL = AUTH_BASE_URL + "/{realm}/login-actions/authenticate"
AUTHENTICATE_URL = AUTH_BASE_URL + "/{realm}/protocol/openid-connect/auth"
TOKEN_URL = AUTH_BASE_URL + "/{realm}/protocol/openid-connect/token"
API_URL_BASE = {
    "tli": "https://api.vaillant-group.com/service-connected-control/end-user-app-api/v1",
    "vrc700": "https://api.vaillant-group.com/service-connected-control/vrc700/v1",
}
CLIENT_ID = "myvaillant"
BRANDS = {
    "vaillant": "Vaillant",
    "sdbg": "Saunier Duval",
    "bulex": "Bulex",
}
DEFAULT_BRAND = "vaillant"
COUNTRIES = {
    "vaillant": {
        "albania": "Albania",
        "austria": "Austria",
        "belgium": "Belgium",
        "bulgaria": "Bulgaria",
        "croatia": "Croatia",
        "czechrepublic": "Czechia",
        "denmark": "Denmark",
        "estonia": "Estonia",
        "finland": "Finland",
        "france": "France",
        "georgia": "Georgia",
        "germany": "Germany",
        "greece": "Greece",
        "hungary": "Hungary",
        "italy": "Italy",
        "latvia": "Latvia",
        "lithuania": "Lithuania",
        "luxembourg": "Luxembourg",
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
        "turkiye": "Turkiye",
        "ukraine": "Ukraine",
        "unitedkingdom": "United Kingdom",
        "uzbekistan": "Uzbekistan",
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
        "luxembourg": "Luxembourg",
        "poland": "Poland",
        "portugal": "Portugal",
        "romania": "Romania",
        "slovakia": "Slovakia",
        "spain": "Spain",
    },
}
ALL_COUNTRIES = {c: n for d in COUNTRIES.values() for c, n in d.items()}
ZONE_OPERATING_TYPES = {"heating", "cooling"}
ZONE_MANUAL_SETPOINT_TYPES = {v: v.title() for v in ZONE_OPERATING_TYPES}
DEFAULT_HOLIDAY_DURATION = 365  # in days
DEFAULT_MANUAL_SETPOINT_TYPE = "HEATING"
DEFAULT_QUICK_VETO_DURATION = 3.0  # in hours
DEFAULT_CONTROL_IDENTIFIER = "tli"
