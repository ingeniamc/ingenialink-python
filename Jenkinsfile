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

/* List of markers that require hardware */
def HARDWARE_MARKERS = ["ethernet", "ethercat", "canopen", "multislave", "fsoe", "eoe"]

/**
 * Build an exclusion string like: 'not develop and not virtual and not ethernet ...'
 * @param excludes List markers to exclude (list of strings)
 * @return A string with 'not <marker>' joined with ' and ' suitable for pytest
 */


def reassignFilePermissions() {
    if (isUnix()) {
        sh 'chmod -R 777 .'
    }
}


/**
 * VEnvManager - Manages Python virtual environments across Jenkins nodes
 * 
 * This class provides a centralized way to create, manage, and execute code within
 * Python virtual environments in Jenkins pipelines. It handles platform differences
 * (Windows/Linux), maintains per-node virtual environment registries, and supports
 * both standard venv and Poetry-based environments.
 * 
 * Key features:
 * - Creates and tracks virtual environments per node and workspace
 * - Platform-agnostic path handling and command execution
 * - Poetry integration for dependency management
 * - Support for multiple Python versions in parallel
 * - Workspace isolation with working folder support
 */
class VEnvManager {
    def pipeline
    String default_python_version
    String poetry_default_install_command

    /**
    * Map of node names to workspace paths to their virtual environments.
    * Structure: {
    *   nodeName1: {
    *     workspacePath1: {
    *       venvName1: venvPath1,
    *       venvName2: venvPath2,
    *       ...
    *     },
    *   },
    */
    Map venvs = [:]

    /**
    * Cache for OS type per node.
    * Structure: {
    *   nodeName1: true/false (true = Unix, false = Windows),
    *   ...
    * }
    */
    Map osCache = [:]

    /**
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

    /**
    * Generate the default virtual environment name for a given Python version
    * Convention: .venv{pythonVersion} (e.g., ".venv3.9", ".venv3.10")
    * Arguments:
    *   pythonVersion: Python version string (e.g., "3.9", "3.10")
    * Returns: Default venv name following the convention
    */
    private def pythonVersionDefaultVenvName(String pythonVersion) {
        return ".venv${pythonVersion}"
    }

    /**
    * Get the current node name from the environment
    * Returns: Node name string
    * Throws: Error if NODE_NAME is not set (not running on a node)
    */
    private def getNodeName() {
        def nodeName = this.pipeline.env.NODE_NAME
        if (!nodeName) {
            this.pipeline.error("NODE_NAME environment variable is not set. Virtual environments must be created inside a Jenkins node.")
        }
        return nodeName
    }

    /**
    * Check if the current node is running Unix (cached)
    * Returns: true if Unix, false if Windows
    */
    private def isUnixNode() {
        def nodeName = this.getNodeName()
        if (!this.osCache.containsKey(nodeName)) {
            this.osCache[nodeName] = this.pipeline.isUnix()
        }
        return this.osCache[nodeName]
    }

    /**
    * Join path segments into a single path string
    * 
    * Intelligently combines path segments while preserving absolute paths and
    * adapting to the platform (Unix vs Windows).
    * 
    * Arguments:
    *   parts: N number of path segments
    * 
    * Returns: Platform-specific path string ('/' on Linux, '\' on Windows)
    * 
    * Examples:
    *   joinPath("/tmp", "mydir", "file.txt") → "/tmp/mydir/file.txt" (Linux)
    *   joinPath("C:\\Users", "admin", "file.txt") → "C:\\Users\\admin\\file.txt" (Windows)
    *   joinPath("/base/", "/subdir/", "file") → "/base/subdir/file"
    *   joinPath("workspace", "dist/") → "workspace/dist/" (trailing slash preserved)
    */
    private def joinPath(String... parts) {
        // Filter out empty strings
        def partsList = (parts as List)
            .collect { it.trim() }
            .findAll { it }
        
        if (partsList.isEmpty()) {
            return ""
        }

        // First segment: keep as-is (preserves /absolute/paths and C:\drive\paths), only strip trailing slashes
        def first = partsList[0].replaceAll('[\\\\/]+$', '')
        
        // Remaining segments: strip leading and trailing slashes
        def rest = partsList.size() > 1 
            ? partsList[1..-1].collect { it.replaceAll('^[\\\\/]+', '').replaceAll('[\\\\/]+$', '') }
            : []

        // Join with / and convert to platform-specific separators
        def joined = ([first] + rest).join('/')
        return this.isUnixNode() ? joined : joined.replace('/', '\\')
    }

