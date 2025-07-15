@Library('cicd-lib@0.14') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.5"
WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.6"
def PUBLISHER_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/publisher:1.8"

DEFAULT_PYTHON_VERSION = "3.9"

ALL_PYTHON_VERSIONS = "3.9,3.10,3.11,3.12"
RUN_PYTHON_VERSIONS = ""
def PYTHON_VERSION_MIN = "3.9"
def PYTHON_VERSION_MAX = "3.12"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"
def RACK_SPECIFIERS_PATH = "tests.setups.rack_specifiers"

WIRESHARK_DIR = "wireshark"
USE_WIRESHARK_LOGGING = ""
START_WIRESHARK_TIMEOUT_S = 10.0

wheel_stashes = []
coverage_stashes = []

def getVersionForPR() {
    if (!env.CHANGE_ID) {
        return ""
    }
    def latest_tag = ''
    if (isUnix()) {
        sh "git config --global --add safe.directory '*'"
        latest_tag = sh(returnStdout: true, script: 'git describe --tags --abbrev=0').trim()
    } else {
        latest_tag = powershell(returnStdout: true, script: 'git describe --tags --abbrev=0').trim()
    }
    return "${latest_tag}+PR${env.CHANGE_ID}B${env.BUILD_NUMBER}"
}

def reassignFilePermissions() {
    if (isUnix()) {
        sh 'chmod -R 777 .'
    }
}

