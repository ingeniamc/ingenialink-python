Examples
========

It is always better to show off some illustrative examples other than presenting
never-ending API docs. So here we go.

.. note:: You can also find full-featured examples in the `repo`_ ``examples``
          folder.
          
.. _repo: https://github.com/ingeniamc/ingenialink-python

Read/Write
----------

::

    import ingenialink as il

    POS_TARGET = il.Register(0x607A, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_POS)
    POS_ACTUAL = il.Register(0x6064, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_POS)

    net = il.Network('/dev/ttyACM0')
    axis = il.Axis(net, 0x20)

    ...
    axis.raw_write(POS_TARGET, 1000)
    ...
    print('Actual position (counts):', axis.raw_read(POS_ACTUAL))

Motion control
--------------

::

    import ingenialink as il

    net = il.Network('/dev/ttyACM0')
    axis = il.Axis(net, 0x20)

    # set position units to degrees
    axis.units_pos = il.UNITS_POS_DEG

    axis.disable()
    axis.mode = il.MODE_PP
    axis.enable()

    axis.position = 90
    axis.wait_reached(timeout=500)

Register polling
----------------

::

    import ingenialink as il

    POS_ACTUAL = il.Register(0x6064, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_POS)

    net = il.Network('/dev/ttyACM0')
    axis = il.Axis(net, 0x20)

    axis.units_pos = il.UNITS_POS_DEG

    poller = il.Poller(axis, POS_ACTUAL, 2, 1000)

    axis.disable()
    axis.mode = il.MODE_PP
    axis.enable()

    poller.start()
    axis.position = 180
    axis.wait_reached(timeout=500)
    poller.stop()

    t, d = poller.data
    ...


Axes listing
------------

::

    import ingenialink as il

    net = il.Network('COM1')
    axes = net.axes()

    print('Available axes:')
    for axis in axes:
        print(axis)

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

