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

def ALL_PYTHON_VERSIONS = "py39,py310,py311,py312"
def RUN_PYTHON_VERSIONS = ""
def PYTHON_VERSION_MIN = "py39"
def PYTHON_VERSION_MAX = "py312"
def DEFAULT_PYTHON_VERSION = "3.9"
def TOX_VERSION = "4.12.1"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"

pipeline {
    agent none
    stages {
        stage("Set run python versions") {
            steps {
                script {
                    if (env.BRANCH_NAME == 'master') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME == 'develop') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else {
                        RUN_PYTHON_VERSIONS = "${PYTHON_VERSION_MIN},${PYTHON_VERSION_MAX}"
                    }
                }
            }
        }

        stage('Get FoE application') {
            agent {
                docker {
                    label "worker"
                    image "ingeniacontainers.azurecr.io/publisher:1.8"
                }
            }
            stages {
                stage('Get FoE application') {
                    steps {
                        script {
                            FOE_APP_VERSION = sh(script: 'cd ingenialink/bin && python3.9 -c "import FoE; print(FoE.__version__)"', returnStdout: true).trim()
                        }
                        copyFromDist(".", "$DIST_FOE_APP_PATH/$FOE_APP_VERSION")
                        sh "mv FoEUpdateFirmwareLinux $FOE_APP_NAME_LINUX"
                        stash includes: "$FOE_APP_NAME,$FOE_APP_NAME_LINUX", name: 'foe_app'
                    }
                }
            }
        }
        stage('Run tests on linux docker') {
            agent {
                docker {
                    label "worker"
                    image "ingeniacontainers.azurecr.io/docker-python:1.4"
                }
            }
            stages {
                stage('Install deps') {
                    steps {
                        sh """
                            python${DEFAULT_PYTHON_VERSION} -m pip install tox==${TOX_VERSION}
                        """
                    }
                }
                stage('Run no-connection tests') {
                    steps {
                        sh """
                            python${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- --junitxml=pytest_no_connection_report.xml
                        """
                    }
                    post {
                        always {
                            junit "pytest_no_connection_report.xml"
                        }
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
                stage('Get FoE application') {
                    steps {
                        unstash 'foe_app'
                        bat """
                            XCOPY $FOE_APP_NAME $LIB_FOE_APP_PATH\\win_64x\\
                            XCOPY $FOE_APP_NAME_LINUX $LIB_FOE_APP_PATH\\linux\\
                        """
                    }
                }
                stage('Install deps') {
                    steps {
                        bat """
                            py -${DEFAULT_PYTHON_VERSION} -m pip install tox==${TOX_VERSION}
                        """
                    }
                }
                stage('Build wheels') {
                    steps {
                        bat '''
                             tox -e build
                        '''
                    }
                }
                stage('Check formatting') {
                    steps {
                        bat """
                            tox -e format
                        """
                    }
                }
                stage('Type checking') {
                    steps {
                        bat """
                            tox -e type
                        """
                    }
                }
                stage('Generate documentation') {
                    steps {
                        bat """
                            tox -e docs
                        """
                    }
                }
                stage('Run docker tests on windows') {
                    steps {
                        bat """
                            tox -e ${RUN_PYTHON_VERSIONS} -- -m docker --junitxml=pytest_docker_report.xml
                        """
                    }
                    post {
                        always {
                            bat """
                                move .coverage ${env.WORKSPACE}\\.coverage_docker
                                move pytest_docker_report.xml ${env.WORKSPACE}\\pytest_docker_report.xml
                            """
                            junit 'pytest_docker_report.xml'
                        }
                    }
                }
                stage('Archive') {
                    steps {
                        bat """
                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                        """
                        stash includes: '.coverage_docker', name: 'coverage_docker'
                        stash includes: 'dist\\*, docs.zip', name: 'publish_files'
                        archiveArtifacts artifacts: 'pytest_docker_report.xml'
                        archiveArtifacts artifacts: "dist\\*, docs.zip"
                    }
                }
            }
        }
        stage('Publish Ingenialink') {
            agent {
                docker {
                    label "worker"
                    image "ingeniacontainers.azurecr.io/publisher:1.8"
                }
            }
            when {
                beforeAgent true
                branch BRANCH_NAME_MASTER
            }
            steps {
                unstash 'publish_files'
                unzip zipFile: 'docs.zip', dir: '.'
                publishDistExt("_docs", DISTEXT_PROJECT_DIR, true)
                publishPyPi("dist/*")
            }
        }
        stage('Run tests with HW') {
            parallel {
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
                        stage('Run EtherCAT tests') {
                            steps {
                                bat """
                                    venv\\Scripts\\python.exe -m tox -e ${RUN_PYTHON_VERSIONS} -- --protocol ethercat --junitxml=pytest_ethercat_report.xml
                                """
                            }
                            post {
                                always {
                                    bat """
                                        move .coverage .coverage_ethercat
                                    """
                                    junit 'pytest_ethercat_report.xml'
                                }
                            }
                        }
                        stage('Run no-connection tests') {
                            steps {
                                bat """
                                    venv\\Scripts\\python.exe -m tox -e ${RUN_PYTHON_VERSIONS} -- --junitxml=pytest_no_connection_report.xml
                                """
                            }
                            post {
                                always {
                                    bat """
                                        move .coverage .coverage_no_connection
                                    """
                                    junit 'pytest_no_connection_report.xml'
                                }
                            }
                        }
                        stage('Archive') {
                            steps {
                                stash includes: '.coverage_ethercat, .coverage_no_connection', name: 'coverage_reports_ecat'
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
                        stage('Run CANopen tests') {
                            steps {
                                bat """
                                    venv\\Scripts\\python.exe -m tox -e ${RUN_PYTHON_VERSIONS} -- --protocol canopen --junitxml=pytest_canopen_report.xml
                                """
                            }
                            post {
                                always {
                                    bat """
                                        move .coverage .coverage_canopen
                                    """
                                    junit 'pytest_canopen_report.xml'
                                }
                            }
                        }
                        stage('Run Ethernet tests') {
                            steps {
                                bat """
                                    venv\\Scripts\\python.exe -m tox -e ${RUN_PYTHON_VERSIONS} -- --protocol ethernet --junitxml=pytest_ethernet_report.xml
                                """
                            }
                            post {
                                always {
                                    bat """
                                        move .coverage .coverage_ethernet
                                    """
                                    junit 'pytest_ethernet_report.xml'
                                }
                            }
                        }
                        stage('Archive') {
                            steps {
                                stash includes: '.coverage_ethernet, .coverage_canopen', name: 'coverage_reports_canopen'
                                archiveArtifacts artifacts: '*.xml'
                            }
                        }
                    }
                }
            }
        }
        stage('Publish test results') {
            agent {
                docker {
                    label "worker"
                    image "ingeniacontainers.azurecr.io/docker-python:1.4"
                }
            }
            steps {
                sh """
                    python${DEFAULT_PYTHON_VERSION} -m pip install tox==${TOX_VERSION}
                """
                unstash 'coverage_docker'
                unstash 'coverage_reports_ecat'
                unstash 'coverage_reports_canopen'
                sh """
                    python${DEFAULT_PYTHON_VERSION} -m tox -e coverage -- .coverage_docker .coverage_no_connection .coverage_ethercat .coverage_ethernet .coverage_canopen
                   """
                publishCoverage adapters: [coberturaReportAdapter('coverage.xml')]
                archiveArtifacts artifacts: '*.xml'
            }
        }
    }
}