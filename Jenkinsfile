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

ALL_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12"] as Set
PYTHON_VERSION_MIN = "3.9"
PYTHON_VERSION_MAX = "3.12"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingenialink-python"
def RACK_SPECIFIERS_PATH = "tests.setups.rack_specifiers"

USE_WIRESHARK_LOGGING = ""
WIRESHARK_DIR = "wireshark"

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



class VEnvManager {
    def pipeline
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
    * Cache for OS type per workspace.
    * Structure: {
    *   workspacePath1: true/false (true = Unix, false = Windows),
    *   ...
    * }
    */
    Map osCache = [:]

    /*
    * Constructor
    * Arguments:
    *   pipeline: The pipeline script context (this)
    *   default_python_version: Default Python version to use when creating venvs
    *   poetry_default_install_command: Default command to install dependencies with Poetry
    */
    VEnvManager(Map args = [pipeline: null, default_python_version: null, poetry_default_install_command: "poetry sync --all-groups"]) {
        this.pipeline = args.pipeline
        this.default_python_version = args.default_python_version
        this.poetry_default_install_command = args.poetry_default_install_command
    }

    /*
    * Generate the default virtual environment name for a given Python version
    * Convention: .venv{pythonVersion} (e.g., ".venv3.9", ".venv3.10")
    * Arguments:
    *   pythonVersion: Python version string (e.g., "3.9", "3.10")
    * Returns: Default venv name following the convention
    */
    def pythonVersionDefaultVenvName(String pythonVersion) {
        return ".venv${pythonVersion}"
    }

    /*
    * Check if a workspace is running on Unix (cached)
    * Arguments:
    *   workingDir: Directory/workspace path (optional, uses current pipeline isUnix if not provided)
    * Returns: true if Unix, false if Windows
    */
    def isUnixWorkspace(String workingDir = null) {
        if (!workingDir) {
            return this.pipeline.isUnix()
        }

        if (!this.osCache.containsKey(workingDir)) {
            this.osCache[workingDir] = this.pipeline.isUnix()
        }
        return this.osCache[workingDir]
    }

    /*
    * Execute code within a specific folder
    * Arguments:
    *   folder: Folder path to change to (optional)
    *   body: Closure to execute inside the folder
    */
    def runInFolder(folder = null, body) {
        def ctx = [
            run: { cmd ->
                def cdCmd = folder ? "cd ${folder}\n " : ""
                if (this.isUnixWorkspace(folder)) {
                    this.pipeline.sh """${cdCmd}${cmd}"""
                } else {
                    this.pipeline.bat """${cdCmd}${cmd}"""
                }
            }
        ]

        body(ctx)
    }

    /*
    * Execute code within a virtual environment
    * Arguments:
    *   venvName: Name of the virtual environment
    *   workingDir: Working directory where the venv is located (optional)
    *   pythonVersion: Python version for this venv (optional, used to set venv.version)
    *   body: Closure to execute inside the venv
    */
    def withVirtualEnv(String venvName, workingDir = null, String pythonVersion = null, body) {
        def ctx = [
            run: { cmd ->
                def activateCmd
                if (this.isUnixWorkspace(workingDir)) {
                    activateCmd = ". ${venvName}/bin/activate\n "
                } else {
                    activateCmd = "call ${venvName}\\Scripts\\activate\n "
                }
                this.runInFolder(workingDir) { folderCtx ->
                    folderCtx.run(activateCmd + cmd)
                }
            },
            name: venvName,
            version: pythonVersion,
        ]

        body(ctx)
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
        def venvName = args.venvName ?: this.pythonVersionDefaultVenvName(pythonVersion)

        // Create the virtual environment using pipeline context
        this.runInFolder(ws) { ctx ->
          ctx.run("py -${pythonVersion} -m venv --without-pip ${venvName}")
        }

        // Store the created venv path
        def venvPath = this.pipeline.joinPath(ws, venvName)
        if (!this.venvs.containsKey(ws)) {
            this.venvs[ws] = [:]
        }
        this.venvs[ws][venvName] = venvPath
        return venvPath
    }

