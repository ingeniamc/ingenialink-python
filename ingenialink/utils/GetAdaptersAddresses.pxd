"""
Wrapper for GetAdaptersAddresses function (iphlpapi.h).
"""
from libc.time cimport time_t
from libc.stdint cimport uint16_t, uint32_t, uint8_t, int32_t, uint64_t

cdef extern from "winsock2.h":
    enum:
        IF_INDEX
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

cdef extern from "iptypes.h":
    enum:
        MAX_ADAPTER_ADDRESS_LENGTH

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


    # https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-ip_adapter_addresses_lh
    ctypedef struct _IP_ADAPTER_ADDRESSES_LH:
        uint64_t Alignment
        uint32_t Length
        uint32_t Flags
        _IP_ADAPTER_ADDRESSES_LH* Next
        char* AdapterName
        PIP_ADAPTER_UNICAST_ADDRESS_LH FirstUnicastAddress
        PIP_ADAPTER_ANYCAST_ADDRESS_XP FirstAnycastAddress
        PIP_ADAPTER_MULTICAST_ADDRESS_XP FirstMulticastAddress
        PIP_ADAPTER_DNS_SERVER_ADDRESS_XP FirstDnsServerAddress
        char* DnsSuffix
        char* Description
        char* FriendlyName
        uint8_t PhysicalAddress[MAX_ADAPTER_ADDRESS_LENGTH]
        uint32_t PhysicalAddressLength
        _FLAGS_UNION FlagsUnion
        uint32_t Mtu
        uint32_t IfType # https://learn.microsoft.com/en-us/windows-hardware/drivers/network/ndis-interface-types
        IF_OPER_STATUS OperStatus
        uint32_t Ipv6IfIndex
        uint32_t ZoneIndices[16]
    ctypedef _IP_ADAPTER_ADDRESSES_LH IP_ADAPTER_ADDRESSES_LH
    ctypedef _IP_ADAPTER_ADDRESSES_LH* PIP_ADAPTER_ADDRESSES_LH

# https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersinfo
cdef extern from "iphlpapi.h":
    unsigned long GetAdaptersAddresses(
        unsigned long Family,
        unsigned long Flags,
        void* Reserved,
        #IP_ADAPTER_INFO* pAdapterInfo,
        unsigned long* pOutBufLen
    ) except +

