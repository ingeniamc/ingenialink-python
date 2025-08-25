cimport ingenialink.cython_files.CyGetAdaptersAddresses
from ingenialink.cython_files.CyGetAdaptersAddresses cimport (
    WCHAR,
    SOCKET_ADDRESS,
    IP_ADAPTER_UNICAST_ADDRESS_LH,
    IP_ADAPTER_ANYCAST_ADDRESS_XP,
    IP_ADAPTER_MULTICAST_ADDRESS_XP,
    IP_ADAPTER_DNS_SERVER_ADDRESS_XP,
    IP_ADAPTER_WINS_SERVER_ADDRESS_LH,
    IP_ADAPTER_GATEWAY_ADDRESS_LH,
    IP_ADAPTER_PREFIX_XP,
    IP_ADAPTER_DNS_SUFFIX,
    NET_IF_NETWORK_GUID,
    PIP_ADAPTER_ADDRESSES_LH,
    PIP_ADAPTER_UNICAST_ADDRESS_LH,
    PIP_ADAPTER_ANYCAST_ADDRESS_XP,
    PIP_ADAPTER_MULTICAST_ADDRESS_XP,
    MAX_DNS_SUFFIX_STRING_LENGTH,
    GetAdaptersAddresses,
)

from libc.stdlib cimport malloc, free
import dataclasses
import cython
from libc.string cimport strlen
from libc.stddef cimport wchar_t
from libc.stdint cimport uint16_t, uint32_t, uint8_t, int32_t, uint64_t
from cpython.unicode cimport PyUnicode_FromWideChar
import logging

_MAX_TRIES = 3
_WORKING_BUFFER_SIZE = 15000

logger = logging.getLogger(__name__)

cdef extern from "winerror.h":
    enum:
        ERROR_BUFFER_OVERFLOW
        ERROR_NO_DATA
        NO_ERROR

cdef extern from "winsock2.h":
    enum:
        # https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersaddresses#parameters
        AF_INET
        AF_INET6
        AF_UNSPEC
        GAA_FLAG_SKIP_UNICAST
        GAA_FLAG_SKIP_ANYCAST
        GAA_FLAG_SKIP_MULTICAST
        GAA_FLAG_SKIP_DNS_SERVER
        GAA_FLAG_INCLUDE_PREFIX
        GAA_FLAG_SKIP_FRIENDLY_NAME
        GAA_FLAG_INCLUDE_WINS_INFO
        GAA_FLAG_INCLUDE_GATEWAYS
        GAA_FLAG_INCLUDE_ALL_INTERFACES
        GAA_FLAG_INCLUDE_ALL_COMPARTMENTS
        GAA_FLAG_INCLUDE_TUNNEL_BINDINGORDER

cpdef enum AdapterFamily:
    INET = AF_INET
    INET6 = AF_INET6
    UNSPEC = AF_UNSPEC

cpdef enum ScanFlags:
    SKIP_UNICAST = GAA_FLAG_SKIP_UNICAST
    SKIP_ANYCAST = GAA_FLAG_SKIP_ANYCAST
    SKIP_MULTICAST = GAA_FLAG_SKIP_MULTICAST
    SKIP_DNS_SERVER = GAA_FLAG_SKIP_DNS_SERVER
    INCLUDE_PREFIX = GAA_FLAG_INCLUDE_PREFIX
    SKIP_FRIENDLY_NAME = GAA_FLAG_SKIP_FRIENDLY_NAME
    INCLUDE_WINS_INFO = GAA_FLAG_INCLUDE_WINS_INFO
    INCLUDE_GATEWAYS = GAA_FLAG_INCLUDE_GATEWAYS
    INCLUDE_ALL_INTERFACES = GAA_FLAG_INCLUDE_ALL_INTERFACES
    INCLUDE_ALL_COMPARTMENTS = GAA_FLAG_INCLUDE_ALL_COMPARTMENTS
    INCLUDE_TUNNEL_BINDINGORDER = GAA_FLAG_INCLUDE_TUNNEL_BINDINGORDER

@cython.cclass
@dataclasses.dataclass
class CylpSockaddr:
    sa_family: int | None
    sa_data: bytes | None

    def __init__(self, sa_family: int | None, sa_data: bytes | None):        
        self.sa_family = sa_family
        if sa_data is not None and len(sa_data) != 14:
            raise ValueError("sa_data must be exactly 14 bytes long")
        self.sa_data = sa_data

@cython.cclass
@dataclasses.dataclass
class CySocketAddress:
    lpSockaddr: CylpSockaddr
    iSockaddrLength: int

