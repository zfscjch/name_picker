cmake_minimum_required(VERSION 3.16)
project(NamePicker LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt5 REQUIRED COMPONENTS Widgets Network)

add_executable(name_picker
    main.cpp
    main_window.cpp main_window.h
    admin_window.cpp admin_window.h
    fish_pet.cpp fish_pet.h
    updater.cpp updater.h
    utils.cpp utils.h
    config.h common.h
    resources.qrc
)

target_link_libraries(name_picker PRIVATE Qt5::Widgets Qt5::Network)

if(WIN32)
    set_target_properties(name_picker PROPERTIES WIN32_EXECUTABLE TRUE)
endif()

install(TARGETS name_picker RUNTIME DESTINATION .)