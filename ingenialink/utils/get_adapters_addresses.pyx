from GetAdaptersAddresses cimport *
from libc.stdlib cimport malloc, free
import dataclasses
import cython
from libc.string cimport strlen

_MAX_TRIES = 3
_WORKING_BUFFER_SIZE = 15000

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

    def __init__(self, sa_family: int, sa_data: bytes):
        self.sa_family = sa_family
        if len(sa_data) != 14:
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
class CyAdapter:
    Alignment: int
    Length: int
    IfIndex: int
    AdapterName: str
    FirstUnicastAddress: list[CyFirstUnicastAddress]
    # FirstAnycastAddress
    # FirstMulticastAddress
    # FirstDnsServerAddress
    # DnsSuffix
    Description: str
    FriendlyName: str
    # PhysicalAddress
    # PhysicalAddressLength
    # FlagsUnion
    Mtu: int
    IfType: int
    # OperStatus
    Ipv6IfIndex: int
    #ZoneIndices
    # FirstPrefix
    TransmitLinkSpeed: int
    ReceiveLinkSpeed: int
    # FirstWinsServerAddress
    # FirstGatewayAddress
    Ipv4Metric: int
    Ipv6Metric: int
    # Luid
    # Dhcpv4Server
    CompartmentId: int
    # NetworkGuid
    # ConnectionType
    # TunnelType
    # Dhcpv6Server
    Dhcpv6ClientDuid: str
    Dhcpv6ClientDuidLength: int
    Dhcpv6Iaid: int
    # FirstDnsSuffix

cdef _pwchar_to_str(PWCHAR wide_str):
    if wide_str is NULL:
        return None
    
    cdef int length = 0
    while wide_str[length] != 0:
        length += 1
    return (<char *>wide_str)[:length * 2].decode('utf-16le')

cdef CySocketAddress _parse_socket_address(SOCKET_ADDRESS socket_address):
    if socket_address.lpSockaddr == NULL:
        lpSockaddr = CylpSockaddr(sa_data=None, sa_family=None)
    else:
        lpSockaddr = CylpSockaddr(sa_data=socket_address.lpSockaddr.sa_data[:14], sa_family=socket_address.lpSockaddr.sa_family)
    return CySocketAddress(
        lpSockaddr=lpSockaddr,
        iSockaddrLength=socket_address.iSockaddrLength,
    )

cdef list[CyFirstUnicastAddress] _parse_unicast_address(IP_ADAPTER_UNICAST_ADDRESS_LH* data):
    cdef IP_ADAPTER_UNICAST_ADDRESS_LH* current_data = data
    parsed_data = []

    while current_data:
        unicast_address = CyFirstUnicastAddress(
            Alignment=current_data.Alignment,
            Length=current_data.Length,
            Flags=current_data.Flags,
            Address=_parse_socket_address(current_data.Address),
            PrefixOrigin=<int>current_data.PrefixOrigin,
            SuffixOrigin=<int>current_data.SuffixOrigin,
            DadState=<int>current_data.DadState,
            ValidLifetime=current_data.ValidLifetime,
            PreferredLifetime=current_data.PreferredLifetime,
            LeaseLifetime=current_data.LeaseLifetime,
            OnLinkPrefixLength=current_data.OnLinkPrefixLength,
        )
        parsed_data.append(unicast_address)
        current_data = current_data.Next
    return parsed_data

cdef list _parse_adapters(PIP_ADAPTER_ADDRESSES_LH adapters_addresses):
    cdef PIP_ADAPTER_ADDRESSES_LH current_adapter = adapters_addresses
    adapters_list = []
    while current_adapter:
        parsed_adapter = CyAdapter(
            Alignment=current_adapter.Alignment,
            Length=current_adapter.Length,
            IfIndex=current_adapter.IfIndex,
            AdapterName=current_adapter.AdapterName.decode("utf-8"),
            FirstUnicastAddress=_parse_unicast_address(current_adapter.FirstUnicastAddress),
            Description=_pwchar_to_str(current_adapter.Description),
            FriendlyName=_pwchar_to_str(current_adapter.FriendlyName),
            # PhysicalAddressLength=current_adapter.PhysicalAddressLength,
            Mtu=current_adapter.Mtu,
            IfType=current_adapter.IfType,
            Ipv6IfIndex=current_adapter.Ipv6IfIndex,
            # ZoneIndices=current_adapter.ZoneIndices,
            TransmitLinkSpeed=current_adapter.TransmitLinkSpeed,
            ReceiveLinkSpeed=current_adapter.ReceiveLinkSpeed,
            Ipv4Metric=current_adapter.Ipv4Metric,
            Ipv6Metric=current_adapter.Ipv6Metric,
            CompartmentId=current_adapter.CompartmentId,
            Dhcpv6ClientDuid=current_adapter.Dhcpv6ClientDuid.decode("utf-8"),
            Dhcpv6ClientDuidLength=current_adapter.Dhcpv6ClientDuidLength,
            Dhcpv6Iaid=current_adapter.Dhcpv6Iaid
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
    adapters = []
    if not isinstance(adapter_families, list):
        adapter_families = [adapter_families]
    for adapter_family in adapter_families:
        adapters.extend(_get_adapters_addresses_by_family(adapter_family, scan_flags))
    return adapters