## Class Hierarchy (Servo)
```mermaid
classDiagram
  class Servo {
    <<base>>
  }

  class VirtualServoBase {
    <<abstract>>
  }

  class EthernetServoBase {
    <<abstract>>
  }
  class EthercatServoBase {
    <<abstract>>
  }
  class CanopenServoBase {
    <<abstract>>
  }

  class EthernetServo
  class VirtualEthernetServo

  class EthercatServo
  class VirtualEthercatServo

  class CanopenServo
  class VirtualCanopenServo

  Servo <|-- EthernetServoBase
  Servo <|-- EthercatServoBase
  Servo <|-- CanopenServoBase

  EthernetServoBase <|-- EthernetServo
  EthernetServoBase <|-- VirtualEthernetServo
  VirtualEthernetServo *-- VirtualServoBase

  EthercatServoBase <|-- EthercatServo
  EthercatServoBase <|-- VirtualEthercatServo
  VirtualEthercatServo *-- VirtualServoBase

  CanopenServoBase <|-- CanopenServo
  CanopenServoBase <|-- VirtualCanopenServo
  VirtualCanopenServo *-- VirtualServoBase
```
- **`Servo` (base)**: Common API for reading/writing registers and device state.
- **`*ServoBase` (protocol base)**: Shared protocol rules for register access.
- **`*Servo` (real)**: Real hardware implementation.
- **`VirtualServoBase` (virtual common)**: Shared virtual device state + socket helpers.
- **`Virtual*Servo` (virtual protocol)**: Protocol-specific virtual behavior (composes `VirtualServoBase`).