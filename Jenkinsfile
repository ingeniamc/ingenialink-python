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

ALL_PYTHON_VERSIONS = "3.9,3.10,3.11,3.12" // TODO Deprecate this in favor of passing lists
ALL_PYTHON_VERSIONS_LST = ALL_PYTHON_VERSIONS.split(',')
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

/* List of markers that require hardware */
def HARDWARE_MARKERS = ["ethernet", "ethercat", "canopen", "multislave", "fsoe", "eoe"]

/**
 * Build an exclusion string like: 'not develop and not virtual and not ethernet ...'
 * @param excludes List markers to exclude (list of strings)
 * @return A string with 'not <marker>' joined with ' and ' suitable for pytest
 */
def markersExcludeString(excludes = []) {
  return excludes.collect { "not ${it}" }.join(' and ')
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

/*
 * Join path segments into a single path string
 * - Accepts varargs (strings or anything with toString()).
 * - Skips null/blank segments.
 * - Trims leading/trailing separators on each segment to avoid double slashes.
 * - Uses '/' on Linux, '\' on Windows.
 */
def joinPath(Object... parts) {
  // Normalize segments: toString, trim, remove leading/trailing separators
  def cleaned = (parts as List)
    .findAll { it != null }
    .collect { it.toString().trim() }
    .findAll { it } // drop empty strings
    .collect { seg ->
      // Remove leading/trailing both types of separators to be safe
      seg.replaceAll('^[\\\\/]+', '').replaceAll('[\\\\/]+$', '')
    }

  // Join using POSIX separator, then normalize for Windows if needed
  def joined = cleaned.join('/')
  return isUnix() ? joined : joined.replace('/', '\\')
}

def archiveWiresharkLogs() {
    archiveArtifacts artifacts: "${WIRESHARK_DIR}\\*.pcap", allowEmptyArchive: true
}

def runInFolder(folder = null, body) {
    ctx = [
        run: { cmd ->
            def cdCmd = folder ? "cd ${folder}\n " : ""
            if (isUnix()) {
              sh """${cdCmd}${cmd}"""
            } else {
              bat """${cdCmd}${cmd}"""
            }
        }
    ]

    body(ctx)
}

def withVirtualEnv(vvenvName, workingDir = null, body) {
    ctx = [
        run: { cmd ->
            def activateCmd
            if (isUnix()) {
                activateCmd = ". ${vvenvName}/bin/activate\n "
            } else {
                activateCmd = "call ${vvenvName}\\Scripts\\activate\n "
            }
            runInFolder(workingDir) { folderCtx ->
                folderCtx.run(activateCmd + cmd)
            }
        },
    ]

    body(ctx)
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
        runInFolder(workingDir) { ctx ->
            ctx.run("py -${version} -m venv --without-pip ${venvName}")
            withVirtualEnv(venvName, workingDir) { venv ->
                venv.run("poetry sync --no-root --all-groups --extras virtual_drive")
                if(installWheel) {
                    venv.run("poetry run poe install-wheel")
                }
            }
        }
    }
}

def buildWheel(py_version) {
     echo "Running build for Python ${py_version} in Docker environment"
    if (isUnix()) {
        withVirtualEnv(".venv${py_version}", LIN_DOCKER_TMP_PATH) { venv ->
            venv.run("poetry run poe build-wheel")
        }
    } else {
        withVirtualEnv(".venv${py_version}", WIN_DOCKER_TMP_PATH) { venv ->
            venv.run("poetry run poe build-wheel")
        }
    }
}