    /*
    * Create multiple virtual environments
    * Arguments:
    *   pythonVersions: Iterable of Python versions to create venvs for (List or Set)
    *   workingDir: Directory where to create the venvs. If null, uses current workspace
    */
    def createVirtualEnvironments(Map args = [pythonVersions: [], workingDir: null]) {
        args.pythonVersions.each { version ->
            this.createVirtualEnvironment([
              venvName: this.pythonVersionDefaultVenvName(version),
              pythonVersion: version,
              workingDir: args.workingDir
            ])
        }
    }

    /*
    * Iterate over virtual environments for a specific workspace/node
    * Arguments:
    *   workingDir: Directory where the venvs were created. Must be explicitly provided (e.g., env.WORKSPACE)
    *   body: Closure to execute for each venv. Receives the venv context as argument
    */
    def forEachEnvironment(String workingDir, body) {
        def venvMap = this.venvs.get(workingDir)
        if (!venvMap) {
          throw new IllegalArgumentException("No virtual environments found for workingDir: ${workingDir}. Did you call createVirtualEnvironment or createPoetryEnvironments first?")
        }
        if (venvMap.isEmpty()) {
          throw new IllegalArgumentException("Virtual environments map is empty for workingDir: ${workingDir}")
        }
        venvMap.each { venvName, venvPath ->
            this.withVirtualEnv(venvName, workingDir) { venv ->
                body(venv)
            }
        }
    }

   /*
    * Execute code within a Python virtual environment
    * Arguments:
    *   pythonVersion: Python version to use (required)
    *   workingDir: Directory where the venv is located
    *   body: Closure to execute inside the venv
    */
    def withPython(String pythonVersion, String workingDir = null, body) {
        def venvName = this.pythonVersionDefaultVenvName(pythonVersion)
        this.withVirtualEnv(venvName, workingDir, pythonVersion, body)
    }


    /**
    * Iterate over specific virtual environments for a specific workspace/node
    * Arguments:
    *   workingDir: Directory where the venvs were created. Must be explicitly provided
    *   pythonVersions: Iterable of Python versions to iterate venvs for (List or Set)
    *   body: Closure to execute for each venv. Receives the venv context
    */

