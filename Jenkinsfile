def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"
def PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9"]
def style_check = false


pipeline {
    agent none
    stages {
        stage('Build wheels and documentation') {
            agent {
                docker {
                    label SW_NODE
                    image 'ingeniacontainers.azurecr.io/ingenialink-builder'
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
                stage('Build wheels') {
                    steps {
                        script {
                            PYTHON_VERSIONS.each { version ->
                                stage("Build Python ${version} wheel") {
                                    bat """
                                        cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                                        py -${version} -m venv py${version}
                                        py${version}\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                                        py${version}\\Scripts\\python.exe -m pip install -e .
                                        py${version}\\Scripts\\python.exe setup.py build sdist bdist_wheel
                                    """
                                }
                            }
                        }
                    }
                }
                stage('Check formatting') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            py${PYTHON_VERSIONS[-1]}\\Scripts\\python.exe -m black --check ingenialink tests
                        """
                    }
                }
                stage('Generate documentation') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            py${PYTHON_VERSIONS[-1]}\\Scripts\\python.exe -m sphinx -b html docs _docs
                        """
                    }
                }
                stage('Archive') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingenialink-python
                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                            XCOPY dist ${env.WORKSPACE}\\dist /i
                            XCOPY docs.zip ${env.WORKSPACE}
                            XCOPY ingenialink\\*.pyd ${env.WORKSPACE}\\ingenialink
                        """
                        archiveArtifacts artifacts: "dist\\*, docs.zip"
                        stash includes: 'ingenialink\\*.pyd', name: 'pyds'
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
                stage('Update drives FW') {
                    steps {
                        bat '''
                            python -m venv ingeniamotion
                            ingeniamotion\\Scripts\\python.exe -m pip install ingeniamotion ping3
                            ingeniamotion\\Scripts\\python.exe tests\\resources\\Scripts\\load_FWs.py ethercat
                        '''
                    }
                }
                stage('Install deps') {
                    steps {
                        unstash 'pyds'
                        bat '''
                            python -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
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
                stage('Update drives FW') {
                    steps {
                        bat '''
                            python -m venv ingeniamotion
                            ingeniamotion\\Scripts\\python.exe -m pip install ingeniamotion ping3
                            ingeniamotion\\Scripts\\python.exe tests\\resources\\Scripts\\load_FWs.py canopen
                        '''
                    }
                }
                stage('Install deps') {
                    steps {
                        unstash 'pyds'
                        bat '''
                            python -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
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
                        unstash 'coverage_reports'
                        bat '''
                            venv\\Scripts\\python.exe -m coverage combine .coverage_no_connection .coverage_ethercat .coverage_ethernet .coverage_canopen
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