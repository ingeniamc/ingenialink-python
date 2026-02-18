## Class Hierarchy (Network)
```mermaid
classDiagram
  class Network {
    <<abstract>>
  }

  class VirtualNetworkBase {
    <<abstract>>
  }

  class EthernetNetworkBase {
    <<abstract>>
  }
  class EthercatNetworkBase {
    <<abstract>>
  }
  class CanopenNetworkBase {
    <<abstract>>
  }

  class EthernetNetwork
  class VirtualEthernetNetwork

  class EthercatNetwork
  class VirtualEthercatNetwork

  class CanopenNetwork
  class VirtualCanopenNetwork

  Network <|-- EthernetNetworkBase
  Network <|-- EthercatNetworkBase
  Network <|-- CanopenNetworkBase

  EthernetNetworkBase <|-- EthernetNetwork
  EthernetNetworkBase <|-- VirtualEthernetNetwork
  VirtualEthernetNetwork *-- VirtualNetworkBase

  EthercatNetworkBase <|-- EthercatNetwork
  EthercatNetworkBase <|-- VirtualEthercatNetwork
  VirtualEthercatNetwork *-- VirtualNetworkBase

  CanopenNetworkBase <|-- CanopenNetwork
  CanopenNetworkBase <|-- VirtualCanopenNetwork
  VirtualCanopenNetwork *-- VirtualNetworkBase
```
- **`Network` (base)**: Common API for connecting, scanning, and tracking devices.
- **`*NetworkBase` (protocol base)**: Shared protocol rules (what a “device” is, how to identify it).
- **`*Network` (real)**: Talks to real hardware and drivers.
- **`VirtualNetworkBase` (virtual common)**: Shared socket transport and virtual device registry.
- **`Virtual*Network` (virtual protocol)**: Protocol-specific virtual behavior and device creation (composes `VirtualNetworkBase`).