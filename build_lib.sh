rm -rf ./_build ./_install ./build ./dist
pipenv run python setup.py build sdist bdist_wheel
rm ./ingenialink/_ingenialink.c ./ingenialink/_ingenialink.cp36-win_amd64.pyd
cp ./build/temp.win-amd64-3.6/Release/ingenialink._ingenialink.c ./ingenialink/_ingenialink.c
cp ./build/lib.win-amd64-3.6/ingenialink/_ingenialink.cp36-win_amd64.pyd ./ingenialink/_ingenialink.cp36-win_amd64.pyd