@cython.cclass
@dataclasses.dataclass
class CyFirstUnicastAddress:
    Alignment: int
    Length: int
    Flags: int
    Address: CySocketAddress
    PrefixOrigin: int
    SuffixOrigin: int
    DadState: int
    ValidLifetime: int
    PreferredLifetime: int
    LeaseLifetime: int
    OnLinkPrefixLength: int

@cython.cclass
@dataclasses.dataclass
class CyFirstAnycastMulticastAddress:
    Alignment: int
    Length: int
    Flags: int
    Address: CySocketAddress

@cython.cclass
@dataclasses.dataclass
class CyFirstAnyServerAddress:
    Alignment: int
    Length: int
    Reserved: int
    Address: CySocketAddress

@cython.cclass
@dataclasses.dataclass
class CyFirstPrefix:
    Alignment: int
    Length: int
    Flags: int
    Address: CySocketAddress
    PrefixLength: int

@cython.cclass
@dataclasses.dataclass
class CyFirstDnsSuffix:
    String: str

@cython.cclass
@dataclasses.dataclass
class CyAdapter:
    Alignment: int
    Length: int
    IfIndex: int
    AdapterName: str
    FirstUnicastAddress: list[CyFirstUnicastAddress]
    FirstAnycastAddress: list[CyFirstAnycastMulticastAddress]
    FirstMulticastAddress: list[CyFirstAnycastMulticastAddress]
    FirstDnsServerAddress: list[CyFirstAnyServerAddress]
    DnsSuffix: str
    Description: str
    FriendlyName: str
    PhysicalAddress: str
    PhysicalAddressLength: int
    Flags: int
    DdnsEnabled: int
    RegisterAdapterSuffix: int
    Dhcpv4Enabled: int
    ReceiveOnly: int
    NoMulticast: int
    Ipv6OtherStatefulConfig: int
    NetbiosOverTcpipEnabled: int
    Ipv4Enabled: int
    Ipv6Enabled: int
    Ipv6ManagedAddressConfigurationSupported: int
    Mtu: int
    IfType: int
    OperStatus: int
    Ipv6IfIndex: int
    ZoneIndices: str
    FirstPrefix: list[CyFirstPrefix]
    TransmitLinkSpeed: int
    ReceiveLinkSpeed: int
    FirstWinsServerAddress: list[CyFirstAnyServerAddress]
    FirstGatewayAddress: list[CyFirstAnyServerAddress]
    Ipv4Metric: int
    Ipv6Metric: int
    Luid: int
    Dhcpv4Server: CySocketAddress
    CompartmentId: int
    NetworkGuid: str
    ConnectionType: int
    TunnelType: int
    Dhcpv6Server: CySocketAddress
    Dhcpv6ClientDuid: str
    Dhcpv6ClientDuidLength: int
    Dhcpv6Iaid: int
    FirstDnsSuffix: list[CyFirstDnsSuffix]

cdef _pwchar_to_str(WCHAR* wide_str, bint safe_parse=True):
    if wide_str is NULL:
        return None
    
    cdef int length = 0
    try:
       return PyUnicode_FromWideChar(<wchar_t*>wide_str, -1)
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _pwchar_to_str: {e}")
            return None
        raise e

cdef CySocketAddress _parse_socket_address(SOCKET_ADDRESS socket_address, bint safe_parse=True):
    if socket_address.lpSockaddr == NULL:
        return CySocketAddress(
            lpSockaddr=CylpSockaddr(sa_data=None, sa_family=None),
            iSockaddrLength=socket_address.iSockaddrLength,
        )
    
    try:
        lpSockaddr = CylpSockaddr(sa_data=socket_address.lpSockaddr.sa_data[:14], sa_family=socket_address.lpSockaddr.sa_family)
        return CySocketAddress(
            lpSockaddr=lpSockaddr,
            iSockaddrLength=socket_address.iSockaddrLength,
        )
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_socket_address: {e}")
            lpSockaddr = CylpSockaddr(sa_data=None, sa_family=None)
            return CySocketAddress(
                lpSockaddr=CylpSockaddr(sa_data=None, sa_family=None),
                iSockaddrLength=socket_address.iSockaddrLength,
            )
        else:
            raise e

