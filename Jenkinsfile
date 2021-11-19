node('sw') {
    deleteDir()


    if (env.BRANCH_NAME == 'test-jenkins') {
        stage('Checkout') {
            checkout scm
        }
        stage('Python 3.6') {
            stage('Remove previous build files') {
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

            stage('Install environment') {
                bat '''
                    pipenv install --dev --python 3.6
                '''
            }

            stage('PEP8 style check')
            {
                // bat '''
                //     pipenv run pycodestyle --first ingenialink/
                // '''
            }

            stage('Build libraries') {
                bat '''
                    pipenv run python setup.py build sdist bdist_wheel
                '''
            }

            stage('Generate documentation') {
                bat '''
                    pipenv run sphinx-build -b html docs _docs
                '''
            }
        }
        stage('Python 3.7') {
            stage('Remove previous build files') {
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

            stage('Install environment') {
                bat '''
                    pipenv install --dev --python 3.7
                '''
            }

            stage('PEP8 style check')
            {
                // bat '''
                //     pipenv run pycodestyle --first ingenialink/
                // '''
            }

            stage('Build libraries') {
                bat '''
                    pipenv run python setup.py build sdist bdist_wheel
                '''
            }

            stage('Generate documentation') {
                bat '''
                    pipenv run sphinx-build -b html docs _docs
                '''
            }
        }
        stage('Python 3.8') {
            stage('Remove previous build files') {
                bat """
                    rmdir /Q /S "_build"
                    rmdir /Q /S "_deps"
                    rmdir /Q /S "_install"
                    rmdir /Q /S "build"
                    del /f "Pipfile.lock"
                """
            }
            stage('Remove previous environments') {
                bat """
                    pipenv --rm
                """
            }

            stage('Install environment') {
                bat '''
                    pipenv install --dev --python 3.8
                '''
            }

            stage('Build libraries') {
                bat '''
                    pipenv run python setup.py build sdist bdist_wheel
                '''
            }


        }
        stage('Python 3.9') {
            stage('Remove previous build files') {
                bat """
                    rmdir /Q /S "_build"
                    rmdir /Q /S "_deps"
                    rmdir /Q /S "_install"
                    rmdir /Q /S "build"
                    del /f "Pipfile.lock"
                """
            }
            stage('Remove previous environments') {
                bat """
                    pipenv --rm
                """
            }

            stage('Install environment') {
                bat '''
                    pipenv install --dev --python 3.9
                '''
            }

            stage('Build libraries') {
                bat '''
                    pipenv run python setup.py build sdist bdist_wheel
                '''
            }
        }

        stage('Archive whl package') {
            bat """
                "C:/Program Files/7-Zip/7z.exe" a -r docs.zip -w _docs -mem=AES256
            """
            archiveArtifacts artifacts: "dist/*, docs.zip"
        }
    }
}