    /**
    * Run a single command in the working folder
    * Arguments:
    *   cmd: Command to execute
    */
    private def run(String cmd) {
        def workingFolder = this.getWorkingFolder()
        // Change directory. Avoid changing directory if working folder is workspace
        def fullCmd = (workingFolder == this.pipeline.env.WORKSPACE) ? cmd : "cd ${workingFolder}\n${cmd}"
        if (this.isUnixNode()) {
            this.pipeline.sh fullCmd
        } else {
            this.pipeline.bat fullCmd
        }
    }

    /**
    * Copy workspace content to working directory
    * Copies all files from WORKSPACE to VENV_WORKING_FOLDER
    * 
    * Jenkins runs steps in WORKSPACE by default, but some operations
    * may require a separate working directory due to problems with docker mounts 
    * and symbolic links or permissions.
    */
    def copyToWorkingFolder() {
        def workingFolder = this.getWorkingFolder()
        if (workingFolder == this.pipeline.env.WORKSPACE) {
            throw new IllegalStateException("copyToWorkingFolder called but VENV_WORKING_FOLDER is not set or equals WORKSPACE. VENV_WORKING_FOLDER must be a separate working directory.")
        }
        if (this.isUnixNode()) {
            this.pipeline.sh "mkdir -p ${workingFolder}"
            this.pipeline.sh "cp -r ${this.pipeline.env.WORKSPACE}/. ${workingFolder}"
        } else {
            this.pipeline.bat "XCOPY ${this.pipeline.env.WORKSPACE} ${workingFolder} /s /i /y /e /h"
        }
    }

    /**
    * Get the working folder from environment
    * Returns: Working folder path. Prefers VENV_WORKING_FOLDER if set; falls back to WORKSPACE.
    *
    */
    private def getWorkingFolder() {
        def v = this.pipeline.env.VENV_WORKING_FOLDER
        if (v) {
            return v
        }
        // Fallback to workspace when VENV_WORKING_FOLDER is not defined
        return this.pipeline.env.WORKSPACE
    }

    /**
    * Copy files/directories from working directory back to workspace
    * Arguments:
    *   source: Source path relative to VENV_WORKING_FOLDER (e.g., "dist/", "pytest_reports/")
    *   dest: Destination path relative to WORKSPACE (optional, defaults to source)
    *
    * Convention: dest MUST end with '/' if it's a directory
    *   - Directory: copyFromWorkingFolder("dist/") - trailing slash required
    *   - File: copyFromWorkingFolder(".coverage", "coverage.xml") - no trailing slash
    */
    def copyFromWorkingFolder(String source, String dest = null) {
        def workingFolder = this.getWorkingFolder()
        if (workingFolder == this.pipeline.env.WORKSPACE) {
            throw new IllegalStateException("copyFromWorkingFolder cannot be used when VENV_WORKING_FOLDER is not defined and working folder equals WORKSPACE. Set env.VENV_WORKING_FOLDER to a separate directory to use this method.")
        }
        if (dest == null) {
            dest = source
        }
        def sourcePath = this.joinPath(workingFolder, source)
        def destPath = this.joinPath(this.pipeline.env.WORKSPACE, dest)
        
        if (this.isUnixNode()) {
            if (dest.endsWith('/')) {
                // Directory: create it
                this.pipeline.sh "mkdir -p \"${destPath}\""
                // Copy contents of source directory into destination, not the directory itself
                this.pipeline.sh "cp -r ${sourcePath}/. ${destPath}"
            } else {
                // File: create parent directory and copy the file
                this.pipeline.sh "mkdir -p \$(dirname \"${destPath}\")"
                this.pipeline.sh "cp -r ${sourcePath} ${destPath}"
            }
        } else {
            if (dest.endsWith('/')) {
                // Directory: XCOPY requires source to end with \* to copy contents, not the folder itself
                // If source already contains wildcard, don't add another one
                def xcopySource = source.contains('*') ? sourcePath : "${sourcePath}\\*"
                this.pipeline.bat "XCOPY \"${xcopySource}\" \"${destPath}\" /s /y /e /h /i"
            } else {
                // File: use simple COPY command
                this.pipeline.bat "COPY /Y \"${sourcePath}\" \"${destPath}\""
            }
        }
    }

