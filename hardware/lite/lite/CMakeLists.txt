cmake_minimum_required(VERSION 3.22)

#
# This file is generated only once,
# and is not re-generated if converter is called multiple times.
#
# User is free to modify the file as much as necessary
#

# Setup compiler settings
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)


# Define the build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug")
endif()

# Set the project name
set(CMAKE_PROJECT_NAME lite)
set(ESP8266_WIFI_SSID "" CACHE STRING "ESP8266 WiFi SSID")
set(ESP8266_WIFI_PASS "" CACHE STRING "ESP8266 WiFi password")
set(TRACE_UPLOAD_HOST "54.39.105.79" CACHE STRING "Trace backend host or IP")
set(TRACE_UPLOAD_PORT "18941" CACHE STRING "Trace backend port")
set(TRACE_UPLOAD_USE_SSL "0" CACHE STRING "Use ESP8266 SSL/TLS connection for trace upload")
set(TRACE_DEVICE_SECRET "" CACHE STRING "Trace device HMAC secret")

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME})
message("Build type: " ${CMAKE_BUILD_TYPE})

# Enable CMake support for ASM and C languages
enable_language(C ASM)

# Create an executable object type
add_executable(${CMAKE_PROJECT_NAME})

# Add STM32CubeMX generated sources
add_subdirectory(cmake/stm32cubemx)

# Link directories setup
target_link_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined library search paths
)

# Add sources to executable
target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user sources here
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined include paths
)

# Add project symbols (macros)
target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined symbols
    ESP8266_WIFI_SSID=\"${ESP8266_WIFI_SSID}\"
    ESP8266_WIFI_PASS=\"${ESP8266_WIFI_PASS}\"
    TRACE_UPLOAD_HOST=\"${TRACE_UPLOAD_HOST}\"
    TRACE_UPLOAD_PORT=${TRACE_UPLOAD_PORT}
    TRACE_UPLOAD_USE_SSL=${TRACE_UPLOAD_USE_SSL}
    TRACE_DEVICE_SECRET=\"${TRACE_DEVICE_SECRET}\"
)

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx

    # Add user defined libraries
)