cdef list[CyFirstUnicastAddress] _parse_unicast_address(IP_ADAPTER_UNICAST_ADDRESS_LH* data, bint safe_parse=True):
    cdef IP_ADAPTER_UNICAST_ADDRESS_LH* current_data = data
    parsed_data = []

    try:
        while current_data:
            address = CyFirstUnicastAddress(
                Alignment=current_data.Alignment,
                Length=current_data.Length,
                Flags=current_data.Flags,
                Address=_parse_socket_address(current_data.Address, False),
                PrefixOrigin=<int>current_data.PrefixOrigin,
                SuffixOrigin=<int>current_data.SuffixOrigin,
                DadState=<int>current_data.DadState,
                ValidLifetime=current_data.ValidLifetime,
                PreferredLifetime=current_data.PreferredLifetime,
                LeaseLifetime=current_data.LeaseLifetime,
                OnLinkPrefixLength=current_data.OnLinkPrefixLength,
            )
            parsed_data.append(address)
            current_data = current_data.Next
        return parsed_data
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_unicast_address: {e}")
            return []
        raise e

ctypedef fused AnycastMulticastAddress:
    IP_ADAPTER_ANYCAST_ADDRESS_XP
    IP_ADAPTER_MULTICAST_ADDRESS_XP

cdef list[CyFirstAnycastMulticastAddress] _parse_anycast_multicast_address(AnycastMulticastAddress* data, bint safe_parse=True):
    cdef AnycastMulticastAddress* current_data = data
    parsed_data = []

    try:
        while current_data:
            address = CyFirstAnycastMulticastAddress(
                Alignment=current_data.Alignment,
                Length=current_data.Length,
                Flags=current_data.Flags,
                Address=_parse_socket_address(current_data.Address, False),
            )
            parsed_data.append(address)
            current_data = current_data.Next
        return parsed_data
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_anycast_multicast_address: {e}")
            return []
        raise e

ctypedef fused AnyServerAddress:
    IP_ADAPTER_DNS_SERVER_ADDRESS_XP
    IP_ADAPTER_WINS_SERVER_ADDRESS_LH
    IP_ADAPTER_GATEWAY_ADDRESS_LH

cdef list[CyFirstAnyServerAddress] _parse_any_server_address(AnyServerAddress* data, bint safe_parse=True):
    cdef AnyServerAddress* current_data = data
    parsed_data = []

    try:
        while current_data:
            address = CyFirstAnyServerAddress(
                Alignment=current_data.Alignment,
                Length=current_data.Length,
                Reserved=current_data.Reserved,
                Address=_parse_socket_address(current_data.Address, False),
            )
            parsed_data.append(address)
            current_data = current_data.Next
        return parsed_data
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_any_server_address: {e}")
            return []
        raise e

cdef list[CyFirstPrefix] _parse_adapter_prefix(IP_ADAPTER_PREFIX_XP* data, bint safe_parse=True):
    cdef IP_ADAPTER_PREFIX_XP* current_data = data
    parsed_data = []

    try:
        while current_data:
            prefix = CyFirstPrefix(
                Alignment=current_data.Alignment,
                Length=current_data.Length,
                Flags=current_data.Flags,
                Address=_parse_socket_address(current_data.Address, False),
                PrefixLength=current_data.PrefixLength
            )
            parsed_data.append(prefix)
            current_data = current_data.Next
        return parsed_data
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_adapter_prefix: {e}")
            return []
        raise e

cdef list[CyFirstDnsSuffix] _parse_dns_suffix(IP_ADAPTER_DNS_SUFFIX* data, bint safe_parse=True):
    cdef IP_ADAPTER_DNS_SUFFIX* current_data = data
    parsed_data = []

    try:
        while current_data:
            dns_suffix_string = _pwchar_to_str(current_data.String, False)
            if dns_suffix_string: 
                parsed_data.append(
                    CyFirstDnsSuffix(String=dns_suffix_string)
                )
            current_data = current_data.Next
        return parsed_data
    except Exception as e:
        if safe_parse:
            return []
        raise e

cdef str _parse_physical_address(uint8_t* physical_adress, uint32_t physical_adress_length, bint safe_parse=True):
    if physical_adress_length == 0:
        return ""
    result = ""

    try:
        for i in range(physical_adress_length):
            if i == (physical_adress_length - 1):
                result += "%.2X" % physical_adress[i]
            else:
                result += "%.2X-" % physical_adress[i]
        return result
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_physical_address: {e}")
            return ""
        raise e

cdef str _parse_network_guid(NET_IF_NETWORK_GUID guid, bint safe_parse=True):
    try:
        parsed_guid = f"{guid.Data1:08x}-{guid.Data2:04x}-{guid.Data3:04x}-"
        for i in range(8):
            parsed_guid += f"{guid.Data4[i]:02x}"
        return parsed_guid
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_network_guid: {e}")
            return ""
        raise e