    /**
    * Execute code within a virtual environment
    * Arguments:
    *   venvName: Name of the virtual environment
    *   pythonVersion: Python version for this venv (optional, used to set venv.version)
    *   body: Closure to execute inside the venv
    */
    def withVirtualEnv(String venvName, String pythonVersion = null, Closure body) {
        def ctx = [
            run: { cmd ->
                def activateCmd
                if (this.isUnixNode()) {
                    activateCmd = ". ${venvName}/bin/activate\n "
                } else {
                    activateCmd = "call ${venvName}\\Scripts\\activate\n "
                }
                this.run(activateCmd + cmd)
            },
            name: venvName,
            version: pythonVersion,
        ]

        body(ctx)
    }

    /**
    * Create a virtual environment
    * Arguments (as Map):
    *   venvName: Name of the virtual environment to create
    *   pythonVersion: Python version to use (e.g., "3.9"). If null, uses default_python_version
    * Returns: Path to the created virtual environment
    * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
    */
    def createVirtualEnvironment(Map args = [venvName: null, pythonVersion: null]) {
        def workingFolder = this.getWorkingFolder()
        // Use default python version if not specified
        def pythonVersion = args.pythonVersion ?: this.default_python_version
        // Use default venv name if not specified
        def venvName = args.venvName ?: this.pythonVersionDefaultVenvName(pythonVersion)

        // Create the virtual environment using pipeline context
        this.run("py -${pythonVersion} -m venv --without-pip ${venvName}")

        // Store the created venv path
        def venvPath = this.joinPath(workingFolder, venvName)
        def nodeName = this.getNodeName()
        if (!this.venvs.containsKey(nodeName)) {
            this.venvs[nodeName] = [:]
        }
        if (!this.venvs[nodeName].containsKey(workingFolder)) {
            this.venvs[nodeName][workingFolder] = [:]
        }
        this.venvs[nodeName][workingFolder][venvName] = venvPath
        return venvPath
    }

    /**
    * Create multiple virtual environments
    * Arguments:
    *   pythonVersions: Iterable of Python versions to create venvs for (List or Set)
    * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
    */
    def createVirtualEnvironments(Map args = [pythonVersions: []]) {
        args.pythonVersions.each { version ->
            this.createVirtualEnvironment([
              venvName: this.pythonVersionDefaultVenvName(version),
              pythonVersion: version
            ])
        }
    }

    /**
    * Iterate over virtual environments for a specific workspace/node
    * Arguments:
    *   body: Closure to execute for each venv. Receives the venv context as argument
    * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
    */
    def forEachEnvironment(Closure body) {
        def nodeName = this.getNodeName()
        def workingFolder = this.getWorkingFolder()
        def nodeVenvs = this.venvs.get(nodeName)
        if (!nodeVenvs) {
            this.pipeline.error("No virtual environments found for node: ${nodeName}")
        }
        def venvMap = nodeVenvs.get(workingFolder)
        if (!venvMap) {
            this.pipeline.error("No virtual environments found for workingFolder: ${workingFolder} on node: ${nodeName}")
        }
        if (venvMap.isEmpty()) {
            this.pipeline.error("Virtual environments map is empty for workingFolder: ${workingFolder} on node: ${nodeName}")
        }
        venvMap.each { venvName, venvPath ->
            this.withVirtualEnv(venvName) { venv ->
                body(venv)
            }
        }
    }

