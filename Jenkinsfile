@Library('cicd-lib@0.3') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def DIST_FOE_APP_PATH = "ECAT-tools"
def LIB_FOE_APP_PATH = "ingenialink\\bin\\FOE"
def FOE_APP_NAME = "FoEUpdateFirmware.exe"
def FOE_APP_VERSION = ""

def PYTHON_VERSIONS = "py38,py39"
def DEFAULT_PYTHON_VERSION = "3.9"
def TOX_VERSION = "4.12.1"

pipeline {
    agent none
    stages {
        stage('Get FoE application') {
            agent {
                docker {
                    label "worker"
                    image "ingeniacontainers.azurecr.io/publisher:1.4"
                }
            }
            stages {
                stage('Get FoE application') {
                    steps {
                        script {
                            FOE_APP_VERSION = sh(script: 'cd ingenialink/bin && python3.9 -c "import FoE; print(FoE.__version__)"', returnStdout: true).trim()
                        }
                        copyFromDist(".", "$DIST_FOE_APP_PATH/$FOE_APP_VERSION")
                        stash includes: "$FOE_APP_NAME", name: 'foe_app'
                    }
                }
            }
        }
        stage('Build wheels and documentation') {
            agent {
                docker {
                    label SW_NODE
                    image 'ingeniacontainers.azurecr.io/win-python-builder:1.5'
                }
            }
            stages {
                stage('Clone repository') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator
                            git clone https://github.com/ingeniamc/ingenialink-python.git
                            cd ingenialink-python
                            git checkout ${env.GIT_COMMIT}
                        """
                    }
                }
                stage('Get FoE application') {
                    steps {
                        unstash 'foe_app'
                        bat """
                            XCOPY $FOE_APP_NAME C:\\Users\\ContainerAdministrator\\ingenialink-python\\$LIB_FOE_APP_PATH\\win_64x\\
                        """
                    }
                }
                stage('Install deps') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            py -${DEFAULT_PYTHON_VERSION} -m pip install tox==${TOX_VERSION}
                        """
                    }
                }
                stage('Build wheels') {
                    steps {
                        bat '''
                             cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                             tox -e build
                        '''
                    }
                }
                stage('Check formatting') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            tox -e format
                        """
                    }
                }
                stage('Type checking') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            tox -e type
                        """
                    }
                }
                stage('Generate documentation') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            tox -e docs
                        """
                    }
                }
                stage('Run docker tests') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            tox -e ${PYTHON_VERSIONS} -- -m docker --junitxml=pytest_docker_report.xml
                        """
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            move .coverage ${env.WORKSPACE}\\.coverage_docker
                            move pytest_docker_report.xml ${env.WORKSPACE}\\pytest_docker_report.xml
                        """
                        junit 'pytest_docker_report.xml'
                    }
                }
                stage('Archive') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                            XCOPY dist ${env.WORKSPACE}\\dist /i
                            XCOPY docs.zip ${env.WORKSPACE}
                        """
                        stash includes: '.coverage_docker', name: 'coverage_docker'
                        archiveArtifacts artifacts: 'pytest_docker_report.xml'
                        archiveArtifacts artifacts: "dist\\*, docs.zip"
                    }
                }
            }
        }
        stage('EtherCAT and no-connection tests') {
            options {
                lock(ECAT_NODE_LOCK)
            }
            agent {
                label ECAT_NODE
            }
            stages {
                stage('Checkout') {
                    steps {
                        checkout scm
                    }
                }
                stage('Get FoE application') {
                    steps {
                        unstash 'foe_app'
                        bat """
                            XCOPY $FOE_APP_NAME $LIB_FOE_APP_PATH\\win_64x\\
                        """
                    }
                }
                stage('Install deps') {
                    steps {
                        bat """
                            py -${DEFAULT_PYTHON_VERSION} -m venv venv
                            venv\\Scripts\\python.exe -m pip install tox==${TOX_VERSION}
                        """
                    }
                }
                stage('Update drives FW') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m tox -e firmware -- ethercat
                        '''
                    }
                }
                stage('Run EtherCAT tests') {
                    steps {
                        bat """
                            venv\\Scripts\\python.exe -m tox -e ${PYTHON_VERSIONS} -- --protocol ethercat --junitxml=pytest_ethercat_report.xml
                        """
                        bat """
                            move .coverage .coverage_ethercat
                        """
                        junit 'pytest_ethercat_report.xml'
                    }
                }
                stage('Run no-connection tests') {
                    steps {
                        bat """
                            venv\\Scripts\\python.exe -m tox -e ${PYTHON_VERSIONS} -- --junitxml=pytest_no_connection_report.xml
                        """
                        bat """
                            move .coverage .coverage_no_connection
                        """
                        junit 'pytest_no_connection_report.xml'
                    }
                }
                stage('Archive') {
                    steps {
                        stash includes: '.coverage_ethercat, .coverage_no_connection', name: 'coverage_reports'
                        archiveArtifacts artifacts: '*.xml'
                    }
                }
            }
        }
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
                stage('Get FoE application') {
                    steps {
                        unstash 'foe_app'
                        bat """
                            XCOPY $FOE_APP_NAME $LIB_FOE_APP_PATH\\win_64x\\
                        """
                    }
                }
                stage('Install deps') {
                    steps {
                        bat """
                            py -${DEFAULT_PYTHON_VERSION} -m venv venv
                            venv\\Scripts\\python.exe -m pip install tox==${TOX_VERSION}
                        """
                    }
                }
                stage('Update drives FW') {
                    steps {
                        bat '''
                             venv\\Scripts\\python.exe -m tox -e firmware -- canopen
                        '''
                    }
                }
                stage('Run CANopen tests') {
                    steps {
                        bat """
                            venv\\Scripts\\python.exe -m tox -e ${PYTHON_VERSIONS} -- --protocol canopen --junitxml=pytest_canopen_report.xml
                        """
                        bat """
                            move .coverage .coverage_canopen
                        """
                        junit 'pytest_canopen_report.xml'
                    }
                }
                stage('Run Ethernet tests') {
                    steps {
                        bat """
                            venv\\Scripts\\python.exe -m tox -e ${PYTHON_VERSIONS} -- --protocol ethernet --junitxml=pytest_ethernet_report.xml
                        """
                        bat """
                            move .coverage .coverage_ethernet
                        """
                        junit 'pytest_ethernet_report.xml'
                    }
                }
                stage('Save test results') {
                    steps {
                        unstash 'coverage_docker'
                        unstash 'coverage_reports'
                        bat '''
                            venv\\Scripts\\python.exe -m tox -e coverage .coverage_docker .coverage_no_connection .coverage_ethercat .coverage_ethernet .coverage_canopen
                        '''
                        publishCoverage adapters: [coberturaReportAdapter('coverage.xml')]
                        archiveArtifacts artifacts: '*.xml'
                    }
                }
            }
        }
    }
}