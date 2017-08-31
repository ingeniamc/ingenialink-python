Examples
========

It is always better to show off some illustrative examples other than presenting
never-ending API docs. So here we go.

Read/Write
----------

::

    import ingenialink as il

    POS_TARGET = il.Register(0x607A, 0x00, il.S32)
    POS_ACTUAL = il.Register(0x6064, 0x00, il.S32)

    net = il.Network('/dev/ttyACM0')
    node = il.Node(net, 0x20)

    ...
    node.write(POS_TARGET, 1000)
    ...
    print('Actual position:', node.read(POS_ACTUAL))

Node listing
------------

::

    import ingenialink as il

    net = il.Network('COM1')
    nodes = net.nodes()

    print('Available nodes:')
    for node in nodes:
        print(node)

Device listing and monitoring
-----------------------------

::

    import ingenialink as il

    devs = il.devices()
    print('Available devices:')
    for dev in devs:
        print(dev)

::

    import ingenialink as il

    def on_event(event, dev):
        if event == il.ADDED:
            print('Added', dev)
        else:
            print('Removed', dev)

    mon = il.NetworkMonitor()
    mon.start(on_event)

