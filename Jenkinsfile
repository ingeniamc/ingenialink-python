@Library('cicd-lib@0.11') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def DIST_FOE_APP_PATH = "ECAT-tools"
def LIB_FOE_APP_PATH = "ingenialink\\bin\\FOE"
def FOE_APP_NAME = "FoEUpdateFirmware.exe"
def FOE_APP_NAME_LINUX = "FoEUpdateFirmware"
def FOE_APP_VERSION = ""

def PYTHON_VERSIONS = "py39,py310,py311,py312"
def DEFAULT_PYTHON_VERSION = "3.9"
def TOX_VERSION = "4.12.1"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"

pipeline {
    agent none
    stages {
        stage('CANopen and Ethernet tests') {
            options {
                lock(CAN_NODE_LOCK)
            }
            agent {
                label CAN_NODE
            }
            stages {
                stage('Checkout') {
                    steps {
                        checkout scm
                    }
                }
                stage('Run CANopen tests') {
                    steps {
                        bat """
                            venv\\Scripts\\python.exe -m tox -e ${PYTHON_VERSIONS} -- --protocol canopen --junitxml=pytest_canopen_report.xml
                        """
                    }
                    post {
                        always {
                            junit 'pytest_canopen_report.xml'
                        }
                    }
                }
                stage('Run Ethernet tests') {
                    steps {
                        bat """
                            venv\\Scripts\\python.exe -m tox -e ${PYTHON_VERSIONS} -- --protocol ethernet --junitxml=pytest_ethernet_report.xml
                        """
                    }
                    post {
                        always {
                            junit 'pytest_ethernet_report.xml'
                        }
                    }
                }
            }
        }
    }
}