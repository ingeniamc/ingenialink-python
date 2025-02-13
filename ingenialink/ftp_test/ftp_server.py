# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.cred.checkers import (
    AllowAnonymousAccess,
    InMemoryUsernamePasswordDatabaseDontUse,
)
from twisted.cred.portal import Portal
from twisted.internet import reactor
from twisted.protocols.ftp import FTPFactory, FTPRealm

# Set server checkers
checker = InMemoryUsernamePasswordDatabaseDontUse()
# Add user/password
checker.addUser("user1", "1234")
checker.addUser("user2", "1234")
# Setup portal&factory
portal = Portal(FTPRealm("./", "./"), [AllowAnonymousAccess(), checker])
factory = FTPFactory(portal)
# Start server with localhost at port 21
print("Starting FTP...")
reactor.listenTCP(21, factory)
print("FTP server created!")
reactor.run()
