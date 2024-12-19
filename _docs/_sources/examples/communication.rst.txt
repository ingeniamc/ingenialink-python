Connection Examples
======================

Slave connection through CANopen Example
----------------------------------------

.. literalinclude:: ../../examples/canopen/can_connection.py

Slave connection through CANopen Example (Linux)
------------------------------------------------

In Linux, the CANopen network should be configured in a terminal before running the ingenialink
script (administrator privileges are needed).

.. code-block:: console

    sudo ip link set can0 up type can bitrate 1000000
    sudo ip link set can0 txqueuelen 1000

Then to establish the connection use always the SOCKETCAN device and the bitrate configured in 
previous step:

.. literalinclude:: ../../examples/canopen/can_connection_linux.py

Slave connection through Ethernet Example
-----------------------------------------

.. literalinclude:: ../../examples/ethernet/eth_connection.py

Slave connection through EtherCAT Example
-----------------------------------------

.. literalinclude:: ../../examples/ethercat/ecat_connection.py

In Linux, administrator privileges are needed to establish the EtherCAT connection.

.. code-block:: console

    sudo python3 examples/ethercat/ecat_connection.py