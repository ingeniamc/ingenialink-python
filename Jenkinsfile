def NODE_NAME = "sw"
def BRANCH_NAME_RELEASE = "release"
def BRANCH_NAME_MASTER = "test-jenkins"
def PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9"]
def style_check = false

node(NODE_NAME)
{
    deleteDir()
    if (env.BRANCH_NAME == BRANCH_NAME_MASTER || env.BRANCH_NAME.contains(BRANCH_NAME_RELEASE))
    {
        stage("Checkout")
        {
            checkout scm
        }
        stage('Remove previous distributed files')
        {
            bat """
                rmdir /Q /S "_build"
                rmdir /Q /S "_deps"
                rmdir /Q /S "_install"
                rmdir /Q /S "_dist"
                rmdir /Q /S "build"
                rmdir /Q /S "_docs"
                del /f "Pipfile.lock"
            """
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
                        del /f "Pipfile.lock"
                    """
                }
                stage("Remove previous environments")
                {
                    bat """
                        pipenv --rm
                    """
                }
                stage("Install environment ${version}")
                {
                    bat """
                        pipenv install --dev --python ${version}
                    """
                }
                if (!style_check) 
                {
                    stage("PEP8 style check")
                    {
                        bat """
                            pipenv run pycodestyle --first ingenialink/ --config=setup.cfg
                        """
                    }
                    style_check = true
                }
                stage("Build libraries ${version}")
                {
                    bat """
                        pipenv run python setup.py build sdist bdist_wheel
                    """
                }
            }
        }
        stage("Generate documentation")
        {
            bat """
                pipenv run sphinx-build -b html docs _docs
            """
        }
        stage("Archive whl package")
        {
            bat """
                "C:/Program Files/7-Zip/7z.exe" a -r docs.zip -w _docs -mem=AES256
            """
            archiveArtifacts artifacts: "dist/*, docs.zip"
        }
    }
}
