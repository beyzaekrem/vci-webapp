cmake_minimum_required(VERSION 3.27)

project(interceptor LANGUAGES CXX)

option(INTERCEPTOR_BUILD_BINDINGS "Build the Python bindings" ON)

include(FetchContent)

# Boost
FetchContent_Declare(
  Boost
  URL https://archives.boost.io/release/1.87.0/source/boost_1_87_0.tar.bz2
)
# Should Work but sometimes doesn't: FetchContent_MakeAvailable(Boost)
# So we do this:
FetchContent_GetProperties(boost)
if(NOT boost_POPULATED)
  FetchContent_Populate(boost)
  set(BOOST_INCLUDE_DIR ${boost_SOURCE_DIR})
endif()


# spdlog
FetchContent_Declare(
  spdlog
  GIT_REPOSITORY https://github.com/gabime/spdlog.git
  GIT_TAG v1.15.0
)
FetchContent_MakeAvailable(spdlog)

# nlohmann/json
FetchContent_Declare(
  json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG v3.11.3
)
set(JSON_BuildTests OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(json)

# pybind11_json
add_library(pybind11_json INTERFACE)
target_include_directories(pybind11_json INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/external/pybind11_json)

find_package(charonload REQUIRED)
# Torch (for pybind11...)
find_package(Torch REQUIRED)
find_package(OpenSSL REQUIRED)

if(INTERCEPTOR_BUILD_BINDINGS)
    charonload_add_torch_library(${TORCH_EXTENSION_NAME} MODULE)
    set(TARGET_NAME ${TORCH_EXTENSION_NAME})
else()
    set(TARGET_NAME interceptor)
    python_add_library(${TARGET_NAME} STATIC)
    target_include_directories(${TARGET_NAME} PRIVATE ${TORCH_INCLUDE_DIRS})
    set(INTERCEPTOR_BINDINGS ${CMAKE_CURRENT_SOURCE_DIR}/python/bindings.cpp PARENT_SCOPE)
endif()

set(SOURCES
    src/buffer.cpp
    src/client.cpp
    src/connection.cpp
    src/error.cpp
    src/handler.cpp
    src/logging.cpp
    src/message.cpp
    src/payload.cpp
    src/server.cpp
    src/util.cpp
)
if(INTERCEPTOR_BUILD_BINDINGS)
    list(APPEND SOURCES python/module.cpp python/bindings.cpp)
endif()
target_sources(${TARGET_NAME} PRIVATE ${SOURCES})

target_include_directories(
  ${TARGET_NAME} PUBLIC
  ${BOOST_INCLUDE_DIR}
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)

target_compile_features(${TARGET_NAME} PUBLIC cxx_std_17)

target_link_libraries(
  ${TARGET_NAME} PUBLIC
  spdlog::spdlog_header_only
  nlohmann_json::nlohmann_json
  pybind11_json
  OpenSSL::SSL
  OpenSSL::Crypto
)
