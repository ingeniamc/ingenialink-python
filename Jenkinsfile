def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def CAN_NODE = "canopen-test"
def PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9"]
def style_check = false

node(ECAT_NODE)
{
    deleteDir()

    stage('Checkout') {
        checkout scm
    }

    stage('Update FW to drives') {
        bat """
            python -m venv ingeniamotion
            ingeniamotion\\Scripts\\python.exe -m pip install ingeniamotion
            ingeniamotion\\Scripts\\python.exe tests\\load_FWs.py soem
        """
    }

    stage('Install deps') {
        bat '''
            python -m venv venv
            venv\\Scripts\\python.exe -m pip install -r requirements\\test-requirements.txt
        '''
    }

    stage('Run EtherCAT embedded tests') {
        bat '''
            venv\\Scripts\\python.exe -m pytest tests --protocol ethercat
            exit /b 0
        '''
    }
}

node(CAN_NODE)
{
    deleteDir()

    stage('Checkout') {
        checkout scm
    }

    stage('Update FW to drives') {
        bat """
            python -m venv ingeniamotion
            ingeniamotion\\Scripts\\python.exe -m pip install ingeniamotion
            ingeniamotion\\Scripts\\python.exe tests\\load_FWs.py canopen
        """
    }

    stage('Install deps') {
        bat '''
            python -m venv venv
            venv\\Scripts\\python.exe -m pip install -r requirements\\test-requirements.txt
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
