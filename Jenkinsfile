@Library('cicd-lib@0.21') _

import python.VirtualEnvironment
import python.VEnvManager
import pytest.TestSession
import pytest.TestGroup
import pytest.PyTestManager
import pytest.TestDashboardBuilder

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.6"
def WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.7"
def PUBLISHER_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/publisher:1.8"

def DEFAULT_PYTHON_VERSION = "3.9"

def ALL_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12"] as Set
def PYTHON_VERSION_MIN = "3.9"
def PYTHON_VERSION_MAX = "3.12"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"


@groovy.transform.Field
List wheel_stashes = []

/* List of markers that require hardware */
def HARDWARE_MARKERS = ["ethernet", "ethercat", "canopen", "multislave", "fsoe", "eoe"]

def reassignFilePermissions() {
    if (isUnix()) {
        sh 'chmod -R 777 .'
    }
}

VEnvManager venvManager = new VEnvManager(
  pipeline: this,
  default_python_version: DEFAULT_PYTHON_VERSION,
  poetry_default_install_command: "poetry sync --no-root --all-groups"
)

PyTestManager testManager = new PyTestManager(pipeline: this, venvManager: venvManager)

/* Define default base test sessions to be used/overridden in stages */
TestSession TEST_SESSIONS = new TestSession(
    covPackageName: "ingenialink",
    wiresharkScope: null, // Set later based on parameter
    wiresharkDir: "wireshark",
    startWiresharkTimeoutS: 10.0,
    importMode: "importlib",
    logCli: true,
    setAttApiToken: true
)
TestSession HW_TEST_SESSIONS = TEST_SESSIONS.override()
TestGroup CAN_TESTS = testManager.createGroup("CAN_TEST_SESSIONS", HW_TEST_SESSIONS.override())
TestGroup ETH_TESTS = testManager.createGroup("ETH_TEST_SESSIONS", HW_TEST_SESSIONS.override()) // Wireshark logging is injected later based on parameter
TestGroup ECAT_TESTS = testManager.createGroup("ECAT_TEST_SESSIONS", HW_TEST_SESSIONS.override()) // Wireshark logging is injected later based on parameter
TestGroup LINUX_DOCKER_TESTS = testManager.createGroup("LINUX_DOCKER_TEST_SESSIONS", TEST_SESSIONS.override())
TestGroup WIN_DOCKER_TESTS = testManager.createGroup("WIN_DOCKER_TEST_SESSIONS", TEST_SESSIONS.override())


/*
 * Cron schedules for the develop branch:
 *
 * Nightly builds (every day):
 *   19:00, 23:00 UTC (21:00, 01:00 Barcelona Time)
 *   → Sets RUN_POLICY_NIGHTLY=true so that tests gated on the 'nightly' policy will run.
 *
 * Weekend extra builds (Saturday & Sunday only):
 *   08:00, 14:00 UTC (10:00, 16:00 Barcelona Time)
 *   → Sets RUN_POLICY_NIGHTLY=true and RUN_POLICY_WEEKEND=true so that tests gated on
 *     either 'nightly' or 'weekends' policy will run.
 */
