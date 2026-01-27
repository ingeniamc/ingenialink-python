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
    def isUnixNode() {
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
            isUnix: this.isUnixNode()
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


/**
 * TestSession - Configuration for a test session
 * 
 * This class encapsulates the configuration options for a test session,
 * including pytest markers, setup configurations, Wireshark logging options,
 * Python versions to test against, and coverage settings.
 * 
 * It supports cascading/inheriting properties to child sessions, allowing
 * for hierarchical test session definitions.
 */
class TestSession implements Serializable {
    TestSession parent = null
    List<TestSession> children = []
    
    /**
     * List of configuration attributes that can be set and cascaded to children.
     */
    private static final List<String> CONFIG_ATTRS = [
        'runPythonVersions',
        'markers',
        'testTimeoutMinutes',
        'runTestBaseCommand',
        'importMode',
        'logCli',
        'useCoverage',
        'covPackageName',
        'setup',
        'useWiresharkLogging',
        'wiresharkScope',
        'wiresharkDir',
        'clearSuccessfulWiresharkLogs',
        'startWiresharkTimeoutS',
        'jobName',
        'setAttApiToken'
    ]

    /**
     * Python versions to run tests against.
     * Default: null
     * Example: ["3.9", "3.10"] as Set
     */
    Set runPythonVersions = null

    /**
     * Pytest marker expression used to select tests.
     * Default: null
     * Example: "ethercat and canopen"
     */
    String markers = null

    /**
     * Timeout for a test session in minutes.
     * Default: 60
     * Can be set via the Jenkins parameter `TEST_TIMEOUT_MINUTES`.
     */
    Integer testTimeoutMinutes = 60

    /**
     * Base command used to run tests inside the virtualenv. The test arguments
     * from `getTestArgs` are appended to this base command.
     * Default: 'poetry run poe tests'
     */
    String runTestBaseCommand = 'poetry run poe tests'

    /**
     * Pytest import mode passed as `--import-mode`.
     * Default: null (commonly set to 'importlib')
     */
    String importMode = null

    /**
     * Enables pytest's `log_cli` option to stream logs to the console.
     * Default: false
     */
    Boolean logCli = false

    /**
     * Coverage-related options
     * `useCoverage`: whether to collect coverage for this session
     * Default: true
     */
    Boolean useCoverage = true

    /**
     * Package name to measure coverage for. Used to build the `--cov` path.
     * Default: null
     * Example: "my_library"
     */
    String covPackageName = null

    
    ///// Summit Testing Framework options /////

    /**
     * Fully-qualified name of the test setup to use.
     * Default: null
     * Example: "tests.setups.rack_specifiers.ECAT_EVE_SETUP"
     */
    String setup = null

    /**
     * Wireshark capture options
     * `useWiresharkLogging`: enable capture during tests
     * `wiresharkScope`: 'function' | 'module' | 'session'
     * `wiresharkDir`: directory where pcaps are written (relative to workspace)
     * `clearSuccessfulWiresharkLogs`: if true, remove pcaps on success
     * `startWiresharkTimeoutS`: seconds to wait for Wireshark to start
     */
    Boolean useWiresharkLogging = false
    String wiresharkScope = "session"
    String wiresharkDir = "wireshark"
    Boolean clearSuccessfulWiresharkLogs = true
    BigDecimal startWiresharkTimeoutS = 10.0

    /**
     * Job name. Used to identify the job in test reports, infrastructure, logs...
     * Example: "my-project@my_branch#2",
     */
    String jobName = null

    /**
     * Whether to set ATT_API_KEY from Jenkins credentials.
     * Default: false
     */
    Boolean setAttApiToken = false

    TestSession(Map args = [:]) {
        args.each { name, value ->
            this."$name" = value
        }
    }

    /**
     * Set attributes on this session and propagate the values to all descendants.
     * This ensures that the values set here are cascaded to all children.
     * 
     * @param attributes Map of property names and values to set
     */
    void setAttributeInCascade(Map attributes) {
        // Validate arguments against whitelist
        def invalidArgs = attributes.keySet().findAll { !CONFIG_ATTRS.contains(it) }
        if (invalidArgs) {
             throw new IllegalArgumentException("Invalid arguments passed to setAttributeInCascade(): ${invalidArgs}. Allowed properties: ${CONFIG_ATTRS}")
        }

        // Set attributes on this session
        attributes.each { name, value ->
            this."$name" = value
        }
        
        // Propagate to children
        children.each { child ->
            child.setAttributeInCascade(attributes)
        }
    }

    /**
     * Generate the list of environment variables for the test session.
     * 
     * @return List of environment variables in 'KEY=VALUE' format
     */
    List<String> getEnvVars() {
        def envList = []
        if (this.wiresharkScope != null) {
            envList.add("WIRESHARK_SCOPE=${this.wiresharkScope}")
        }
        if (this.clearSuccessfulWiresharkLogs != null) {
            envList.add("CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${this.clearSuccessfulWiresharkLogs}")
        }
        if (this.startWiresharkTimeoutS != null) {
            envList.add("START_WIRESHARK_TIMEOUT_S=${this.startWiresharkTimeoutS}")
        }
        return envList
    }

    /**
     * Generate the list of credentials specifications for the test session.
     * 
     * @param pipeline The pipeline object to use for creating credential bindings
     * @return List of credential bindings suitable for withCredentials
     */
    List getCredentialsSpec(def pipeline) {
        def credentials = []
        if (this.setAttApiToken) {
            credentials.add(pipeline.string(credentialsId: 'ATT_api_token', variable: 'ATT_API_KEY'))
        }
        return credentials
    }
    
    /**
     * Generate the list of arguments for the pytest command.
     * 
     * @param venv The virtual environment context map
     * @return List of arguments as strings
     */
    List<String> getTestArgs(Map venv) {
        def args = []

        if (this.useCoverage) {
            def covPath
            if (venv.isUnix) {
                covPath = "${venv.name}/lib/python${venv.version}/site-packages/${this.covPackageName}"
            } else {
                covPath = "${venv.name}\\lib\\site-packages\\${this.covPackageName}"
            }
            args.add("--cov=${covPath}")
        }

        args.add("--import-mode=${this.importMode}")
        args.add("--junitxml=pytest_reports/junit-${venv.version}.xml")
        args.add("--junit-prefix=${venv.version}")
        args.add("-m \"${this.markers}\"")
        args.add("--job_name=\"${this.jobName}-${this.setup}\"")
        
        if (this.setup) {
            args.add("--setup ${this.setup}")
        }
        if (this.useWiresharkLogging) {
            args.add("--run_wireshark")
        }
        if (this.logCli) {
            args.add("-o log_cli=True")
        }
        
        return args
    }

    /**
     * Create a child session that inherits from this one.
     * Properties specified in args override the parent's values.
     * 
     * @param args Map of properties to override
     * @return New child TestSession
     */
    TestSession override(Map args = [:]) {
        // Validate arguments against whitelist
        def invalidArgs = args.keySet().findAll { !CONFIG_ATTRS.contains(it) }
        if (invalidArgs) {
             throw new IllegalArgumentException("Invalid arguments passed to override(): ${invalidArgs}. Allowed properties: ${CONFIG_ATTRS}")
        }

        TestSession child = new TestSession()
        child.parent = this
        this.children.add(child)
        
        // Copy allowed properties from parent or args
        CONFIG_ATTRS.each { name ->
            child."$name" = args.containsKey(name) ? args[name] : this."$name"
        }
        
        return child
    }

    /**
     * Return a map with the current configuration attributes and their values.
     * Useful for debugging and printing session configuration in pipeline logs.
     */
    Map getConfigMap() {
        def m = [:]
        CONFIG_ATTRS.each { name ->
            m[name] = this."$name"
        }
        return m
    }

    /**
     * Summary of session configuration.
     */
    String configSummary() {
        // Preserve CONFIG_ATTRS ordering and emit one key=value per line
        return CONFIG_ATTRS.collect { name -> "${name}=${this."$name"}" }.join('\n')
    }
}

class PyTestManager {
    private def venvManager
    private def pipeline
    private List coverageStashes = []

    PyTestManager(Map args = [pipeline: null, venvManager: null]) {
        this.venvManager = args.venvManager
        this.pipeline = args.pipeline
    }

    /**
     * Unstashes all coverage files.
     * 
     * @return Set of coverage file stash names
     */
    def getCoverageFiles() {
        this.coverageStashes.each { stash ->
             this.pipeline.unstash stash
        }
        return this.coverageStashes as Set
    }

    static def markersExcludeString(excludes = []) {
        return excludes.collect { "not ${it}" }.join(' and ')
    }

    private def archiveWiresharkLogs(String wiresharkDir) {
        this.pipeline.archiveArtifacts artifacts: "${wiresharkDir}\\*.pcap", allowEmptyArchive: true
    }

    private def clearWiresharkLogs(String wiresharkDir) {
        if (this.venvManager.isUnixNode()) {
            this.pipeline.sh(script: "rm -f ${wiresharkDir}/*.pcap", returnStatus: true)
        } else {
            this.pipeline.bat(script: "del /f \"${wiresharkDir}\\\\*.pcap\"", returnStatus: true)
        }
    }

    private def clearCoverageFiles() {
        if (this.venvManager.isUnixNode()) {
            this.pipeline.sh(script: 'rm -f *.coverage*', returnStatus: true)
        } else {
            this.pipeline.bat(script: 'del /f "*.coverage*"', returnStatus: true)
        }
    }

    /**
     * Stash coverage file for later merging.
     * Moves the coverage file to a unique stash name to avoid collisions and stashes it.
     * 
     * @param setup The name of the setup (e.g. 'virtual', 'ethernet') used as suffix for the stash name.
     */
    private def stashCoverageFile(String setup) {
        def workingFolder = this.venvManager.getWorkingFolder()
        def base_stash_name = ".coverage_${setup}"
        def coverage_stash = base_stash_name
        
        // Handle stash name collision by appending index
        int index = 1
        while (this.coverageStashes.contains(coverage_stash)) {
            coverage_stash = "${base_stash_name}_${index}"
            index++
        }
        
        // Copy coverage file back from working folder if it differs from workspace
        if (workingFolder != this.pipeline.env.WORKSPACE) {
            this.venvManager.copyFromWorkingFolder(".coverage")
        }
        
        // Rename coverage file to unique stash name
        if (this.venvManager.isUnixNode()) {
            this.pipeline.sh "mv .coverage ${coverage_stash}"
        } else {
            this.pipeline.bat "move .coverage ${coverage_stash}"
        }
        
        // Stash coverage file and record it for later merging
        this.pipeline.stash includes: coverage_stash, name: coverage_stash
        this.coverageStashes.add(coverage_stash)
    }

    /**
     * Publish JUnit reports and clean them up.
     * Copies reports from working folder if necessary, publishes them, and then deletes them
     * to prevent re-publishing in subsequent stages.
     */
    private def publishAndCleanupJunitReports() {
        def workingFolder = this.venvManager.getWorkingFolder()
        
        // Copy junit reports back from working folder to workspace if they're separate
        if (workingFolder != this.pipeline.env.WORKSPACE) {
            this.venvManager.copyFromWorkingFolder("pytest_reports/")
        }
        
        // Publish junit reports
        this.pipeline.junit "pytest_reports/*.xml"
        
        // Delete the junit after publishing it so it not re-published on the next stage
        if (this.venvManager.isUnixNode()) {
            this.pipeline.sh "rm -f pytest_reports/*.xml"
        } else {
            this.pipeline.bat "del /S /Q pytest_reports\\*.xml"
        }
    }

    /**
     * Run a test session for the configured Python versions.
     * 
     * Executes pytest with the specified markers and setup configuration across all 
     * configured Python versions. Handles environment setup, Wireshark logging (if enabled),
     * coverage collection, and results publishing.
     * 
     * @param session TestSession configuration object
     */
    def runTestSession(TestSession session) {
        try {
            this.pipeline.echo("Starting test session with config:\n${session.configSummary()}")
            this.pipeline.timeout(time: session.testTimeoutMinutes, unit: 'MINUTES') {
                if (session.useWiresharkLogging) {
                    this.clearWiresharkLogs(session.wiresharkDir)
                }
                if (session.useCoverage) {
                    this.clearCoverageFiles()
                }
                def firstIteration = true
                this.venvManager.forPythons(session.runPythonVersions) { venv ->
                    this.pipeline.withEnv(session.getEnvVars()) {
                        try {
                            def testArgs = session.getTestArgs(venv)
                            def testArgsStr = testArgs.join(' ')

                            def credentials = session.getCredentialsSpec(this.pipeline)
                            if (credentials) {
                                this.pipeline.withCredentials(credentials) {
                                    venv.run("${session.runTestBaseCommand} ${testArgsStr}")
                                }
                            } else {
                                venv.run("${session.runTestBaseCommand} ${testArgsStr}")
                            }
                        } catch (err) {
                            this.pipeline.unstable(message: "Tests failed")
                        } finally {
                            this.publishAndCleanupJunitReports()
                            if (firstIteration && session.useCoverage) {
                                this.stashCoverageFile(session.setup)
                                firstIteration = false
                            }
                        }
                    }
                }
            }
        } finally {
            if (session.useWiresharkLogging) {
                this.archiveWiresharkLogs(session.wiresharkDir)
                this.clearWiresharkLogs(session.wiresharkDir)
            }
            if (session.useCoverage) {
                this.clearCoverageFiles()
            }
        }
    }
}

VEnvManager venvManager = new VEnvManager(
  pipeline: this,
  default_python_version: DEFAULT_PYTHON_VERSION,
  poetry_default_install_command: "poetry sync --no-root --all-groups --extras virtual_drive"
)

PyTestManager testManager = new PyTestManager(pipeline: this, venvManager: venvManager)

/* Define default base test sessions to be used/overridden in stages */
TestSession TEST_SESSIONS = new TestSession(
    covPackageName: "ingenialink",
    wiresharkScope: "",
    wiresharkDir: "wireshark",
    clearSuccessfulWiresharkLogs: true,
    startWiresharkTimeoutS: 10.0,
    importMode: "importlib",
    logCli: true,
    setAttApiToken: true
)
TestSession HW_TEST_SESSIONS = TEST_SESSIONS.override()
TestSession CAN_TEST_SESSIONS = HW_TEST_SESSIONS.override()
TestSession ETH_TEST_SESSIONS = HW_TEST_SESSIONS.override() // Wireshark logging is injected later based on parameter
TestSession ECAT_TEST_SESSIONS = HW_TEST_SESSIONS.override() // Wireshark logging is injected later based on parameter


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
                        TEST_SESSIONS.setAttributeInCascade(runPythonVersions: ALL_PYTHON_VERSIONS)
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        TEST_SESSIONS.setAttributeInCascade(runPythonVersions: ALL_PYTHON_VERSIONS)
                    } else {
                        if (env.PYTHON_VERSIONS == "MIN_MAX") {
                            TEST_SESSIONS.setAttributeInCascade(runPythonVersions: [PYTHON_VERSION_MIN, PYTHON_VERSION_MAX] as Set)
                        } else if (env.PYTHON_VERSIONS == "MIN") {
                            TEST_SESSIONS.setAttributeInCascade(runPythonVersions: [PYTHON_VERSION_MIN] as Set)
                        } else if (env.PYTHON_VERSIONS == "MAX") {
                            TEST_SESSIONS.setAttributeInCascade(runPythonVersions: [PYTHON_VERSION_MAX] as Set)
                        } else if (env.PYTHON_VERSIONS == "All") {
                            TEST_SESSIONS.setAttributeInCascade(runPythonVersions: ALL_PYTHON_VERSIONS)
                        } else { // Branch-indexing
                            TEST_SESSIONS.setAttributeInCascade(runPythonVersions: [PYTHON_VERSION_MIN] as Set)
                        }
                    }

                    // Set dynamic properties according to job and parameters
                    TEST_SESSIONS.setAttributeInCascade(
                        wiresharkScope: params.WIRESHARK_LOGGING_SCOPE,
                        clearSuccessfulWiresharkLogs: params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS,
                        jobName: "${env.JOB_NAME}-#${env.BUILD_NUMBER}"
                    )

                    // Configure ECAT sessions with Wireshark settings from params
                    ECAT_TEST_SESSIONS.setAttributeInCascade(
                        useWiresharkLogging: params.WIRESHARK_LOGGING
                    )
                    ETH_TEST_SESSIONS.setAttributeInCascade(
                        useWiresharkLogging: params.WIRESHARK_LOGGING
                    )

                    echo("Test sessions have been configured to run with the following base configuration:\n${TEST_SESSIONS.configSummary()}")
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
                                            venvManager.forPythons(TEST_SESSIONS.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                            }
                                            testManager.runTestSession(TEST_SESSIONS.override(markers: win_marker))
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
                                              pythonVersions: ([DEFAULT_PYTHON_VERSION] as Set) + TEST_SESSIONS.runPythonVersions
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
                                            venvManager.forPythons(TEST_SESSIONS.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                            }
                                            testManager.runTestSession(TEST_SESSIONS.override(markers: lin_marker))
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
                                            venvManager.forPythons(TEST_SESSIONS.runPythonVersions) { venv ->
                                                venv.run("poetry run poe install-wheel")
                                            }
                                            testManager.runTestSession(TEST_SESSIONS.override(markers: 'virtual', setup: 'summit_testing_framework.setups.virtual_drive.TESTS_SETUP'))
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
                                        pythonVersions: ECAT_TEST_SESSIONS.runPythonVersions,
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
                                    testManager.runTestSession(ETH_TEST_SESSIONS.override(markers: "pcap"))
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
                                    testManager.runTestSession(ECAT_TEST_SESSIONS.override(
                                        markers: "ethercat",
                                        setup: "${RACK_SPECIFIERS_PATH}.ECAT_EVE_SETUP"
                                    ))
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
                                    testManager.runTestSession(ECAT_TEST_SESSIONS.override(
                                        markers: "ethercat",
                                        setup: "${RACK_SPECIFIERS_PATH}.ECAT_CAP_SETUP"
                                    ))
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
                                    testManager.runTestSession(ECAT_TEST_SESSIONS.override(
                                        markers: "multislave",
                                        setup: "${RACK_SPECIFIERS_PATH}.ECAT_MULTISLAVE_SETUP"
                                    ))
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
                                    testManager.runTestSession(ECAT_TEST_SESSIONS.override(
                                        markers: "fsoe",
                                        setup: "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE1_SETUP"
                                    ))
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
                                    testManager.runTestSession(ECAT_TEST_SESSIONS.override(
                                        markers: "fsoe",
                                        setup: "${RACK_SPECIFIERS_PATH}.ECAT_DEN_S_PHASE2_SETUP"
                                    ))
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
                                        pythonVersions: HW_TEST_SESSIONS.runPythonVersions,
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
                                    testManager.runTestSession(CAN_TEST_SESSIONS.override(
                                        markers: "canopen",
                                        setup: "${RACK_SPECIFIERS_PATH}.CAN_EVE_SETUP"
                                    ))
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
                                    testManager.runTestSession(CAN_TEST_SESSIONS.override(
                                        markers: "canopen",
                                        setup: "${RACK_SPECIFIERS_PATH}.CAN_CAP_SETUP"
                                    ))
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
                                    testManager.runTestSession(ETH_TEST_SESSIONS.override(
                                        markers: "ethernet",
                                        setup: "${RACK_SPECIFIERS_PATH}.ETH_EVE_SETUP"
                                    ))
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
                                    testManager.runTestSession(ETH_TEST_SESSIONS.override(
                                        markers: "ethernet",
                                        setup: "${RACK_SPECIFIERS_PATH}.ETH_CAP_SETUP"
                                    ))
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


