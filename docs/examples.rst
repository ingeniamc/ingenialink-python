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
    servo = il.Servo(net, 0x20)

    ...
    servo.raw_write(POS_TARGET, 1000)
    ...
    print('Actual position (counts):', servo.raw_read(POS_ACTUAL))

Motion control
--------------

::

    import ingenialink as il

    net = il.Network('/dev/ttyACM0')
    servo = il.Servo(net, 0x20)

    # set position units to degrees
    servo.units_pos = il.UNITS_POS_DEG

    servo.disable()
    servo.mode = il.MODE_PP
    servo.enable()

    servo.position = 90
    servo.wait_reached(timeout=500)

Register polling
----------------

::

    import ingenialink as il

    POS_ACTUAL = il.Register(0x6064, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_POS)

    net = il.Network('/dev/ttyACM0')
    servo = il.Servo(net, 0x20)

    servo.units_pos = il.UNITS_POS_DEG

    poller = il.Poller(servo, POS_ACTUAL, 2, 1000)

    servo.disable()
    servo.mode = il.MODE_PP
    servo.enable()

    poller.start()
    servo.position = 180
    servo.wait_reached(timeout=500)
    poller.stop()

    t, d = poller.data
    ...


Servos listing
--------------

::

    import ingenialink as il

    net = il.Network('COM1')
    servos = net.servos()

    print('Available servos:')
    for servo in servos:
        print(servo)

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

