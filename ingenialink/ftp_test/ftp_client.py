from ftplib import FTP

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"


# Settings
ip = "localhost"
user = "user1"
password = "1234"
timeout = 2  # seconds

# Create FTP host
ftp = FTP()
try:
    print("Connecting...")
    ftp_output = ftp.connect(ip, timeout=timeout)
except Exception as e:
    print("Unable to create the FTP session: ", e)
    quit()
if FTP_SESSION_OK_CODE not in ftp_output:
    print("[ERROR] Unable to open the FTP session due to not FTP_SESSION_OK_CODE.")
    quit()
# Login into FTP session.
try:
    print("Logging into FTP session...")
    ftp_output = ftp.login(user, password)
except Exception as e:
    print("[ERROR] Wrong user/password: ", e)
    quit()
if FTP_LOGIN_OK_CODE not in ftp_output:
    print("[ERROR] Unable to login the FTP session due to not FTP_LOGIN_OK_CODE.")
print("Success!")
