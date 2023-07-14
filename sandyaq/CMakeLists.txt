cmake_minimum_required(VERSION 3.10 FATAL_ERROR)

if(UNIX AND NOT APPLE)
  add_definitions(-DLINUX)
endif()

project(SandyAQ)

file(GLOB sources ${PROJECT_SOURCE_DIR}/src/*.cc)
file(GLOB headers ${PROJECT_SOURCE_DIR}/inc/*.hh)

# file(GLOB configurations ${PROJECT_SOURCE_DIR}/config/*.txt)
# file(COPY ${configurations} DESTINATION ${PROJECT_BINARY_DIR})

add_executable(sandyaq main.cc ${sources})
target_include_directories(sandyaq PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/inc)

# add_compile_options(-lm)
target_link_libraries(sandyaq m)
# target_link_libraries(zle_exe chrono)
target_link_libraries(sandyaq CAENDigitizer)
target_link_libraries(sandyaq CAENComm)
# target_link_libraries(zle_exe CAENVMELib)

add_custom_target(SandyAQ DEPENDS sandyaq)
target_compile_features(sandyaq PRIVATE cxx_std_17)