"""
Wrapper for GetAdaptersAddresses function (iphlpapi.h).
"""
from libc.time cimport time_t
from libc.stdint cimport uint16_t, uint32_t, uint8_t, int32_t, uint64_t
from libc.stdint cimport uint16_t

cdef extern from "winsock2.h":
    enum:
        AF_INET
        AF_INET6
        AF_UNSPEC
        GAA_FLAG_INCLUDE_PREFIX

    # https://learn.microsoft.com/is-is/windows/win32/api/winsock2/ns-winsock2-in_addr
    ctypedef struct in_addr:
        uint32_t s_addr

    ctypedef struct in6_addr:
        uint8_t s6_addr[16]

    # https://learn.microsoft.com/es-es/windows/win32/winsock/sockaddr-2
    ctypedef struct sockaddr:
        unsigned int sa_family
        char sa_data[14]
    ctypedef sockaddr SOCKADDR
    ctypedef sockaddr* PSOCKADDR
    ctypedef sockaddr* LPSOCKADDR
    
    ctypedef struct sockaddr_in:
        uint16_t sin_family
        uint16_t sin_port
        in_addr sin_addr
        char sin_zero[8]

    ctypedef struct sockaddr_in6:
        uint16_t sin6_family
        uint16_t sin6_port
        uint32_t sin6_flowinfo
        in6_addr sin6_addr
        uint32_t sin6_scope_id
    ctypedef sockaddr_in6 SOCKADDR_IN6
    ctypedef sockaddr_in6* PSOCKADDR_IN6
    ctypedef sockaddr_in6* LPSOCKADDR_IN6

    # https://learn.microsoft.com/en-us/previous-versions/windows/desktop/legacy/ms740504(v=vs.85)
    ctypedef struct sockaddr_storage:
        uint16_t ss_family
        char __ss_pad1[6]
        uint32_t __ss_align
        char __ss_pad2[112]

cdef extern from "winerror.h":
    enum:
        ERROR_BUFFER_OVERFLOW
        ERROR_NO_DATA
        NO_ERROR

cdef extern from "ifdef.h":
    # https://learn.microsoft.com/en-us/windows/win32/api/ifdef/
    ctypedef enum _IF_OPER_STATUS:
        IfOperStatusUp = 1
        IfOperStatusDown = 2
        IfOperStatusTesting = 3
        IfOperStatusUnknown = 4
        IfOperStatusDormant = 5
        IfOperStatusNotPresent = 6
        IfOperStatusLowerLayerDown = 7
    ctypedef _IF_OPER_STATUS IF_OPER_STATUS

    # https://learn.microsoft.com/en-us/windows/win32/api/ifdef/ns-ifdef-net_luid_lh
    ctypedef union _NET_LUID_LH:
        uint64_t Value
        uint64_t Reserved
        uint64_t NetLuidIndex
        uint64_t IfType
    ctypedef _NET_LUID_LH IF_LUID
    ctypedef _NET_LUID_LH NET_LUID_LH

    # https://learn.microsoft.com/en-us/windows/win32/api/ifdef/ne-ifdef-net_if_connection_type
    ctypedef enum _NET_IF_CONNECTION_TYPE:
        NET_IF_CONNECTION_DEDICATED = 1
        NET_IF_CONNECTION_PASSIVE = 2
        NET_IF_CONNECTION_DEMAND = 3
        NET_IF_CONNECTION_MAXIMUM = 4
    ctypedef _NET_IF_CONNECTION_TYPE NET_IF_CONNECTION_TYPE

    # https://learn.microsoft.com/en-us/windows/win32/api/ifdef/ne-ifdef-tunnel_type
    ctypedef enum _TUNNEL_TYPE:
        TUNNEL_TYPE_NONE = 0
        TUNNEL_TYPE_OTHER = 1
        TUNNEL_TYPE_DIRECT = 2
        TUNNEL_TYPE_6TO4 = 11
        TUNNEL_TYPE_ISATAP = 13
        TUNNEL_TYPE_TEREDO = 14
        TUNNEL_TYPE_IPHTTPS = 15
    ctypedef _TUNNEL_TYPE TUNNEL_TYPE

