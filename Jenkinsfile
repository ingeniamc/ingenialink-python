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
PYTHON_VERSION_MIN = "3.9"
PYTHON_VERSION_MAX = "3.12"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"
def RACK_SPECIFIERS_PATH = "tests.setups.rack_specifiers"

DOCKER_TMP_PATH = "C:\\Users\\ContainerAdministrator\\ingenialink_python"

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

def clearWiresharkLogs() {
    bat(script: 'del /f "%WIRESHARK_DIR%\\*.pcap"', returnStatus: true)
}

def clearCoverageFiles() {
    bat(script: 'del /f "*.coverage*"', returnStatus: true)
}

def runPython(command, py_version = DEFAULT_PYTHON_VERSION) {
    if (isUnix()) {
        sh "python${py_version} -I -m ${command}"
    } else {
        bat "py -${py_version} -I -m ${command}"
    }
}

def archiveWiresharkLogs() {
    archiveArtifacts artifacts: "${WIRESHARK_DIR}\\*.pcap", allowEmptyArchive: true
}

def activatePoetryEnv(py_version) {
    runPython("poetry env use ${py_version}")
}

def setupEnvironments(py_version = null) {
    runPython("pip install poetry==2.1.3", DEFAULT_PYTHON_VERSION) // Remove poetry install: https://novantamotion.atlassian.net/browse/CIT-412
    def pythonVersions = py_version != null ? [py_version] : RUN_PYTHON_VERSIONS.split(',')
    pythonVersions.each { version ->
        activatePoetryEnv(version)
        runPython("poetry sync --with dev") // Remove all dependencies that are not in the lock file + install main dependencies
    }
}

def buildWheel(py_version) {
    if (isUnix()) {
        runPython("poetry install --no-root --only build,dev") // Install build dependencies
        runPython("poetry run poe build") // Build wheel
    } else {
        echo "Running build for Python ${py_version} in Docker environment"
        // Remove poetry install: https://novantamotion.atlassian.net/browse/CIT-412
        bat """
            cd ${DOCKER_TMP_PATH}
            poetry env use ${py_version}
            poetry sync --no-root --only build,dev
            poetry run poe build
            poetry env remove
        """
    }
}