    /**
     * Execute code within a Python virtual environment
     * Arguments:
     *   pythonVersion: Python version to use (required)
     *   body: Closure to execute inside the venv
     * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
     */
    def withPython(String pythonVersion, Closure body) {
        def venvName = this.pythonVersionDefaultVenvName(pythonVersion)
        this.withVirtualEnv(venvName, pythonVersion, body)
    }


    /**
    * Iterate over specific virtual environments for a specific workspace/node
    * Arguments:
    *   pythonVersions: Iterable of Python versions to iterate venvs for (List or Set)
    *   body: Closure to execute for each venv. Receives the venv context
    * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
    */

    def forPythons(Iterable pythonVersions, Closure body) {
        pythonVersions.each { version ->
            this.withPython(version) { venv ->
                body(venv)
            }
        }
    }


    /**
    * Create a Poetry virtual environment and install dependencies
    * Arguments (as Map):
    *  pythonVersion: Python version to use (e.g., "3.9"). If null, uses default_python_version
    *  installCommand: Command to install dependencies with Poetry. If null, uses poetry_default_install_command
    *  additionalCommands: List of additional commands to run inside the venv after installation
    * Note: Virtual environment is created using default naming convention .venv{pythonVersion}
    * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
    */
    def createPoetryEnvironment(Map args = [pythonVersion: null, installCommand: null, additionalCommands: []]) {
        def version = args.pythonVersion ?: this.default_python_version
        def venvName = this.pythonVersionDefaultVenvName(version)
        def installCmd = args.installCommand ?: this.poetry_default_install_command
        def additionalCmds = args.additionalCommands ?: []

        this.createVirtualEnvironment([venvName: venvName, pythonVersion: version])
        this.withVirtualEnv(venvName) { venv ->
            venv.run(installCmd)
            additionalCmds.each { cmd ->
                venv.run(cmd)
            }
        }
    }