cdef extern from "iptypes.h":
    enum:
        MAX_ADAPTER_ADDRESS_LENGTH
        MAX_DNS_SUFFIX_STRING_LENGTH
        MAX_DHCPV6_DUID_LENGTH

    # https://learn.microsoft.com/en-us/windows/win32/api/ws2def/ns-ws2def-socket_address
    ctypedef struct _SOCKET_ADDRESS:
        LPSOCKADDR lpSockaddr
        int32_t iSockaddrLength
    ctypedef _SOCKET_ADDRESS SOCKET_ADDRESS
    ctypedef _SOCKET_ADDRESS* PSOCKET_ADDRESS
    ctypedef _SOCKET_ADDRESS* LPSOCKET_ADDRESS

    # https://learn.microsoft.com/en-us/windows/win32/api/nldef/ne-nldef-nl_prefix_origin
    ctypedef enum _IP_PREFIX_ORIGIN:
        IpPrefixOriginOther
        IpPrefixOriginManual
        IpPrefixOriginWellKnown
        IpPrefixOriginDhcp
        IpPrefixOriginRouterAdvertisement
    ctypedef _IP_PREFIX_ORIGIN IP_PREFIX_ORIGIN

    # https://learn.microsoft.com/en-us/windows/win32/api/nldef/ne-nldef-nl_suffix_origin
    ctypedef enum _IP_SUFFIX_ORIGIN:
        IpSuffixOriginOther
        IpSuffixOriginManual
        IpSuffixOriginWellKnown
        IpSuffixOriginDhcp
        IpSuffixOriginLinkLayerAddress
        IpSuffixOriginRandom
    ctypedef _IP_SUFFIX_ORIGIN IP_SUFFIX_ORIGIN

    # https://learn.microsoft.com/en-us/windows/win32/api/nldef/ne-nldef-nl_dad_state
    ctypedef enum _IP_DAD_STATE:
        IpDadStateInvalid
        IpDadStateTentative
        IpDadStateDuplicate
        IpDadStateDeprecated
        IpDadStatePreferred
    ctypedef _IP_DAD_STATE IP_DAD_STATE

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_unicast_address_lh
    ctypedef struct _IP_ADAPTER_UNICAST_ADDRESS_LH:
        # flatten the union
        uint64_t Alignment
        uint32_t Length
        uint32_t Flags
        
        _IP_ADAPTER_UNICAST_ADDRESS_LH* Next
        SOCKET_ADDRESS Address
        IP_PREFIX_ORIGIN PrefixOrigin
        IP_SUFFIX_ORIGIN SuffixOrigin
        IP_DAD_STATE DadState
        uint32_t ValidLifetime
        uint32_t PreferredLifetime
        uint32_t LeaseLifetime
        uint8_t OnLinkPrefixLength
    ctypedef _IP_ADAPTER_UNICAST_ADDRESS_LH IP_ADAPTER_UNICAST_ADDRESS_LH
    ctypedef _IP_ADAPTER_UNICAST_ADDRESS_LH* PIP_ADAPTER_UNICAST_ADDRESS_LH

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_anycast_address_xp
    ctypedef struct _IP_ADAPTER_ANYCAST_ADDRESS_XP:
        uint64_t Alignment
        uint32_t Length
        uint32_t Flags
        _IP_ADAPTER_ANYCAST_ADDRESS_XP* Next
        SOCKET_ADDRESS Address
    ctypedef _IP_ADAPTER_ANYCAST_ADDRESS_XP IP_ADAPTER_ANYCAST_ADDRESS_XP
    ctypedef _IP_ADAPTER_ANYCAST_ADDRESS_XP* PIP_ADAPTER_ANYCAST_ADDRESS_XP

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_multicast_address_xp
    ctypedef struct _IP_ADAPTER_MULTICAST_ADDRESS_XP:
        uint64_t Alignment
        uint32_t Length
        uint32_t Flags
        _IP_ADAPTER_MULTICAST_ADDRESS_XP* Next
        SOCKET_ADDRESS Address
    ctypedef _IP_ADAPTER_MULTICAST_ADDRESS_XP IP_ADAPTER_MULTICAST_ADDRESS_XP
    ctypedef _IP_ADAPTER_MULTICAST_ADDRESS_XP* PIP_ADAPTER_MULTICAST_ADDRESS_XP

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_dns_server_address_xp
    ctypedef struct _IP_ADAPTER_DNS_SERVER_ADDRESS_XP:
        uint64_t Alignment
        uint32_t Length
        uint32_t Flags
        _IP_ADAPTER_DNS_SERVER_ADDRESS_XP* Next
        SOCKET_ADDRESS Address
    ctypedef _IP_ADAPTER_DNS_SERVER_ADDRESS_XP IP_ADAPTER_DNS_SERVER_ADDRESS_XP
    ctypedef _IP_ADAPTER_DNS_SERVER_ADDRESS_XP* PIP_ADAPTER_DNS_SERVER_ADDRESS_XP

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_prefix_xp
    ctypedef struct _IP_ADAPTER_PREFIX_XP:
        uint64_t Alignment
        uint32_t Length
        uint32_t Flags
        _IP_ADAPTER_PREFIX_XP* Next
        SOCKET_ADDRESS Address
        uint32_t PrefixLength
    ctypedef _IP_ADAPTER_PREFIX_XP IP_ADAPTER_PREFIX_XP
    ctypedef _IP_ADAPTER_PREFIX_XP* PIP_ADAPTER_PREFIX_XP

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_wins_server_address_lh
    ctypedef struct _IP_ADAPTER_WINS_SERVER_ADDRESS_LH:
        uint64_t Alignment
        uint32_t Length
        uint32_t Reserved
        _IP_ADAPTER_WINS_SERVER_ADDRESS_LH* Next
        SOCKET_ADDRESS Address
    ctypedef _IP_ADAPTER_WINS_SERVER_ADDRESS_LH IP_ADAPTER_WINS_SERVER_ADDRESS_LH
    ctypedef _IP_ADAPTER_WINS_SERVER_ADDRESS_LH* PIP_ADAPTER_WINS_SERVER_ADDRESS_LH

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_gateway_address_lh
    ctypedef struct _IP_ADAPTER_GATEWAY_ADDRESS_LH:
        uint64_t Alignment
        uint32_t Length
        uint32_t Reserved
        _IP_ADAPTER_GATEWAY_ADDRESS_LH* Next
        SOCKET_ADDRESS Address
    ctypedef _IP_ADAPTER_GATEWAY_ADDRESS_LH IP_ADAPTER_GATEWAY_ADDRESS_LH
    ctypedef _IP_ADAPTER_GATEWAY_ADDRESS_LH* PIP_ADAPTER_GATEWAY_ADDRESS_LH

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_dns_suffix
    ctypedef struct _IP_ADAPTER_DNS_SUFFIX:
        _IP_ADAPTER_DNS_SUFFIX* Next
        char* String[MAX_DNS_SUFFIX_STRING_LENGTH]
    ctypedef _IP_ADAPTER_DNS_SUFFIX IP_ADAPTER_DNS_SUFFIX
    ctypedef _IP_ADAPTER_DNS_SUFFIX* PIP_ADAPTER_DNS_SUFFIX

    cdef struct _FLAGS_STRUCT:
        uint32_t DdnsEnabled
        uint32_t RegisterAdapterSuffix
        uint32_t Dhcpv4Enabled
        uint32_t ReceiveOnly
        uint32_t NoMulticast
        uint32_t Ipv6OtherStatefulConfig
        uint32_t NetbiosOverTcpipEnabled
        uint32_t Ipv4Enabled
        uint32_t Ipv6Enabled
        uint32_t Ipv6ManagedAddressConfigurationSupported

    cdef union _FLAGS_UNION:
        uint32_t Flags
        _FLAGS_STRUCT BitFields

    ctypedef uint8_t NET_IF_NETWORK_GUID[16]

    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_addresses_lh
    ctypedef struct _IP_ADAPTER_ADDRESSES_LH:
        uint64_t Alignment
        uint32_t Length
        uint32_t IfIndex
        _IP_ADAPTER_ADDRESSES_LH* Next
        char* AdapterName
        PIP_ADAPTER_UNICAST_ADDRESS_LH FirstUnicastAddress
        PIP_ADAPTER_ANYCAST_ADDRESS_XP FirstAnycastAddress
        PIP_ADAPTER_MULTICAST_ADDRESS_XP FirstMulticastAddress
        PIP_ADAPTER_DNS_SERVER_ADDRESS_XP FirstDnsServerAddress
        uint16_t* DnsSuffix
        uint16_t* Description
        uint16_t* FriendlyName
        uint8_t PhysicalAddress[MAX_ADAPTER_ADDRESS_LENGTH]
        uint32_t PhysicalAddressLength
        _FLAGS_UNION FlagsUnion
        uint32_t Mtu
        uint32_t IfType # https://learn.microsoft.com/en-us/windows-hardware/drivers/network/ndis-interface-types
        IF_OPER_STATUS OperStatus
        uint32_t Ipv6IfIndex
        uint32_t ZoneIndices[16]
        PIP_ADAPTER_PREFIX_XP FirstPrefix
        uint64_t TransmitLinkSpeed
        uint64_t ReceiveLinkSpeed
        PIP_ADAPTER_WINS_SERVER_ADDRESS_LH FirstWinsServerAddress
        PIP_ADAPTER_GATEWAY_ADDRESS_LH FirstGatewayAddress
        uint32_t Ipv4Metric
        uint32_t Ipv6Metric
        IF_LUID Luid
        SOCKET_ADDRESS  Dhcpv4Server
        uint32_t CompartmentId
        NET_IF_NETWORK_GUID NetworkGuid
        NET_IF_CONNECTION_TYPE ConnectionType
        TUNNEL_TYPE TunnelType
        SOCKET_ADDRESS Dhcpv6Server
        uint8_t  Dhcpv6ClientDuid[MAX_DHCPV6_DUID_LENGTH]
        uint32_t Dhcpv6ClientDuidLength
        uint32_t Dhcpv6Iaid
        PIP_ADAPTER_DNS_SUFFIX FirstDnsSuffix
    ctypedef _IP_ADAPTER_ADDRESSES_LH IP_ADAPTER_ADDRESSES_LH
    ctypedef _IP_ADAPTER_ADDRESSES_LH* PIP_ADAPTER_ADDRESSES_LH

# https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersinfo
cdef extern from "iphlpapi.h":
    uint32_t GetAdaptersAddresses(
        uint32_t Family,
        uint32_t Flags,
        void* Reserved,
        PIP_ADAPTER_ADDRESSES_LH AdapterAddresses,
        unsigned long* pOutBufLen
    ) except +