def runTestHW(markers, setup_name = "", extra_args = "") {
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
                        withVirtualEnv(venvName) { venv ->
                            venv.run("""poetry run poe tests --import-mode=importlib --cov=${venvName}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-${version}.xml --junit-prefix=${version} -m \"${markers}\" ${setupArg} --job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${setup_name}\" -o log_cli=True ${extra_args}""")
                        }
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

class VEnvManager {
    def script
    String default_python_version
    String poetry_default_install_command

    /*
    * Map of workspace paths to their virtual environments.
    * Structure: {
    *   workspacePath1: {
    *     venvName1: venvPath1,
    *     venvName2: venvPath2,
    *     ...
    *   },
    */
    Map venvs = [:]

    /*
    * Constructor
    * Arguments:
    *   script: The pipeline script context (this)
    *   default_python_version: Default Python version to use when creating venvs
    *   poetry_default_install_command: Default command to install dependencies with Poetry
    */
    VEnvManager(Map args = [script: null, default_python_version: null, poetry_default_install_command: "poetry sync --all-groups"]) {
        this.script = args.script
        this.default_python_version = args.default_python_version
        this.poetry_default_install_command = args.poetry_default_install_command
    }

    /* Get virtual environment path
    * from a previously created venv
    * Arguments:
    *   venvName: Name of the virtual environment
    *   workingDir: Directory where the venv was created. Required.
    * Returns: Path to the virtual environment, or null if not found
    */
    def getVirtualEnvPath(String venvName, String workingDir) {
        return venvs.get(workingDir)?.get(venvName)
    }

    /*
    * Create a virtual environment
    * Arguments (as Map):
    *   venvName: Name of the virtual environment to create
    *   pythonVersion: Python version to use (e.g., "3.9"). If null, uses default_python_version
    *   workingDir: Directory where to create the venv. Required.
    * Returns: Path to the created virtual environment
    */
    def createVirtualEnvironment(Map args = [venvName: null, pythonVersion: null, workingDir: null]) {
        def ws = args.workingDir
        if (!ws) {
            throw new IllegalArgumentException("workingDir is required for createVirtualEnvironment")
        }
        // Use default python version if not specified
        def pythonVersion = args.pythonVersion ?: this.default_python_version
        // Use default venv name if not specified
        def venvName = args.venvName ?: ".venv${pythonVersion}"

        // Create the virtual environment using script context
        script.runInFolder(ws) { ctx ->
          ctx.run("py -${pythonVersion} -m venv --without-pip ${venvName}")
        }

        // Store the created venv path
        def venvPath = script.joinPath(ws, venvName)
        if (!venvs.containsKey(ws)) {
            venvs[ws] = [:]
        }
        venvs[ws][venvName] = venvPath
        return venvPath
    }

    /*
    * Create multiple virtual environments
    * Arguments:
    *   pythonVersions: List of Python versions to create venvs for
    *   workingDir: Directory where to create the venvs. If null, uses current workspace
    */
    def createVirtualEnvironments(Map args = [pythonVersions: [], workingDir: null]) {
        args.pythonVersions.each { version ->
            def venvName = ".venv${version}"
            createVirtualEnvironment([venvName: venvName, pythonVersion: version, workingDir: args.workingDir])
        }
    }

    /*
    * Iterate over virtual environments for a specific workspace/node
    * Arguments:
    *   workingDir: Directory where the venvs were created. Must be explicitly provided (e.g., env.WORKSPACE)
    *   body: Closure to execute for each venv. Receives the venv context as argument
    */
    def forEachEnvironment(String workingDir, body) {
        if (!workingDir) {
            throw new IllegalArgumentException("workingDir is required. Pass env.WORKSPACE from the caller's context.")
        }
        def venvMap = venvs.get(workingDir)
        if (venvMap) {
            venvMap.each { venvName, venvPath ->
                script.withVirtualEnv(venvName, workingDir) { venv ->
                    body(venv)
                }
            }
        }
    }

    /*
    * Create a Poetry virtual environment and install dependencies
    * Arguments (as Map):
    *  pythonVersion: Python version to use (e.g., "3.9"). If null, uses default_python_version
    *  workingDir: Directory where to create the venv. If null, uses current workspace
    *  installCommand: Command to install dependencies with Poetry. If null, uses poetry_default_install_command
    *  additionalCommands: List of additional commands to run inside the venv after installation
    */
    def createPoetryEnvironment(Map args = [pythonVersion: null, workingDir: null, installCommand: null, additionalCommands: []]) {
        def version = args.pythonVersion ?: this.default_python_version
        def venvName = ".venv${version}"
        def installCmd = args.containsKey('installCommand') && args.installCommand ? args.installCommand : this.poetry_default_install_command
        def additionalCmds = args.containsKey('additionalCommands') && args.additionalCommands ? args.additionalCommands : []

        createVirtualEnvironment([venvName: venvName, pythonVersion: version, workingDir: args.workingDir])
        script.withVirtualEnv(venvName, args.workingDir) { venv ->
            venv.run(installCmd)
            additionalCmds.each { cmd ->
                venv.run(cmd)
            }
        }
    }

    /*
    * Create multiple Poetry virtual environments
    * Arguments: (as Map):
    *   pythonVersions: List of Python versions to create venvs for 
    *   workingDir: Directory where to create the venvs. If null, uses current workspace
    *   installCommand: Command to install dependencies with Poetry. If null, uses poetry_default_install_command
    *   additionalCommands: List of additional commands to run inside each venv after installation
    */
    def createPoetryEnvironments(Map args = [pythonVersions: [], workingDir: null, installCommand: null, additionalCommands: []]) {
        args.pythonVersions.each { version ->
            createPoetryEnvironment(
              pythonVersion: version,
              workingDir: args.workingDir,
              installCommand: args.installCommand,
              additionalCommands: args.additionalCommands
            )
        }
    }
}

VEnvManager venvManager = new VEnvManager(
  script:this, 
  default_python_version: DEFAULT_PYTHON_VERSION,
  poetry_default_install_command: "poetry sync --no-root --all-groups --extras virtual_drive"
)

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
        choice(
            choices: [
                '.*',
                'virtual_drive_tests',
                'no_pcap',
                'pcap',
                'ethercat.*',
                'ethercat_everest',
                'ethercat_capitan',
                'ethercat_multislave',
                'fsoe.*',
                'fsoe_phase1',
                'fsoe_phase2',
                'canopen.*',
                'canopen_everest',
                'canopen_capitan',
                'ethernet.*',
                'ethernet_everest',
                'ethernet_capitan',
            ],
            name: 'run_test_stages',
            description: 'Regex pattern for which testing stage or substage to run (e.g. "fsoe.*", "ethercat_everest", ".*" for all)'
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
                                            venvManager.createPoetryEnvironments(
                                              pythonVersions: ALL_PYTHON_VERSIONS_LST,
                                              workingDir: WIN_DOCKER_TMP_PATH
                                            )
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
                                            withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", WIN_DOCKER_TMP_PATH) { venv ->
                                                venv.run("poetry run poe check-wheels")
                                            }
                                            bat "COPY ${WIN_DOCKER_TMP_PATH}\\ingenialink\\_version.py ${env.WORKSPACE}\\ingenialink\\_version.py"
                                            bat "XCOPY ${WIN_DOCKER_TMP_PATH}\\dist ${env.WORKSPACE}\\dist /s /i"
                                        }
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        script {
                                            withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", WIN_DOCKER_TMP_PATH) { venv ->
                                                venv.run("poetry run poe type")
                                            }
                                        }
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        script {
                                            withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", WIN_DOCKER_TMP_PATH) { venv ->
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
                                            withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", WIN_DOCKER_TMP_PATH) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                venv.run("poetry run poe docs")
                                            }
                                        }
                                    }
                                    post {
                                        success {
                                            bat """
                                                cd ${WIN_DOCKER_TMP_PATH}
                                                "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                                                XCOPY docs.zip ${env.WORKSPACE}
                                            """
                                            stash includes: 'docs.zip', name: 'docs'
                                        }
                                    }
                                }
                                stage('Run units tests windows docker (no-pcap) tests on docker') {
                                    when {
                                        expression {
                                            "no_pcap" ==~ params.run_test_stages
                                        }
                                    }
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                /* Windows docker does not have npcap/winpcap installed so runs no_pcap tests */
                                                def win_marker = markersExcludeString(["virtual", "pcap"] + HARDWARE_MARKERS)
                                                withVirtualEnv(".venv${version}", WIN_DOCKER_TMP_PATH) { venv ->
                                                    venv.run("poetry run poe install-wheel")
                                                    venv.run("""poetry run poe tests --import-mode=importlib --cov=.venv${version}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m "${win_marker}" -o log_cli=True
                                                """)
                                                }
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
                                        script {
                                            venvManager.createPoetryEnvironment(workingDir: LIN_DOCKER_TMP_PATH)
                                        }
                                    }
                                }
                                stage('Build wheels') {
                                    environment {
                                        SETUPTOOLS_SCM_PRETEND_VERSION = getPythonVersionForPr()
                                    }
                                    steps {
                                        script {
                                            buildWheel(DEFAULT_PYTHON_VERSION)
                                            withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", LIN_DOCKER_TMP_PATH) { venv ->
                                                venv.run("poetry run poe check-wheels")
                                            }
                                            sh "mkdir -p ${env.WORKSPACE}/dist"
                                            sh "cp ${LIN_DOCKER_TMP_PATH}/dist/* ${env.WORKSPACE}/dist/"
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
                                stage('Run unit tests on linux docker') {
                                    when{
                                        expression {
                                            "pcap" ==~ params.run_test_stages
                                        }
                                    }
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                              pythonVersions.each { version ->
                                                /* Linux has libpcap installed so does not run no_pcap, but runs pcap tests */
                                                def lin_marker = markersExcludeString(HARDWARE_MARKERS + ["virtual", "no_pcap"])
                                                withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", LIN_DOCKER_TMP_PATH) { venv ->
                                                    venv.run("poetry run poe install-wheel")
                                                    venv.run("""poetry run poe tests --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m '${lin_marker}' -o log_cli=True""")
                                                }
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
                                    when {
                                        expression {
                                            "virtual_drive_tests" ==~ params.run_test_stages
                                        }
                                    }
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", LIN_DOCKER_TMP_PATH) { venv ->
                                                    venv.run("poetry run poe install-wheel")
                                                    venv.run("""poetry run poe tests --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP -o log_cli=True""")
                                                }
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
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                          [
                            "pcap",
                            "ethercat_everest",
                            "ethercat_capitan",
                            "ethercat_multislave",
                            "fsoe_phase1",
                            "fsoe_phase2"
                          ].any { it ==~ params.run_test_stages }
                        }
                    }
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
                                    venvManager.createPoetryEnvironments(
                                        pythonVersions: RUN_PYTHON_VERSIONS.split(','),
                                        workingDir: env.WORKSPACE,
                                        additionalCommands: ["poetry run poe install-wheel"]
                                    )
                                }
                            }
                        }
                        stage('Pcap Tests') {
                            when {
                                expression {
                                    "pcap" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                /* Windows docker did not have npcap/winpcap installed so tests that require pcap are
                                run on ethercat machine */
                                runTestHW("pcap")
                            }
                        }
                        stage('EtherCAT Everest') {
                            when {
                                expression {
                                    "ethercat_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_EVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('EtherCAT Capitan') {
                            when {
                                expression {
                                    "ethercat_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_CAP_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('EtherCAT Multislave') {
                            when {
                                expression {
                                    "ethercat_multislave" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("multislave", "${RACK_SPECIFIERS_PATH}.ECAT_MULTISLAVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Safety Denali Phase I") {
                            when {
                                expression {
                                    "fsoe_phase1" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("fsoe", "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE1_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Safety Denali Phase II") {
                            when {
                                expression {
                                    "fsoe_phase2" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("fsoe", "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE2_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                    }
                }
                stage('CANopen/Ethernet - Tests') {
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                          [
                            "canopen_everest",
                            "canopen_capitan",
                            "ethernet_everest",
                            "ethernet_capitan"
                          ].any { it ==~ params.run_test_stages }
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
                                        pythonVersions: RUN_PYTHON_VERSIONS.split(','),
                                        workingDir: env.WORKSPACE,
                                        additionalCommands: ["poetry run poe install-wheel"]
                                    )
                                }
                            }
                        }
                        stage('CANopen Everest') {
                            when {
                                expression {
                                    "canopen_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_EVE_SETUP")
                            }
                        }
                        stage('CANopen Capitan') {
                            when {
                                expression {
                                    "canopen_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_CAP_SETUP")
                            }
                        }
                        stage('Ethernet Everest') {
                            when {
                                expression {
                                    "ethernet_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_EVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage('Ethernet Capitan') {
                            when {
                                expression {
                                    "ethernet_capitan" ==~ params.run_test_stages
                                }
                            }
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
                    venvManager.createPoetryEnvironment(
                      workingDir: WIN_DOCKER_TMP_PATH,
                      additionalCommands: ["poetry run poe install-wheel"]
                    )
                    script {
                        withVirtualEnv(".venv${DEFAULT_PYTHON_VERSION}", WIN_DOCKER_TMP_PATH) { venv ->
                            venv.run("poetry run poe cov-combine --${coverage_files}")
                            venv.run("poetry run poe cov-report")
                            venv.run("XCOPY coverage.xml ${env.WORKSPACE}")
                        }
                    }
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                    archiveArtifacts artifacts: '*.xml'
                }
            }
        }
    }
}
