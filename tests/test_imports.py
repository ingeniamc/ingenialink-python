def test_exported_comms_symbols():
    import ingenialink

    expected_attrs = []

    for obj_type in ["Network", "Servo", "Dictionary", "Register", "DictionaryV2", "DictionaryV3"]:
        expected_attrs.extend(
            f"{comm_type}{obj_type}"
            for comm_type in [
                "Ethercat",
                "Ethernet",
                "Canopen",
                "",  # Generic
            ]
        )
    all_attrs = set(getattr(ingenialink, "__all__", []))
    for attr in expected_attrs:
        assert attr in all_attrs, f"{attr} missing from ingenialink.__all__"
        assert hasattr(ingenialink, attr), f"ingenialink missing {attr} in __init__"
