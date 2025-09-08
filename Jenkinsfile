@Library('cicd-lib@0.16') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.6"
WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.7"
def PUBLISHER_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/publisher:1.8"

DEFAULT_PYTHON_VERSION = "3.9"

ALL_PYTHON_VERSIONS = "3.9,3.10,3.11,3.12"
RUN_PYTHON_VERSIONS = ""
PYTHON_VERSION_MIN = "3.9"
PYTHON_VERSION_MAX = "3.12"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"
def RACK_SPECIFIERS_PATH = "tests.setups.rack_specifiers"

WIN_DOCKER_TMP_PATH = "C:\\Users\\ContainerAdministrator\\ingenialink_python"
LIN_DOCKER_TMP_PATH = "/tmp/ingenialink_python"

WIRESHARK_DIR = "wireshark"
USE_WIRESHARK_LOGGING = ""
START_WIRESHARK_TIMEOUT_S = 10.0

wheel_stashes = []
coverage_stashes = []

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

def createVirtualEnvironments(boolean installWheel = true, String workingDir = null, String pythonVersionList = "") {
    def versions = pythonVersionList?.trim() ? pythonVersionList : RUN_PYTHON_VERSIONS
    def pythonVersions = versions.split(',')
    // Ensure DEFAULT_PYTHON_VERSION is included if not already present
    if (!pythonVersions.contains(DEFAULT_PYTHON_VERSION)) {
        pythonVersions = pythonVersions + [DEFAULT_PYTHON_VERSION]
    }
    pythonVersions.each { version ->
        def venvName = ".venv${version}"
        def cdCmd = workingDir ? "cd ${workingDir}" : ""
        if (isUnix()) {
            sh """
                ${cdCmd}
                python${version} -m venv --without-pip ${venvName}
                . ${venvName}/bin/activate
                poetry sync --no-root --all-groups
                deactivate
            """
        } else {
            def installWheelCmd = installWheel ? "poetry run poe install-wheel" : ""
            bat """
                ${cdCmd}
                py -${version} -m venv ${venvName}
                call ${venvName}/Scripts/activate
                poetry sync --no-root --all-groups
                ${installWheelCmd}
                deactivate
            """
        }
    }
}

