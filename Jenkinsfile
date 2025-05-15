@Library('cicd-lib@0.12') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.5"
def WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.6"
def PUBLISHER_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/publisher:1.8"

DEFAULT_PYTHON_VERSION = "3.9"

ALL_PYTHON_VERSIONS = "py39,py310,py311,py312"
RUN_PYTHON_VERSIONS = ""
PYTHON_VERSION_MIN = "py39"
def PYTHON_VERSION_MAX = "py312"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"
def RACK_SPECIFIERS_PATH = "tests.setups.rack_specifiers"

coverage_stashes = []

// Run this before PYTEST tox command that requires develop ingenialink installation and that 
// may run in parallel/after with EtherCAT/CANopen tests, because these tests alter its value
def restoreIngenialinkWheelEnvVar() {
    env.INGENIALINK_WHEEL_PATH = null
    env.TOX_SKIP_INSTALL = false
}

def getWheelPath(tox_skip_install, python_version) {
    if (tox_skip_install) {
        script {
            def pythonVersionTag = "cp${python_version.replace('py', '')}"
            def files = findFiles(glob: "dist/*${pythonVersionTag}*.whl")
            if (files.length == 0) {
                error "No .whl file found for Python version ${python_version} in the dist directory."
            }
            def wheelFile = files[0].name
            return "dist\\${wheelFile}"
        }
    }
    else {
        return ""
    }
}

def runTest(markers, setup_name, tox_skip_install = false) {
    unstash 'wheels'
    def firstIteration = true
    def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
    pythonVersions.each { version ->
        def wheelFile = getWheelPath(tox_skip_install, version)
        env.TOX_SKIP_INSTALL = tox_skip_install.toString()
        env.INGENIALINK_WHEEL_PATH = wheelFile
        try {
            bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${version} -- " +
                    "-m \"${markers}\" " +
                    "--setup ${setup_name} " +
                    "--job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${setup_name}\""

        } catch (err) {
            unstable(message: "Tests failed")
        } finally {
            junit "pytest_reports\\*.xml"
            // Delete the junit after publishing it so it not re-published on the next stage
            bat "del /S /Q pytest_reports\\*.xml"
            if (firstIteration) {
                def coverage_stash = ".coverage_${setup_name}"
                bat "move .coverage ${coverage_stash}"
                stash includes: coverage_stash, name: coverage_stash
                coverage_stashes.add(coverage_stash)
                firstIteration = false
            }
        }
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
                        stage ('Git Commit to Build description') {
                            steps {
                                // Build description should follow the format VAR1=value1;VAR2=value2...
                                script {
                                    def currentCommit = bat(script: "git rev-parse HEAD", returnStdout: true).trim()
                                    def currentCommitHash = (currentCommit =~ /\b[0-9a-f]{40}\b/)[0]
                                    echo "Current Commit Hash: ${currentCommitHash}"
                                    def currentCommitBranch = bat(script: "git branch --contains ${currentCommitHash}", returnStdout: true).trim().split("\n").find { it.contains('*') }.replace('* ', '').trim()
                                    echo "currentCommitBranch: ${currentCommitBranch}"
                                    
                                    if (currentCommitBranch.contains('detached')) {
                                        def shortCommitHash = (currentCommitBranch =~ /\b[0-9a-f]{7,40}\b/)[0]
                                        def detachedCommit = bat(script: "git rev-parse ${shortCommitHash}", returnStdout: true).trim()
                                        def detachedCommitHash = (detachedCommit =~ /\b[0-9a-f]{40}\b/)[0]
                                        echo "Detached Commit Hash: ${detachedCommitHash}"
                                        currentBuild.description = "ORIGINAL_GIT_COMMIT_HASH=${detachedCommitHash}"
                                    } else {
                                        echo "No detached HEAD state found. Using current commit hash ${currentCommitHash}."
                                        currentBuild.description = "ORIGINAL_GIT_COMMIT_HASH=${currentCommitHash}"
                                    }
                                }
                            }
                        }
                        stage('Move workspace') {
                            steps {
                                bat "XCOPY ${env.WORKSPACE} C:\\Users\\ContainerAdministrator\\ingenialink_python /s /i /y"
                            }
                        }
                        // stage('Type checking') {
                        //     steps {
                        //         bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e type"
                        //     }
                        // }
                        // stage('Format checking') {
                        //     steps {
                        //         bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e format"
                        //     }
                        // }
                        stage('Build') {
                            steps {
                                script {
                                    def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                    pythonVersions.each { version ->
                                        def distDir = version == PYTHON_VERSION_MIN ? "dist" : "dist_${version}"
                                        def buildDir = version == PYTHON_VERSION_MIN ? "build" : "build_${version}"
                                        env.TOX_PYTHON_VERSION = version
                                        env.TOX_DIST_DIR = distDir
                                        env.TOX_BUILD_ENV_DIR = buildDir
                                        bat """
                                            cd C:\\Users\\ContainerAdministrator\\ingenialink_python
                                            py -${DEFAULT_PYTHON_VERSION} -m tox -e build
                                            XCOPY ${distDir}\\*.whl ${env.WORKSPACE}\\dist /s /i
                                        """
                                    }
                                }
                            }
                        }
                        stage('Archive artifacts') {
                            steps {
                                archiveArtifacts(artifacts: "dist\\*", followSymlinks: false)
                                stash includes: "dist\\*", name: 'wheels'
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
                        unstash 'wheels'
                        publishPyPi("dist/*")
                    }
                }
            }
        }
        
        stage('Tests') {
            parallel {
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
                                script {
                                    restoreIngenialinkWheelEnvVar()
                                }
                                bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                                        "-m docker --setup summit_testing_framework.setups.no_drive.TESTS_SETUP"
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
                                script {
                                    restoreIngenialinkWheelEnvVar()
                                }
                                sh """
                                    python${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- -m no_connection --setup summit_testing_framework.setups.no_drive.TESTS_SETUP
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
                        stage('EtherCAT Everest') {
                            steps {
                                runTest("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_EVE_SETUP", true)
                            }
                        }
                        stage('EtherCAT Capitan') {
                            steps {
                                runTest("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_CAP_SETUP", true)
                            }
                        }
                        stage('EtherCAT Multislave') {
                            steps {
                                runTest("multislave", "${RACK_SPECIFIERS_PATH}.ECAT_MULTISLAVE_SETUP", true)
                            }
                        }
                        stage('Run no-connection tests') {
                            steps {
                                runTest("no_connection", "summit_testing_framework.setups.no_drive.TESTS_SETUP", true)
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
                                runTest("canopen", "${RACK_SPECIFIERS_PATH}.CAN_EVE_SETUP", true)
                            }
                        }
                        stage('CANopen Capitan') {
                            steps {
                                runTest("canopen", "${RACK_SPECIFIERS_PATH}.CAN_CAP_SETUP", true)
                            }
                        }
                        stage('Ethernet Everest') {
                            steps {
                                runTest("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_EVE_SETUP", true)
                            }
                        }
                        stage('Ethernet Capitan') {
                            steps {
                                runTest("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_CAP_SETUP", true)
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