def NIGHTLY_CRON   = '0 19,23 * * * % PYTHON_VERSIONS=All;RUN_POLICY_NIGHTLY=true'
def WEEKEND_CRON   = '0 8,14 * * 6-7 % PYTHON_VERSIONS=All;RUN_POLICY_NIGHTLY=true;RUN_POLICY_WEEKEND=true'
def CRON_SETTINGS  = BRANCH_NAME == "develop" ? "${NIGHTLY_CRON}\n${WEEKEND_CRON}" : ""

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
        choice(
            choices: [
                '.*',
                'virtual_drive_tests',
                'no_pcap',
                'pcap',
                'ethercat.*',
                'ethercat_everest.*',
                'ethercat_capitan.*',
                'ethercat_multislave',
                'fsoe.*',
                'fsoe_phase1',
                'fsoe_phase2',
                'canopen.*',
                'canopen_everest.*',
                'canopen_capitan.*',
                'ethernet.*',
                'ethernet_everest.*',
                'ethernet_capitan.*',
            ],
            name: 'test_session_filter',
            description: 'Regex pattern for which test sessions to run (e.g. "fsoe.*", "ethercat_everest.*", ".*" for all)'
        )
        booleanParam(name: 'WIRESHARK_LOGGING', defaultValue: false, description: 'Enable Wireshark logging')
        choice(
                choices: ['function', 'module', 'session'],
                name: 'WIRESHARK_LOGGING_SCOPE'
        )
        booleanParam(name: 'CLEAR_SUCCESSFUL_WIRESHARK_LOGS', defaultValue: true, description: 'Clears Wireshark logs if the test passed')
        booleanParam(name: 'RUN_POLICY_NIGHTLY', defaultValue: false, description: 'Tag this build as a nightly build (set automatically by cron triggers)')
        booleanParam(name: 'RUN_POLICY_WEEKEND', defaultValue: false, description: 'Tag this build as a weekend build (set automatically by weekend cron triggers)')
    }
    stages {
        stage("Set env") {
            steps {
                script {
                    // Determine which Python versions to run tests against based on branch and parameters
                    Set pythonVersions
                    if (env.BRANCH_NAME == 'master') {
                        pythonVersions = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        pythonVersions = ALL_PYTHON_VERSIONS
                    } else {
                        if (env.PYTHON_VERSIONS == "MIN_MAX") {
                            pythonVersions = [PYTHON_VERSION_MIN, PYTHON_VERSION_MAX] as Set
                        } else if (env.PYTHON_VERSIONS == "MIN") {
                            pythonVersions = [PYTHON_VERSION_MIN] as Set
                        } else if (env.PYTHON_VERSIONS == "MAX") {
                            pythonVersions = [PYTHON_VERSION_MAX] as Set
                        } else if (env.PYTHON_VERSIONS == "All") {
                            pythonVersions = ALL_PYTHON_VERSIONS
                        } else { // Branch-indexing
                            pythonVersions = [PYTHON_VERSION_MIN] as Set
                        }
                    }

                    // Set dynamic properties according to job and parameters
                    TEST_SESSIONS.setAttributeInCascade(
                        runInVirtualEnvs: venvManager.pythonVersionsToDefaultVenvNames(pythonVersions),
                        jobName: "${env.JOB_NAME}-#${env.BUILD_NUMBER}",
                        wiresharkScope: params.WIRESHARK_LOGGING_SCOPE,
                        clearSuccessfulWiresharkLogs: params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS,
                    )

                    // Configure if ECAT and ETH sessions use Wireshark logging based on parameter
                    ECAT_TESTS.baseTestSession.setAttributeInCascade(
                        useWiresharkLogging: params.WIRESHARK_LOGGING,
                    )
                    ETH_TESTS.baseTestSession.setAttributeInCascade(
                        useWiresharkLogging: params.WIRESHARK_LOGGING,
                    )

                    testManager.testSessionFilter = params.test_session_filter

                    // Parse run policy tags from boolean parameters
                    def runPolicyTags = [] as Set
                    if (params.RUN_POLICY_NIGHTLY) { runPolicyTags.add("nightly") }
                    if (params.RUN_POLICY_WEEKEND) { runPolicyTags.add("weekends") }
                    testManager.runPolicyTags = runPolicyTags

                    echo("Test sessions have been configured to run with the following base configuration:\n${TEST_SESSIONS.configSummary()}")
                }
            }
        }

        stage('Register manual test sessions') {
            steps {
                script {
                    // Pcap tests run on the EtherCAT machine — add manually since they're not in rack_specifiers
                    ECAT_TESTS.addSession(uid: "pcap", markers: "pcap", stageName: "Pcap Tests")

                    // Linux pcap tests: runs pcap-marked tests that don't need hardware
                    LINUX_DOCKER_TESTS.addSession(
                        uid: "pcap",
                        markers: "pcap",
                        stageName: "Pcap Tests (Linux)")

                    // Linux unit tests: everything that does not have a marker
                    LINUX_DOCKER_TESTS.addSession(
                        uid: "no_pcap",
                        markers: PyTestManager.markersExcludeString(HARDWARE_MARKERS + ["virtual", "pcap", "no_pcap"]),
                        stageName: "Unit Tests (Linux)")

                    // Windows unit tests: mirrors the ad-hoc session in Build Windows for dashboard visibility
                    WIN_DOCKER_TESTS.addSession(
                        uid: "no_pcap",
                        markers: PyTestManager.markersExcludeString(["virtual", "pcap"] + HARDWARE_MARKERS),
                        stageName: "Unit Tests (Windows)")
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
                                VENV_WORKING_FOLDER = "C:\\Users\\ContainerAdministrator\\ingenialink_python"
                            }
                            stages {
                                stage('Move workspace') {
                                    steps {
                                        script {
                                            venvManager.copyToWorkingFolder()
                                        }
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            venvManager.createPoetryEnvironments(
                                              pythonVersions: ALL_PYTHON_VERSIONS
                                            )
                                        }
                                    }
                                }
                                stage('Build wheels') {
                                    steps {
                                        script {
                                            venvManager.runInWorkingFolder("if exist dist rmdir /s /q dist")
                                            venvManager.forEachEnvironment() { venv ->
                                                venv.run("poetry run poe build-wheel")
                                                venv.run("poetry run poe check-wheels")
                                            }
                                            venvManager.copyFromWorkingFolder("ingenialink/_version.py")
                                            venvManager.copyFromWorkingFolder("dist/")

                                        }
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe type")
                                            }
                                        }
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe format")
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
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                venv.run("poetry run poe docs")
                                            }
                                        }
                                    }
                                    post {
                                        success {
                                            script {
                                                venvManager.runInWorkingFolder('"C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256')
                                                venvManager.copyFromWorkingFolder("docs.zip")
                                            }
                                            stash includes: 'docs.zip', name: 'docs'
                                        }
                                    }
                                }
                                stage('Run unit tests (no-pcap) tests on docker') {
                                    when {
                                        expression {
                                            WIN_DOCKER_TESTS.anyShouldRun()
                                        }
                                    }
                                    steps {
                                        script {
                                            venvManager.forVirtualEnvs(TEST_SESSIONS.runInVirtualEnvs) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                            }
                                            WIN_DOCKER_TESTS.runTestStages()
                                        }
                                    }
                                }
                            }
                        }
                        stage('Build Linux') {
                            agent {
                                docker {
                                    label 'lin-worker'
                                    image LIN_DOCKER_IMAGE
                                    args '-u root:root'
                                }
                            }
                            environment {
                                VENV_WORKING_FOLDER = "/tmp/ingenialink_python"
                            }
                            stages {
                                // TODO: Re-enable once all release dependencies are resolved
                                // See Jira issue for tracking
                                // stage('Check Dependencies') {
                                //     steps {
                                //         script {
                                //             checkDependencies()
                                //         }
                                //     }
                                // }
                                stage('Move workspace') {
                                    steps {
                                        script {
                                            venvManager.copyToWorkingFolder()
                                        }
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            venvManager.createPoetryEnvironments(
                                              pythonVersions: ([DEFAULT_PYTHON_VERSION] as Set) + venvManager.defaultVenvNamesToVersion(TEST_SESSIONS.runInVirtualEnvs)
                                            )
                                        }
                                    }
                                }
                                stage('Build wheels') {
                                    steps {
                                        script {
                                            venvManager.runInWorkingFolder("rm -rf dist")
                                            // Linux for now does not contain compiled code
                                            // so building on one python version is enough
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe build-wheel")
                                                venv.run("poetry run poe check-wheels")
                                            }
                                            venvManager.copyFromWorkingFolder("dist/")
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
                                stage('Prepare test sessions') {
                                    steps {
                                        script {
                                            // Install wheel first (needed for summit_testing_framework to import ingenialink)
                                            venvManager.forVirtualEnvs(TEST_SESSIONS.runInVirtualEnvs) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                            }
                                            
                                            // Export specifiers and populate TestGroup sessions (policy + uid-regex evaluated here).
                                            testManager.buildTestSessions("tests.setups.rack_specifiers")
                                            testManager.buildTestSessions("tests.setups.virtual_drive_specifier")

                                            testManager.echoTestGroupsSummary()
                                            testManager.generateTestDashboard()
                                        }
                                    }
                                }
                                stage('Run Linux Docker tests') {
                                    when {
                                        expression { LINUX_DOCKER_TESTS.anyShouldRun() }
                                    }
                                    steps {
                                        script {
                                            venvManager.forVirtualEnvs(TEST_SESSIONS.runInVirtualEnvs) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                            }
                                            LINUX_DOCKER_TESTS.runTestStages()
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
                        label 'lin-worker'
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
                            label 'lin-worker'
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
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                            ECAT_TESTS.anyShouldRun()
                        }
                    }
                    options {
                        lock(ECAT_NODE_LOCK)
                    }
                    agent {
                        label ECAT_NODE
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
                                    venvManager.createPoetryEnvironments(
                                        pythonVersions: venvManager.defaultVenvNamesToVersion(ECAT_TESTS.baseTestSession.runInVirtualEnvs),
                                        additionalCommands: ["poetry run poe install-wheel"]
                                    )
                                }
                            }
                        }
                        stage('Run EtherCAT Tests') {
                            steps {
                                script {
                                    ECAT_TESTS.runTestStages()
                                }
                            }
                        }
                    }
                }
                stage('CANopen/Ethernet - Tests') {
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                            CAN_TESTS.anyShouldRun() || ETH_TESTS.anyShouldRun()
                        }
                    }
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
                                    venvManager.createPoetryEnvironments(
                                        pythonVersions: venvManager.defaultVenvNamesToVersion(HW_TEST_SESSIONS.runInVirtualEnvs),
                                        additionalCommands: ["poetry run poe install-wheel"]
                                    )
                                }
                            }
                        }
                        stage('Run CANopen/Ethernet Tests') {
                            steps {
                                script {
                                    CAN_TESTS.runTestStages()
                                    ETH_TESTS.runTestStages()
                                }
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
            when {
                expression { testManager.hasCoverageFiles() }
            }
            environment {
                VENV_WORKING_FOLDER = "C:\\Users\\ContainerAdministrator\\ingenialink_python"
            }
            steps {
                script {
                    def coverage_files = testManager.getCoverageFiles().join(" ")
                    for (stash_name in wheel_stashes) {
                        unstash stash_name
                    }
                    venvManager.copyToWorkingFolder()
                    venvManager.createPoetryEnvironment(
                      additionalCommands: ["poetry run poe install-wheel"]
                    )
                    venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                        venv.run("poetry run poe cov-combine -- ${coverage_files}")
                        venv.run("poetry run poe cov-report")
                    }
                    venvManager.copyFromWorkingFolder("coverage.xml")
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                    archiveArtifacts artifacts: '*.xml'
                }
            }
        }
    }
}

