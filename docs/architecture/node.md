# Class Hierarchy (Node)
```mermaid
classDiagram
  class Node {
    <<abstract>>
  }

  class TSNNode

  Node <|-- TSNNode
```
- **`Node` (base)**: Common API for representing a physical drive and managing its lifecycle.
- **`TSNNode` (protocol node)**: TSN-specific implementation for discovery updates, servo connections, disconnections, and TFTP firmware loading.