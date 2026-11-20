#!/bin/bash
cmake -S . -B name_picker -G Ninja
cmake --build name_picker
windeployqt-qt5 --release name_picker/name_picker.exe