cdef str _parse_adapter_name(char* value, str encoding="utf-8", bint safe_parse=True):
    try:
        return value.decode(encoding)
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_adapter_name: {e}")
            return ""
        raise e

cdef str _parse_zone_indices(uint32_t* zone_indices_array, bint safe_parse=True):
    try:
        return ' '.join('%lx' % zone_indices_array[i] for i in range(16))
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_zone_indices: {e}")
            return ""
        raise e

cdef str _parse_dhcpv6_client_duid(uint8_t* duid_array, uint32_t duid_length, bint safe_parse=True):
    try:
        if duid_length == 0:
            return ""
        result = ""
        for i in range(duid_length):
            if i == (duid_length - 1):
                result += "%.2X" % duid_array[i]
            else:
                result += "%.2X-" % duid_array[i]
        return result
    except Exception as e:
        if safe_parse:
            logger.warning(f"Exception in _parse_dhcpv6_client_duid: {e}")
            return ""
        raise e

cdef list _parse_adapters(PIP_ADAPTER_ADDRESSES_LH adapters_addresses):
    cdef PIP_ADAPTER_ADDRESSES_LH current_adapter = adapters_addresses
    
    adapters_list = []
    while current_adapter:
        parsed_adapter = CyAdapter(
            Alignment=current_adapter.Alignment,
            Length=current_adapter.Length,
            IfIndex=current_adapter.IfIndex,
            AdapterName=_parse_adapter_name(current_adapter.AdapterName),
            FirstUnicastAddress=_parse_unicast_address(current_adapter.FirstUnicastAddress),
            FirstAnycastAddress=_parse_anycast_multicast_address(current_adapter.FirstAnycastAddress),
            FirstMulticastAddress=_parse_anycast_multicast_address(current_adapter.FirstMulticastAddress),
            FirstDnsServerAddress=_parse_any_server_address(current_adapter.FirstDnsServerAddress),
            DnsSuffix=_pwchar_to_str(current_adapter.DnsSuffix),
            Description=_pwchar_to_str(current_adapter.Description),
            FriendlyName=_pwchar_to_str(current_adapter.FriendlyName),
            PhysicalAddress=_parse_physical_address(current_adapter.PhysicalAddress, current_adapter.PhysicalAddressLength),
            PhysicalAddressLength=current_adapter.PhysicalAddressLength,
            Flags=current_adapter.Flags,
            DdnsEnabled=current_adapter.DdnsEnabled,
            RegisterAdapterSuffix=current_adapter.RegisterAdapterSuffix,
            Dhcpv4Enabled=current_adapter.Dhcpv4Enabled,
            ReceiveOnly=current_adapter.ReceiveOnly,
            NoMulticast=current_adapter.NoMulticast,
            Ipv6OtherStatefulConfig=current_adapter.Ipv6OtherStatefulConfig,
            NetbiosOverTcpipEnabled=current_adapter.NetbiosOverTcpipEnabled,
            Ipv4Enabled=current_adapter.Ipv4Enabled,
            Ipv6Enabled=current_adapter.Ipv6Enabled,
            Ipv6ManagedAddressConfigurationSupported=current_adapter.Ipv6ManagedAddressConfigurationSupported,
            Mtu=current_adapter.Mtu,
            IfType=current_adapter.IfType,
            OperStatus=<int>current_adapter.OperStatus,
            Ipv6IfIndex=current_adapter.Ipv6IfIndex,
            ZoneIndices=_parse_zone_indices(<uint32_t*>current_adapter.ZoneIndices),
            FirstPrefix=_parse_adapter_prefix(current_adapter.FirstPrefix),
            TransmitLinkSpeed=current_adapter.TransmitLinkSpeed,
            ReceiveLinkSpeed=current_adapter.ReceiveLinkSpeed,
            FirstWinsServerAddress=_parse_any_server_address(current_adapter.FirstWinsServerAddress),
            FirstGatewayAddress=_parse_any_server_address(current_adapter.FirstGatewayAddress),
            Ipv4Metric=current_adapter.Ipv4Metric,
            Ipv6Metric=current_adapter.Ipv6Metric,
            Luid=current_adapter.Luid.Value,
            Dhcpv4Server=_parse_socket_address(current_adapter.Dhcpv4Server),
            CompartmentId=current_adapter.CompartmentId,
            NetworkGuid=_parse_network_guid(current_adapter.NetworkGuid),
            ConnectionType=<int>current_adapter.ConnectionType,
            TunnelType=<int>current_adapter.TunnelType,
            Dhcpv6Server=_parse_socket_address(current_adapter.Dhcpv6Server),
            Dhcpv6ClientDuid=_parse_dhcpv6_client_duid(current_adapter.Dhcpv6ClientDuid, current_adapter.Dhcpv6ClientDuidLength),
            Dhcpv6ClientDuidLength=current_adapter.Dhcpv6ClientDuidLength,
            Dhcpv6Iaid=current_adapter.Dhcpv6Iaid,
            FirstDnsSuffix=_parse_dns_suffix(current_adapter.FirstDnsSuffix)
        )
        adapters_list.append(parsed_adapter)
        current_adapter = current_adapter.Next

    return adapters_list