    def forPythons(String workingDir, Iterable pythonVersions, body) {
        pythonVersions.each { version ->
            this.withPython(version, workingDir) { venv ->
                body(venv)
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
    * Note: Virtual environment is created using default naming convention .venv{pythonVersion}
    */
    def createPoetryEnvironment(Map args = [pythonVersion: null, workingDir: null, installCommand: null, additionalCommands: []]) {
        def version = args.pythonVersion ?: this.default_python_version
        def venvName = this.pythonVersionDefaultVenvName(version)
        def installCmd = args.installCommand ?: this.poetry_default_install_command
        def additionalCmds = args.additionalCommands ?: []

        this.createVirtualEnvironment([venvName: venvName, pythonVersion: version, workingDir: args.workingDir])
        this.withVirtualEnv(venvName, args.workingDir) { venv ->
            venv.run(installCmd)
            additionalCmds.each { cmd ->
                venv.run(cmd)
            }
        }
    }

    /*
    * Create multiple Poetry virtual environments
    * Arguments: (as Map):
    *   pythonVersions: Iterable of Python versions to create venvs for (List or Set)
    *   workingDir: Directory where to create the venvs. If null, uses current workspace
    *   installCommand: Command to install dependencies with Poetry. If null, uses poetry_default_install_command
    *   additionalCommands: List of additional commands to run inside each venv after installation
    */
    def createPoetryEnvironments(Map args = [pythonVersions: [], workingDir: null, installCommand: null, additionalCommands: []]) {
        args.pythonVersions.each { version ->
            this.createPoetryEnvironment(
              pythonVersion: version,
              workingDir: args.workingDir,
              installCommand: args.installCommand,
              additionalCommands: args.additionalCommands
            )
        }
    }
}

class PyTestManager {
    def venvManager
    def pipeline
    def runPythonVersions = [] as Set
    def wiresharkScope = ""
    def clearSuccessfulWiresharkLogs = true
    def startWiresharkTimeoutS = 10.0
    def coverageStashes = []

    PyTestManager(Map args = [pipeline: null, venvManager: null]) {
        this.venvManager = args.venvManager
        this.pipeline = args.pipeline
    }

    def runTestHW(markers, setup_name = "", extra_args = "") {
        try {
            pipeline.timeout(time: 1, unit: 'HOURS') {
                pipeline.clearCoverageFiles()
                def firstIteration = true
                venvManager.forPythons(pipeline.env.WORKSPACE, runPythonVersions) { venv ->
                    pipeline.withEnv(["WIRESHARK_SCOPE=${wiresharkScope}", "CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${clearSuccessfulWiresharkLogs}", "START_WIRESHARK_TIMEOUT_S=${startWiresharkTimeoutS}"]) {
                        try {
                            def setupArg = setup_name ? "--setup ${setup_name} " : ""
                            venv.run("""poetry run poe tests --import-mode=importlib --cov=${venv.name}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-${venv.version}.xml --junit-prefix=${venv.version} -m \"${markers}\" ${setupArg} --job_name=\"${pipeline.env.JOB_NAME}-#${pipeline.env.BUILD_NUMBER}-${setup_name}\" -o log_cli=True ${extra_args}""")
                        } catch (err) {
                            pipeline.unstable(message: "Tests failed")
                        } finally {
                            pipeline.junit "pytest_reports\\*.xml"
                            // Delete the junit after publishing it so it not re-published on the next stage
                            pipeline.bat "del /S /Q pytest_reports\\*.xml"
                            if (firstIteration) {
                                def coverage_stash = ".coverage_${setup_name}"
                                pipeline.bat "move .coverage ${coverage_stash}"
                                pipeline.stash includes: coverage_stash, name: coverage_stash
                                coverageStashes.add(coverage_stash)
                                firstIteration = false
                            }
                        }
                    }
                }
            }
        } finally {
            pipeline.archiveWiresharkLogs()
            pipeline.clearCoverageFiles()
        }
    }
}

VEnvManager venvManager = new VEnvManager(
  pipeline: this,
  default_python_version: DEFAULT_PYTHON_VERSION,
  poetry_default_install_command: "poetry sync --no-root --all-groups --extras virtual_drive"
)

PyTestManager testManager = new PyTestManager(pipeline: this, venvManager: venvManager)

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
                        testManager.runPythonVersions = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        testManager.runPythonVersions = ALL_PYTHON_VERSIONS
                    } else {
                        if (env.PYTHON_VERSIONS == "MIN_MAX") {
                            testManager.runPythonVersions = [PYTHON_VERSION_MIN, PYTHON_VERSION_MAX] as Set
                        } else if (env.PYTHON_VERSIONS == "MIN") {
                            testManager.runPythonVersions = [PYTHON_VERSION_MIN] as Set
                        } else if (env.PYTHON_VERSIONS == "MAX") {
                            testManager.runPythonVersions = [PYTHON_VERSION_MAX] as Set
                        } else if (env.PYTHON_VERSIONS == "All") {
                            testManager.runPythonVersions = ALL_PYTHON_VERSIONS
                        } else { // Branch-indexing
                            testManager.runPythonVersions = [PYTHON_VERSION_MIN] as Set
                        }
                    }

                    // Set wireshark properties on testManager
                    testManager.wiresharkScope = params.WIRESHARK_LOGGING_SCOPE
                    testManager.clearSuccessfulWiresharkLogs = params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS

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
                                WORKING_FOLDER = "C:\\Users\\ContainerAdministrator\\ingenialink_python"
                            }
                            stages {
                                stage('Move workspace') {
                                    steps {
                                        bat "XCOPY ${env.WORKSPACE} ${env.WORKING_FOLDER} /s /i /y /e /h"
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            venvManager.createPoetryEnvironments(
                                              pythonVersions: ALL_PYTHON_VERSIONS,
                                              workingDir: env.WORKING_FOLDER
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
                                            venvManager.forEachEnvironment(env.WORKING_FOLDER) { venv ->
                                                venv.run("poetry run poe build-wheel")
                                                venv.run("poetry run poe check-wheels")
                                            }
                                            bat "COPY ${env.WORKING_FOLDER}\\ingenialink\\_version.py ${env.WORKSPACE}\\ingenialink\\_version.py"
                                            bat "XCOPY ${env.WORKING_FOLDER}\\dist ${env.WORKSPACE}\\dist /s /i"
                                        }
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION, env.WORKING_FOLDER) { venv ->
                                                venv.run("poetry run poe type")
                                            }
                                        }
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION, env.WORKING_FOLDER) { venv ->
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
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION, env.WORKING_FOLDER) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                venv.run("poetry run poe docs")
                                            }
                                        }
                                    }
                                    post {
                                        success {
                                            bat """
                                                cd ${env.WORKING_FOLDER}
                                                "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                                                XCOPY docs.zip ${env.WORKSPACE}
                                            """
                                            stash includes: 'docs.zip', name: 'docs'
                                        }
                                    }
                                }
                                stage('Run unit tests (no-pcap) tests on docker') {
                                    when {
                                        expression {
                                            "no_pcap" ==~ params.run_test_stages
                                        }
                                    }
                                    steps {
                                        script {
                                            /* Windows docker does not have npcap/winpcap installed so runs no_pcap tests */
                                            def win_marker = markersExcludeString(["virtual", "pcap"] + HARDWARE_MARKERS)
                                            venvManager.forPythons(env.WORKING_FOLDER, testManager.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                venv.run("""poetry run poe tests --import-mode=importlib --cov=${venv.name}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-tests-${venv.version}.xml --junit-prefix=${venv.version} -m "${win_marker}" -o log_cli=True""")
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            bat """
                                                mkdir -p pytest_reports
                                                XCOPY ${env.WORKING_FOLDER}\\pytest_reports\\* pytest_reports\\ /s /i /y /e /h
                                                move ${env.WORKING_FOLDER}\\.coverage .coverage_docker
                                            """
                                            junit 'pytest_reports/*.xml'
                                            stash includes: '.coverage_docker', name: '.coverage_docker'
                                            script {
                                                testManager.coverageStashes.add(".coverage_docker")
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
                            environment {
                                WORKING_FOLDER = "/tmp/ingenialink_python"
                            }
                            stages {
                                stage('Move workspace') {
                                    steps {
                                        script {
                                            sh """
                                                mkdir -p ${env.WORKING_FOLDER}
                                                cp -r ${env.WORKSPACE}/. ${env.WORKING_FOLDER}
                                            """
                                        }
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            venvManager.createPoetryEnvironments(
                                              pythonVersions: ([DEFAULT_PYTHON_VERSION] as Set) + testManager.runPythonVersions,
                                              workingDir: env.WORKING_FOLDER
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
                                            // Linux for now does not contain compiled code
                                            // so building on one python version is enough
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION, env.WORKING_FOLDER) { venv ->
                                                venv.run("poetry run poe build-wheel")
                                                venv.run("poetry run poe check-wheels")
                                            }
                                            sh "mkdir -p ${env.WORKSPACE}/dist"
                                            sh "cp ${env.WORKING_FOLDER}/dist/* ${env.WORKSPACE}/dist/"
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
                                            def lin_marker = markersExcludeString(HARDWARE_MARKERS + ["virtual", "no_pcap"])
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION, env.WORKING_FOLDER) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                venv.run("""poetry run poe tests --junitxml=pytest_reports/junit-tests-${venv.name}.xml --junit-prefix=${venv.name} -m '${lin_marker}' -o log_cli=True""")
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            sh """
                                                mkdir -p pytest_reports
                                                cp ${env.WORKING_FOLDER}/pytest_reports/* pytest_reports/
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
                                            venvManager.forPythons(env.WORKING_FOLDER, testManager.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                venv.run("""poetry run poe tests --junitxml=pytest_reports/junit-tests-${venv.version}.xml --junit-prefix=${venv.version} -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP -o log_cli=True""")
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            sh """
                                                mkdir -p pytest_reports
                                                cp ${env.WORKING_FOLDER}/pytest_reports/* pytest_reports/
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
                                        pythonVersions: testManager.runPythonVersions,
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
                                script {
                                    testManager.runTestHW("pcap")
                                }
                            }
                        }
                        stage('EtherCAT Everest') {
                            when {
                                expression {
                                    "ethercat_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_EVE_SETUP", USE_WIRESHARK_LOGGING)
                                }
                            }
                        }
                        stage('EtherCAT Capitan') {
                            when {
                                expression {
                                    "ethercat_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("ethercat", "${RACK_SPECIFIERS_PATH}.ECAT_CAP_SETUP", USE_WIRESHARK_LOGGING)
                                }
                            }
                        }
                        stage('EtherCAT Multislave') {
                            when {
                                expression {
                                    "ethercat_multislave" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("multislave", "${RACK_SPECIFIERS_PATH}.ECAT_MULTISLAVE_SETUP", USE_WIRESHARK_LOGGING)
                                }
                            }
                        }
                        stage("Safety Denali Phase I") {
                            when {
                                expression {
                                    "fsoe_phase1" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("fsoe", "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE1_SETUP", USE_WIRESHARK_LOGGING)
                                }
                            }
                        }
                        stage("Safety Denali Phase II") {
                            when {
                                expression {
                                    "fsoe_phase2" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("fsoe", "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE2_SETUP", USE_WIRESHARK_LOGGING)
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
                                        pythonVersions: testManager.runPythonVersions,
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
                                script {
                                    testManager.runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_EVE_SETUP")
                                }
                            }
                        }
                        stage('CANopen Capitan') {
                            when {
                                expression {
                                    "canopen_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("canopen", "${RACK_SPECIFIERS_PATH}.CAN_CAP_SETUP")
                                }
                            }
                        }
                        stage('Ethernet Everest') {
                            when {
                                expression {
                                    "ethernet_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_EVE_SETUP", USE_WIRESHARK_LOGGING)
                                }
                            }
                        }
                        stage('Ethernet Capitan') {
                            when {
                                expression {
                                    "ethernet_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                script {
                                    testManager.runTestHW("ethernet", "${RACK_SPECIFIERS_PATH}.ETH_CAP_SETUP", USE_WIRESHARK_LOGGING)
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
            environment {
                WORKING_FOLDER = "C:\\Users\\ContainerAdministrator\\ingenialink_python"
            }
            steps {
                script {
                    def coverage_files = ""
                    for (coverage_stash in testManager.coverageStashes) {
                        unstash coverage_stash
                        coverage_files += " " + coverage_stash
                    }
                    for (stash_name in wheel_stashes) {
                        unstash stash_name
                    }
                    bat "XCOPY ${env.WORKSPACE} ${env.WORKING_FOLDER} /s /i /y /e /h"
                    venvManager.createPoetryEnvironment(
                      workingDir: env.WORKING_FOLDER,
                      additionalCommands: ["poetry run poe install-wheel"]
                    )
                    script {
                        venvManager.withPython(DEFAULT_PYTHON_VERSION, env.WORKING_FOLDER) { venv ->
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
