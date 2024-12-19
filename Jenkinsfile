@Library('cicd-lib@CIT-296-evaluate-using-scp-for-publishing-to-distext') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.5"
def WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.6"
def PUBLISHER_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/publisher:dev"

def DIST_FOE_APP_PATH = "ECAT-tools"
def LIB_FOE_APP_PATH = "ingenialink\\bin\\FOE"
def FOE_APP_NAME = "FoEUpdateFirmware.exe"
def FOE_APP_NAME_LINUX = "FoEUpdateFirmware"
def FOE_APP_VERSION = ""

DEFAULT_PYTHON_VERSION = "3.9"

ALL_PYTHON_VERSIONS = "py39,py310,py311,py312"
RUN_PYTHON_VERSIONS = ""
def PYTHON_VERSION_MIN = "py39"
def PYTHON_VERSION_MAX = "py312"

def BRANCH_NAME_MASTER = "CIT-296-evaluate-using-scp-for-publishing-to-distext"
def DISTEXT_PROJECT_DIR = "tests/ingenialink-python"

coverage_stashes = []

def runTest(protocol, slave = 0) {
    try {
        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                "--protocol ${protocol} " +
                "--slave ${slave} " +
                "--cov=ingenialink " +
                "--job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${protocol}-${slave}\""

    } catch (err) {
        unstable(message: "Tests failed")
    } finally {
        def coverage_stash = ".coverage_${protocol}_${slave}"
        bat "move .coverage ${coverage_stash}"
        junit "pytest_reports\\*.xml"
        // Delete the junit after publishing it so it not re-published on the next stage
        bat "del /S /Q pytest_reports\\*.xml"
        stash includes: coverage_stash, name: coverage_stash
        coverage_stashes.add(coverage_stash)
    }
}

pipeline {
    agent none
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
        stage('Build wheels and documentation') {
            agent {
                docker {
                    label SW_NODE
                    image WIN_DOCKER_IMAGE
                }
            }
            stages {
                stage('Archive') {
                    steps {
                        bat """
                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                        """
                        stash includes: 'dist\\*, docs.zip', name: 'publish_files'
                        archiveArtifacts artifacts: "dist\\*, docs.zip"
                    }
                }
            }
        }
        stage('Publish wheels and documentation') {
            agent {
                label "worker"
            }
            when {
                beforeAgent true
                branch BRANCH_NAME_MASTER
            }
            steps {
                unstash 'publish_files'
                unzip zipFile: 'docs.zip', dir: '.'
                publishDistExt("_docs", DISTEXT_PROJECT_DIR, true)
            }
        }
    }
}