def runTestHW(markers, setup_name, extra_args = "") {
    try {
        timeout(time: 1, unit: 'HOURS') {
            clearCoverageFiles()
            def firstIteration = true
            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
            pythonVersions.each { version ->
                withEnv(["WIRESHARK_SCOPE=${params.WIRESHARK_LOGGING_SCOPE}", "CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS}", "START_WIRESHARK_TIMEOUT_S=${START_WIRESHARK_TIMEOUT_S}"]) {
                    try {
                        def py_version = "py" + version.replace(".", "")
                        def setupArg = setup_name ? "--setup ${setup_name} " : ""
                        activatePoetryEnv(version)
                        runPython("poetry sync --with dev,tests") // Remove all dependencies except poethepoet (importlib mode)
                        runPython("poetry run poe install-wheel")
                        runPython("poetry run poe tests --import-mode=importlib --cov=.venv\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-tests.xml --junit-prefix=tests -m \"${markers}\" ${setupArg} --job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${setup_name}\" -o log_cli=True ${extra_args}")

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
                            stages {
                                stage('Move workspace') {
                                    steps {
                                        bat "XCOPY ${env.WORKSPACE} C:\\Users\\ContainerAdministrator\\ingenialink_python /s /i /y /e /h"
                                    }
                                }
                                stage('Build wheels') {
                                    environment {
                                        SETUPTOOLS_SCM_PRETEND_VERSION = getVersionForPR()
                                    }
                                    steps {
                                        script {
                                            runPython("pip install poetry==2.1.3", DEFAULT_PYTHON_VERSION)
                                            def pythonVersions = ALL_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                buildWheel(version)
                                            }
                                        }
                                        bat """
                                            cd ${DOCKER_TMP_PATH}
                                            COPY ingenialink\\_version.py ${env.WORKSPACE}\\ingenialink\\_version.py
                                            XCOPY dist ${env.WORKSPACE}\\dist /s /i
                                        """
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        runPython("poetry install --with type,dev")
                                        runPython("poetry run poe type")
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        runPython("poetry install --with format,dev")
                                        runPython("poetry run poe format")
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
                                        runPython("poetry install --with docs,dev")
                                        runPython("poetry run poe docs")
                                        bat '''"C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256'''
                                        stash includes: 'docs.zip', name: 'docs'
                                    }
                                }
                                stage('Run no-connection tests on docker') {
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                bat """
                                                    cd ${DOCKER_TMP_PATH}
                                                    poetry env use ${version}
                                                    poetry install --with dev,tests
                                                    poetry run poe install-wheel
                                                    poetry run poe tests -- --import-mode=importlib --cov=.venv\\lib\\site-packages\\ingenialink --junitxml=pytest_reports\\junit-tests.xml --junit-prefix=tests -m docker -o log_cli=True
                                                    poetry env remove
                                                """
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            bat """
                                                move ${DOCKER_TMP_PATH}\\.coverage .coverage_docker
                                                move ${DOCKER_TMP_PATH}\\pytest_reports\\junit-tests.xml junit-tests.xml
                                            """
                                            junit "junit-tests.xml"
                                            stash includes: '.coverage_docker', name: '.coverage_docker'
                                            script {
                                                coverage_stashes.add(".coverage_docker")
                                            }
                                        }
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
                            stages {
                                stage ('Setup Poetry environments') {
                                    steps {
                                        setupEnvironments(PYTHON_VERSION_MAX)
                                        activatePoetryEnv(DEFAULT_PYTHON_VERSION)
                                    }
                                }
                                stage('Build wheels') {
                                    environment {
                                        SETUPTOOLS_SCM_PRETEND_VERSION = getVersionForPR()
                                    }
                                    steps {
                                        buildWheel(PYTHON_VERSION_MAX)
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
                                stage('Run no-connection tests on docker') {
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                activatePoetryEnv(version)
                                                runPython("poetry install --with dev,tests")
                                                runPython("poetry run poe install-wheel")
                                                runPython("poetry run poe tests -- --junitxml=pytest_reports/junit-tests.xml --junit-prefix=tests -m no_connection -o log_cli=True")
                                            }
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
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                activatePoetryEnv(version)
                                                runPython("poetry install --with dev,tests")
                                                runPython("poetry run poe install-wheel")
                                                runPython("poetry run poe tests -- --junitxml=pytest_reports/junit-tests.xml --junit-prefix=tests -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP  -o log_cli=True")
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            junit "pytest_reports\\*.xml"
                                        }
                                    }
                                }
                            }
                            post {
                                always {
                                    reassignFilePermissions()
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
                                runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_EVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('EtherCAT Capitan') {
                            steps {
                                runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_CAP_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('EtherCAT Multislave') {
                            steps {
                                runTestHW("multislave", "${RACK_SPECIFIERS_PATH}.ECAT_MULTISLAVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('Run no-connection tests') {
                            steps {
                                runTestHW("no_connection", null)
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
                                runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_EVE_SETUP")
                            }
                        }
                        stage('CANopen Capitan') {
                            steps {
                                runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_CAP_SETUP")
                            }
                        }
                        stage('Ethernet Everest') {
                            steps {
                                runTestHW("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_EVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('Ethernet Capitan') {
                            steps {
                                runTestHW("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_CAP_SETUP", USE_WIRESHARK_LOGGING)
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
                    for (stash_name in wheel_stashes) {
                        unstash stash_name
                    }
                    bat "XCOPY ${env.WORKSPACE} C:\\Users\\ContainerAdministrator\\ingenialink_python /s /i /y /e /h"
                    runPython("pip install poetry==2.1.3", DEFAULT_PYTHON_VERSION)
                    bat """
                        cd ${DOCKER_TMP_PATH}
                        poetry env use ${PYTHON_VERSION_MAX}
                        poetry install --with dev,tests
                        poetry run poe cov-combine --${coverage_files}
                        poetry run poe cov-report
                        poetry env remove
                        XCOPY coverage.xml ${env.WORKSPACE}
                    """
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                    archiveArtifacts artifacts: '*.xml'
                }
            }
        }
    }
}