    /**
    * Create multiple Poetry virtual environments
    * Arguments: (as Map):
    *   pythonVersions: Iterable of Python versions to create venvs for (List or Set)
    *   installCommand: Command to install dependencies with Poetry. If null, uses poetry_default_install_command
    *   additionalCommands: List of additional commands to run inside each venv after installation
    * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
    */
    def createPoetryEnvironments(Map args = [pythonVersions: [], installCommand: null, additionalCommands: []]) {
        args.pythonVersions.each { version ->
            this.createPoetryEnvironment(
              pythonVersion: version,
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

    static def markersExcludeString(excludes = []) {
        return excludes.collect { "not ${it}" }.join(' and ')
    }

    def archiveWiresharkLogs() {
        this.pipeline.archiveArtifacts artifacts: "${WIRESHARK_DIR}\\*.pcap", allowEmptyArchive: true
    }

    def clearWiresharkLogs() {
        this.pipeline.bat(script: 'del /f "%WIRESHARK_DIR%\\*.pcap"', returnStatus: true)
    }

    def clearCoverageFiles() {
        this.pipeline.bat(script: 'del /f "*.coverage*"', returnStatus: true)
    }

    def runTestHW(markers, setup_name = "", extra_args = "") {
        try {
            this.pipeline.timeout(time: 1, unit: 'HOURS') {
                this.clearCoverageFiles()
                def firstIteration = true
                this.venvManager.forPythons(this.runPythonVersions) { venv ->
                    this.pipeline.withEnv(["WIRESHARK_SCOPE=${this.wiresharkScope}", "CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${this.clearSuccessfulWiresharkLogs}", "START_WIRESHARK_TIMEOUT_S=${this.startWiresharkTimeoutS}"]) {
                        try {
                            def setupArg = setup_name ? "--setup ${setup_name} " : ""
                            venv.run("poetry run poe tests --import-mode=importlib --cov=${venv.name}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-${venv.version}.xml --junit-prefix=${venv.version} -m \"${markers}\" ${setupArg} --job_name=\"${this.pipeline.env.JOB_NAME}-#${this.pipeline.env.BUILD_NUMBER}-${setup_name}\" -o log_cli=True ${extra_args}")
                        } catch (err) {
                            this.pipeline.unstable(message: "Tests failed")
                        } finally {
                            this.pipeline.junit "pytest_reports\\*.xml"
                            // Delete the junit after publishing it so it not re-published on the next stage
                            this.pipeline.bat "del /S /Q pytest_reports\\*.xml"
                            if (firstIteration) {
                                def coverage_stash = ".coverage_${setup_name}"
                                this.pipeline.bat "move .coverage ${coverage_stash}"
                                this.pipeline.stash includes: coverage_stash, name: coverage_stash
                                this.coverageStashes.add(coverage_stash)
                                firstIteration = false
                            }
                        }
                    }
                }
            }
        } finally {
            this.archiveWiresharkLogs()
            this.clearWiresharkLogs()
            this.clearCoverageFiles()
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
                                    environment {
                                        SETUPTOOLS_SCM_PRETEND_VERSION = getPythonVersionForPr()
                                    }
                                    steps {
                                        script {
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
                                                venvManager.run('"C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256')
                                                venvManager.copyFromWorkingFolder("docs.zip")
                                            }
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
                                            def win_marker = PyTestManager.markersExcludeString(["virtual", "pcap"] + HARDWARE_MARKERS)
                                            venvManager.forPythons(testManager.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                withCredentials([string(credentialsId: 'ATT_api_token', variable: 'ATT_API_KEY')]) {
                                                    venv.run("poetry run poe tests --import-mode=importlib --cov=${venv.name}\\lib\\site-packages\\ingenialink --junitxml=pytest_reports/junit-tests-${venv.version}.xml --junit-prefix=${venv.version} -m \"${win_marker}\" -o log_cli=True")
                                                }
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            script {
                                                venvManager.copyFromWorkingFolder("pytest_reports/")
                                                venvManager.copyFromWorkingFolder(".coverage", ".coverage_docker")
                                            }
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
                                VENV_WORKING_FOLDER = "/tmp/ingenialink_python"
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
                                              pythonVersions: ([DEFAULT_PYTHON_VERSION] as Set) + testManager.runPythonVersions
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
                                stage('Run unit tests on linux docker') {
                                    when{
                                        expression {
                                            "pcap" ==~ params.run_test_stages
                                        }
                                    }
                                    steps {
                                        script {
                                            def lin_marker = PyTestManager.markersExcludeString(HARDWARE_MARKERS + ["virtual", "no_pcap"])
                                            venvManager.forPythons(testManager.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                withCredentials([string(credentialsId: 'ATT_api_token', variable: 'ATT_API_KEY')]) {
                                                    venv.run("poetry run poe tests --junitxml=pytest_reports/junit-tests-${venv.version}.xml --junit-prefix=${venv.version} -m '${lin_marker}' -o log_cli=True")
                                                }
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            script {
                                                venvManager.copyFromWorkingFolder("pytest_reports/")
                                            }
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
                                            venvManager.forPythons(testManager.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                                venv.run("poetry run poe tests --junitxml=pytest_reports/junit-tests-${venv.version}.xml --junit-prefix=${venv.version} -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP -o log_cli=True")
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            script {
                                                venvManager.copyFromWorkingFolder("pytest_reports/")
                                            }
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
                                script {
                                    testManager.clearWiresharkLogs()
                                }
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
                VENV_WORKING_FOLDER = "C:\\Users\\ContainerAdministrator\\ingenialink_python"
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
                    venvManager.copyToWorkingFolder()
                    venvManager.createPoetryEnvironment(
                      additionalCommands: ["poetry run poe install-wheel"]
                    )
                    venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                        venv.run("poetry run poe cov-combine --${coverage_files}")
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
