from ftplib import FTP
from threading import Thread

from twisted.cred.checkers import (
    AllowAnonymousAccess,
    InMemoryUsernamePasswordDatabaseDontUse,
)
from twisted.cred.portal import Portal
from twisted.internet import reactor
from twisted.protocols.ftp import FTPFactory, FTPRealm

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"


class FTPServer(Thread):
    def __init__(self):
        super().__init__()
        self.fpt_checker = InMemoryUsernamePasswordDatabaseDontUse()
        self.fpt_checker.addUser("user1", "1234")
        self.ftp_portal = Portal(FTPRealm("./", "./"), [AllowAnonymousAccess(), self.fpt_checker])
        self.ftp_factory = FTPFactory(self.ftp_portal)
        reactor.listenTCP(21, self.ftp_factory)

    def run(self) -> None:
        """Run FTP server."""
        print("Running server!")
        reactor.run()

    def stop(self) -> None:
        """Stop FTP server."""
        print("Stopping server!")
        reactor.stop()


def test_ftp_connection() -> None:
    ftp = FTP()
    print("Connecting...")
    try:
        ftp_output = ftp.connect(host="localhost", port=21, timeout=10)
    except ConnectionError as e:
        print("Connection error = ", e)
        return
    print("Success!")
    if FTP_SESSION_OK_CODE not in ftp_output:
        print("Unable to open the FTP session")
    print("Logging...")
    ftp_output = ftp.login(user="user2", passwd="1234")
    if FTP_LOGIN_OK_CODE not in ftp_output:
        print("Unable to login the FTP session")
    print("Success!")
    ftp.quit()
    return


server = FTPServer()
# Start thread
server.start()

test_ftp_connection()

server.stop()
server.join()
