from get_adapters_addresses import (
    AdapterFamily,
    ScanFlags,  # noqa: F401
    get_adapters_addresses,
)

adapters = get_adapters_addresses(
    adapter_families=AdapterFamily.INET,
    scan_flags=[ScanFlags.INCLUDE_PREFIX, ScanFlags.INCLUDE_ALL_INTERFACES],
)
n_adapters = len(adapters)
for idx, adapter in enumerate(adapters, start=1):
    print(adapter)
    # https://learn.microsoft.com/en-us/windows/win32/api/ifdef/ns-ifdef-net_luid_lh
    # correct_type = adapter.IfType in [6, 24, 71]
    if adapter.IfType == 6 and len(adapter.FirstUnicastAddress):
        print(f"\n{idx}/{n_adapters}: {adapter}")
    # print(
    #     f"{idx}/{n_adapters}: \n  interface_index={adapter.IfIndex}, \n  interface_name={adapter.Description}, \n  interface_guid={adapter.AdapterName}"
    # )
