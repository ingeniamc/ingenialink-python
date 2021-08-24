node('windows') {
    deleteDir()


    if (env.BRANCH_NAME == 'libraries-refactor') {
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
            stage('Remove previous environments') {
                bat """
                    pipenv --rm
                """
            }
            stage('Set environment Python version to 3.6') {
                bat """
                    @set "PATH=C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python36\\;C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python36\\Scripts\\;%PATH%"
                """
            }
            stage('Install environment') {
                bat '''
                    python -m pipenv install --dev --python 3.6
                '''
            }

            stage('Build libraries') {
                bat '''
                    python -m pipenv run python setup.py build sdist bdist_wheel
                '''
            }

            stage('PEP8 style check')
            {
                bat '''
                    python -m pipenv run pycodestyle --first ingenialink/
                '''
            }

            stage('Generate documentation') {
                bat '''
                    python -m pipenv run sphinx-build -b html docs _docs
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
            stage('Set environment Python version to 3.9') {
                bat """
                    @set "PATH=C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python39\\;C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python39\\Scripts\\;%PATH%"
                """
            }
            stage('Install environment') {
                bat '''
                    python -m pipenv install --dev --python 3.9
                '''
            }

            stage('Build libraries') {
                bat '''
                    python -m pipenv run python setup.py build sdist bdist_wheel
                '''
            }

            stage('PEP8 style check')
            {
                bat '''
                    python -m pipenv run pycodestyle --first ingenialink/
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
