def NODE_NAME = "sw"
def BRANCH_NAME_RELEASE = "release"
def BRANCH_NAME_MASTER = "master"
def PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9"]
def style_check = false

node(NODE_NAME)
{
    deleteDir()
    if (true)
    {
        stage("Checkout")
        {
            checkout scm
        }
        for (version in PYTHON_VERSIONS)
        {   
            stage("Python ${version}")
            {
                stage("Remove previous build files")
                {
                    bat """
                        rmdir /Q /S "_build"
                        rmdir /Q /S "_deps"
                        rmdir /Q /S "_install"
                        rmdir /Q /S "build"
                    """
                }
                stage("Install environment ${version}")
                {
                    bat """
                        python${version} -m venv python${version}
                        python${version}\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                    """
                }
                if (!style_check) 
                {
                    stage("PEP8 style check")
                    {
                        bat """
                            python${version}\\Scripts\\python.exe run pycodestyle --first ingenialink/ --config=setup.cfg
                        """
                    }
                    style_check = true
                }
                stage("Build libraries ${version}")
                {
                    bat """
                        python${version}\\Scripts\\python.exe setup.py build sdist bdist_wheel
                    """
                }
            }
        }
        stage("Generate documentation")
        {
            bat """
                python${PYTHON_VERSIONS[0]}\\Scripts\\python.exe -m sphinx -b html docs _docs
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
                    rd /s /q "python${version}"
                """
            }
        }
    }
}
