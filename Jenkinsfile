@Library('cicd-lib@CIT-296-evaluate-using-scp-for-publishing-to-distext') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.5"
def WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.6"
def PUBLISHER_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/publisher:1.8"

def DIST_FOE_APP_PATH = "ECAT-tools"
def LIB_FOE_APP_PATH = "ingenialink\\bin\\FOE"
def FOE_APP_NAME = "FoEUpdateFirmware.exe"
def FOE_APP_NAME_LINUX = "FoEUpdateFirmware"
def FOE_APP_VERSION = ""

DEFAULT_PYTHON_VERSION = "3.9"

ALL_PYTHON_VERSIONS = "py39,py310,py311,py312"
RUN_PYTHON_VERSIONS = ""
def PYTHON_VERSION_MIN = "py39"
def PYTHON_VERSION_MAX = "py312"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"

coverage_stashes = []

def runTest(protocol, slave = 0) {
    try {
        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                "--protocol ${protocol} " +
                "--slave ${slave} " +
                "--cov=ingenialink " +
                "--job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${protocol}-${slave}\""

    } catch (err) {
        unstable(message: "Tests failed")
    } finally {
        def coverage_stash = ".coverage_${protocol}_${slave}"
        bat "move .coverage ${coverage_stash}"
        junit "pytest_reports\\*.xml"
        // Delete the junit after publishing it so it not re-published on the next stage
        bat "del /S /Q pytest_reports\\*.xml"
        stash includes: coverage_stash, name: coverage_stash
        coverage_stashes.add(coverage_stash)
    }
}

/* Build develop everyday at 19:00 UTC (21:00 Barcelona Time), running all tests */
CRON_SETTINGS = BRANCH_NAME == "develop" ? '''0 19 * * *''' : ""

pipeline {
    agent none
    triggers {
        cron(CRON_SETTINGS)
    }
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
                    image PUBLISHER_DOCKER_IMAGE
                }
            }
            steps {
                script {
                    FOE_APP_VERSION = sh(script: 'cd ingenialink/bin && python3.9 -c "import FoE; print(FoE.__version__)"', returnStdout: true).trim()
                }
                copyFromDist(".", "$DIST_FOE_APP_PATH/$FOE_APP_VERSION")
                sh "mv FoEUpdateFirmwareLinux $FOE_APP_NAME_LINUX"
                stash includes: "$FOE_APP_NAME,$FOE_APP_NAME_LINUX", name: 'foe_app'
            }
        }
        stage('Build and Tests') {
            parallel {
                stage('Build and publish') {
                    stages {
                        stage('Build') {
                            agent {
                                docker {
                                    label SW_NODE
                                    image WIN_DOCKER_IMAGE
                                }
                            }
                            stages {
                                stage('Type checking') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e type"
                                    }
                                }
                                stage('Format checking') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e format"
                                    }
                                }
                                stage('Get FoE application') {
                                    steps {
                                        unstash 'foe_app'
                                        bat "XCOPY $FOE_APP_NAME $LIB_FOE_APP_PATH\\win_64x\\"
                                        bat "XCOPY $FOE_APP_NAME_LINUX $LIB_FOE_APP_PATH\\linux\\"
                                    }
                                }
                                stage('Build') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e build"
                                        stash includes: 'dist\\*', name: 'build'
                                    }
                                }
                                stage('Generate documentation') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e docs"
                                        bat '''"C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256'''
                                        stash includes: 'docs.zip', name: 'docs'
                                    }
                                }
                            }
                        }
                        stage('Publish documentation') {
                            when {
                                beforeAgent true
                                branch BRANCH_NAME_MASTER
                            }
                            agent {
                                label 'worker'
                            }
                            steps {
                                unstash 'docs'
                                unzip zipFile: 'docs.zip', dir: '.'
                                publishDistExt('_docs', DISTEXT_PROJECT_DIR, true)
                            }
                        }
                        stage('Publish to pypi') {
                            when {
                                beforeAgent true
                                branch BRANCH_NAME_MASTER
                            }
                            agent {
                                docker {
                                    label 'worker'
                                    image PUBLISHER_DOCKER_IMAGE
                                }
                            }
                            steps {
                                unstash 'build'
                                publishPyPi("dist/*")
                            }
                        }
                    }
                }
                stage('Docker Windows - Tests') {
                    agent {
                        docker {
                            label SW_NODE
                            image WIN_DOCKER_IMAGE
                        }
                    }
                    stages {
                        stage('Run no-connection tests on docker') {
                            steps {
                                bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                                        "-m docker " +
                                        "--cov=ingenialink"
                            }
                            post {
                                always {
                                    bat "move .coverage .coverage_docker"
                                    junit "pytest_reports\\*.xml"
                                    // Delete the junit after publishing it so it not re-published on the next stage
                                    bat "del /S /Q pytest_reports\\*.xml"
                                    stash includes: '.coverage_docker', name: '.coverage_docker'
                                    script {
                                        coverage_stashes.add(".coverage_docker")
                                    }
                                }
                            }
                        }
                    }
                }
                stage('Docker Linux - Tests') {
                    agent {
                        docker {
                            label "worker"
                            image LIN_DOCKER_IMAGE
                        }
                    }
                    stages {
                        stage('Run no-connection tests on docker') {
                            steps {
                                sh """
                                    python${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS}
                                """
                            }
                            post {
                                always {
                                    junit "pytest_reports\\*.xml"
                                }
                            }
                        }
                    }
                }
                stage('EtherCAT/No Connection - Tests') {
                    options {
                        lock(ECAT_NODE_LOCK)
                    }
                    agent {
                        label ECAT_NODE
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
                        stage('EtherCAT Everest') {
                            steps {
                                runTest("ethercat", 0)
                            }
                        }
                        stage('EtherCAT Capitan') {
                            steps {
                                runTest("ethercat", 1)
                            }
                        }
                        stage('Run no-connection tests') {
                            steps {
                                runTest("no_connection")
                            }
                        }
                    }
                }
                stage('CANopen/Ethernet - Tests') {
                    options {
                        lock(CAN_NODE_LOCK)
                    }
                    agent {
                        label CAN_NODE
                    }
                    stages {
                        stage('CANopen Everest') {
                            steps {
                                runTest("canopen", 0)
                            }
                        }
                        stage('CANopen Capitan') {
                            steps {
                                runTest("canopen", 1)
                            }
                        }
                        stage('Ethernet Everest') {
                            steps {
                                runTest("ethernet", 0)
                            }
                        }
                        stage('Ethernet Capitan') {
                            steps {
                                runTest("ethernet", 1)
                            }
                        }
                    }
                }
            }
        }
        stage('Publish coverage') {
            agent {
                docker {
                    label SW_NODE
                    image WIN_DOCKER_IMAGE
                }
            }
            steps {
                script {
                    def coverage_files = ""

                    for (coverage_stash in coverage_stashes) {
                        unstash coverage_stash
                        coverage_files += " " + coverage_stash
                    }
                    bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e coverage -- ${coverage_files}"
                }
                recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                archiveArtifacts artifacts: '*.xml'
            }
        }
    }
}