def buildWheel(py_version) {
     echo "Running build for Python ${py_version} in Docker environment"
    if (isUnix()) {
        sh """
            cd ${LIN_DOCKER_TMP_PATH}
            . .venv${py_version}/bin/activate
            poetry run poe build-wheel
            deactivate
        """
    } else {
        bat """
            cd ${WIN_DOCKER_TMP_PATH}
            call .venv${py_version}/Scripts/activate
            poetry run poe build-wheel
            deactivate
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
                        def setupArg = setup_name ? "--setup ${setup_name} " : ""
                        def venvName = ".venv${version}"
                        bat """
                            call ${venvName}/Scripts/activate
                            poetry run poe tests --import-mode=importlib --cov=${venvName}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-${version}.xml --junit-prefix=${version} -m \"${markers}\" ${setupArg} --job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${setup_name}\" -o log_cli=True ${extra_args}"
                            deactivate
                        """
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
CRON_SETTINGS = BRANCH_NAME == "develop" ? '''0 19,21,23 * * * % PYTHON_VERSIONS=All''' : ""

pipeline {
    agent none
    options {
        timestamps()
    }
    triggers {
        parameterizedCron(CRON_SETTINGS)
    }
    parameters {
        choice(
                choices: ['MIN', 'MAX', 'MIN_MAX', 'All'],
                name: 'PYTHON_VERSIONS'
        )
        booleanParam(name: 'WIRESHARK_LOGGING', defaultValue: false, description: 'Enable Wireshark logging')
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
                                        bat "XCOPY ${env.WORKSPACE} ${WIN_DOCKER_TMP_PATH} /s /i /y /e /h"
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            createVirtualEnvironments(false, WIN_DOCKER_TMP_PATH, ALL_PYTHON_VERSIONS)
                                        }
                                    }
                                }
                                stage('Build wheels') {
                                    environment {
                                        SETUPTOOLS_SCM_PRETEND_VERSION = getPythonVersionForPr()
                                    }
                                    steps {
                                        script {
                                            def pythonVersions = ALL_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                buildWheel(version)
                                            }
                                        }
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe check-wheels
                                            COPY ingenialink\\_version.py ${env.WORKSPACE}\\ingenialink\\_version.py
                                            XCOPY dist ${env.WORKSPACE}\\dist /s /i
                                        """
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe type
                                        """
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe format
                                        """
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
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe docs
                                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                                            XCOPY docs.zip ${env.WORKSPACE}
                                        """
                                        stash includes: 'docs.zip', name: 'docs'
                                    }
                                }
                                stage('Run no-connection tests on docker') {
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                bat """
                                                    cd ${WIN_DOCKER_TMP_PATH}
                                                    call .venv${version}/Scripts/activate
                                                    poetry run poe install-wheel
                                                    poetry run poe tests --import-mode=importlib --cov=.venv${version}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m docker -o log_cli=True
                                                """
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            bat """
                                                mkdir -p pytest_reports
                                                XCOPY ${WIN_DOCKER_TMP_PATH}\\pytest_reports\\* pytest_reports\\ /s /i /y /e /h
                                                move ${WIN_DOCKER_TMP_PATH}\\.coverage .coverage_docker
                                            """
                                            junit 'pytest_reports/*.xml'
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
                                stage('Move workspace') {
                                    steps {
                                        script {
                                            sh """
                                                mkdir -p ${LIN_DOCKER_TMP_PATH}
                                                cp -r ${env.WORKSPACE}/. ${LIN_DOCKER_TMP_PATH}
                                            """
                                        }
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        createVirtualEnvironments(false, LIN_DOCKER_TMP_PATH)
                                    }
                                }
                                stage('Build wheels') {
                                    environment {
                                        SETUPTOOLS_SCM_PRETEND_VERSION = getPythonVersionForPr()
                                    }
                                    steps {
                                        script {
                                            buildWheel(DEFAULT_PYTHON_VERSION)
                                            sh """
                                                cd ${LIN_DOCKER_TMP_PATH}
                                                . .venv${DEFAULT_PYTHON_VERSION}/bin/activate
                                                poetry run poe check-wheels
                                                deactivate
                                                mkdir -p ${env.WORKSPACE}/dist
                                                cp dist/* ${env.WORKSPACE}/dist/
                                            """
                                        }
                                    }
                                }
                                stage('Archive artifacts') {
                                    steps {
                                        archiveArtifacts(artifacts: "dist/*", followSymlinks: false)
                                        script {
                                            stash_name = "publish_wheels-linux"
                                            wheel_stashes.add(stash_name)
                                            stash includes: "dist/*", name: stash_name
                                        }
                                    }
                                }
                                stage('Run no-connection tests on docker') {
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                sh """
                                                    cd ${LIN_DOCKER_TMP_PATH}
                                                    . .venv${version}/bin/activate
                                                    poetry run poe install-wheel
                                                    poetry run poe tests --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m no_connection -o log_cli=True
                                                    deactivate
                                                """
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            sh """
                                                mkdir -p pytest_reports
                                                cp ${LIN_DOCKER_TMP_PATH}/pytest_reports/* pytest_reports/
                                            """
                                            junit 'pytest_reports/*.xml'
                                        }
                                    }
                                }
                                stage('Run virtual drive tests on docker') {
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                sh """
                                                    cd ${LIN_DOCKER_TMP_PATH}
                                                    . .venv${version}/bin/activate
                                                    poetry run poe install-wheel
                                                    poetry run poe tests --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP -o log_cli=True
                                                    deactivate
                                                """
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            sh """
                                                mkdir -p pytest_reports
                                                cp ${LIN_DOCKER_TMP_PATH}/pytest_reports/* pytest_reports/
                                            """
                                            junit 'pytest_reports/*.xml'
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
                        stage('Publish Novanta PyPi') {
                            steps {
                                publishNovantaPyPi('dist/*')
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
                        stage('Create virtual environments') {
                            steps {
                                script {
                                    createVirtualEnvironments()
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
                        stage("Safety Denali Phase I") {
                            runTestHW("fsoe", "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE1_SETUP", USE_WIRESHARK_LOGGING)
                        }
                        stage("Safety Denali Phase II") {
                            runTestHW("fsoe", "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE2_SETUP", USE_WIRESHARK_LOGGING)
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
                        stage('Create virtual environments') {
                            steps {
                                script {
                                    createVirtualEnvironments()
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
                    bat "XCOPY ${env.WORKSPACE} ${WIN_DOCKER_TMP_PATH} /s /i /y /e /h"
                    createVirtualEnvironments(true, WIN_DOCKER_TMP_PATH, DEFAULT_PYTHON_VERSION)
                    bat """
                        cd ${WIN_DOCKER_TMP_PATH}
                        call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                        poetry run poe cov-combine --${coverage_files}
                        poetry run poe cov-report
                        XCOPY coverage.xml ${env.WORKSPACE}
                        deactivate
                    """
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                    archiveArtifacts artifacts: '*.xml'
                }
            }
        }
    }
}
