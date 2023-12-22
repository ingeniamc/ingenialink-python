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
                    image 'ingeniacontainers.azurecr.io/win-python-builder:dev'
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
                        bat '''
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            py -3.9 -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                            venv\\Scripts\\python.exe -m pip install -e .
                        '''
                    }
                }
                stage('Build wheels') {
                    steps {
                        bat '''
                             cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                             venv\\Scripts\\python.exe setup.py build sdist bdist_wheel
                        '''
                    }
                }
                stage('Check formatting') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            venv\\Scripts\\python.exe -m black --check ingenialink tests
                        """
                    }
                }
                stage('Type checking') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            venv\\Scripts\\python.exe -m mypy ingenialink
                        """
                    }
                }
                stage('Generate documentation') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            venv\\Scripts\\python.exe -m sphinx -b html docs _docs
                        """
                    }
                }
                stage('Run docker tests') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            venv\\Scripts\\python.exe -m coverage run -m pytest tests -m docker --junitxml=pytest_docker_report.xml
                            move .coverage ${env.WORKSPACE}\\.coverage_docker
                            move pytest_docker_report.xml ${env.WORKSPACE}\\pytest_docker_report.xml
                            exit /b 0
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
                        bat '''
                            python -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                        '''
                    }
                }
                stage('Update drives FW') {
                    steps {
                        bat '''
                             venv\\Scripts\\python.exe -m tests.resources.Scripts.load_FWs ethercat
                        '''
                    }
                }
                stage('Run EtherCAT tests') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m coverage run -m pytest tests --protocol ethercat --junitxml=pytest_ethercat_report.xml
                            move .coverage .coverage_ethercat
                            exit /b 0
                        '''
                        junit 'pytest_ethercat_report.xml'
                    }
                }
                stage('Run no-connection tests') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m coverage run -m pytest tests --junitxml=pytest_no_connection_report.xml
                            move .coverage .coverage_no_connection
                            exit /b 0
                        '''
                        junit 'pytest_no_connection_report.xml'
                    }
                }
                stage('Archive') {
                    steps {
                        stash includes: '.coverage_no_connection, .coverage_ethercat', name: 'coverage_reports'
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
                        bat '''
                            python -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                        '''
                    }
                }
                stage('Update drives FW') {
                    steps {
                        bat '''
                             venv\\Scripts\\python.exe -m tests.resources.Scripts.load_FWs canopen
                        '''
                    }
                }
                stage('Run CANopen tests') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m coverage run -m pytest tests --protocol canopen --junitxml=pytest_canopen_report.xml
                            move .coverage .coverage_canopen
                            exit /b 0
                        '''
                        junit 'pytest_canopen_report.xml'
                    }
                }
                stage('Run Ethernet tests') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m coverage run -m pytest tests --protocol ethernet --junitxml=pytest_ethernet_report.xml
                            move .coverage .coverage_ethernet
                            exit /b 0
                        '''
                        junit 'pytest_ethernet_report.xml'
                    }
                }
                stage('Save test results') {
                    steps {
                        unstash 'coverage_docker'
                        unstash 'coverage_reports'
                        bat '''
                            venv\\Scripts\\python.exe -m coverage combine .coverage_docker .coverage_no_connection .coverage_ethercat .coverage_ethernet .coverage_canopen
                            venv\\Scripts\\python.exe -m coverage xml --include=ingenialink/*
                        '''
                        publishCoverage adapters: [coberturaReportAdapter('coverage.xml')]
                        archiveArtifacts artifacts: '*.xml'
                    }
                }
            }
        }
    }
}