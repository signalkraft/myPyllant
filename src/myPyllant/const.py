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
}
