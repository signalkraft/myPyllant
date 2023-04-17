from .generate_test_data import _recursive_data_anonymize


def test_anonymize_systems_data():
    original_systems_data = [
        {
            "gateway": {
                "deviceId": "PRIVATE_deviceId",
                "serialNumber": "PRIVATE_serialNumber",
                "systemId": "PRIVATE_systemId",
                "diagnosticTroubleCodes": [],
            },
            "devices": [
                {
                    "deviceId": "PRIVATE_deviceId",
                    "serialNumber": "PRIVATE_serialNumber",
                    "articleNumber": "0020260951",
                    "name": "sensoHOME",
                    "type": "CONTROL",
                    "systemId": "PRIVATE_systemId",
                    "diagnosticTroubleCodes": [],
                },
                {
                    "deviceId": "PRIVATE_deviceId",
                    "serialNumber": "PRIVATE_serialNumber",
                    "articleNumber": "0010022040",
                    "name": "ecoTEC",
                    "type": "HEAT_GENERATOR",
                    "operationalData": {},
                    "systemId": "PRIVATE_systemId",
                    "diagnosticTroubleCodes": [],
                    "properties": [],
                },
            ],
            "status": {},
            "systemControlState": {},
            "systemConfiguration": {},
            "systemId": "PRIVATE_systemId",
            "hasOwnership": True,
        }
    ]

    anonymized_data = _recursive_data_anonymize(original_systems_data)

    assert anonymized_data == [
        {
            "gateway": {
                "deviceId": "707e295cf73b49584939e3fe6e0a96713ca22800",
                "serialNumber": "f18bbf5a183946e978558a1556ed62c4cfb9dc5e",
                "systemId": "823c180c5c91bff1ab96e14d253aaa8218b511f4",
                "diagnosticTroubleCodes": [],
            },
            "devices": [
                {
                    "deviceId": "707e295cf73b49584939e3fe6e0a96713ca22800",
                    "serialNumber": "f18bbf5a183946e978558a1556ed62c4cfb9dc5e",
                    "articleNumber": "0020260951",
                    "name": "sensoHOME",
                    "type": "CONTROL",
                    "systemId": "823c180c5c91bff1ab96e14d253aaa8218b511f4",
                    "diagnosticTroubleCodes": [],
                },
                {
                    "deviceId": "707e295cf73b49584939e3fe6e0a96713ca22800",
                    "serialNumber": "f18bbf5a183946e978558a1556ed62c4cfb9dc5e",
                    "articleNumber": "0010022040",
                    "name": "ecoTEC",
                    "type": "HEAT_GENERATOR",
                    "operationalData": {},
                    "systemId": "823c180c5c91bff1ab96e14d253aaa8218b511f4",
                    "diagnosticTroubleCodes": [],
                    "properties": [],
                },
            ],
            "status": {},
            "systemControlState": {},
            "systemConfiguration": {},
            "systemId": "823c180c5c91bff1ab96e14d253aaa8218b511f4",
            "hasOwnership": True,
        }
    ]


def test_anonymize_current_system():
    original_current_system_data = {
        "system_type": "BOILER_OR_ELECTRIC_HEATER",
        "primary_heat_generator": {
            "device_uuid": "private_device_uuid",
            "ebus_id": "BAI00",
            "spn": 376,
            "bus_coupler_address": 0,
            "article_number": "0010022040",
            "emfValid": True,
            "device_serial_number": "private_device_serial_number",
            "device_type": "BOILER",
            "first_data": "2022-11-10T13:33:34Z",
            "last_data": "2023-02-28T13:20:31Z",
            "data": [],
            "product_name": "VMW 23CS/1-5 C (N-ES) ecoTEC plus",
        },
        "secondary_heat_generators": [],
        "electric_backup_heater": None,
        "solar_station": None,
        "ventilation": None,
    }

    anonymized_data = _recursive_data_anonymize(original_current_system_data)

    assert anonymized_data == {
        "system_type": "BOILER_OR_ELECTRIC_HEATER",
        "primary_heat_generator": {
            "device_uuid": "53be2a18985b87f5613e32a9ba44cc4ccbb4f6b4",
            "ebus_id": "BAI00",
            "spn": 376,
            "bus_coupler_address": 0,
            "article_number": "0010022040",
            "emfValid": True,
            "device_serial_number": "d97b53961ee397e2e9b1bb0cabff02949c360f4f",
            "device_type": "BOILER",
            "first_data": "2022-11-10T13:33:34Z",
            "last_data": "2023-02-28T13:20:31Z",
            "data": [],
            "product_name": "VMW 23CS/1-5 C (N-ES) ecoTEC plus",
        },
        "secondary_heat_generators": [],
        "electric_backup_heater": None,
        "solar_station": None,
        "ventilation": None,
    }
