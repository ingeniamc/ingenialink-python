@Library('cicd-lib@0.20') _

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


/**
 * VirtualEnvironment - Represents an activated Python virtual environment.
 *
 * Instances are created and registered by VEnvManager.createVirtualEnvironment().
 * Retrieve them via VEnvManager.withVirtualEnv() and call venv.run(cmd) to
 * execute commands inside the activated environment.
 */
class VirtualEnvironment implements Serializable {
    /** Virtual environment directory name (e.g. ".venv3.9", ".venv-without-x-lib") */
    final String name
    /** Python version string (e.g. "3.9") */
    final String version
    /** True when running on a Unix agent */
    final boolean isUnix

    private final VEnvManager _manager

    VirtualEnvironment(String name, String version, boolean isUnix, VEnvManager manager) {
        this.name = name
        this.version = version
        this.isUnix = isUnix
        this._manager = manager
    }

    /** Execute a shell command inside this virtual environment. */
    def run(String cmd) {
        def activateCmd = isUnix
            ? ". ${name}/bin/activate\n "
            : "call ${name}\\Scripts\\activate\n "
        _manager.runInWorkingFolder(activateCmd + cmd)
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
    *       venvName1: VirtualEnvironment,
    *       venvName2: VirtualEnvironment,
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
    * Convert multiple Python versions to their corresponding virtual environment names.
    * Uses the convention: .venv{pythonVersion} (e.g., ".venv3.9")
    * 
    * Arguments:
    *   pythonVersions: Iterable of Python version strings (e.g., ["3.9", "3.10"])
    * Returns: Set of virtual environment names (e.g., [".venv3.9", ".venv3.10"])
    */
    def pythonVersionsToDefaultVenvNames(Iterable pythonVersions) {
        return pythonVersions.collect { version ->
            this.pythonVersionDefaultVenvName(version)
        } as Set
    }

    /**
    * Convert a set of virtual environment names back to their Python versions.
    * Reverses the convention: .venv{pythonVersion} → pythonVersion
    * 
    * This is useful when you need to extract Python versions from venv names
    * for operations like createPoetryEnvironments that require version strings.
    * 
    * Arguments:
    *   venvNames: Iterable of virtual environment names (e.g., [".venv3.9", ".venv3.10"])
    * Returns: Set of Python version strings (e.g., ["3.9", "3.10"])
    */
    def defaultVenvNamesToVersion(Iterable venvNames) {
        return venvNames.collect { it.replaceAll('^.venv', '') } as Set
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
    def runInWorkingFolder(String cmd) {
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
    * Look up the VirtualEnvironment stored at creation time for a given venv name.
    * Returns null if the venv was not created via createVirtualEnvironment.
    */
    private def getStoredVenv(String venvName) {
        def nodeName = this.getNodeName()
        def workingFolder = this.getWorkingFolder()
        return this.venvs.get(nodeName)?.get(workingFolder)?.get(venvName)
    }

    /**
    * Retrieve a registered virtual environment and execute code within it.
    * Arguments:
    *   venvName: Name of the virtual environment (must have been created via createVirtualEnvironment)
    *   body: Closure to execute, receives the VirtualEnvironment as its argument
    */
    def withVirtualEnv(String venvName, Closure body) {
        def venv = this.getStoredVenv(venvName)
        if (venv == null) {
            this.pipeline.error("Virtual environment '${venvName}' has not been registered. Call createVirtualEnvironment() first.")
        }
        body(venv)
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
        this.runInWorkingFolder("py -${pythonVersion} -m venv --without-pip ${venvName}")

        // Register the virtual environment
        def nodeName = this.getNodeName()
        if (!this.venvs.containsKey(nodeName)) {
            this.venvs[nodeName] = [:]
        }
        if (!this.venvs[nodeName].containsKey(workingFolder)) {
            this.venvs[nodeName][workingFolder] = [:]
        }
        this.venvs[nodeName][workingFolder][venvName] = new VirtualEnvironment(venvName, pythonVersion, this.isUnixNode(), this)
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
        venvMap.each { venvName, venv ->
            body(venv)
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
        this.withVirtualEnv(venvName, body)
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
    * Iterate over specific virtual environments by their venv names
    * Arguments:
    *   venvNames: Iterable of virtual environment names (List or Set)
    *   body: Closure to execute for each venv. Receives the venv context
    * Note: Uses env.VENV_WORKING_FOLDER if set, otherwise env.WORKSPACE
    */
    def forVirtualEnvs(Iterable venvNames, Closure body) {
        venvNames.each { venvName ->
            this.withVirtualEnv(venvName) { venv ->
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

    /**
    * Parent session (if any)
    * Ancestor from which the session was created via override()
    */
    private TestSession parent = null

    /**
     * Child sessions
     * Offspring sessions created via override()
     * Used to propagate configuration changes via setAttributeInCascade()
     */
    private List<TestSession> children = []
    
    /**
     * List of configuration attributes that can be set and cascaded to children.
     */
    private static final List<String> CONFIG_ATTRS = [
        'uid',
        'shouldRun',
        'skipReason',
        'runInVirtualEnvs',
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
        'setAttApiToken',
        'enableFirmwareVersionCheck',
        'stageName',
        'policy'
    ]

    /**
     * Unique identifier for this test session.
     * Used for identifying stashes, logs, and reports (e.g., "ethercat_everest", "ethernet_pcap")
     * Default: null
     */
    String uid = null

    /**
     * Display name for the Jenkins stage generated for this session.
     * Used by runTestStages() as the stage label.
     * Default: null
     */
    String stageName = null

    /**
     * Whether this session should be executed.
     * Set to false when a policy or uid-regex check determines the session should be skipped.
     * Default: true
     */
    Boolean shouldRun = true

    /**
     * Human-readable reason why this session is skipped (null when shouldRun is true).
     * Default: null
     */
    String skipReason = null

    /**
     * Virtual environment names to run tests against.
     * Default: null
     * Example: [".venv3.9", ".venv3.10"] as Set
     */
    Set runInVirtualEnvs = null

    /**
     * Pytest marker expression used to select tests.
     * Default: null
     * Example: "ethercat and canopen"
     */
    String markers = null

    /**
     * Timeout for a test session in minutes.
     * Default: 60
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
     * Examples: 
        "tests.setups.rack_specifiers.ECAT_EVE_SETUP"
        "tests.setups.rack_specifiers.ECAT_SETUP@EVE_NET@2.0.0"
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


    /**
     * Firmware version check option
     * `enableFirmwareVersionCheck`: if true, enables firmware version check during tests
     * Filters test selection according to firmware version markers
     * Default: true
     */
    Boolean enableFirmwareVersionCheck = true

    /**
     * Execution policy tag for this session (e.g. 'always', 'nightly', 'weekends').
     * Default: null
     */
    String policy = null

    TestSession(Map args = [:]) {
        // Validate arguments against whitelist
        def invalidArgs = args.keySet().findAll { !CONFIG_ATTRS.contains(it) }
        if (invalidArgs) {
            throw new IllegalArgumentException("Invalid arguments passed to TestSession constructor: ${invalidArgs}. Allowed properties: ${CONFIG_ATTRS}")
        }

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
        if (this.useWiresharkLogging) {
            if (this.wiresharkScope) {
                envList.add("WIRESHARK_SCOPE=${this.wiresharkScope}")
            }
            if (this.clearSuccessfulWiresharkLogs) {
                envList.add("CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${this.clearSuccessfulWiresharkLogs}")
            }
            if (this.startWiresharkTimeoutS) {
                envList.add("START_WIRESHARK_TIMEOUT_S=${this.startWiresharkTimeoutS}")
            }
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
     * @param venv The virtual environment to run tests in
     * @return List of arguments as strings
     */
    List<String> getTestArgs(VirtualEnvironment venv) {
        def args = []

        if (this.useCoverage) {
            if (!this.covPackageName) {
                throw new IllegalStateException("covPackageName must be set when useCoverage is true")
            }
            def covPath
            if (venv.isUnix) {
                covPath = "${venv.name}/lib/python${venv.version}/site-packages/${this.covPackageName}"
            } else {
                covPath = "${venv.name}\\lib\\site-packages\\${this.covPackageName}"
            }
            args.add("--cov=${covPath}")
        }

        if (this.importMode) {
            args.add("--import-mode=${this.importMode}")
        }
        args.add("--junitxml=pytest_reports/junit-${venv.version}.xml")
        if (this.markers) {
            args.add("-m \"${this.markers}\"")
        }
        if (this.jobName) {
            if (this.setup) {
                args.add("--job_name=\"${this.jobName}-${this.setup}-${venv.version}\"")
            } else {
                args.add("--job_name=\"${this.jobName}-${venv.version}\"")
            }
        }
        
        if (this.setup) {
            args.add("--setup=${this.setup}")
        }
        if (this.useWiresharkLogging) {
            args.add("--run_wireshark")
        }
        if (this.logCli) {
            args.add("-o log_cli=True")
        }
        if (this.enableFirmwareVersionCheck) {
            args.add("--enable_firmware_version_check")
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

/**
 * TestGroup - Named container for a set of TestSession objects that share a base configuration.
 *
 * A TestGroup ties together:
 *  - A logical name that matches the key used in rack_specifiers test_configs
 *    (e.g. "ECAT_TEST_SESSIONS", "CAN_TEST_SESSIONS", "ETH_TEST_SESSIONS").
 *  - A base TestSession whose attributes are inherited by every session in the group.
 *  - A list of TestSession objects (populated by PyTestManager.buildTestSessions() and
 *    optionally extended manually for sessions not covered by rack_specifiers).
 *
 * Usage pattern:
 *   1. Declare the group via the test manager (registers it for buildTestSessions):
 *        TestGroup ECAT_TESTS = testManager.createGroup("ECAT_TEST_SESSIONS", HW_TEST_SESSIONS.override())
 *   2. Export and populate sessions from the specifier module:
 *        testManager.buildTestSessions("tests.setups.rack_specifiers")
 *   3. Optionally append manually-managed sessions via addSession():
 *        ECAT_TESTS.addSession(uid: "pcap", markers: "pcap", stageName: "Pcap Tests")
 *   4. Gate the hardware node on the group and run all sessions:
 *        when { expression { ECAT_TESTS.anyShouldRun() } }
 *        ECAT_TESTS.runTestStages()
 */
class TestGroup {
    /** Key used to look up this group in rack_specifiers test_configs (e.g. "ECAT_TEST_SESSIONS"). */
    final String name
    /** Template session; every session in this group is derived via baseTestSession.override(). */
    final TestSession baseTestSession
    /** Ordered list of sessions to run; populated by buildTestSessions() and addSession(). */
    private List<TestSession> _sessions
    /** Back-reference to the PyTestManager that created this group */
    private final PyTestManager manager
    /** When true, addSession() will throw. Set automatically by runTestStages() to prevent
     *  concurrent modifications from parallel branches. */
    private boolean locked = false

    TestGroup(String name, TestSession baseTestSession, PyTestManager manager) {
        this.name = name
        this.baseTestSession = baseTestSession
        this._sessions = []
        this.manager = manager
    }

    /** Read-only access to the sessions list. */
    @NonCPS
    List<TestSession> getSessions() {
        return this._sessions
    }

    /**
     * Add a new session to this group, by creating a session from the baseTestSession and overriding it with the given attributes.   
     *
     * The 'overrides' map uses the same keys as TestSession.override() (e.g. uid, markers, setup,
     * stageName, shouldRun, skipReason). Policy evaluation in buildTestSessions() is encoded
     * by including shouldRun/skipReason in the map before calling this method.
     *
     * Usage examples:
     *   // Manual session (always runs when uid matches):
     *   ECAT_TESTS.addSession(uid: "pcap", markers: "pcap", stageName: "Pcap Tests")
     *
     *   // Session with policy already evaluated (used by buildTestSessions()):
     *   group.addSession(uid: ..., ..., shouldRun: false, skipReason: "...")
     *
     * @param overrides  Map of TestSession attribute overrides (must include at least 'uid')
     */
    void addSession(Map overrides) {
        if (this.locked) {
            throw new IllegalStateException(
                "Cannot add session to locked group '${this.name}'. "
                + "The group was locked by runTestStages() to prevent concurrent modifications from parallel branches."
            )
        }
        if (!overrides.containsKey('uid') || !overrides.uid) {
            throw new IllegalArgumentException("addSession() requires a non-null 'uid' in overrides. Got: ${overrides}")
        }
        if (!overrides.containsKey('stageName') || !overrides.stageName) {
            throw new IllegalArgumentException("addSession() requires a non-null 'stageName' in overrides. Got: ${overrides}")
        }
        def session = this.baseTestSession.override(overrides)
        def testSessionFilter = this.manager.testSessionFilter
        if (!(session.uid ==~ testSessionFilter)) {
            session.shouldRun = false
            session.skipReason = "uid '${session.uid}' does not match test_session_filter '${testSessionFilter}'"
        }
        this._sessions << session
    }

    /**
     * Returns true if at least one session in this group has shouldRun == true.
     * Used as the gate condition for allocating the hardware node.
     */
    boolean anyShouldRun() {
        return this._sessions.any { it.shouldRun }
    }

    /**
     * Returns a human-readable summary of the group and all its sessions.
     * Includes run/skip status and the skip reason for excluded sessions.
     */
    String configSummary() {
        def runCount = this._sessions.count { it.shouldRun }
        def lines = ["TestGroup '${this.name}': ${this._sessions.size()} session(s), ${runCount} to run"]
        this._sessions.each { session ->
            def status = session.shouldRun ? 'run ' : 'skip'
            def reason = session.shouldRun ? '' : " (${session.skipReason})"
            lines << "  [${status}] ${session.stageName} [uid=${session.uid}]${reason}"
        }
        return lines.join('\n')
    }

    /**
     * Run test stages from pre-built TestSession objects.
     *
     * Locks the group to prevent concurrent modifications, then runs each session
     * as a Jenkins stage. Sessions with shouldRun==false are marked with
     * Utils.markStageSkippedForConditional() so they appear grey (skipped) in the
     * Jenkins UI rather than green (passed).
     */
    def runTestStages() {
        this.locked = true
        this._sessions.each { session ->
            this.manager.pipeline.stage(session.stageName) {
                if (session.shouldRun) {
                    this.manager.runTestSession(session)
                } else {
                    this.manager.pipeline.echo "Skipped: ${session.skipReason}"
                    org.jenkinsci.plugins.pipeline.modeldefinition.Utils.markStageSkippedForConditional(session.stageName)
                }
            }
        }
    }
}

class PyTestManager {
    private VEnvManager venvManager
    private def pipeline
    /**
     * Set of active run-policy tags for this build (e.g. "nightly", "weekends").
     * Populated from pipeline boolean parameters (RUN_POLICY_NIGHTLY, RUN_POLICY_WEEKEND).
     * Used by shouldRunPolicy() for tag-based test gating.
     */
    Set<String> runPolicyTags = [] as Set
    private List coverageStashes = []
    /** All TestGroups registered via createGroup(), keyed by group name; */
    private Map registeredGroups = [:]
    /** Regex pattern used to filter which test sessions run; matched against each session's uid. */
    String testSessionFilter = '.*'

    PyTestManager(Map args = [pipeline: null, venvManager: null]) {
        this.venvManager = args.venvManager
        this.pipeline = args.pipeline
    }

    /**
     * Check if tests should run based on the given policy key.
     * "always" and "never" are reserved; everything else is a tag lookup against runPolicyTags.
     * @param policyKey Policy key to evaluate
     * @return Map [result: boolean, reason: String]
     */
    Map shouldRunPolicy(String policyKey) {
        if (policyKey == "always") {
            return [result: true, reason: "Policy 'always' is always enabled"]
        }
        if (policyKey == "never") {
            return [result: false, reason: "Policy 'never' is always disabled"]
        }
        def hasTag = this.runPolicyTags.contains(policyKey)
        def reason = hasTag
            ? "Policy '${policyKey}': tag is present (runPolicyTags=${this.runPolicyTags})"
            : "Policy '${policyKey}': tag is not present (runPolicyTags=${this.runPolicyTags})"
        return [result: hasTag, reason: reason]
    }

    /**
     * Create a TestGroup, register it for use by buildTestSessions(), and return it.
     *
     * All groups created this way are automatically considered when buildTestSessions() is
     * called
     *
     * @param name            Key matching the session name in the specifier JSON (e.g. "ECAT_TEST_SESSIONS")
     * @param baseTestSession Template session whose attributes are inherited by every session in the group
     * @return The newly created TestGroup
     */
    TestGroup createGroup(String name, TestSession baseTestSession) {
        def group = new TestGroup(name, baseTestSession, this)
        this.registeredGroups[name] = group
        return group
    }

    /**
     * Echo a configSummary() for every registered TestGroup.
     * Useful at the end of session preparation to give a readable overview of what will run.
     */
    void echoTestGroupsSummary() {
        this.registeredGroups.each { name, group ->
            this.pipeline.echo(group.configSummary())
        }
    }

    /**
     * Export specifiers to JSON file and return parsed data.
     *
     * The output filename is derived from the last segment of specifierModule
     * (e.g. "tests.setups.rack_specifiers" → "rack_specifiers.json") and the
     * file is always stored under tests/setups/specifiers_json/ in the working folder.
     * The file is copied back to the workspace if needed, archived as a build
     * artifact, and the parsed map is returned. Always overwrites an existing file.
     *
     * @param specifierModule Specifier module to export (e.g., "tests.setups.rack_specifiers")
     * @return Map of parsed specifiers
     */
    private Map exportSpecifiersModule(String specifierModule) {
        def outputFileName = specifierModule.tokenize('.').last() + '.json'
        // Always save in tests/setups/specifiers_json/ subdirectory of working folder
        def workingFolder = this.venvManager.getWorkingFolder()
        def workingOutputFile = this.venvManager.joinPath(workingFolder, "tests", "setups", "specifiers_json", outputFileName)

        // Export specifiers (always override)
        this.venvManager.withPython(this.venvManager.default_python_version) { venv ->
            venv.run("poetry run poe export_specifier_module -- --specifier_module ${specifierModule} --output_file ${workingOutputFile} --root_dir ${workingFolder} --override")
        }

        // Copy from working folder to workspace if they're different
        if (workingFolder != this.pipeline.env.WORKSPACE) {
            this.venvManager.copyFromWorkingFolder("tests/setups/specifiers_json/${outputFileName}")
        }

        // Archive the artifact from workspace
        this.pipeline.archiveArtifacts artifacts: "tests/setups/specifiers_json/${outputFileName}", allowEmptyArchive: true

        // Load and return the parsed specifiers
        return this.loadSpecifiers("${this.pipeline.env.WORKSPACE}/tests/setups/specifiers_json/${outputFileName}")
    }
    
    /**
     * Load specifiers from a JSON file.
     * 
     * @param jsonPath Path to the specifiers JSON file
     * @return Map of parsed specifiers
     */
    private Map loadSpecifiers(String jsonPath) {
        if (!this.pipeline.fileExists(jsonPath)) {
            throw new Exception("Specifiers JSON file not found at ${jsonPath}. Cannot load specifiers.")
        }
        
        def jsonText = this.pipeline.readFile(file: jsonPath)
        def specifiers = this.pipeline.readJSON(text: jsonText)
        return specifiers
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

    /**
     * Checks if there are any coverage files available.
     * 
     * @return true if coverage files have been stashed, false otherwise
     */
    def hasCoverageFiles() {
        return !this.coverageStashes.isEmpty()
    }

    /**
     * Build an exclusion string for pytest markers.
     * Converts a list of marker names into a pytest-compatible exclusion string.
     * 
     * @param excludes List of marker names to exclude
     * @return A string like 'not marker1 and not marker2' suitable for pytest -m option
     */
    static def markersExcludeString(excludes) {
        return excludes.collect { "not ${it}" }.join(' and ')
    }

    /**
     * Delete files matching a glob pattern (e.g. "wireshark/*.pcap", "*.coverage*").
     * Silently succeeds if no files match or the path does not exist.
     *
     * @param pattern Unix-style glob pattern (forward slashes). On Windows, slashes are
     *                converted to backslashes automatically.
     */
    private def deleteFiles(String pattern) {
        if (this.venvManager.isUnixNode()) {
            this.pipeline.sh(script: "rm -f ${pattern}", returnStatus: true)
        } else {
            this.pipeline.bat(script: "del /f \"${pattern.replace('/', '\\')}\" ", returnStatus: true)
        }
    }

    /**
     * Archive Wireshark log files as Jenkins artifacts.
     * Archives all .pcap files from the specified directory.
     * 
     * @param wiresharkDir Directory containing Wireshark log files
     */
    private def archiveWiresharkLogs(String wiresharkDir) {
        if (this.venvManager.isUnixNode()) {
            this.pipeline.archiveArtifacts artifacts: "${wiresharkDir}/*.pcap", allowEmptyArchive: true
        } else {
            this.pipeline.archiveArtifacts artifacts: "${wiresharkDir}\\*.pcap", allowEmptyArchive: true
        }
    }

    /**
     * Clear Wireshark log files from the specified directory.
     * Removes all .pcap files to prepare for new test runs.
     * 
     * @param wiresharkDir Directory containing Wireshark log files to clear
     */
    private def clearWiresharkLogs(String wiresharkDir) {
        this.deleteFiles("${wiresharkDir}/*.pcap")
    }

    /**
     * Clear coverage files from the current directory.
     * Removes all .coverage* files to prepare for new test runs.
     */
    private def clearCoverageFiles() {
        this.deleteFiles('*.coverage*')
    }

    /**
     * Stash coverage file for later merging.
     * Moves the coverage file to a unique stash name to avoid collisions and stashes it.
     * 
     * @param uid Unique identifier of the test session
     * @param venvName Name of the virtual environment (e.g., '.venv3.9')
     */
    private def stashCoverageFile(String uid, String venvName) {
        def workingFolder = this.venvManager.getWorkingFolder()
        // Copy coverage file back from working folder if it differs from workspace
        if (workingFolder != this.pipeline.env.WORKSPACE) {
            this.venvManager.copyFromWorkingFolder(".coverage")
        }

        // Build stash name with uid and venv name to ensure uniqueness
        def base_stash_name = ".coverage_${uid}_${venvName}"
        
        // Handle stash name collision by appending index as fallback
        def coverage_stash = base_stash_name
        int index = 1
        while (this.coverageStashes.contains(coverage_stash)) {
            coverage_stash = "${base_stash_name}_${index}"
            index++
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
        
        // Delete the junit after publishing it so it is not re-published on the next stage
        this.deleteFiles('pytest_reports/*.xml')
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
        // Validate that uid is set
        if (!session.uid) {
            throw new IllegalArgumentException("TestSession uid must be set before running tests")
        }
        
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
                if (session.runInVirtualEnvs == null) {
                    throw new IllegalArgumentException("runInVirtualEnvs must be set in the TestSession to specify which virtual environments to run tests against.")
                }
                this.venvManager.forVirtualEnvs(session.runInVirtualEnvs) { venv ->
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
                        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
                            // Build was cancelled or a timeout expired — re-throw so Jenkins marks
                            // the build as ABORTED instead of UNSTABLE, and skip publishing.
                            throw e
                        } catch (err) {
                            this.pipeline.unstable(message: "Tests failed")
                        }
                        // Only reached on success or after a caught test failure.
                        // Skipped entirely if FlowInterruptedException was re-thrown above.
                        this.publishAndCleanupJunitReports()
                        if (firstIteration && session.useCoverage) {
                            this.stashCoverageFile(session.uid, venv.name)
                        }
                        firstIteration = false
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

    /**
     * Export and parse a specifier module, then populate test sessions into all registered TestGroups.
     *
     * Exports the specifier module to a JSON artifact (filename derived from the module
     * path's last segment), then creates TestSession objects eagerly before any hardware
     * node runs. Policy and uid-regex checks are evaluated immediately; every entry
     * (including sessions that will be skipped) is retained so runTestStages() can mark
     * them correctly. Only registered groups (created via createGroup()) are considered;
     * additional sessions can be appended via group.addSession() after this call.
     *
     * @param specifierModule  Python module path to export
     *                         (e.g. "tests.setups.rack_specifiers").    
     */
    void buildTestSessions(String specifierModule) {
        def exportedSpecifiers = this.exportSpecifiersModule(specifierModule)

        exportedSpecifiers.each { setupKey, specifiers ->
            // A SpecifierContainer wraps multiple part numbers; a direct specifier exposes one.
            // This determines the pytest --setup path format:
            //   Container:         SETUP@PART_NUMBER@VERSION
            //   Direct specifier:  SETUP@VERSION  (no part-number segment)
            boolean isContainer = specifiers.size() > 1

            specifiers.each { specifierName, specifierData ->
                // Normalise no-version specifiers (extra_data at the specifier level, no version key)
                // to version "" so the loop below works uniformly for both versioned and unversioned.
                // https://novantamotion.atlassian.net/browse/CIT-612
                def versionedData = specifierData.containsKey("extra_data") ? ["": specifierData] : specifierData

                versionedData.each { version, versionData ->
                    // "" and "latest" both mean no version suffix.
                    // "" covers unversioned specifiers (e.g. Multislave, where extra_data
                    // sits directly under the specifier and gets normalised to version="").
                    // "latest" covers virtual-drive specifiers whose JSON always carries a
                    // "latest" key even though there is no real version to pin; appending
                    // "@latest" to the setup path would produce an invalid import path.
                    // https://novantamotion.atlassian.net/browse/CIT-612
                    def versionTag = (version && version != "latest") ? "@${version}" : ""
                    def setupPath = isContainer
                        ? "${specifierModule}.${setupKey}@${specifierName}${versionTag}"
                        : "${specifierModule}.${setupKey}${versionTag}"
                    def executionPolicy = versionData?.extra_data?.execution_policy

                    def testConfigs = versionData?.extra_data?.test_configs
                    if (!testConfigs) {
                        this.pipeline.error(
                            "Missing 'extra_data.test_configs' for specifier '${specifierName}' "
                            + "(version='${version}') in setup '${setupKey}'. "
                            + "Ensure the specifier JSON contains extra_data with test_configs."
                        )
                    }

                    testConfigs.each { groupName, testConfig ->
                        def group = this.registeredGroups[groupName]
                        if (!group) {
                            this.pipeline.error("No TestGroup found for group name '${groupName}'. Available groups: ${this.registeredGroups.keySet()}")
                        }
                        def overrides = [
                            uid: testConfig.run_test_stage_uid,
                            markers: testConfig.markers,
                            setup: setupPath,
                            stageName: testConfig.stage_name,
                            policy: executionPolicy ?: 'always'
                        ]
                        if (executionPolicy) {
                            def policyResult = this.shouldRunPolicy(executionPolicy)
                            if (!policyResult.result) {
                                overrides.shouldRun = false
                                overrides.skipReason = policyResult.reason
                            }
                        }
                        group.addSession(overrides)
                    }
                }
            }
        }
    }

    // --- Test Dashboard ---

    /**
     * Run pytest --collect-only and return the list of selected test node IDs.
     *
     * When session is null the collection is unfiltered (no markers, no setup args),
     * giving the full set of discoverable tests. When a session is supplied its
     * getTestArgs() is used to mirror the exact arguments that runTestSession would pass.
     *
     * Always cleans up the temporary output file after reading it.
     *
     * @param session  TestSession to collect for, or null for unfiltered baseline
     * @return Ordered list of test node IDs (e.g. "tests/test_servo.py::test_connect")
     */
    private List<String> collectTests(TestSession session = null) {
        def outputFile = "${this.pipeline.env.WORKSPACE}/.collect_output.txt"

        this.venvManager.withPython(this.venvManager.default_python_version) { venv ->
            def testArgsStr = session ? session.getTestArgs(venv).join(' ') : ''
            venv.run("poetry run pytest --collect-only -q --tb=no --no-header ${testArgsStr} > \"${outputFile}\" 2>&1")
        }

        def output = this.pipeline.readFile(file: outputFile)
        this.deleteFiles(outputFile)
        return output.readLines().findAll { line ->
            def t = line.trim()
            t && t.contains('::') && !t.startsWith('#') && !t.contains('PytestCollectionWarning')
        }.collect { it.trim() }
    }

    /** Collect test data and delegate HTML generation to TestDashboardBuilder. */
    def generateTestDashboard() {
        try {
            def allSessions = []
            this.registeredGroups.each { name, group ->
                group.sessions.each { session -> allSessions << session }
            }
            if (allSessions.isEmpty()) {
                this.pipeline.echo("generateTestDashboard: no sessions registered; skipping.")
                return
            }

            // Baseline: collect ALL tests (no filters) so uncovered tests still appear as rows
            def allTestsList = this.collectTests()

            // Collect per-session test sets (one pytest --collect-only run per session)
            def uidToTests = [:]
            allSessions.each { session ->
                uidToTests[session.uid] = this.collectTests(session)
                uidToTests[session.uid].each { test ->
                    if (!allTestsList.contains(test)) allTestsList << test
                }
            }

            this.pipeline.echo("generateTestDashboard: building HTML (${allTestsList.size()} tests, ${allSessions.size()} sessions)...")
            new TestDashboardBuilder(this.pipeline, this.registeredGroups)
                .buildAndPublish(allTestsList, uidToTests)
            this.pipeline.echo("generateTestDashboard: complete.")
        } catch (Exception e) {
            this.pipeline.echo("generateTestDashboard FAILED: ${e.getClass().getName()}: ${e.getMessage()}")
            throw e
        }
    }
}

// TestDashboardBuilder - Generates an HTML test-coverage dashboard

class TestDashboardBuilder {
    private def pipeline
    private Map registeredGroups

    TestDashboardBuilder(def pipeline, Map registeredGroups) {
        this.pipeline = pipeline
        this.registeredGroups = registeredGroups
    }

    // --- Policy helpers ---

    /**
     * Map a policy tag to a CSS class name for the dashboard table.
     */
    @NonCPS
    private static String policyCssClass(String policy) {
        def map = [always: 'policy-always', nightly: 'policy-nightly', weekends: 'policy-weekends', never: 'policy-never']
        return map.getOrDefault(policy ?: 'always', 'policy-other')
    }

    @NonCPS
    private static Map policyLetterMap() {
        return [always: '&#x2705;', nightly: '&#x1F319;', weekends: '&#x1F31E;', never: '&#x274C;']
    }

    // --- UID trie helpers ---

    /**
     * Build a trie from session UIDs split on '_'.
     * Each node: Map with keys 'label' (String), 'children' (List), 'session' (TestSession or null).
     * Leaf nodes carry the session reference.
     *
     * NOTE: All trie helpers use explicit Map.get()/put() and typed for-loops
     * to avoid DefaultGroovyMethods.invokeMethod which the Jenkins sandbox blocks.
     */
    @NonCPS
    private static Map buildUidTrie(List sessions) {
        Map root = [label: '', children: [], session: null]
        for (int i = 0; i < sessions.size(); i++) {
            def session = sessions.get(i)
            String[] parts = session.uid.split('_')
            Map node = root
            for (int p = 0; p < parts.length; p++) {
                String part = parts[p]
                List children = (List) node.get('children')
                Map existing = null
                for (int c = 0; c < children.size(); c++) {
                    Map child = (Map) children.get(c)
                    if (child.get('label') == part) {
                        existing = child
                        break
                    }
                }
                if (existing == null) {
                    existing = [label: part, children: [], session: null]
                    children.add(existing)
                }
                node = existing
            }
            node.put('session', session)
        }
        return root
    }

    /** Max depth of a trie (0 for a leaf). */
    @NonCPS
    private static int trieDepth(Map node) {
        List children = (List) node.get('children')
        if (children.isEmpty()) return 0
        int maxD = 0
        for (int i = 0; i < children.size(); i++) {
            int d = trieDepth((Map) children.get(i))
            if (d > maxD) maxD = d
        }
        return 1 + maxD
    }

    /** Number of leaf nodes below (inclusive). */
    @NonCPS
    private static int trieLeafCount(Map node) {
        List children = (List) node.get('children')
        if (children.isEmpty()) return 1
        int sum = 0
        for (int i = 0; i < children.size(); i++) {
            sum += trieLeafCount((Map) children.get(i))
        }
        return sum
    }

    /**
     * Collect header cells from a trie, returning a list of lists (one per header row).
     * Each cell: Map with keys 'label', 'colspan', 'rowspan', 'session'.
     */
    @NonCPS
    private static List collectTrieHeaderCells(Map root, int totalRows) {
        List rows = []
        for (int i = 0; i < totalRows; i++) { rows.add([]) }
        List rootChildren = (List) root.get('children')
        for (int i = 0; i < rootChildren.size(); i++) {
            traverseTrieNode((Map) rootChildren.get(i), 0, totalRows, rows)
        }
        return rows
    }

    @NonCPS
    private static void traverseTrieNode(Map node, int depth, int totalRows, List rows) {
        List children = (List) node.get('children')
        List rowList = (List) rows.get(depth)
        if (children.isEmpty()) {
            rowList.add([label: node.get('label'), colspan: 1, rowspan: totalRows - depth, session: node.get('session')])
        } else {
            rowList.add([label: node.get('label'), colspan: trieLeafCount(node), rowspan: 1, session: null])
            for (int i = 0; i < children.size(); i++) {
                traverseTrieNode((Map) children.get(i), depth + 1, totalRows, rows)
            }
        }
    }

    // --- HTML builder helpers ---

    /** CSS styles for the dashboard. */
    @NonCPS
    private static String buildCssStyles() {
        return '''\
  <style>
    body { font-family: monospace; font-size: 11px; margin: 20px; }
    h1   { font-size: 16px; }
    .table-wrap { overflow: auto; max-width: 100%; max-height: 85vh; }
    table#dashboard { border-collapse: collapse; }
    .search-box { margin: 8px 0; }
    .search-box input { padding: 4px 8px; font-size: 12px; width: 300px; }
    thead th { white-space: nowrap; position: sticky; z-index: 10; background: #fff; }
    thead th.sortable { cursor: pointer; user-select: none; }
    thead th.sortable:hover { background: #eef3fa; }
    thead th .sort-arrow { font-size: 9px; margin-left: 2px; color: #999; }
    thead tr.group-row th { background: #dde8f5 !important; font-weight: bold; text-align: center; }
    thead tr.session-row th { white-space: normal; text-align: center; min-width: 40px; max-width: 80px; font-size: 10px; }
    tbody tr:nth-child(even) td { background-color: #f9f9f9; }
    tbody tr:nth-child(even) td.test-name { background-color: #f9f9f9; }
    tbody tr:hover td { filter: brightness(0.92); }
    td.test-name, th.test-name { position: sticky; left: 0; z-index: 5; background: #fff;
                   text-align: left; white-space: nowrap; max-width: 400px;
                   overflow: hidden; text-overflow: ellipsis; }
    thead th.test-name { z-index: 20; background: #fff; }
    thead tr.group-row th.test-name { background: #dde8f5 !important; }
    tr.file-group td { font-weight: bold; background: #eee !important; border-bottom: 1px solid #ccc; padding: 4px 6px; }
    th.skipped { color: #888; font-style: italic; }
    td.policy-cell { text-align: center; font-weight: bold; font-size: 12px; }
    .policy-always   { background: #c6efce; }
    .policy-nightly  { background: #ffeb9c; }
    .policy-weekends { background: #f4b942; }
    .policy-never    { background: #d9d9d9; }
    .policy-other    { background: #9fc5e8; }
    .legend { margin: 8px 0; }
    .legend-item { display: inline-block; margin-right: 8px;
                   padding: 2px 10px; border: 1px solid #ccc; }
    .policy-none     { background: #ffc7ce; }
  </style>'''
    }

    /** Summary line and policy legend HTML. */
    @NonCPS
    private static String buildLegendHtml(int testCount, int sessionCount) {
        def sb = new StringBuilder()
        sb.append("  <p>${testCount} test(s) &nbsp;|&nbsp; ${sessionCount} session(s)</p>\n")
        sb.append('  <div class="legend">\n')
        def letters = policyLetterMap()
        List labels = ['always', 'nightly', 'weekends', 'never']
        for (int i = 0; i < labels.size(); i++) {
            String label = (String) labels.get(i)
            String letter = (String) letters.getOrDefault(label, '&#x2753;')
            sb.append("    <span class=\"legend-item policy-${label}\">${letter} = ${label}</span>\n")
        }
        sb.append('    <span class="legend-item policy-none">&#x1F6AB; = not covered</span>\n')
        sb.append('  </div>\n')
        sb.append('  <div class="search-box"><input id="search" type="text" placeholder="Filter tests..."></div>\n')
        return sb.toString()
    }

    /** Table header: group name row + hierarchical UID trie rows. */
    @NonCPS
    private static String buildTableHeaderHtml(List groupedSessions, List groupTries, int maxTrieDepth) {
        def sb = new StringBuilder()
        int totalHeaderRows = maxTrieDepth + 1

        // Row 1: group headers
        sb.append('      <tr class="group-row">\n')
        sb.append("        <th rowspan=\"${totalHeaderRows}\" class=\"test-name\">Test Node ID</th>\n")
        sb.append("        <th rowspan=\"${totalHeaderRows}\">Best</th>\n")
        for (int gi = 0; gi < groupedSessions.size(); gi++) {
            List pair = (List) groupedSessions.get(gi)
            String groupName = (String) pair.get(0)
            List sessions = (List) pair.get(1)
            sb.append("        <th colspan=\"${sessions.size()}\">${groupName}</th>\n")
        }
        sb.append('      </tr>\n')

        // Rows 2..N: hierarchical UID headers
        List allTrieRows = []
        for (int gi = 0; gi < groupTries.size(); gi++) {
            allTrieRows.add(collectTrieHeaderCells((Map) groupTries.get(gi), maxTrieDepth))
        }
        for (int row = 0; row < maxTrieDepth; row++) {
            sb.append('      <tr class="session-row">\n')
            for (int gi = 0; gi < allTrieRows.size(); gi++) {
                List trieRows = (List) allTrieRows.get(gi)
                List rowCells = (List) trieRows.get(row)
                for (int ci = 0; ci < rowCells.size(); ci++) {
                    Map cell = (Map) rowCells.get(ci)
                    List attrs = []
                    int colspanVal = (int) cell.get('colspan')
                    int rowspanVal = (int) cell.get('rowspan')
                    if (colspanVal > 1) attrs.add("colspan=\"${colspanVal}\"")
                    if (rowspanVal > 1) attrs.add("rowspan=\"${rowspanVal}\"")
                    def cellSession = cell.get('session')
                    if (cellSession != null) {
                        if (!cellSession.shouldRun) attrs.add('class="skipped"')
                        List titleLines = []
                        if (cellSession.markers) { titleLines.add("markers: ${cellSession.markers}") }
                        if (cellSession.setup)   { titleLines.add("setup: ${cellSession.setup}") }
                        if (!cellSession.shouldRun && cellSession.skipReason) { titleLines.add("skip: ${cellSession.skipReason}") }
                        if (!titleLines.isEmpty()) {
                            attrs.add("title=\"${titleLines.join('&#10;').replace('"', '&quot;')}\"")
                        }
                    }
                    String attrStr = attrs.isEmpty() ? '' : ' ' + attrs.join(' ')
                    String cellLabel = (String) cell.get('label')
                    sb.append("        <th${attrStr}>${cellLabel}</th>\n")
                }
            }
            sb.append('      </tr>\n')
        }
        return sb.toString()
    }

    /** Table body: one row per test with best-policy and per-session indicator cells. */
    @NonCPS
    private static String buildTableBodyHtml(List<String> allTests, List allSessions, Map sessionTestSets) {
        def sb = new StringBuilder()
        List policyPriority = ['always', 'weekends', 'nightly', 'never']

        for (int ti = 0; ti < allTests.size(); ti++) {
            String testId = (String) allTests.get(ti)
            sb.append('      <tr>\n')
            String displayName = testId.startsWith('tests/') ? testId.substring(6) : testId
            sb.append("        <td class=\"test-name\">${displayName.replace('&', '&amp;').replace('<', '&lt;')}</td>\n")

            // Best policy across all sessions for this test
            int bestIdx = policyPriority.size()
            for (int si = 0; si < allSessions.size(); si++) {
                def session = allSessions.get(si)
                List tests = (List) sessionTestSets.get(session.uid)
                if (tests != null && tests.contains(testId)) {
                    String policyTag = session.policy ?: 'always'
                    int idx = policyPriority.indexOf(policyTag)
                    if (idx >= 0 && idx < bestIdx) { bestIdx = idx }
                }
            }
            if (bestIdx < policyPriority.size()) {
                String bestPolicy = (String) policyPriority.get(bestIdx)
                String bestClass = policyCssClass(bestPolicy)
                String bestLetter = (String) policyLetterMap().getOrDefault(bestPolicy, '&#x2753;')
                sb.append("        <td class=\"${bestClass} policy-cell\" title=\"${bestPolicy}\">${bestLetter}</td>\n")
            } else {
                sb.append('        <td class="policy-none policy-cell" title="not covered">&#x1F6AB;</td>\n')
            }

            // Per-session cells
            for (int si = 0; si < allSessions.size(); si++) {
                def session = allSessions.get(si)
                List tests = (List) sessionTestSets.get(session.uid)
                if (tests != null && tests.contains(testId)) {
                    String policyClass = policyCssClass(session.policy ?: 'always')
                    String policyTag = session.policy ?: 'always'
                    String policyLabel = policyTag.replace('"', '&quot;')
                    String policyLetter = (String) policyLetterMap().getOrDefault(policyTag, '&#x2753;')
                    sb.append("        <td class=\"${policyClass} policy-cell\" title=\"${policyLabel}\">${policyLetter}</td>\n")
                } else {
                    sb.append('        <td></td>\n')
                }
            }
            sb.append('      </tr>\n')
        }
        return sb.toString()
    }

    /** Client-side JavaScript: search filter, sticky headers, file-group rows. */
    @NonCPS
    private static String buildScriptHtml() {
        return '''\
  <script>
    (function () {
      // Sticky header row offsets: cascade each row below the previous
      var hrows = document.querySelectorAll('#dashboard thead tr');
      var offset = 0;
      for (var r = 0; r < hrows.length; r++) {
        var ths = hrows[r].querySelectorAll('th');
        for (var t = 0; t < ths.length; t++) { ths[t].style.top = offset + 'px'; }
        offset += hrows[r].offsetHeight;
      }
      // Search filter
      var input = document.getElementById('search');
      if (input) {
        input.addEventListener('input', function() {
          var term = this.value.toLowerCase();
          var rows = document.querySelectorAll('#dashboard tbody tr');
          for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            if (row.classList.contains('file-group')) { row.style.display = 'none'; continue; }
            var td = row.querySelector('td.test-name');
            var text = td ? (td.title || td.textContent).toLowerCase() : '';
            row.style.display = text.indexOf(term) >= 0 ? '' : 'none';
          }
          // Re-show file-group rows that have visible siblings after them
          var allRows = document.querySelectorAll('#dashboard tbody tr');
          for (var i = 0; i < allRows.length; i++) {
            if (!allRows[i].classList.contains('file-group')) continue;
            for (var j = i + 1; j < allRows.length; j++) {
              if (allRows[j].classList.contains('file-group')) break;
              if (allRows[j].style.display !== 'none') { allRows[i].style.display = ''; break; }
            }
          }
        });
      }
      // Group tests by file: insert file header rows and shorten test names
      function rebuildFileGroups() {
        var tbody = document.querySelector('#dashboard tbody');
        // Remove existing file-group rows
        var existing = tbody.querySelectorAll('tr.file-group');
        for (var i = 0; i < existing.length; i++) existing[i].remove();
        var rows = Array.from(tbody.querySelectorAll('tr'));
        var lastFile = '';
        var totalCols = rows.length > 0 ? rows[0].children.length : 1;
        rows.forEach(function(row) {
          var td = row.querySelector('td.test-name');
          if (!td) return;
          var text = td.title || td.textContent;
          var idx = text.indexOf('::');
          if (idx < 0) return;
          var file = text.substring(0, idx);
          if (file !== lastFile) {
            var groupRow = document.createElement('tr');
            groupRow.className = 'file-group';
            var fileTd = document.createElement('td');
            fileTd.className = 'test-name';
            fileTd.colSpan = totalCols;
            fileTd.textContent = file;
            groupRow.appendChild(fileTd);
            row.parentNode.insertBefore(groupRow, row);
            lastFile = file;
          }
        });
      }
      // Initial file-group build + shorten test names
      (function() {
        var tbody = document.querySelector('#dashboard tbody');
        var rows = Array.from(tbody.querySelectorAll('tr'));
        var lastFile = '';
        var totalCols = rows.length > 0 ? rows[0].children.length : 1;
        rows.forEach(function(row) {
          var td = row.querySelector('td.test-name');
          if (!td) return;
          var text = td.textContent;
          var idx = text.indexOf('::');
          if (idx < 0) return;
          var file = text.substring(0, idx);
          var func = text.substring(idx + 2);
          if (file !== lastFile) {
            var groupRow = document.createElement('tr');
            groupRow.className = 'file-group';
            var fileTd = document.createElement('td');
            fileTd.className = 'test-name';
            fileTd.colSpan = totalCols;
            fileTd.textContent = file;
            groupRow.appendChild(fileTd);
            row.parentNode.insertBefore(groupRow, row);
            lastFile = file;
          }
          td.textContent = func;
          td.title = text;
        });
      })();
      // Column sorting
      (function() {
        var policyOrder = {'\u2705':0, '\uD83C\uDF1E':1, '\uD83C\uDF19':2, '\u274C':3, '\uD83D\uDEAB':4};
        var sortCol = -1, sortAsc = true;
        // Collect leaf header cells (bottom row + any rowspan cells reaching it)
        var thead = document.querySelector('#dashboard thead');
        var headerRows = thead.querySelectorAll('tr');
        var numHeaderRows = headerRows.length;
        var leafHeaders = [];
        for (var r = 0; r < numHeaderRows; r++) {
          var ths = headerRows[r].querySelectorAll('th');
          for (var t = 0; t < ths.length; t++) {
            var rs = parseInt(ths[t].getAttribute('rowspan')) || 1;
            if (r + rs >= numHeaderRows) {
              leafHeaders.push(ths[t]);
            }
          }
        }
        // Compute visual column index for each leaf header
        var colIdx = 0;
        leafHeaders.forEach(function(th, i) {
          th.dataset.colIdx = colIdx;
          var cs = parseInt(th.getAttribute('colspan')) || 1;
          if (cs === 1) {
            th.classList.add('sortable');
            th.innerHTML += ' <span class="sort-arrow"></span>';
            th.addEventListener('click', function() { doSort(parseInt(this.dataset.colIdx)); });
          }
          colIdx += cs;
        });
        function doSort(ci) {
          if (sortCol === ci) { sortAsc = !sortAsc; } else { sortCol = ci; sortAsc = true; }
          var tbody = document.querySelector('#dashboard tbody');
          // Remove file-group rows before sorting
          var fgs = tbody.querySelectorAll('tr.file-group');
          for (var i = 0; i < fgs.length; i++) fgs[i].remove();
          var rows = Array.from(tbody.querySelectorAll('tr'));
          rows.sort(function(a, b) {
            var ac = a.cells[ci], bc = b.cells[ci];
            var at = ac ? ac.textContent.trim() : '', bt = bc ? bc.textContent.trim() : '';
            // Policy cells: sort by priority
            var ap = policyOrder[at], bp = policyOrder[bt];
            if (ap !== undefined || bp !== undefined) {
              var av = ap !== undefined ? ap : 5, bv = bp !== undefined ? bp : 5;
              return sortAsc ? av - bv : bv - av;
            }
            // Text: sort alphabetically, empties last
            if (!at && bt) return 1;
            if (at && !bt) return -1;
            var cmp = at.localeCompare(bt);
            return sortAsc ? cmp : -cmp;
          });
          rows.forEach(function(row) { tbody.appendChild(row); });
          rebuildFileGroups();
          // Update sort arrows
          leafHeaders.forEach(function(th) {
            var arrow = th.querySelector('.sort-arrow');
            if (!arrow) return;
            var ci2 = parseInt(th.dataset.colIdx);
            arrow.textContent = ci2 === sortCol ? (sortAsc ? '\u25B2' : '\u25BC') : '';
          });
        }
      })();
      // Hide Jenkins HTML Publisher "back to" wrapper link if present
      try { if (window.parent) {
        var wrapper = window.parent.document.querySelector('.htmlpublisher-wrapper a[href*="Back"]');
        if (wrapper) wrapper.style.display = 'none';
      }} catch(e) {}
    })();
  </script>'''
    }

    // --- HTML builder (orchestrator) ---

    /**
     * Assemble the full HTML dashboard document.
     *
     * @param allTests    Ordered list of all pytest node IDs (row headers)
     * @param uidToTests  Map from session uid to list of matching test node IDs
     * @return Complete HTML string
     */
    @NonCPS
    private String buildDashboardHtml(List<String> allTests, Map uidToTests) {
        // Collect sessions from registered groups (preserves insertion order)
        List groupedSessions = []
        List groupNames = []
        groupNames.addAll(this.registeredGroups.keySet())
        for (int gi = 0; gi < groupNames.size(); gi++) {
            String groupName = (String) groupNames.get(gi)
            def group = this.registeredGroups.get(groupName)
            if (!group.sessions.isEmpty()) {
                groupedSessions.add([groupName, group.sessions])
            }
        }
        List allSessions = []
        for (int gi = 0; gi < groupedSessions.size(); gi++) {
            List pair = (List) groupedSessions.get(gi)
            List sessions = (List) pair.get(1)
            for (int si = 0; si < sessions.size(); si++) {
                allSessions.add(sessions.get(si))
            }
        }

        // Pre-compute per-session test sets
        Map sessionTestSets = [:]
        for (int si = 0; si < allSessions.size(); si++) {
            def session = allSessions.get(si)
            sessionTestSets.put(session.uid, uidToTests.get(session.uid) ?: [])
        }

        // Build UID tries and compute max depth across all groups
        List groupTries = []
        int maxTrieDepth = 0
        for (int gi = 0; gi < groupedSessions.size(); gi++) {
            List pair = (List) groupedSessions.get(gi)
            Map trie = buildUidTrie((List) pair.get(1))
            int depth = trieDepth(trie)
            if (depth > maxTrieDepth) maxTrieDepth = depth
            groupTries.add(trie)
        }

        // Assemble the complete HTML document
        def sb = new StringBuilder()
        sb.append('<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n')
        sb.append('  <title>Test Coverage Dashboard</title>\n')
        sb.append(buildCssStyles())
        sb.append('\n</head>\n<body>\n  <h1>Test Coverage Dashboard</h1>\n')
        sb.append(buildLegendHtml(allTests.size(), allSessions.size()))
        sb.append('  <div class="table-wrap">\n')
        sb.append('  <table id="dashboard">\n    <thead>\n')
        sb.append(buildTableHeaderHtml(groupedSessions, groupTries, maxTrieDepth))
        sb.append('    </thead>\n    <tbody>\n')
        sb.append(buildTableBodyHtml(allTests, allSessions, sessionTestSets))
        sb.append('    </tbody>\n  </table>\n  </div>\n')
        sb.append(buildScriptHtml())
        sb.append('\n</body>\n</html>\n')
        return sb.toString()
    }


    // --- Build and publish ---

    /**
     * Build the HTML dashboard and publish it as a Jenkins HTML report.
     *
     * @param allTests   Ordered list of all pytest node IDs (row headers)
     * @param uidToTests Map from session uid to list of matching test node IDs
     */
    def buildAndPublish(List<String> allTests, Map uidToTests) {
        def html = this.buildDashboardHtml(allTests, uidToTests)
        this.pipeline.echo("generateTestDashboard: HTML built (${html.size()} chars), writing file...")

        def reportDir  = 'test_dashboard'
        def reportFile = 'index.html'
        this.pipeline.writeFile(file: "${reportDir}/${reportFile}", text: html, encoding: 'UTF-8')
        this.pipeline.echo("generateTestDashboard: writeFile done, calling publishHTML...")
        this.pipeline.publishHTML([
            allowMissing         : false,
            alwaysLinkToLastBuild: true,
            keepAll              : true,
            reportDir            : reportDir,
            reportFiles          : reportFile,
            reportName           : 'Test Coverage Dashboard',
            reportTitles         : ''
        ])
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
            description: 'Regex pattern for which test sessions to run (e.g. "fsoe.*", "ethercat_everest", ".*" for all)'
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

