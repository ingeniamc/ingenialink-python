node('windows') {
	  deleteDir()

    stage('Checkout') {
        checkout scm
    }

	stage('Install environment') {
		bat '''
			pipenv install --dev
		'''
	}

	stage('Build libraries') {
		bat '''
			pipenv run python setup.py build sdist bdist_wheel
		'''
	}

    stage('PEP8 style check')
    {
        bat '''
            pipenv run pycodestyle --first ingenialink/
        '''
    }

	stage('Tests') {
	    bat '''

	    '''
	}

	stage('Archive whl package') {
	    bat '''
            archiveArtifacts artifacts: 'dist/*.whl'
	    '''
	}
}
