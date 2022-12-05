def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"
def PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9"]
def style_check = false


node(SW_NODE)
{
    deleteDir()
    agent {
        docker {
            label 'worker'
            image 'ingeniacontainers.azurecr.io/ingenialink-builder'
        }
    }
    stage("Checkout")
    {
        checkout scm
    }
    for (version in PYTHON_VERSIONS)
    {
        stage("Python ${version}")
        {
            stage("Install environment ${version}")
            {
                bat """
                    py -${version} -m venv py${version}
                    py${version}\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                    py${version}\\Scripts\\python.exe -m pip install -e .
                """
            }
            if (!style_check)
            {
                stage("PEP8 style check")
                {
                    bat """
                        py${version}\\Scripts\\python.exe -m pycodestyle --first ingenialink/ --config=setup.cfg
                    """
                }
                style_check = true
            }
            stage("Build libraries ${version}")
            {
                bat """
                    py${version}\\Scripts\\python.exe setup.py build sdist bdist_wheel
                """
            }
        }
    }
    stage("Generate documentation")
    {
        bat """
            py${PYTHON_VERSIONS[0]}\\Scripts\\python.exe -m sphinx -b html docs _docs
        """
    }
    stage("Archive whl package")
    {
        bat """
            "C:/Program Files/7-Zip/7z.exe" a -r docs.zip -w _docs -mem=AES256
        """
        archiveArtifacts artifacts: "dist/*, docs.zip"
        stash includes: 'dist/*', name: 'wheels'
    }
    stage("Remove previous environments")
    {
        for (version in PYTHON_VERSIONS)
        {
            bat """
                rmdir /Q /S "py${version}"
            """
        }
    }
}

lock(ECAT_NODE_LOCK)
{
    node(ECAT_NODE)
    {
        deleteDir()

        stage('Checkout') {
            checkout scm
        }

        stage('Update FW to drives') {
            bat """
                python -m venv ingeniamotion
                ingeniamotion\\Scripts\\python.exe -m pip install ingeniamotion ping3
                ingeniamotion\\Scripts\\python.exe tests\\load_FWs.py ethercat
            """
        }

        stage('Install deps') {
            unstash 'wheels'
            bat '''
                python -m venv venv
                venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                venv\\Scripts\\python.exe -m pip install --find-links dist/ ingenialink
            '''
        }

        stage('Run EtherCAT embedded tests') {
            bat '''
                venv\\Scripts\\python.exe -m pytest tests --protocol ethercat
                exit /b 0
            '''
        }

       stage('Run no-connection tests') {
            bat '''
                venv\\Scripts\\python.exe -m pytest tests
                exit /b 0
            '''
        }
    }
}

lock(CAN_NODE_LOCK)
{
    node(CAN_NODE)
    {
        deleteDir()

        stage('Checkout') {
            checkout scm
        }

        stage('Update FW to drives') {
            bat """
                python -m venv ingeniamotion
                ingeniamotion\\Scripts\\python.exe -m pip install ingeniamotion ping3
                ingeniamotion\\Scripts\\python.exe tests\\load_FWs.py canopen
            """
        }

        stage('Install deps') {
            unstash 'wheels'
            bat '''
                python -m venv venv
                venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                venv\\Scripts\\python.exe -m pip install --find-links dist/ ingenialink
            '''
        }

        stage('Run CANopen tests') {
            bat '''
                venv\\Scripts\\python.exe -m pytest tests --protocol canopen
                exit /b 0
            '''
        }

        stage('Run Ethernet tests') {
            bat '''
                venv\\Scripts\\python.exe -m pytest tests --protocol ethernet
                exit /b 0
            '''
        }
    }
}