cdef _get_adapters_addresses_by_family(
    adapter_family: AdapterFamily,
    scan_flags: list[ScanFlags] | ScanFlags,
):
    cdef:
        unsigned long dwRetVal = 0
        unsigned int i = 0
        uint32_t flags = 0
        uint32_t family = <uint32_t> adapter_family

        PIP_ADAPTER_ADDRESSES_LH pAddresses = NULL
        unsigned long outBufLen = 0
        uint32_t Iterations = 0

        PIP_ADAPTER_ADDRESSES_LH pCurrAddresses = NULL
        PIP_ADAPTER_UNICAST_ADDRESS_LH pUnicast = NULL
        PIP_ADAPTER_ANYCAST_ADDRESS_XP pAnycast = NULL
        PIP_ADAPTER_MULTICAST_ADDRESS_XP pMulticast = NULL
        IP_ADAPTER_DNS_SERVER_ADDRESS_XP *pDnServer = NULL
        IP_ADAPTER_PREFIX_XP* pPrefix = NULL
    
    if not isinstance(scan_flags, list):
        scan_flags = [scan_flags]
    for flag in scan_flags:
        flags |= <uint32_t> flag

    outBufLen = _WORKING_BUFFER_SIZE
    while Iterations < _MAX_TRIES:
        pAddresses = <PIP_ADAPTER_ADDRESSES_LH> malloc(outBufLen)
        if pAddresses == NULL:
            raise MemoryError("Memory allocation failed for IP_ADAPTER_ADDRESSES struct")

        dwRetVal = GetAdaptersAddresses(family, flags, NULL, pAddresses, &outBufLen)
        if dwRetVal == ERROR_BUFFER_OVERFLOW:
            free(pAddresses)
            pAddresses = NULL
        else:
            break
        Iterations += 1

    if dwRetVal != NO_ERROR:
        free(pAddresses)
        if dwRetVal == ERROR_NO_DATA:
            raise OSError("No addresses were found for the requested parameters")
        else:
            raise OSError(f"Error trying to retrieve adapter addresses: {dwRetVal}")

    adapters = _parse_adapters(pAddresses)
    free(pAddresses)
    return adapters

def get_adapters_addresses(
    adapter_families: list[AdapterFamily] | AdapterFamily = AdapterFamily.UNSPEC,
    scan_flags: list[ScanFlags] | ScanFlags = ScanFlags.INCLUDE_PREFIX,
) -> list[CyAdapter]:
    """Retrieves the addresses associated with the adapters on the local Windows computer.

    Returns:
        adapters on the local computer.
    """
    adapters = []
    if not isinstance(adapter_families, list):
        adapter_families = [adapter_families]
    for adapter_family in adapter_families:
        adapters.extend(_get_adapters_addresses_by_family(adapter_family, scan_flags))
    return adapters

def get_adapter(ifname: str, adapter_family: AdapterFamily = AdapterFamily.UNSPEC, scan_flags: list[ScanFlags] | ScanFlags = [ScanFlags.INCLUDE_PREFIX, ScanFlags.INCLUDE_ALL_INTERFACES]) -> CyAdapter | None:
    """Retrieves the address of a specific adapter by its name.

    Args:
        ifname: The name of the adapter to retrieve.
            Should match the AdapterName field in the CyAdapter structure, ex:
                AdapterName='{129BCE68-6859-4A78-B17E-6A80054E9F98}'
        adapter_family: The address family to filter by (default is UNSPEC).
        scan_flags: Flags to control the scanning behavior (default includes prefix).

    Returns:
        The adapter information or None if not found.
    """
    adapters = get_adapters_addresses(adapter_families=adapter_family, scan_flags=scan_flags)
    for adapter in adapters:
        if adapter.AdapterName == ifname:
            return adapter
    return None