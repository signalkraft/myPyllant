from tests.generate_test_data import _recursive_data_anonymize


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
                "deviceId": "ANONYMIZED",
                "serialNumber": "ANONYMIZED",
                "systemId": "ANONYMIZED",
                "diagnosticTroubleCodes": [],
            },
            "devices": [
                {
                    "deviceId": "ANONYMIZED",
                    "serialNumber": "ANONYMIZED",
                    "articleNumber": "0020260951",
                    "name": "sensoHOME",
                    "type": "CONTROL",
                    "systemId": "ANONYMIZED",
                    "diagnosticTroubleCodes": [],
                },
                {
                    "deviceId": "ANONYMIZED",
                    "serialNumber": "ANONYMIZED",
                    "articleNumber": "0010022040",
                    "name": "ecoTEC",
                    "type": "HEAT_GENERATOR",
                    "operationalData": {},
                    "systemId": "ANONYMIZED",
                    "diagnosticTroubleCodes": [],
                    "properties": [],
                },
            ],
            "status": {},
            "systemControlState": {},
            "systemConfiguration": {},
            "systemId": "ANONYMIZED",
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
            "device_uuid": "ANONYMIZED",
            "ebus_id": "BAI00",
            "spn": 376,
            "bus_coupler_address": 0,
            "article_number": "0010022040",
            "emfValid": True,
            "device_serial_number": "ANONYMIZED",
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