def getWheelPath(tox_skip_install, python_version) {
    if (tox_skip_install) {
        script {
            def pythonVersionTag = "cp${python_version.replace('.', '')}"
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

def clearWiresharkLogs() {
    bat(script: 'del /f "%WIRESHARK_DIR%\\*.pcap"', returnStatus: true)
}

def archiveWiresharkLogs() {
    archiveArtifacts artifacts: "${WIRESHARK_DIR}\\*.pcap", allowEmptyArchive: true
}

def runTestHW(markers, setup_name, tox_skip_install = false, extra_args = "") {
    try {
        timeout(time: 1, unit: 'HOURS') {
            def firstIteration = true
            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
            pythonVersions.each { version ->
                def wheelFile = getWheelPath(tox_skip_install, version)
                withEnv(["INGENIALINK_WHEEL_PATH=${wheelFile}", "TOX_SKIP_INSTALL=${tox_skip_install.toString()}", "WIRESHARK_SCOPE=${params.WIRESHARK_LOGGING_SCOPE}", "CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS}", "START_WIRESHARK_TIMEOUT_S=${START_WIRESHARK_TIMEOUT_S}"]) {
                    try {
                        def py_version = "py" + DEFAULT_PYTHON_VERSION.replace(".", "")
                        def setupArg = setup_name ? "--setup ${setup_name} " : ""
                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${py_version} -- " +
                                "-m \"${markers}\" " +
                                "${setupArg}" +
                                "--job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${setup_name}\" " +
                                "-o log_cli=True " +
                                "${extra_args}"

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
        }
    } finally {
        archiveWiresharkLogs()
        clearWiresharkLogs()
    }
}

/* Build develop everyday 3 times starting at 19:00 UTC (21:00 Barcelona Time), running all tests */
CRON_SETTINGS = BRANCH_NAME == "develop" ? '''0 19,21,23 * * *''' : ""

pipeline {
    agent none
    options {
        timestamps()
    }
    triggers {
        cron(CRON_SETTINGS)
    }
    parameters {
        choice(
                choices: ['MIN', 'MAX', 'MIN_MAX', 'All'],
                name: 'PYTHON_VERSIONS'
        )
        booleanParam(name: 'WIRESHARK_LOGGING', defaultValue: true, description: 'Enable Wireshark logging')
        choice(
                choices: ['function', 'module', 'session'],
                name: 'WIRESHARK_LOGGING_SCOPE'
        )
        booleanParam(name: 'CLEAR_SUCCESSFUL_WIRESHARK_LOGS', defaultValue: true, description: 'Clears Wireshark logs if the test passed')
    }
    stages {
        stage("Set env") {
            steps {
                script {
                    if (env.BRANCH_NAME == 'master') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME == 'develop') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else {
                        if (env.PYTHON_VERSIONS == "MIN_MAX") {
                          RUN_PYTHON_VERSIONS = "${PYTHON_VERSION_MIN},${PYTHON_VERSION_MAX}"
                        } else if (env.PYTHON_VERSIONS == "MIN") {
                          RUN_PYTHON_VERSIONS = PYTHON_VERSION_MIN
                        } else if (env.PYTHON_VERSIONS == "MAX") {
                          RUN_PYTHON_VERSIONS = PYTHON_VERSION_MAX
                        } else if (env.PYTHON_VERSIONS == "All") {
                          RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                        } else { // Branch-indexing
                          RUN_PYTHON_VERSIONS = PYTHON_VERSION_MIN
                        }
                    }

                    if (params.WIRESHARK_LOGGING) {
                        USE_WIRESHARK_LOGGING = "--run_wireshark"
                    } else {
                        USE_WIRESHARK_LOGGING = ""
                    }
                }
            }
        }

        stage('Build and publish') {
            stages {
                stage('Build') {
                    parallel {
                        stage('Build Windows') {
                            agent {
                                docker {
                                    label SW_NODE
                                    image WIN_DOCKER_IMAGE
                                }
                            }
                            environment {
                                SETUPTOOLS_SCM_PRETEND_VERSION = getVersionForPR()
                            }
                            stages {
                                stage('Move workspace') {
                                    steps {
                                        bat "XCOPY ${env.WORKSPACE} C:\\Users\\ContainerAdministrator\\ingenialink_python /s /i /y /e /h"
                                    }
                                }
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
                                stage('Build') {
                                    steps {
                                        script {
                                            def pythonVersions = ALL_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                def result = bat(returnStatus: true, script: """
                                                        cd C:\\Users\\ContainerAdministrator\\ingenialink_python
                                                        py -${version} -m tox -e build
                                                        robocopy dist ${env.WORKSPACE}\\dist *.whl /XO /NFL /NDL /NJH /NJS
                                                    """)
                                                if (result > 7) {
                                                    error "Robocopy failed with exit code ${result}"
                                                }
                                            }
                                        }
                                    }
                                }
                                stage('Archive artifacts') {
                                    steps {
                                        archiveArtifacts(artifacts: "dist\\*", followSymlinks: false)
                                        script {
                                            stash_name = "publish_wheels-windows"
                                            wheel_stashes.add(stash_name)
                                            stash includes: "dist\\*", name: stash_name
                                        }
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
                        stage('Build Linux') {
                            agent {
                                docker {
                                    label 'worker'
                                    image LIN_DOCKER_IMAGE
                                    args '-u root:root'
                                }
                            }
                            environment {
                                SETUPTOOLS_SCM_PRETEND_VERSION = getVersionForPR()
                            }
                            stages {
                                stage('Build') {
                                    steps {
                                        sh "python${DEFAULT_PYTHON_VERSION} -m tox -e build"
                                    }
                                    post {
                                        always {
                                            reassignFilePermissions()
                                        }
                                    }
                                }
                                stage('Archive artifacts') {
                                    steps {
                                        archiveArtifacts(artifacts: "dist\\*", followSymlinks: false)
                                        script {
                                            stash_name = "publish_wheels-linux"
                                            wheel_stashes.add(stash_name)
                                            stash includes: "dist\\*", name: stash_name
                                        }
                                    }
                                }
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
                stage('Publish wheels') {
                    agent {
                        docker {
                            label 'worker'
                            image PUBLISHER_DOCKER_IMAGE
                        }
                    }
                    stages {
                        stage('Unstash')
                        {
                            steps {
                                script {
                                    for (stash_name in wheel_stashes) {
                                        unstash stash_name
                                    }
                                }
                            }
                        }
                        stage('Publish Ingenia PyPi') {
                            steps {
                                publishIngeniaPyPi('dist/*')
                            }
                        }
                        stage('Publish PyPi') {
                            when {
                                branch 'master'
                            }
                            steps {
                                publishPyPi('dist/*')
                            }
                        }
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
                                bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                                        "-m docker " +
                                        "-o log_cli=True"
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
                                    def run_py_versions = RUN_PYTHON_VERSIONS.split(',').collect { "py" + it.replace('.', '') }.join(',')
                                    sh """
                                        python${DEFAULT_PYTHON_VERSION} -m tox -e ${run_py_versions} -- -m no_connection -o log_cli=True
                                    """
                                }
                            }
                            post {
                                always {
                                    junit "pytest_reports\\*.xml"
                                }
                            }
                        }
                        stage('Run virtual drive tests on docker') {
                            steps {
                                script {
                                    def run_py_versions = RUN_PYTHON_VERSIONS.split(',').collect { "py" + it.replace('.', '') }.join(',')
                                    sh """
                                        python${DEFAULT_PYTHON_VERSION} -m tox -e ${run_py_versions} -- -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP -o log_cli=True
                                    """
                                }
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
                        stage ("Clear Wireshark logs") {
                            steps {
                                clearWiresharkLogs()
                            }
                        }
                        stage('Unstash')
                        {
                            steps {
                                script {
                                    for (stash_name in wheel_stashes) {
                                        unstash stash_name
                                    }
                                }
                            }
                        }
                        stage('EtherCAT Everest') {
                            steps {
                                runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_EVE_SETUP", true, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('EtherCAT Capitan') {
                            steps {
                                runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_CAP_SETUP", true, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('EtherCAT Multislave') {
                            steps {
                                runTestHW("multislave", "${RACK_SPECIFIERS_PATH}.ECAT_MULTISLAVE_SETUP", true, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('Run no-connection tests') {
                            steps {
                                runTestHW("no_connection", null, true)
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
                        stage('Unstash')
                        {
                            steps {
                                script {
                                    for (stash_name in wheel_stashes) {
                                        unstash stash_name
                                    }
                                }
                            }
                        }
                        stage('CANopen Everest') {
                            steps {
                                runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_EVE_SETUP", true)
                            }
                        }
                        stage('CANopen Capitan') {
                            steps {
                                runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_CAP_SETUP", true)
                            }
                        }
                        stage('Ethernet Everest') {
                            steps {
                                runTestHW("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_EVE_SETUP", true, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('Ethernet Capitan') {
                            steps {
                                runTestHW("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_CAP_SETUP", true, USE_WIRESHARK_LOGGING)
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

                    bat "py -3.9 -m pip install pytest==7.0.1 pytest-cov==2.12.1"
                    bat "py -3.9 -m coverage combine ${coverage_files}"
                    bat "py -3.9 -m coverage xml --include='*/ingenialink/*'"
                }
                recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                archiveArtifacts artifacts: '*.xml'
            }
        }
    }
}
